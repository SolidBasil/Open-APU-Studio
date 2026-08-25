"""explosion.py
Repositorio de explosión de insumos (tres niveles de cálculo).
"""
import logging
from .base import RepoBase

log = logging.getLogger(__name__)

# ponytail: mapeo sufijo unidad → tipo_id destino para porcentajes
#
# "CONCEPTO" (unidad "(%)CONCEPTO") se agrupa con "SUBC" porque
# recalculo.py ya los trata como el mismo bucket de costo (ver
# _resumenes_matrices(): "pct_val_subc" suma '(%)SUBC' Y '(%)CONCEPTO'
# juntos, ambos aplicados sobre "subcontratos"). Antes de este fix, aquí
# faltaba "CONCEPTO", así que _parse_unidad_pct() caía al default (tipo_id
# 2 = Mano de Obra) para cualquier insumo con unidad "(%)CONCEPTO": el
# costo real ya lo trataba como subcontrato, pero el reporte de explosión
# lo mostraba como si fuera mano de obra — Hallazgo 4 de la auditoría.
_PCT_TIPO_DESTINO = {
    "MO": 2, "MA": 1, "MAT": 1,
    "EQ": 8, "AUX": 16, "SUBC": 32, "CONCEPTO": 32, "FL": 64, "TR": 128,
}

def _parse_unidad_pct(unidad: str) -> tuple:
    """Retorna (es_porcentaje, sufijo, tipo_id_destino).

    Si unidad empieza con '(%' se considera porcentaje.
    El sufijo determina sobre qué tipo de insumo se aplica:
      (%)MO → Mano de Obra, (%)MA/MAT → Material, (%)EQ → Equipo, etc.
    """
    if not unidad or not unidad.startswith("(%"):
        return False, None, None
    sufijo = (unidad[3:] or "").upper().strip()
    if sufijo not in _PCT_TIPO_DESTINO:
        # Sufijo desconocido: cae al default (Mano de Obra) por
        # compatibilidad histórica, pero avisamos — este mismo silencio
        # fue exactamente el Hallazgo 4 (con "CONCEPTO", ya corregido
        # arriba). Si aparece un aviso de éste, probablemente sea un
        # nuevo sufijo real que falta agregar al mapeo, o una unidad mal
        # capturada por el usuario.
        log.warning(
            "Unidad porcentual con sufijo desconocido %r (unidad=%r) — "
            "se está clasificando como Mano de Obra por default. Si es un "
            "sufijo válido, agrégalo a _PCT_TIPO_DESTINO en explosion.py.",
            sufijo, unidad,
        )
    tipo_destino = _PCT_TIPO_DESTINO.get(sufijo, 2)  # default MO
    return True, sufijo, tipo_destino


class ExplosionRepo(RepoBase):
    """Calcula la explosión de insumos para un conjunto de conceptos.

    Niveles:
        'basico'       — bottom-up: desde cada insumo hoja rastrea todas las
                          rutas hacia arriba hasta el presupuesto. Cada rama es
                          independiente, no omite duplicados.
        'compuesto'    — solo insumos compuestos del APU directo
        'primer_nivel' — todos los insumos del APU directo (sin bajar)

    Porcentajes: un insumo se calcula como % cuando su unidad empieza con '(%'.
    El sufijo (MO, MA, EQ…) determina el subtotal base (ver _parse_unidad_pct).
    """

    TIPO_ID_MO = 2

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
        """Filtra por tipos, calcula pct_base para ítems % y ordena."""
        filas = [f for f in filas if f.get("tipo_id") in tipos_set]

        total_global = sum(f.get("total") or 0 for f in filas)
        total_por_tipo = {}
        for f in filas:
            total_por_tipo[f["tipo_id"]] = total_por_tipo.get(f["tipo_id"], 0) + f["total"]

        for f in filas:
            f["pct"] = (f["total"] / total_global * 100) if total_global else 0
            es_pct, sufijo, tipo_destino = _parse_unidad_pct(f.get("unidad"))
            if es_pct:
                base = total_por_tipo.get(tipo_destino, 0)
                f["pct_base"] = f["total"] / base if base else None
                f["pct_sufijo"] = sufijo
            else:
                f["pct_base"] = None
                f["pct_sufijo"] = None

        filas.sort(key=lambda f: (f.get("tipo_orden") or 99, -(f.get("total") or 0)))
        return filas, total_global

    # ── Niveles básico / compuesto: bottom-up (cada ruta insumo→presupuesto es independiente) ──

    def _calcular_basico_bottom_up(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        tipos_ids: list[int],
        ph_conceptos: str,
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

        # ── 1. Budget concepts ──
        rows = self._lista(f"""
            SELECT id, cantidad FROM estructura_presupuesto
            WHERE id IN ({ph_conceptos}) AND tipo='concepto' AND activo=1
        """, concepto_ids)
        budget_cant = {r["id"]: r["cantidad"] for r in rows if r["cantidad"]}

        # ── 2. All insumos del proyecto ──
        insumos = self._lista("""
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
        matrices = self._lista("""
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
            es_pct, sufijo, _ = _parse_unidad_pct(info.get("unidad"))
            parents = reverse.get(insumo_id, [])
            if not parents:
                continue

            qty_total = 0.0
            pct_importe = 0.0

            for p in parents:
                mult = _calc_mult(p["matriz_id"])
                if mult == 0.0:
                    continue
                if es_pct:
                    pct_importe += self._ef_qty(p) * (p["precio"] or 0) * mult
                else:
                    qty_total += self._ef_qty(p) * mult

            pu = info.get("costo_directo") or 0
            if es_pct:
                if pct_importe:
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
                        "importe_pct":    pct_importe,
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
                        "total":          qty_total * pu,
                        "importe_pct":    0.0,
                    }

        # ── 6. Convertir a lista ──
        filas = []
        for entry in acumulado.values():
            es_pct, _, _ = _parse_unidad_pct(entry.get("unidad"))
            filas.append({**entry, "total": entry["importe_pct"] if es_pct else entry["total"]})

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
        tipos_set = set(tipos_ids)

        cte_matriz = f"""
            WITH ep_apu AS (
                SELECT id, proyecto_id, cantidad,
                       CASE WHEN insumo_id IS NOT NULL THEN -insumo_id ELSE id END AS matriz_apu
                FROM estructura_presupuesto
                WHERE id IN ({ph_conceptos}) AND tipo='concepto' AND activo=1
            )
        """

        # Items normales (sin unidad %) + items con unidad % en una sola query
        sql = f"""{cte_matriz}
            SELECT
                i.id                AS insumo_id,
                i.tipo_id,
                ti.nombre           AS tipo_nombre,
                ti.orden            AS tipo_orden,
                i.clave_opus        AS clave,
                COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                i.unidad,
                CASE WHEN i.unidad LIKE '(%' THEN NULL
                     ELSE SUM(CASE WHEN am.operador='*' THEN am.valor*ep.cantidad ELSE ep.cantidad/am.valor END)
                END AS cantidad_total,
                CASE WHEN i.unidad LIKE '(%'
                     THEN SUM(am.valor * am.precio * ep.cantidad)
                     ELSE SUM(CASE WHEN am.operador='*' THEN am.valor*ep.cantidad ELSE ep.cantidad/am.valor END) * i.costo_directo
                END AS total
            FROM ep_apu ep
            JOIN apu_matrices am ON am.matriz_id = ep.matriz_apu
            JOIN insumos i       ON i.id = am.insumo_id
            JOIN tipos_insumo ti ON ti.id = i.tipo_id
            WHERE ep.proyecto_id  = ?
              AND i.proyecto_id   = ?
              AND i.tipo_id       IN ({','.join('?' * len(tipos_ids))})
              AND i.activo        = 1
              {filtro_nivel}
            GROUP BY i.id
        """
        params = concepto_ids + [proyecto_id, proyecto_id] + tipos_ids
        filas = self._lista(sql, params)

        return self._postprocesar(filas, tipos_set)

    # ── API pública ───────────────────────────────────────────────────────

    def calcular(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        nivel: str,
        tipos_ids: list[int],
    ) -> tuple[list[dict], float]:
        """
        Devuelve (filas, total_global).
        filas — lista de dicts con tipo_id, tipo_nombre, tipo_orden, clave,
                descripcion, unidad, pu, cantidad_total, total, pct, pct_mo.
        Ordenada por tipo_orden asc, total desc dentro de cada tipo.

        nivel     — 'basico' | 'compuesto' | 'primer_nivel'
        """
        if not concepto_ids or not tipos_ids:
            return [], 0.0

        ph = ",".join("?" * len(concepto_ids))

        if nivel == "compuesto":
            return self._calcular_basico_bottom_up(proyecto_id, concepto_ids, tipos_ids, ph,
                                                   solo_compuestos=True)
        elif nivel == "basico":
            return self._calcular_basico_bottom_up(proyecto_id, concepto_ids, tipos_ids, ph)
        else:  # primer_nivel
            return self._calcular_sql(proyecto_id, concepto_ids, tipos_ids, ph, "")
