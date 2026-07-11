"""presupuesto.py
Repositorios del árbol del presupuesto (capítulos y conceptos).
"""
from .base import RepoBase

ESTADO_COLOR = {
    0: "#808080",  # Sin revisar
    1: "#F5A623",  # En revisión
    2: "#4CAF7D",  # Verificado
    3: "#E05252",  # Cuestionado
}

ESTADO_NOMBRE = {
    0: "Sin revisar",
    1: "En revisión",
    2: "Verificado",
    3: "Cuestionado",
}


class NodoRepo(RepoBase):
    """Acceso a estructura_presupuesto: capítulos y conceptos del presupuesto.
    El árbol viene con padre_id correctamente resuelto desde la importación.
    """

    TABLA = "estructura_presupuesto"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def todos(self, proyecto_id, tipo: str | None = None):
        """Devuelve todos los nodos activos del presupuesto ordenados por
        jerarquía real (padre_id, orden) — no por wbs, que es solo una
        etiqueta derivada (ver reindexar()).
        Si tipo se especifica ('capitulo' o 'concepto'), filtra por ese tipo.
        Para conceptos incluye unidad desde el catálogo de insumos.
        """
        if tipo == "concepto":
            return self._lista(f"""
                SELECT ep.*, i.unidad
                FROM estructura_presupuesto ep
                LEFT JOIN insumos i ON i.id = ep.insumo_id
                WHERE ep.proyecto_id = ? AND ep.activo = 1 AND ep.tipo = 'concepto'
                ORDER BY ep.padre_id, ep.orden, ep.id
            """, [proyecto_id])
        filtro = f"AND tipo = '{tipo}'" if tipo else ""
        return self._lista(f"""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1 {filtro}
            ORDER BY padre_id, orden, id
        """, [proyecto_id])

    def buscar(self, concepto_id):
        """Busca un nodo por su ID."""
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE id = ? AND activo = 1
        """, [concepto_id])

    def descendientes(self, concepto_id):
        """Devuelve todos los descendientes de un nodo mediante CTE recursiva."""
        return self._lista("""
            WITH RECURSIVE sub AS (
                SELECT * FROM estructura_presupuesto WHERE id = ? AND activo = 1
                UNION ALL
                SELECT n.* FROM estructura_presupuesto n
                JOIN sub s ON n.padre_id = s.id
                WHERE n.activo = 1
            )
            SELECT * FROM sub ORDER BY wbs
        """, [concepto_id])

    def ids_por_tipo(self, proyecto_id, tipo="concepto"):
        """Devuelve los IDs de nodos de un tipo específico."""
        rows = self._lista("""
            SELECT id FROM estructura_presupuesto
            WHERE proyecto_id = ? AND tipo = ? AND activo = 1
        """, [proyecto_id, tipo])
        return [r["id"] for r in rows]

    def arbol(self, proyecto_id: int) -> list[dict]:
        """Lee el árbol de presupuesto y lo devuelve como lista de nodos
        raíz con sus hijos anidados en el campo 'hijos'.

        El árbol ya viene con padre_id correctamente resuelto desde la
        importación (algoritmo WBS) — no se necesita reconstrucción
        adicional más que agrupar por padre_id en memoria.

        Migrado desde core.build_budget_tree() (Fase 4, ver
        ARQUITECTURA_SERVICIOS.md). Estructura de cada nodo:
            {
                "id":               int,
                "padre_id":         int | None,
                "wbs":              str,        # "1", "11", "111", "11101"
                "nivel":            int,        # 0=raíz, 1=capítulo...
                "tipo":             str,        # "capitulo" | "concepto"
                "insumo_id":        int | None, # solo conceptos
                "descripcion":      str,        # conceptos: COALESCE(i.descripcion, n.descripcion)
                                                # capítulos: n.descripcion
                "unidad":           str | None, # desde insumos.unidad (solo conceptos)
                "clave_opus":       str | None, # desde insumos.clave_opus (referencial)
                "precio_unitario":  float | None, # desde insumos.costo_final (solo conceptos)
                "cantidad":         float | None,
                "total":            float,      # unificado: conceptos=importe, capítulos=subtotal
                "notas_rapidas":    str | None,
                "modificado_en":    str | None,
                "creado_en":        str | None,
                "estado":           int,        # 0=sin revisar, 1=en revisión, 2=verificado, 3=cuestionado
                "hijos":            list[dict], # recursivo
            }
        """
        filas = self._lista("""
            SELECT
                n.id,
                n.padre_id,
                n.wbs,
                n.nivel,
                n.tipo,
                n.insumo_id,
                n.orden,
                n.formula,
                CASE WHEN n.tipo = 'concepto'
                     THEN COALESCE(i.descripcion, n.descripcion)
                     ELSE n.descripcion
                END AS descripcion,
                i.unidad                AS unidad,
                i.clave_opus            AS clave_opus,
                i.costo_final           AS precio_unitario,
                n.cantidad,
                n.total,
                n.notas_rapidas,
                n.modificado_en,
                n.creado_en,
                n.estado,
                t.id AS tipo_id
            FROM estructura_presupuesto n
            LEFT JOIN insumos i ON i.id = n.insumo_id
            LEFT JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE n.proyecto_id = ? AND n.activo = 1
            ORDER BY n.padre_id, n.orden, n.id
        """, [proyecto_id])

        if not filas:
            return []

        # Construir árbol en memoria.
        # La jerarquía real es padre_id (relación) + orden (posición entre
        # hermanos, alcance local a cada padre_id) — ver reindexar(). El wbs
        # es solo una ETIQUETA derivada para mostrar/exportar; no se usa
        # aquí para nada estructural, así que nunca puede desincronizar la
        # construcción del árbol aunque un proyecto viejo tenga wbs
        # inconsistente de antes de este cambio.
        by_id = {f["id"]: f for f in filas}
        for f in filas:
            f["hijos"] = []

        raices = []
        for f in filas:
            pid = f["padre_id"]
            if pid and pid in by_id:
                by_id[pid]["hijos"].append(f)
            else:
                raices.append(f)

        return raices

    def reindexar(self, proyecto_id: int) -> None:
        """Recalcula wbs y nivel de TODO el árbol del proyecto en una sola
        pasada, a partir de la única fuente de verdad de la jerarquía:
        padre_id (relación real) + orden (posición entre hermanos, con
        alcance local a cada padre_id).

        Esta es la ÚNICA función que escribe wbs/nivel. Los handlers de
        mover nodos (Subir/Bajar/Izquierda/Derecha) SOLO tocan padre_id y
        orden del nodo movido — nunca calculan wbs a mano ni tocan a sus
        descendientes — y llaman a reindexar() al final. Como wbs/nivel se
        regeneran completos desde cero cada vez (no se parchean
        incrementalmente), nunca pueden desincronizarse de la jerarquía
        real, sin importar cuántas veces se mueva algo.

        wbs se genera como sufijos de 2 dígitos concatenados por nivel
        (ej. capítulo "11", concepto "1103"), igual que el formato que ya
        usaba el importador — así no se rompe la exportación OPUS (PRE_WBS)
        ni la numeración de partidas en los reportes LaTeX, que siguen
        leyendo wbs/nivel tal cual sin saber que ahora son derivados.

        Debe llamarse tras cualquier cambio estructural: mover un nodo,
        insertar, eliminar (soft-delete), o importar desde OPUS.
        """
        filas = self._lista("""
            SELECT id, padre_id, orden FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1
        """, [proyecto_id])
        if not filas:
            return

        # Si padre_id apunta a un nodo inactivo/borrado, se trata como raíz
        # (mismo criterio de tolerancia que ya usa arbol() al construir el
        # árbol), para no dejar huérfanos con wbs/nivel obsoletos para siempre.
        ids_activos = {f["id"] for f in filas}
        hijos_de: dict[int | None, list[dict]] = {}
        for f in filas:
            pid = f["padre_id"] if f["padre_id"] in ids_activos else None
            hijos_de.setdefault(pid, []).append(f)
        for grupo in hijos_de.values():
            grupo.sort(key=lambda f: (f["orden"], f["id"]))

        cambios: list[tuple[str, int, int]] = []

        def caminar(padre_id, prefijo: str, nivel: int) -> None:
            for i, f in enumerate(hijos_de.get(padre_id, []), start=1):
                wbs = f"{prefijo}{i:02d}"
                cambios.append((wbs, nivel, f["id"]))
                caminar(f["id"], wbs, nivel + 1)

        caminar(None, "", 0)

        self._cursor.executemany(
            "UPDATE estructura_presupuesto SET wbs = ?, nivel = ? WHERE id = ?",
            cambios
        )

    def proximo_orden(self, proyecto_id: int, padre_id: int | None) -> int:
        """Siguiente valor de 'orden' libre entre los hijos activos de
        padre_id (o de la raíz del proyecto, si padre_id es None).
        Coloca al FINAL de ese grupo de hermanos — uso: Derecha (indent),
        donde el nodo se vuelve el último hijo de su nuevo hermano-padre."""
        if padre_id is None:
            row = self._uno("""
                SELECT MAX(orden) AS m FROM estructura_presupuesto
                WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
            """, [proyecto_id])
        else:
            row = self._uno("""
                SELECT MAX(orden) AS m FROM estructura_presupuesto
                WHERE padre_id = ? AND activo = 1
            """, [padre_id])
        return ((row or {}).get("m") or 0) + 1

    def orden_tras(self, proyecto_id: int, padre_id: int | None,
                   orden_referencia: int, hueco: int = 1) -> int:
        """Abre un hueco de 'hueco' posiciones justo DESPUÉS de
        orden_referencia entre los hermanos de padre_id, recorriendo el
        orden de los que ya estaban después, y devuelve el primer valor
        de orden libre dentro de ese hueco (los siguientes son
        +1, +2... hasta 'hueco').

        Uso: Izquierda (outdent) — el nodo (o grupo de nodos, si se
        seleccionaron varios con Shift) debe aparecer justo después de su
        antiguo padre (el agrupador del que salió), no al final de todo
        el grupo de hermanos del abuelo. Sin esto, sacar un concepto de
        un capítulo lo mandaría hasta el último lugar entre TODOS los
        capítulos del proyecto, perdiendo su ubicación relativa.
        """
        if padre_id is None:
            self._cursor.execute("""
                UPDATE estructura_presupuesto SET orden = orden + ?
                WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
                  AND orden > ?
            """, (hueco, proyecto_id, orden_referencia))
        else:
            self._cursor.execute("""
                UPDATE estructura_presupuesto SET orden = orden + ?
                WHERE padre_id = ? AND activo = 1 AND orden > ?
            """, (hueco, padre_id, orden_referencia))
        return orden_referencia + 1

    @staticmethod
    def reordenar_grupo(ids_en_orden: list[int], seleccionados: set[int],
                         direccion: int) -> list[int]:
        """Calcula el nuevo orden de una lista de hermanos tras mover un
        subconjunto seleccionado un paso hacia arriba (direccion=-1) o
        hacia abajo (direccion=+1).

        Trata cada tramo CONTIGUO de seleccionados como un bloque que se
        mueve como unidad, intercambiando posición con el único vecino no
        seleccionado inmediato. Esto generaliza correctamente tanto una
        selección contigua (Shift+click — el caso común) como una
        selección salteada (Ctrl+click — cada tramo se mueve por
        separado). No usa swaps por pares vía SQL (eso entrelaza mal los
        elementos cuando hay más de uno seleccionado); calcula la lista
        final completa en memoria y el caller escribe 'orden' de una sola
        pasada a partir de las posiciones resultantes.

        ids_en_orden: ids de los hermanos, ya ordenados (orden, id) — el
        orden actual real, de donde salen los índices a mover.
        Devuelve la misma lista de ids, reordenada.
        """
        ids = list(ids_en_orden)
        n = len(ids)
        if direccion < 0:
            i = 0
            while i < len(ids):
                if ids[i] in seleccionados:
                    j = i
                    while j < len(ids) and ids[j] in seleccionados:
                        j += 1
                    if i > 0:
                        anterior = ids[i - 1]
                        ids = ids[:i - 1] + ids[i:j] + [anterior] + ids[j:]
                    i = j
                else:
                    i += 1
        else:
            i = n - 1
            while i >= 0:
                if ids[i] in seleccionados:
                    j = i
                    while j >= 0 and ids[j] in seleccionados:
                        j -= 1
                    # j = índice justo antes del bloque (o -1)
                    if i < len(ids) - 1:
                        siguiente = ids[i + 1]
                        ids = ids[:j + 1] + [siguiente] + ids[j + 1:i + 1] + ids[i + 2:]
                    i = j
                else:
                    i -= 1
        return ids

    def hermanos_de(self, padre_id: int | None, proyecto_id: int) -> list[int]:
        """Ids de los hermanos activos de padre_id, ordenados (orden, id)
        — mismo criterio que reindexar()/arbol(). Usado para calcular
        movimientos de grupo (Subir/Bajar con selección múltiple)."""
        if padre_id is None:
            filas = self._lista("""
                SELECT id FROM estructura_presupuesto
                WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
                ORDER BY orden, id
            """, [proyecto_id])
        else:
            filas = self._lista("""
                SELECT id FROM estructura_presupuesto
                WHERE padre_id = ? AND activo = 1
                ORDER BY orden, id
            """, [padre_id])
        return [f["id"] for f in filas]

    def escribir_orden(self, ids_en_orden: list[int]) -> None:
        """Escribe 'orden' = 1..n según la posición de cada id en la
        lista dada. Usado tras reordenar_grupo() para persistir el nuevo
        orden calculado en memoria."""
        self._cursor.executemany(
            "UPDATE estructura_presupuesto SET orden = ? WHERE id = ?",
            [(i, nid) for i, nid in enumerate(ids_en_orden, start=1)]
        )

    def actualizar_cantidad(self, concepto_id, cantidad, usuario_id=1):
        """Actualiza la cantidad de un concepto y recalcula totales."""
        self._update("estructura_presupuesto", concepto_id, {"cantidad": cantidad})
        self.recalcular_desde(concepto_id)

    def recalcular_desde(self, concepto_id):
        """Recalcula el total propio del concepto (cantidad × precio del
        insumo vinculado) y luego la cascada hacia arriba hasta la raíz.

        No toca 'cantidad': úsalo después de que 'cantidad' ya fue escrita
        por otro camino (ej. DataService.actualizar) para no duplicar el
        write ni el evento semántico.
        """
        self._cursor.execute("""
            UPDATE estructura_presupuesto SET
                total = COALESCE(cantidad, 0) * COALESCE(
                    (SELECT costo_final FROM insumos WHERE id = insumo_id), 0
                ),
                modificado_en = datetime('now')
            WHERE id = ? AND tipo = 'concepto'
        """, (concepto_id,))
        self.actualizar_total(concepto_id)

    def actualizar_total(self, concepto_id):
        """Recalcula total desde concepto_id hacia arriba hasta la raíz.
        capítulos: total = SUM(hijos.total). conceptos: total = cantidad × precio.
        """
        cur    = self._cursor
        actual = concepto_id
        while actual is not None:
            cur.execute("""
                UPDATE estructura_presupuesto SET
                    total = (
                        SELECT COALESCE(SUM(COALESCE(total, 0)), 0)
                        FROM estructura_presupuesto
                        WHERE padre_id = ? AND activo = 1
                    ),
                    modificado_en = datetime('now')
                WHERE id = ? AND tipo = 'capitulo'
            """, (actual, actual))
            row = cur.execute(
                "SELECT padre_id FROM estructura_presupuesto WHERE id = ?", (actual,)
            ).fetchone()
            actual = row["padre_id"] if row else None


# =============================================================================
# INSUMOS
# =============================================================================
