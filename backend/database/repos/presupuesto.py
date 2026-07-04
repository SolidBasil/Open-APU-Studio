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

    def actualizar_descripcion_agrupador(self, nodo_id, descripcion, usuario_id=1):
        """Actualiza la descripción de un agrupador (capítulo)."""
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                descripcion = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ? AND tipo = 'capitulo'
        """, [descripcion, usuario_id, nodo_id])

    def actualizar_cantidad(self, concepto_id, cantidad, usuario_id=1):
        """Actualiza la cantidad de un concepto y recalcula totales."""
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                cantidad = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [cantidad, usuario_id, concepto_id])
        # Recalc propio total = cant × precio del insumo vinculado
        self._cursor.execute("""
            UPDATE estructura_presupuesto SET
                total = ? * COALESCE(
                    (SELECT costo_final FROM insumos WHERE id = insumo_id), 0
                ),
                modificado_en = datetime('now')
            WHERE id = ? AND tipo = 'concepto'
        """, (cantidad, concepto_id))
        self._conn.commit()
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
        self._conn.commit()


# =============================================================================
# INSUMOS
# =============================================================================
