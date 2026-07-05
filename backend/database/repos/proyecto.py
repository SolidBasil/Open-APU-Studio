"""proyecto.py
Repositorios de proyecto y factores de sobrecosto.
"""
from .base import RepoBase

class ProyectoRepo(RepoBase):

    TABLA = "proyectos"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def buscar(self, proyecto_id):
        """Busca un proyecto por su ID."""
        return self._uno("""
            SELECT * FROM proyectos WHERE id = ? AND activo = 1
        """, [proyecto_id])

    def obtener(self, proyecto_id: int) -> dict | None:
        """Devuelve los metadatos del proyecto (nombre, total, config).

        A diferencia de buscar(), incluye los campos de configuracion_proyecto
        (horas_dia, tasas, decimales) vía LEFT JOIN. Migrado desde
        core.get_proyecto() (Fase 4, ver ARQUITECTURA_SERVICIOS.md).
        """
        return self._uno("""
            SELECT p.*, pc.horas_dia, pc.tasa_seguro, pc.tasa_interes,
                   pc.decimales_costo, pc.decimales_cantidad
            FROM proyectos p
            LEFT JOIN configuracion_proyecto pc ON pc.proyecto_id = p.id
            WHERE p.id = ? AND p.activo = 1
        """, [proyecto_id])


# =============================================================================
# FACTORES DE SOBRECOSTO
# =============================================================================
# costo_final = costo_directo * COALESCE(factor_total, 1.0)
# factor_total = producto de (1 + pct/100) para los 5 factores

class FactoresSobrecostoRepo(RepoBase):

    TABLA = "factores_sobrecosto"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def buscar(self, registro_id: int) -> dict | None:
        """Busca por proyecto_id (el id de factores_sobrecosto es el proyecto_id)."""
        return super().buscar(registro_id)

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
        """Guarda los factores, calcula factor_total y lo persiste. No hace commit."""
        factor = self._calcular_factor(
            pct_indirectos_campo, pct_indirectos_oficina,
            pct_financiamiento, pct_utilidad, pct_cargos_adicionales)
        self._cursor.execute("""
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
