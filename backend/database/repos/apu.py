"""apu.py
Repositorios de matrices APU — subtotales se calculan al vuelo.
"""
from .base import RepoBase
from .recalculo import RecalculoRepo, _RESUMEN_DEFAULT


class ApuMatricesRepo(RepoBase):
    """Componentes del APU: desglose de insumos por concepto o insumo compuesto.
    matriz_id unificado: positivo para nodos del árbol, negativo para insumos compuestos.
    """

    TABLA = "apu_matrices"

    def proximo_orden(self, matriz_id: int) -> int:
        row = self._uno(
            "SELECT COALESCE(MAX(orden), 0) + 1 AS prox FROM apu_matrices WHERE matriz_id = ?",
            [matriz_id],
        )
        return row["prox"] if row else 1

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

    def conceptos_con_insumo_compuesto(self, proyecto_id: int) -> list[dict]:
        """Conceptos del árbol cuyo insumo es compuesto (es_compuesto=1)."""
        return self._lista("""
            SELECT ep.id AS cid, ep.insumo_id
            FROM estructura_presupuesto ep
            JOIN insumos i ON i.id = ep.insumo_id
            WHERE ep.proyecto_id = ? AND i.es_compuesto = 1
        """, [proyecto_id])

    def contar_por_matriz(self, matriz_id: int) -> int:
        """Filas en apu_matrices para un matriz_id dado."""
        row = self._uno(
            "SELECT COUNT(*) AS n FROM apu_matrices WHERE matriz_id = ?",
            [matriz_id],
        )
        return row["n"] if row else 0

    def redirigir_matriz(self, origen: int, destino: int) -> None:
        """Mueve todos los componentes de apu_matrices de origen a destino."""
        self._conn.execute(
            "UPDATE apu_matrices SET matriz_id = ? WHERE matriz_id = ?",
            [destino, origen],
        )

    def eliminar_matriz(self, matriz_id: int) -> None:
        """Borra todos los componentes de apu_matrices de un matriz_id."""
        self._conn.execute(
            "DELETE FROM apu_matrices WHERE matriz_id = ?", [matriz_id]
        )

    def con_detalle(self, matriz_id: int) -> dict:
        """Devuelve el APU completo de una matriz (concepto o insumo compuesto):
        componentes con su insumo enriquecido + totales por tipo (al vuelo).

        Returns:
            {
                "detalle":  list[dict],   # componentes con insumo completo
                "totales":  dict | None,  # subtotales por tipo calculados al vuelo
            }
        """
        detalle = self._lista("""
            SELECT
                ad.id,
                ad.orden,
                ad.valor,
                ad.operador,
                ad.precio,
                CASE WHEN ad.operador = '*' THEN ad.valor * ad.precio ELSE ad.precio / ad.valor END AS importe,
                ad.formula,
                ad.creado_en,
                ad.modificado_en,
                i.es_compuesto      AS insumo_es_compuesto,
                i.id                AS insumo_id,
                i.descripcion       AS insumo_descripcion,
                i.descripcion_corta AS insumo_desc_corta,
                i.unidad            AS insumo_unidad,
                t.clave             AS tipo_clave,
                t.nombre            AS tipo_nombre,
                t.id                AS tipo_id
            FROM apu_matrices ad
            JOIN insumos i      ON i.id  = ad.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE ad.matriz_id = ?
            ORDER BY ad.orden
        """, [matriz_id])

        # ponytail: calcular resumen al vuelo en vez de leer de apu_resumen_totales
        proyecto_id = self._obtener_proyecto_id(matriz_id)
        if proyecto_id is not None:
            rc = RecalculoRepo(self._conn)
            totales = rc.calcular_resumen(proyecto_id, matriz_id)
        else:
            totales = _RESUMEN_DEFAULT.copy()

        return {"detalle": detalle, "totales": totales}

    def _obtener_proyecto_id(self, matriz_id: int) -> int | None:
        """Resuelve proyecto_id desde matriz_id (positivo=árbol, negativo=compuesto)."""
        if matriz_id > 0:
            row = self._uno(
                "SELECT proyecto_id FROM estructura_presupuesto WHERE id = ?",
                [matriz_id],
            )
        else:
            row = self._uno(
                "SELECT proyecto_id FROM insumos WHERE id = ?",
                [-matriz_id],
            )
        return row["proyecto_id"] if row else None


# =============================================================================
# APU RESUMEN (antes: apu_totales)
# =============================================================================
# ponytail: eliminado — los subtotales se calculan al vuelo en memoria
