"""proyecto.py
Repositorios de proyecto y sobrecostos.
"""
from .base import RepoBase

class ProyectoRepo(RepoBase):

    def todos(self):
        """Devuelve todos los proyectos activos ordenados por fecha descendente."""
        return self._lista("""
            SELECT * FROM proyectos WHERE activo = 1 ORDER BY creado_en DESC
        """)

    def buscar(self, proyecto_id):
        """Busca un proyecto por su ID."""
        return self._uno("""
            SELECT * FROM proyectos WHERE id = ? AND activo = 1
        """, [proyecto_id])

    def config(self, proyecto_id):
        """Devuelve la configuración de un proyecto."""
        return self._uno("""
            SELECT * FROM configuracion_proyecto WHERE proyecto_id = ?
        """, [proyecto_id])

    def actualizar_total(self, proyecto_id):
        """Recalcula y actualiza el total_obra del proyecto desde sus raíces."""
        self._ejecutar("""
            UPDATE proyectos SET
                total_obra = (
                    SELECT COALESCE(SUM(total), 0)
                    FROM estructura_presupuesto
                    WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
                ),
                modificado_en = datetime('now')
            WHERE id = ?
        """, [proyecto_id, proyecto_id])


# =============================================================================
# SOBRECOSTOS (antes: pie_precios)
# =============================================================================

class SobrecostosRepo(RepoBase):

    def por_proyecto(self, proyecto_id):
        """Devuelve los sobrecostos de un proyecto ordenados por orden."""
        return self._lista("""
            SELECT * FROM sobrecostos
            WHERE proyecto_id = ?
            ORDER BY orden
        """, [proyecto_id])

    def insertar(self, datos):
        """Inserta un nuevo sobrecosto en el proyecto."""
        return self._ejecutar("""
            INSERT INTO sobrecostos
                (proyecto_id, orden, variable, descripcion, formula,
                 porcentaje_mn, porcentaje_me, suma_en_total,
                 es_egreso_financ, es_ingreso_financ, se_imprime, tipo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            datos.get("proyecto_id"),
            datos.get("orden", 0),
            datos.get("variable", ""),
            datos.get("descripcion", ""),
            datos.get("formula"),
            datos.get("porcentaje_mn", 0),
            datos.get("porcentaje_me", 0),
            datos.get("suma_en_total", 1),
            datos.get("es_egreso_financ", 0),
            datos.get("es_ingreso_financ", 0),
            datos.get("se_imprime", 1),
            datos.get("tipo", "formula_porcentaje"),
        ])

    def limpiar(self, proyecto_id):
        """Elimina todos los sobrecostos de un proyecto."""
        self._ejecutar("""
            DELETE FROM sobrecostos WHERE proyecto_id = ?
        """, [proyecto_id])


# =============================================================================
# NODOS — estructura_presupuesto (capítulos y conceptos)
# =============================================================================
