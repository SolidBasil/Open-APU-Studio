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

        # Cascada de sobrecostos: costo_directo * factor_total → costo_final
        self._aplicar_cascada_sobrecosto(cur, proyecto_id)

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

        # ponytail: commit removido — el repo no commitea, lo hace el servicio
        return {"iteraciones_compuestos": n_iter}

    def _sincronizar_precios_componentes(self, cur, proyecto_id):
        """Copia insumos.costo_directo → apu_matrices.precio en todos los
        componentes de matrices que pertenecen a este proyecto (tanto
        conceptos del árbol como insumos compuestos).

        Usa costo_directo (no costo_final) para que la cascada de sobrecosto
        solo se aplique una vez al final, no se acumule en padres.

        Excluye ítems con unidad (%): su costo no es un precio unitario fijo
        del catálogo, es un % del subtotal del tipo que indica el sufijo
        (MO, MA, EQ…). Su `precio` no debe sobreescribirse.
        """
        cur.execute("""
            UPDATE apu_matrices
            SET precio = (SELECT costo_directo FROM insumos WHERE id = apu_matrices.insumo_id),
                modificado_en = datetime('now')
            WHERE matriz_id IN (
                SELECT id  FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
                UNION ALL
                SELECT -id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
            )
            AND insumo_id NOT IN (
                SELECT id FROM insumos
                WHERE proyecto_id = ? AND unidad LIKE '(%'
            )
        """, (proyecto_id, proyecto_id, proyecto_id))

    def _recalcular_resumenes(self, cur, proyecto_id):
        """Recalcula apu_resumen_totales para todas las matrices del
        proyecto (conceptos del árbol e insumos compuestos).

        Los ítems con unidad (%) son porcentajes cuyo importe real es
        (valor / 100) × subtotal del tipo destino que indica el sufijo:
          (%)MO → mano_obra, (%)MA/MAT → material, (%)EQ → equipo, etc.
        """
        ph_matrices = """
            SELECT id  FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
            UNION ALL
            SELECT -id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
        """
        cur.execute(f"""
            WITH base AS (
                SELECT
                    ac.matriz_id,
                    COALESCE(SUM(CASE WHEN t.clave='material'  AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS materiales,
                    COALESCE(SUM(CASE WHEN t.clave='mano_obra' AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS mano_obra,
                    COALESCE(SUM(CASE WHEN t.clave='equipo'    AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS equipo,
                    COALESCE(SUM(CASE WHEN t.clave='auxiliar'  AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS auxiliares,
                    COALESCE(SUM(CASE WHEN t.clave='concepto'  AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS subcontratos,
                    COALESCE(SUM(CASE WHEN t.clave='flete'     AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS fletes,
                    COALESCE(SUM(CASE WHEN t.clave='trabajo'   AND i.unidad NOT LIKE '(%' THEN
                      CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END ELSE 0 END),0) AS trabajos,
                    COALESCE(SUM(CASE WHEN i.unidad = '(%)MO'  THEN ac.valor ELSE 0 END),0) AS pct_val_mo,
                    COALESCE(SUM(CASE WHEN i.unidad IN('(%)MA','(%)MAT') THEN ac.valor ELSE 0 END),0) AS pct_val_ma,
                    COALESCE(SUM(CASE WHEN i.unidad = '(%)EQ'  THEN ac.valor ELSE 0 END),0) AS pct_val_eq,
                    COALESCE(SUM(CASE WHEN i.unidad = '(%)AUX' THEN ac.valor ELSE 0 END),0) AS pct_val_aux,
                    COALESCE(SUM(CASE WHEN i.unidad IN('(%)SUBC','(%)CONCEPTO') THEN ac.valor ELSE 0 END),0) AS pct_val_subc,
                    COALESCE(SUM(CASE WHEN i.unidad = '(%)FL'  THEN ac.valor ELSE 0 END),0) AS pct_val_fl,
                    COALESCE(SUM(CASE WHEN i.unidad = '(%)TR'  THEN ac.valor ELSE 0 END),0) AS pct_val_tr
                FROM apu_matrices ac
                JOIN insumos i      ON i.id = ac.insumo_id
                JOIN tipos_insumo t ON t.id = i.tipo_id
                WHERE ac.matriz_id IN ({ph_matrices})
                GROUP BY ac.matriz_id
            )
            INSERT INTO apu_resumen_totales
                (matriz_id, materiales, mano_obra, herramienta, equipo,
                 auxiliares, subcontratos, fletes, trabajos, costo_directo,
                 modificado_en)
            SELECT
                matriz_id,
                materiales + pct_val_ma * COALESCE(materiales, 0),
                mano_obra + pct_val_mo * COALESCE(mano_obra, 0),
                0.0,  -- herramienta: columna legacy, ahora se suma al tipo destino
                equipo + pct_val_eq * COALESCE(equipo, 0),
                auxiliares + pct_val_aux * COALESCE(auxiliares, 0),
                subcontratos + pct_val_subc * COALESCE(subcontratos, 0),
                fletes + pct_val_fl * COALESCE(fletes, 0),
                trabajos + pct_val_tr * COALESCE(trabajos, 0),
                (materiales + pct_val_ma * COALESCE(materiales, 0))
                + (mano_obra + pct_val_mo * COALESCE(mano_obra, 0))
                + (equipo + pct_val_eq * COALESCE(equipo, 0))
                + (auxiliares + pct_val_aux * COALESCE(auxiliares, 0))
                + (subcontratos + pct_val_subc * COALESCE(subcontratos, 0))
                + (fletes + pct_val_fl * COALESCE(fletes, 0))
                + (trabajos + pct_val_tr * COALESCE(trabajos, 0)),
                datetime('now')
            FROM base WHERE 1=1
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
        """, (proyecto_id, proyecto_id))

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
                UPDATE insumos SET costo_directo = ?, costo_final = ?, modificado_en = datetime('now')
                WHERE id = ?
            """, (nuevo, nuevo, row["id"]))
        return cambios

    def _aplicar_cascada_sobrecosto(self, cur, proyecto_id):
        """Aplica los factores de sobrecosto del proyecto: costo_final = costo_directo * factor_total."""
        cur.execute("""
            UPDATE insumos SET
                costo_final = costo_directo * COALESCE(
                    (SELECT factor_total FROM factores_sobrecosto WHERE proyecto_id = ?), 1.0),
                modificado_en = datetime('now')
            WHERE proyecto_id = ? AND activo = 1
        """, (proyecto_id, proyecto_id))


# =============================================================================
# APU AUXILIARES (antes: apu_nodos)
# =============================================================================

# Migrado a v3: apu_matrices usa matriz_id unico en vez de dos columnas.


# =============================================================================
# FAMILIAS Y SUBFAMILIAS
# =============================================================================
