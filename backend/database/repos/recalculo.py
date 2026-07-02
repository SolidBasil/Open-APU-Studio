"""recalculo.py
Repositorio de recálculo bottom-up del árbol de presupuesto.
"""
from .base import RepoBase

class RecalculoRepo(RepoBase):
    """Recalcula en cascada todo el presupuesto de un proyecto:

        1. Sincroniza el precio congelado en cada componente de matriz
           (apu_matrices.precio) con el costo_final vigente de su insumo.
        2. Recalcula apu_resumen_totales y, con eso, el costo_final de los
           insumos compuestos — iterando porque un compuesto puede usar a
           otro compuesto como componente (anidamiento).
        3. Recalcula el total de cada concepto del árbol (cantidad × costo
           final del insumo vinculado).
        4. Recalcula el total de cada capítulo, de hojas hacia la raíz.

    Se usa cuando se editan precios o cantidades a mano y hay que propagar
    los cambios sin necesidad de reimportar desde OPUS.
    """

    MAX_ITERACIONES = 15  # cota de seguridad para compuestos anidados

    def recalcular_proyecto(self, proyecto_id: int) -> dict:
        cur = self._cursor

        self._sincronizar_precios_componentes(cur, proyecto_id)

        n_iter  = 0
        cambios = True
        while cambios and n_iter < self.MAX_ITERACIONES:
            self._recalcular_resumenes(cur, proyecto_id)
            cambios = self._actualizar_costo_compuestos(cur, proyecto_id)
            if cambios:
                self._sincronizar_precios_componentes(cur, proyecto_id)
            n_iter += 1

        # Resumen final de todas las matrices ya con precios definitivos
        self._recalcular_resumenes(cur, proyecto_id)

        # Totales de conceptos = cantidad × costo_final del insumo vinculado
        cur.execute("""
            UPDATE estructura_presupuesto
            SET total = (
                SELECT COALESCE(estructura_presupuesto.cantidad, 0) * COALESCE(i.costo_final, 0)
                FROM insumos i
                WHERE i.id = estructura_presupuesto.insumo_id
            ),
            modificado_en = datetime('now')
            WHERE proyecto_id = ?
              AND tipo = 'concepto'
              AND activo = 1
              AND insumo_id IS NOT NULL
        """, (proyecto_id,))

        # Totales de capítulos, de hojas hacia la raíz
        cur.execute("""
            SELECT MAX(nivel) FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
        """, (proyecto_id,))
        max_nivel = cur.fetchone()[0] or 0
        for nivel in range(max_nivel, -1, -1):
            cur.execute("""
                UPDATE estructura_presupuesto SET
                    total = (
                        SELECT COALESCE(SUM(COALESCE(total, 0)), 0)
                        FROM estructura_presupuesto h
                        WHERE h.padre_id = estructura_presupuesto.id AND h.activo = 1
                    ),
                    modificado_en = datetime('now')
                WHERE proyecto_id = ? AND nivel = ?
                  AND tipo = 'capitulo' AND activo = 1
            """, (proyecto_id, nivel))

        self._conn.commit()
        return {"iteraciones_compuestos": n_iter}

    def _sincronizar_precios_componentes(self, cur, proyecto_id):
        """Copia insumos.costo_final → apu_matrices.precio en todos los
        componentes de matrices que pertenecen a este proyecto (tanto
        conceptos del árbol como insumos compuestos).

        Excluye herramienta: su costo no es un precio unitario fijo del
        catálogo, es un % del subtotal de mano de obra de cada matriz
        (ver _recalcular_resumenes), así que su `precio` no debe
        sobreescribirse aquí.
        """
        cur.execute("""
            UPDATE apu_matrices
            SET precio = (SELECT costo_final FROM insumos WHERE id = apu_matrices.insumo_id),
                modificado_en = datetime('now')
            WHERE matriz_id IN (
                SELECT id  FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
                UNION ALL
                SELECT -id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
            )
            AND insumo_id NOT IN (
                SELECT i.id FROM insumos i
                JOIN tipos_insumo t ON t.id = i.tipo_id
                WHERE t.clave = 'herramienta'
            )
        """, (proyecto_id, proyecto_id))

    def _recalcular_resumenes(self, cur, proyecto_id):
        """Recalcula apu_resumen_totales para todas las matrices del
        proyecto (conceptos del árbol e insumos compuestos).

        Herramienta es un caso especial: en apu_matrices su columna
        `cantidad` no es una cantidad física, es un PORCENTAJE. Su importe
        real es ese % multiplicado por el subtotal de mano de obra de esa
        misma matriz — no cantidad × precio como el resto de los tipos
        (ver ExplosionRepo, que ya calcula herramienta de esta forma).
        """
        cur.execute("""
            WITH mo AS (
                SELECT ac.matriz_id AS matriz_id,
                       COALESCE(SUM(ac.cantidad * ac.precio), 0) AS subtotal
                FROM apu_matrices ac
                JOIN insumos i      ON i.id = ac.insumo_id
                JOIN tipos_insumo t ON t.id = i.tipo_id
                WHERE t.clave = 'mano_obra'
                  AND ac.matriz_id IN (
                      SELECT id  FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
                      UNION ALL
                      SELECT -id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
                  )
                GROUP BY ac.matriz_id
            )
            INSERT INTO apu_resumen_totales
                (matriz_id, materiales, mano_obra, herramienta, equipo,
                 auxiliares, subcontratos, fletes, trabajos, costo_directo,
                 modificado_en)
            SELECT
                ac.matriz_id,
                COALESCE(SUM(CASE WHEN t.clave='material'    THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='mano_obra'   THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='herramienta' THEN ac.cantidad ELSE 0 END),0) * COALESCE(mo.subtotal, 0),
                COALESCE(SUM(CASE WHEN t.clave='equipo'      THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='auxiliar'    THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='concepto'    THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='flete'       THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='trabajo'     THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave<>'herramienta' THEN ac.cantidad*ac.precio ELSE 0 END),0)
                    + COALESCE(SUM(CASE WHEN t.clave='herramienta' THEN ac.cantidad ELSE 0 END),0) * COALESCE(mo.subtotal, 0),
                datetime('now')
            FROM apu_matrices ac
            JOIN insumos i      ON i.id = ac.insumo_id
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN mo ON mo.matriz_id = ac.matriz_id
            WHERE ac.matriz_id IN (
                SELECT id  FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
                UNION ALL
                SELECT -id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
            )
            GROUP BY ac.matriz_id
            ON CONFLICT(matriz_id) DO UPDATE SET
                materiales    = excluded.materiales,
                mano_obra     = excluded.mano_obra,
                herramienta   = excluded.herramienta,
                equipo        = excluded.equipo,
                auxiliares    = excluded.auxiliares,
                subcontratos  = excluded.subcontratos,
                fletes        = excluded.fletes,
                trabajos      = excluded.trabajos,
                costo_directo = excluded.costo_directo,
                modificado_en = excluded.modificado_en
        """, (proyecto_id, proyecto_id, proyecto_id, proyecto_id))

    def _actualizar_costo_compuestos(self, cur, proyecto_id) -> bool:
        """Copia el costo_directo del resumen de cada insumo compuesto a su
        costo_final. Devuelve True si algún valor cambió — señal de que hay
        que iterar de nuevo por si hay compuestos anidados dentro de otros."""
        cur.execute("""
            SELECT i.id AS id, i.costo_final AS costo_final, r.costo_directo AS costo_directo
            FROM insumos i
            JOIN apu_resumen_totales r ON r.matriz_id = -i.id
            WHERE i.proyecto_id = ? AND i.es_compuesto = 1 AND i.activo = 1
        """, (proyecto_id,))
        filas   = cur.fetchall()
        cambios = False
        for row in filas:
            actual = row["costo_final"] or 0.0
            nuevo  = row["costo_directo"] or 0.0
            if abs(actual - nuevo) > 1e-6:
                cambios = True
            cur.execute("""
                UPDATE insumos SET costo_mn = ?, costo_final = ?, modificado_en = datetime('now')
                WHERE id = ?
            """, (nuevo, nuevo, row["id"]))
        return cambios


# =============================================================================
# APU AUXILIARES (antes: apu_nodos)
# =============================================================================

# Migrado a v3: apu_matrices usa matriz_id unico en vez de dos columnas.


# =============================================================================
# FAMILIAS Y SUBFAMILIAS
# =============================================================================
