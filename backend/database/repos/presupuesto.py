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

    def todos(self, proyecto_id, tipo: str | None = None):
        """Devuelve todos los nodos activos del presupuesto ordenados por wbs.
        Si tipo se especifica ('capitulo' o 'concepto'), filtra por ese tipo.
        """
        filtro = f"AND tipo = '{tipo}'" if tipo else ""
        return self._lista(f"""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1 {filtro}
            ORDER BY wbs
        """, [proyecto_id])

    def hijos(self, padre_id, tipo: str | None = None):
        """Devuelve los hijos directos de un nodo.
        Si tipo se especifica ('capitulo' o 'concepto'), filtra por ese tipo.
        """
        filtro = f"AND tipo = '{tipo}'" if tipo else ""
        return self._lista(f"""
            SELECT * FROM estructura_presupuesto
            WHERE padre_id = ? AND activo = 1 {filtro}
            ORDER BY wbs
        """, [padre_id])

    def raices(self, proyecto_id):
        """Devuelve los nodos raíz (capítulos) de un proyecto."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])

    def buscar(self, concepto_id):
        """Busca un nodo por su ID."""
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE id = ? AND activo = 1
        """, [concepto_id])

    def buscar_por_clave(self, clave, proyecto_id):
        """Busca un nodo por su clave — columna eliminada, retorna None."""
        return None

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

    def ruta(self, concepto_id):
        """Devuelve la ruta desde un nodo hasta la raíz mediante CTE recursiva."""
        return self._lista("""
            WITH RECURSIVE ruta AS (
                SELECT * FROM estructura_presupuesto WHERE id = ?
                UNION ALL
                SELECT n.* FROM estructura_presupuesto n
                JOIN ruta r ON n.id = r.padre_id
            )
            SELECT * FROM ruta ORDER BY nivel
        """, [concepto_id])

    def por_estado(self, proyecto_id, estado: int):
        """Devuelve los nodos con un estado específico (semáforo)."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND estado = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id, estado])

    def conceptos_sin_apu(self, proyecto_id):
        """Devuelve los conceptos que no tienen APU asociado."""
        return self._lista("""
            SELECT ep.* FROM estructura_presupuesto ep
            LEFT JOIN apu_matrices ac ON ac.matriz_id = ep.id
            WHERE ep.proyecto_id = ? AND ep.tipo = 'concepto'
              AND ep.activo = 1 AND ac.id IS NULL
            ORDER BY ep.wbs
        """, [proyecto_id])

    def actualizar_cantidad(self, concepto_id, cantidad, usuario_id=1):
        """Actualiza la cantidad de un concepto y recalcula totales."""
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                cantidad = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [cantidad, usuario_id, concepto_id])
        self.actualizar_total(concepto_id)

    def actualizar_estado(self, concepto_id, estado: int, usuario_id=1):
        """Actualiza el estado (semáforo) de un nodo."""
        if estado not in ESTADO_COLOR:
            return
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                estado = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [estado, usuario_id, concepto_id])

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

    def eliminar(self, concepto_id, usuario_id=1):
        """Marca un nodo y sus descendientes como inactivos (borrado lógico)."""
        # Leer padre_id ANTES del UPDATE — buscar() filtra activo=1,
        # por lo que después del marcado siempre devuelve None.
        nodo = self.buscar(concepto_id)
        padre_id = nodo.get("padre_id") if nodo else None

        desc = self.descendientes(concepto_id)
        ids  = [d["id"] for d in desc]
        if ids:
            ph = ",".join("?" for _ in ids)
            self._ejecutar(f"""
                UPDATE estructura_presupuesto SET activo = 0,
                    modificado_por = ?, modificado_en = datetime('now')
                WHERE id IN ({ph})
            """, [usuario_id] + ids)

        if padre_id:
            self.actualizar_total(padre_id)


# =============================================================================
# INSUMOS
# =============================================================================
