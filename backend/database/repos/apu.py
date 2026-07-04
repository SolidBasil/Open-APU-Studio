"""apu.py
Repositorios de matrices APU y resúmenes de totales.
"""
from .base import RepoBase

class ApuMatricesRepo(RepoBase):
    """Componentes del APU: desglose de insumos por concepto o insumo compuesto.
    matriz_id unificado: positivo para nodos del árbol, negativo para insumos compuestos.
    """

    TABLA = "apu_matrices"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def por_matriz(self, matriz_id):
        """Devuelve los componentes del APU de una matriz (concepto o compuesto)."""
        return self._lista("""
            SELECT ac.*,
                   i.descripcion       AS insumo_descripcion,
                   i.descripcion_corta AS insumo_desc_corta,
                   i.unidad            AS insumo_unidad,
                   t.clave             AS tipo_clave,
                   t.nombre            AS tipo_nombre,
                   t.id                AS tipo_id
            FROM apu_matrices ac
            JOIN insumos i      ON i.id = ac.insumo_id
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE ac.matriz_id = ?
            ORDER BY ac.orden
        """, [matriz_id])

    def actualizar_campo(self, comp_id, campo, valor, usuario_id=1):
        """Actualiza un campo de un componente APU."""
        self._actualizar_campo("apu_matrices", comp_id, campo, valor,
                               {'valor', 'operador', 'precio', 'formula', 'orden'},
                               usuario_id)


# =============================================================================
# APU RESUMEN (antes: apu_totales)
# =============================================================================
# Clase eliminada — recalculo.py maneja apu_resumen_totales directamente.
