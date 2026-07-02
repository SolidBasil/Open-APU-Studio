"""apu.py
Repositorios de matrices APU y resúmenes de totales.
"""
from .base import RepoBase

class ApuMatricesRepo(RepoBase):
    """Componentes del APU: desglose de insumos por concepto o insumo compuesto.
    matriz_id unificado: positivo para nodos del árbol, negativo para insumos compuestos.
    """

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

    def insertar(self, datos):
        """Inserta un componente en la matriz APU."""
        return self._ejecutar("""
            INSERT INTO apu_matrices
                (matriz_id, insumo_id, valor, operador,
                 precio, formula, orden, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            datos.get("matriz_id"),
            datos.get("insumo_id"),
            datos.get("valor", 0),
            datos.get("operador", "*"),
            datos.get("precio", 0),
            datos.get("formula"),
            datos.get("orden", 0),
            datos.get("creado_por", 1),
        ])

    def eliminar(self, comp_id):
        """Elimina un componente de la matriz por su ID."""
        self._ejecutar("DELETE FROM apu_matrices WHERE id = ?", [comp_id])

    def limpiar(self, matriz_id):
        """Elimina todos los componentes de una matriz."""
        self._ejecutar("DELETE FROM apu_matrices WHERE matriz_id = ?", [matriz_id])


# =============================================================================
# APU RESUMEN (antes: apu_totales)
# =============================================================================

class ApuResumenTotalesRepo(RepoBase):
    """Resumen de costos por tipo de insumo para cada APU.
    Se recalcula desde apu_matrices cuando cambian precios o cantidades.
    """

    def por_matriz(self, matriz_id):
        """Devuelve el resumen de costos de una matriz APU."""
        return self._uno("""
            SELECT * FROM apu_resumen_totales WHERE matriz_id = ?
        """, [matriz_id])

    def recalcular(self, matriz_id):
        """Recalcula el resumen de costos de un APU desde apu_matrices.

        Usa INSERT ... ON CONFLICT(matriz_id) DO UPDATE en lugar de
        INSERT OR REPLACE para evitar que se destruya el id existente.
        INSERT OR REPLACE elimina la fila y la reinsertar con un id nuevo,
        lo que invalida cualquier referencia cacheada al id anterior.

        Herramienta es un caso especial: en apu_matrices su columna
        `valor` no es una cantidad física, es un PORCENTAJE. Su importe
        real es ese % multiplicado por el subtotal de mano de obra de esta
        misma matriz — no cantidad × precio como el resto de los tipos.
        """
        subtotal_mo = self._uno("""
            SELECT COALESCE(SUM(CASE WHEN ac.operador = '*'
                                     THEN ac.valor * ac.precio
                                     ELSE ac.precio / ac.valor END), 0) AS total
            FROM apu_matrices ac
            JOIN insumos i      ON i.id = ac.insumo_id
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE ac.matriz_id = ? AND t.clave = 'mano_obra'
        """, [matriz_id])["total"]

        self._ejecutar("""
            INSERT INTO apu_resumen_totales
                (matriz_id, materiales, mano_obra, herramienta, equipo,
                 auxiliares, subcontratos, fletes, trabajos, costo_directo,
                 modificado_en)
            SELECT
                ac.matriz_id,
                COALESCE(SUM(CASE WHEN t.clave='material'    THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='mano_obra'   THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='herramienta' THEN ac.valor ELSE 0 END),0) * ?,
                COALESCE(SUM(CASE WHEN t.clave='equipo'      THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='auxiliar'    THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='concepto'    THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='flete'       THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='trabajo'     THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave<>'herramienta' THEN
                  CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0)
                    + COALESCE(SUM(CASE WHEN t.clave='herramienta' THEN ac.valor ELSE 0 END),0) * ?,
                datetime('now')
            FROM apu_matrices ac
            JOIN insumos i      ON i.id  = ac.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE ac.matriz_id = ?
            GROUP BY ac.matriz_id
            ON CONFLICT(matriz_id) DO UPDATE SET
                materiales         = excluded.materiales,
                mano_obra          = excluded.mano_obra,
                herramienta        = excluded.herramienta,
                equipo             = excluded.equipo,
                auxiliares         = excluded.auxiliares,
                subcontratos       = excluded.subcontratos,
                fletes             = excluded.fletes,
                trabajos           = excluded.trabajos,
                costo_directo      = excluded.costo_directo,
                modificado_en      = excluded.modificado_en
        """, [subtotal_mo, subtotal_mo, matriz_id])


# =============================================================================
# RECÁLCULO EN CASCADA DEL PRESUPUESTO
# =============================================================================
