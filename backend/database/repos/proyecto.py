"""proyecto.py
Repositorios de proyecto y factores de sobrecosto.
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
# FACTORES DE SOBRECOSTO
# =============================================================================
# costo_final = costo_directo * COALESCE(factor_total, 1.0)
# factor_total = producto de (1 + pct/100) para los 5 factores

class FactoresSobrecostoRepo(RepoBase):

    @staticmethod
    def _calcular_factor(pct_indirectos_campo=0, pct_indirectos_oficina=0,
                         pct_financiamiento=0, pct_utilidad=0,
                         pct_cargos_adicionales=0) -> float:
        f = 1 + ((pct_indirectos_campo or 0) + (pct_indirectos_oficina or 0)) / 100
        f *= (1 + (pct_financiamiento or 0) / 100)
        f *= (1 + (pct_utilidad or 0) / 100)
        f *= (1 + (pct_cargos_adicionales or 0) / 100)
        return f

    def obtener(self, proyecto_id):
        """Devuelve los factores de sobrecosto de un proyecto o valores por defecto."""
        return self._uno("""
            SELECT * FROM factores_sobrecosto WHERE proyecto_id = ?
        """, [proyecto_id])

    def guardar(self, proyecto_id, pct_indirectos_campo=0, pct_indirectos_oficina=0,
                pct_financiamiento=0, pct_utilidad=0, pct_cargos_adicionales=0):
        """Guarda los factores, calcula factor_total y lo persiste."""
        factor = self._calcular_factor(
            pct_indirectos_campo, pct_indirectos_oficina,
            pct_financiamiento, pct_utilidad, pct_cargos_adicionales)
        self._ejecutar("""
            INSERT INTO factores_sobrecosto
                (proyecto_id, pct_indirectos_campo, pct_indirectos_oficina,
                 pct_financiamiento, pct_utilidad, pct_cargos_adicionales, factor_total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(proyecto_id) DO UPDATE SET
                pct_indirectos_campo   = excluded.pct_indirectos_campo,
                pct_indirectos_oficina = excluded.pct_indirectos_oficina,
                pct_financiamiento     = excluded.pct_financiamiento,
                pct_utilidad           = excluded.pct_utilidad,
                pct_cargos_adicionales = excluded.pct_cargos_adicionales,
                factor_total           = excluded.factor_total
        """, [proyecto_id, pct_indirectos_campo, pct_indirectos_oficina,
              pct_financiamiento, pct_utilidad, pct_cargos_adicionales, factor])
        return factor

    def limpiar(self, proyecto_id):
        """Elimina los factores de sobrecosto de un proyecto (vuelve a factor=1.0)."""
        self._ejecutar("DELETE FROM factores_sobrecosto WHERE proyecto_id = ?", [proyecto_id])


# =============================================================================
# NODOS — estructura_presupuesto (capítulos y conceptos)
# =============================================================================
