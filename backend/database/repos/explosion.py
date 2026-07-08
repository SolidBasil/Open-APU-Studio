"""explosion.py
Repositorio de explosión de insumos (tres niveles de cálculo).
"""
from .base import RepoBase

class ExplosionRepo(RepoBase):
    """Calcula la explosión de insumos para un conjunto de conceptos.

    Niveles:
        'basico'       — bottom-up: desde cada insumo hoja rastrea todas las
                          rutas hacia arriba hasta el presupuesto. Cada rama es
                          independiente, no omite duplicados.
        'compuesto'    — solo insumos compuestos del APU directo
        'primer_nivel' — todos los insumos del APU directo (sin bajar)

    Herramienta: su importe es % × subtotal_MO del APU, no valor × costo_final.
    """

    TIPO_ID_HERRAMIENTA = 4
    TIPO_ID_MO          = 2

    @staticmethod
    def _ef_qty(row: dict) -> float:
        """Cantidad efectiva desde una fila de apu_matrices.

        Si operador='*' → la cantidad es valor (ej: 2 bolsas de cemento).
        Si operador='/' → la cantidad efectiva es 1/valor (ej: rendimiento 10m²/día
        significa que por cada unidad se necesita 0.1 días).
        """
        v = row.get("valor") or 0
        return v if row.get("operador", "*") == "*" else (1.0 / v if v else 0.0)

    # ── Helpers internos ─────────────────────────────────────────────────

    def _postprocesar(self, filas: list[dict], tipos_set: set) -> tuple[list[dict], float]:
        """Filtra por tipos, calcula pct_mo para herramienta, % global y ordena."""
        filas = [f for f in filas if f.get("tipo_id") in tipos_set]

        total_global = sum(f.get("total") or 0 for f in filas)
        total_mo     = sum(f["total"] for f in filas if f["tipo_id"] == self.TIPO_ID_MO)

        for f in filas:
            f["pct"] = (f["total"] / total_global * 100) if total_global else 0
            if f["tipo_id"] == self.TIPO_ID_HERRAMIENTA:
                f.setdefault("pct_mo", f["total"] / total_mo if total_mo else None)
            else:
                f.setdefault("pct_mo", None)

        filas.sort(key=lambda f: (f.get("tipo_orden") or 99, -(f.get("total") or 0)))
        return filas, total_global

    # ── Niveles básico / compuesto: bottom-up (cada ruta insumo→presupuesto es independiente) ──

    def _calcular_basico_bottom_up(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        tipos_ids: list[int],
        ph_conceptos: str,
        decimales: int | None = None,
        solo_compuestos: bool = False,
    ) -> tuple[list[dict], float]:
        """
        Bottom-up: para cada insumo, rastrea hacia arriba todas las rutas
        hasta llegar a un concepto del presupuesto. Cada rama es independiente
        — no se omiten duplicados aunque el mismo compuesto aparezca varias veces.

        solo_compuestos=False → insumos hoja (es_compuesto=0)
        solo_compuestos=True  → insumos compuestos (es_compuesto=1)
        """
        tipos_set = set(tipos_ids)

        def rd(v):
            return round(v, decimales) if decimales is not None else v

        # ── 1. Budget concepts ──
        rows = self._lista(f"""
            SELECT id, cantidad FROM estructura_presupuesto
            WHERE id IN ({ph_conceptos}) AND tipo='concepto' AND activo=1
        """, concepto_ids)
        budget_cant = {r["id"]: r["cantidad"] for r in rows if r["cantidad"]}

        # ── 2. All insumos del proyecto ──
        insumos = self._lista(f"""
            SELECT i.id, i.clave_opus,
                   COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                   i.unidad, i.costo_directo, i.es_compuesto, i.tipo_id,
                   ti.nombre AS tipo_nombre, ti.orden AS tipo_orden
            FROM insumos i
            JOIN tipos_insumo ti ON ti.id = i.tipo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
        """, [proyecto_id])
        insumos_map = {r["id"]: r for r in insumos}

        # ── 2b. All conceptos -> insumo_id mapping (for intermedios) ──
        # insumo_id ya está resuelto en estructura_presupuesto desde la importación.
        # El cruce por clave/clave_opus ya no es necesario.
        conceptos = self._lista("""
            SELECT id, insumo_id FROM estructura_presupuesto
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
              AND insumo_id IS NOT NULL
        """, [proyecto_id])
        concepto_a_insumo: dict[int, int] = {
            r["id"]: r["insumo_id"] for r in conceptos
        }

        # ── 3. All APU matrices (reverse index) ──
        matrices = self._lista(f"""
            SELECT am.matriz_id, am.insumo_id, am.valor, am.operador, am.precio
            FROM apu_matrices am
            JOIN insumos i ON i.id = am.insumo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
        """, [proyecto_id])

        # Reverse: insumo_id -> [padres]
        reverse: dict[int, list[dict]] = {}
        for row in matrices:
            iid = row["insumo_id"]
            reverse.setdefault(iid, []).append(row)

        # ── 3b. Mapa compuesto→presupuesto (unificación: apu_matrices no guarda
        # el vínculo directo compuesto→concepto, solo estructura_presupuesto.insumo_id)
        budget_por_compuesto: dict[int, float] = {}
        for cid, cant in budget_cant.items():
            ins_id = concepto_a_insumo.get(cid)
            if ins_id is not None:
                budget_por_compuesto[ins_id] = budget_por_compuesto.get(ins_id, 0.0) + cant

        # ── 4. Caché de multiplicadores bottom-up ──
        #   _mult_cache[matriz_id] = cantidad_total_acumulada_hasta_presupuesto
        #   Para conceptos en budget_cant: devuelve cantidad del presupuesto
        #   Para conceptos intermedios: rastrea su insumo en el índice reverso
        #   Para compuestos (mid<0): suma de (cantidad × multiplicador del padre)
        _mult_cache: dict[int, float] = {}
        _visitando: set = set()

        def _calc_mult(matriz_id: int) -> float:
            """Multiplicador desde matriz_id hasta el presupuesto (suma de todas las rutas).

            _visitando protege contra ciclos en el grafo de insumos compuestos.
            Se usa try/finally para garantizar que el id se retire del set incluso
            si ocurre una excepción durante la recursión — de lo contrario el id
            quedaría "bloqueado" y todos los cálculos siguientes devolverían 0.
            """
            if matriz_id in _visitando:
                return 0.0  # ciclo detectado
            if matriz_id in _mult_cache:
                return _mult_cache[matriz_id]

            if matriz_id > 0:
                if matriz_id in budget_cant:
                    return budget_cant[matriz_id]
                # Concepto intermedio (usado como componente de otro APU)
                ins_id = concepto_a_insumo.get(matriz_id)
                if ins_id is None:
                    return 0.0
                _visitando.add(matriz_id)
                try:
                    total = 0.0
                    for p in reverse.get(ins_id, []):
                        total += self._ef_qty(p) * _calc_mult(p["matriz_id"])
                finally:
                    _visitando.discard(matriz_id)
                _mult_cache[matriz_id] = total
                return total

            # matriz_id < 0 → insumo compuesto
            _visitando.add(matriz_id)
            try:
                total = budget_por_compuesto.get(-matriz_id, 0.0)
                for p in reverse.get(-matriz_id, []):
                    total += self._ef_qty(p) * _calc_mult(p["matriz_id"])
            finally:
                _visitando.discard(matriz_id)
            _mult_cache[matriz_id] = total
            return total

        # ── 5. Procesar cada insumo ──
        acumulado: dict[int, dict] = {}

        for insumo_id, info in insumos_map.items():
            if info["tipo_id"] not in tipos_set:
                continue
            if solo_compuestos:
                if not info["es_compuesto"]:
                    continue
            else:
                if info["es_compuesto"]:
                    continue
            is_herr = (info["tipo_id"] == self.TIPO_ID_HERRAMIENTA)
            parents = reverse.get(insumo_id, [])
            if not parents:
                continue

            qty_total = 0.0
            herr_importe = 0.0

            for p in parents:
                mult = _calc_mult(p["matriz_id"])
                if mult == 0.0:
                    continue
                if is_herr:
                    herr_importe += rd(self._ef_qty(p) * (p["precio"] or 0) * mult)
                else:
                    qty_total += rd(self._ef_qty(p) * mult)

            pu = info.get("costo_directo") or 0
            if is_herr:
                if herr_importe:
                    acumulado[insumo_id] = {
                        "insumo_id":      insumo_id,
                        "tipo_id":        info["tipo_id"],
                        "tipo_nombre":    info["tipo_nombre"],
                        "tipo_orden":     info["tipo_orden"],
                        "clave":          info["clave_opus"],
                        "descripcion":    info["descripcion"] or "",
                        "unidad":         info["unidad"] or "",
                        "pu":             None,
                        "cantidad_total": 0.0,
                        "total":          0.0,
                        "importe_herr":   herr_importe,
                    }
            else:
                if qty_total:
                    acumulado[insumo_id] = {
                        "insumo_id":      insumo_id,
                        "tipo_id":        info["tipo_id"],
                        "tipo_nombre":    info["tipo_nombre"],
                        "tipo_orden":     info["tipo_orden"],
                        "clave":          info["clave_opus"],
                        "descripcion":    info["descripcion"] or "",
                        "unidad":         info["unidad"] or "",
                        "pu":             pu,
                        "cantidad_total": qty_total,
                        "total":          rd(qty_total * pu),
                        "importe_herr":   0.0,
                    }

        # ── 6. Convertir a lista ──
        filas = []
        for entry in acumulado.values():
            es_herr = (entry["tipo_id"] == self.TIPO_ID_HERRAMIENTA)
            filas.append({**entry, "total": entry["importe_herr"] if es_herr else entry["total"]})

        return self._postprocesar(filas, tipos_set)

    # ── Niveles primer_nivel / compuesto: vía SQL ─────────────────────────

    def _calcular_sql(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        tipos_ids: list[int],
        ph_conceptos: str,
        filtro_nivel: str,
    ) -> tuple[list[dict], float]:
        """Niveles 'primer_nivel' o 'compuesto': resuelve por SQL agregado."""
        tipos_set      = set(tipos_ids)
        tipos_normales = [t for t in tipos_ids if t != self.TIPO_ID_HERRAMIENTA]
        filas_normales = []

        # CTE: resolver matriz_id real — tras unificar_matrices_apu() los
        # componentes viven en matriz_id = -insumo_id (negativo), no en ep.id.
        cte_matriz = f"""
            WITH ep_apu AS (
                SELECT id, proyecto_id, cantidad,
                       CASE WHEN insumo_id IS NOT NULL THEN -insumo_id ELSE id END AS matriz_apu
                FROM estructura_presupuesto
                WHERE id IN ({ph_conceptos}) AND tipo='concepto' AND activo=1
            )
        """

        if tipos_normales:
            ph_tipos = ",".join("?" * len(tipos_normales))
            sql = f"""{cte_matriz}
                SELECT
                    i.id                AS insumo_id,
                    i.tipo_id,
                    ti.nombre           AS tipo_nombre,
                    ti.orden            AS tipo_orden,
                    i.clave_opus        AS clave,
                    COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                    i.unidad,
                    SUM(CASE WHEN am.operador='*' THEN am.valor*ep.cantidad ELSE ep.cantidad/am.valor END) AS cantidad_total,
                    SUM(CASE WHEN am.operador='*' THEN am.valor*ep.cantidad ELSE ep.cantidad/am.valor END) * i.costo_directo AS total
                FROM ep_apu ep
                JOIN apu_matrices am ON am.matriz_id = ep.matriz_apu
                JOIN insumos i       ON i.id = am.insumo_id
                JOIN tipos_insumo ti ON ti.id = i.tipo_id
                WHERE ep.proyecto_id  = ?
                  AND i.proyecto_id   = ?
                  AND i.tipo_id       IN ({ph_tipos})
                  AND i.activo        = 1
                  {filtro_nivel}
                GROUP BY i.id
            """
            filas_normales = self._lista(sql, concepto_ids + [proyecto_id, proyecto_id] + tipos_normales)

        filas_herr = []
        if self.TIPO_ID_HERRAMIENTA in tipos_ids:
            sql_h = f"""{cte_matriz}
                SELECT
                    i.id                AS insumo_id,
                    i.tipo_id,
                    ti.nombre           AS tipo_nombre,
                    ti.orden            AS tipo_orden,
                    i.clave_opus        AS clave,
                    COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                    i.unidad,
                    SUM(am.valor * am.precio * ep.cantidad) AS total,
                    SUM(am.valor * am.precio * ep.cantidad) /
                    NULLIF(SUM(am.precio * ep.cantidad), 0) AS pct_mo
                FROM ep_apu ep
                JOIN apu_matrices am ON am.matriz_id = ep.matriz_apu
                JOIN insumos i       ON i.id = am.insumo_id
                JOIN tipos_insumo ti ON ti.id = i.tipo_id
                WHERE ep.proyecto_id  = ?
                  AND i.proyecto_id   = ?
                  AND i.tipo_id       = {self.TIPO_ID_HERRAMIENTA}
                  AND i.activo        = 1
                  {filtro_nivel}
                GROUP BY i.id
            """
            params_h = [proyecto_id, proyecto_id]
            filas_herr = self._lista(sql_h, concepto_ids + params_h)

        return self._postprocesar(filas_normales + filas_herr, tipos_set)

    # ── API pública ───────────────────────────────────────────────────────

    def calcular(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        nivel: str,
        tipos_ids: list[int],
        decimales: int | None = None,
    ) -> tuple[list[dict], float]:
        """
        Devuelve (filas, total_global).
        filas — lista de dicts con tipo_id, tipo_nombre, tipo_orden, clave,
                descripcion, unidad, pu, cantidad_total, total, pct, pct_mo.
        Ordenada por tipo_orden asc, total desc dentro de cada tipo.

        nivel     — 'basico' | 'compuesto' | 'primer_nivel'
        decimales — None = precisión flotante completa
                    2    = redondea como OPUS (para comparación)
        """
        if not concepto_ids or not tipos_ids:
            return [], 0.0

        ph = ",".join("?" * len(concepto_ids))

        if nivel == "compuesto":
            return self._calcular_basico_bottom_up(proyecto_id, concepto_ids, tipos_ids, ph, decimales,
                                                   solo_compuestos=True)
        elif nivel == "basico":
            return self._calcular_basico_bottom_up(proyecto_id, concepto_ids, tipos_ids, ph, decimales)
        else:  # primer_nivel
            return self._calcular_sql(proyecto_id, concepto_ids, tipos_ids, ph, "")
