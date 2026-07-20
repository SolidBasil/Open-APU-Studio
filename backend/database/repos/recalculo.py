"""recalculo.py
Repositorio de recálculo bottom-up del árbol de presupuesto.
"""
from .base import RepoBase

# ponytail: resumen por tipo de costo — se calcula en memoria, no se persiste
_RESUMEN_DEFAULT = {
    "materiales": 0.0, "mano_obra": 0.0, "herramienta": 0.0,
    "equipo": 0.0, "auxiliares": 0.0, "subcontratos": 0.0,
    "fletes": 0.0, "trabajos": 0.0, "costo_directo": 0.0,
}


class RecalculoRepo(RepoBase):
    """Recalcula en cascada todo el presupuesto de un proyecto:

        1. Sincroniza el precio congelado en cada componente de matriz
           (apu_matrices.precio) con el costo_final vigente de su insumo.
        2. Calcula subtotales por tipo en memoria (dict) y, con eso, el
           costo_final de los insumos compuestos — iterando porque un
           compuesto puede usar a otro compuesto como componente.
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

        resumenes: dict[int, dict] = {}
        n_iter  = 0
        cambios = True
        while cambios and n_iter < self.MAX_ITERACIONES:
            resumenes = self._recalcular_resumenes(cur, proyecto_id)
            cambios = self._actualizar_costo_compuestos(cur, proyecto_id, resumenes)
            if cambios:
                self._sincronizar_precios_componentes(cur, proyecto_id)
            n_iter += 1

        # Resumen final de todas las matrices ya con precios definitivos
        resumenes = self._recalcular_resumenes(cur, proyecto_id)

        # Cascada de FSR + sobrecostos: costo_directo * factor_fsr * factor_total → costo_final
        self._aplicar_cascada_sobrecosto(cur, proyecto_id)

        # Totales de conceptos = cantidad × costo_final del insumo vinculado
        self.recalcular_totales_conceptos(proyecto_id)

        # Totales de capítulos, de hojas hacia la raíz
        self.recalcular_totales_capitulos(proyecto_id)

        return {"iteraciones_compuestos": n_iter, "resumenes": resumenes}

    def recalcular_totales_conceptos(self, proyecto_id: int) -> None:
        """Totales de conceptos = cantidad × costo_final del insumo vinculado.

        Reutilizable fuera de la cascada completa de recalcular_proyecto()
        (p.ej. backend/importar/importar.py, justo tras vincular insumo_id).
        """
        self._cursor.execute("""
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

    def recalcular_totales_capitulos(self, proyecto_id: int) -> None:
        """Totales de capítulos, de hojas hacia la raíz.

        Reutilizable fuera de la cascada completa de recalcular_proyecto()
        (p.ej. backend/importar/importar.py, al cerrar la importación).
        """
        cur = self._cursor
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

    def calcular_resumen(self, proyecto_id: int, matriz_id: int) -> dict:
        """Calcula el resumen de un APU específico al vuelo (para UI/exportar)."""
        resumenes = self._recalcular_resumenes(
            self._cursor, proyecto_id, filtro_matriz=matriz_id
        )
        return resumenes.get(matriz_id, _RESUMEN_DEFAULT.copy())

    def calcular_todos_resumenes(self, proyecto_id: int) -> dict[int, dict]:
        """Calcula todos los resúmenes del proyecto en memoria."""
        return self._recalcular_resumenes(self._cursor, proyecto_id)

    def _sincronizar_precios_componentes(self, cur, proyecto_id):
        """Copia insumos.costo_directo → apu_matrices.precio, aplicando
        factor_fsr a mano de obra para que el APU muestre el precio final.

        Usa costo_directo (base sin FSR) para que la cascada de sobrecosto
        solo se aplique una vez al final, no se acumule en padres.

        Excluye ítems con unidad (%): su costo no es un precio unitario fijo
        del catálogo, es un % del subtotal del tipo que indica el sufijo
        (MO, MA, EQ…). Su `precio` no debe sobreescribirse.
        """
        cur.execute("""
            UPDATE apu_matrices
            SET precio = (SELECT i.costo_directo * COALESCE(i.factor_fsr, 1.0)
                          FROM insumos i WHERE i.id = apu_matrices.insumo_id),
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

    def _recalcular_resumenes(self, cur, proyecto_id, filtro_matriz=None) -> dict[int, dict]:
        """Calcula subtotales por tipo de costo para todas las matrices del
        proyecto. Devuelve dict[matriz_id → resumen].

        Si filtro_matriz se proporciona, solo calcula para esa matriz.

        Los ítems con unidad (%) son porcentajes cuyo importe real es
        (valor / 100) × subtotal del tipo destino que indica el sufijo:
          (%)MO → mano_obra, (%)MA/MAT → material, (%)EQ → equipo, etc.
        """
        if filtro_matriz is not None:
            ph = "SELECT ? AS matriz_id"
            params: list = [filtro_matriz]
        else:
            ph = """
                SELECT id AS matriz_id FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
                UNION ALL
                SELECT -id AS matriz_id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
            """
            params = [proyecto_id, proyecto_id]

        cur.execute(f"""
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
            WHERE ac.matriz_id IN ({ph})
            GROUP BY ac.matriz_id
        """, params)

        resumenes: dict[int, dict] = {}
        for row in cur.fetchall():
            mid = row["matriz_id"]
            mat  = row["materiales"]  + row["pct_val_ma"] * row["materiales"]
            mo   = row["mano_obra"]   + row["pct_val_mo"] * row["mano_obra"]
            eq   = row["equipo"]      + row["pct_val_eq"] * row["equipo"]
            aux  = row["auxiliares"]  + row["pct_val_aux"] * row["auxiliares"]
            subc = row["subcontratos"] + row["pct_val_subc"] * row["subcontratos"]
            fl   = row["fletes"]      + row["pct_val_fl"] * row["fletes"]
            tr   = row["trabajos"]    + row["pct_val_tr"] * row["trabajos"]
            cd   = mat + mo + eq + aux + subc + fl + tr
            resumenes[mid] = {
                "materiales": mat, "mano_obra": mo, "herramienta": 0.0,
                "equipo": eq, "auxiliares": aux, "subcontratos": subc,
                "fletes": fl, "trabajos": tr, "costo_directo": cd,
            }
        return resumenes

    def _actualizar_costo_compuestos(self, cur, proyecto_id, resumenes: dict) -> bool:
        """Copia el costo_directo del resumen de cada insumo compuesto a su
        costo_final. Devuelve True si algún valor cambió."""
        cur.execute("""
            SELECT id, costo_final FROM insumos
            WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
        """, (proyecto_id,))
        cambios = False
        for row in cur.fetchall():
            nuevo = resumenes.get(-row["id"], _RESUMEN_DEFAULT)["costo_directo"]
            actual = row["costo_final"] or 0.0
            if abs(actual - nuevo) > 1e-6:
                cambios = True
            cur.execute("""
                UPDATE insumos SET costo_directo = ?, costo_final = ?, modificado_en = datetime('now')
                WHERE id = ?
            """, (nuevo, nuevo, row["id"]))
        return cambios

    def _aplicar_cascada_sobrecosto(self, cur, proyecto_id):
        """Aplica FSR y sobrecostos: costo_final = costo_directo * factor_fsr * factor_total."""
        cur.execute("""
            UPDATE insumos SET
                costo_final = costo_directo * COALESCE(factor_fsr, 1.0) * COALESCE(
                    (SELECT factor_total FROM factores_sobrecosto WHERE proyecto_id = ?), 1.0),
                modificado_en = datetime('now')
            WHERE proyecto_id = ? AND activo = 1
        """, (proyecto_id, proyecto_id))
