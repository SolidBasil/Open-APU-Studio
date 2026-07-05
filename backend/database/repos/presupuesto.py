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
        """Devuelve todos los nodos activos del presupuesto ordenados por wbs.
        Si tipo se especifica ('capitulo' o 'concepto'), filtra por ese tipo.
        Para conceptos incluye unidad desde el catálogo de insumos.
        """
        if tipo == "concepto":
            return self._lista(f"""
                SELECT ep.*, i.unidad
                FROM estructura_presupuesto ep
                LEFT JOIN insumos i ON i.id = ep.insumo_id
                WHERE ep.proyecto_id = ? AND ep.activo = 1 AND ep.tipo = 'concepto'
                ORDER BY ep.wbs
            """, [proyecto_id])
        filtro = f"AND tipo = '{tipo}'" if tipo else ""
        return self._lista(f"""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1 {filtro}
            ORDER BY wbs
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
                n.estado
            FROM estructura_presupuesto n
            LEFT JOIN insumos i ON i.id = n.insumo_id
            WHERE n.proyecto_id = ? AND n.activo = 1
            ORDER BY n.wbs
        """, [proyecto_id])

        if not filas:
            return []

        # Construir árbol en memoria.
        # ORDER BY wbs garantiza que los padres siempre se procesan antes que sus hijos.
        by_id  = {f["id"]: f for f in filas}
        raices = []

        for f in filas:
            f["hijos"] = []
            pid = f["padre_id"]
            if pid and pid in by_id:
                by_id[pid]["hijos"].append(f)
            else:
                raices.append(f)

        return raices

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
