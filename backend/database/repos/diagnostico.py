"""diagnostico.py
Repositorio de diagnóstico e integridad del catálogo y presupuesto.
Todas las queries de depuración que antes vivían en handlers.py.
"""
from .base import RepoBase


class DiagnosticoRepo(RepoBase):
    """Consultas de diagnóstico del catálogo e integridad del presupuesto."""

    def insumos_sin_uso(self, proyecto_id):
        """Insumos activos que no aparecen en ninguna matriz APU."""
        return self._lista("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id
            FROM insumos i
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND NOT EXISTS (SELECT 1 FROM apu_matrices am WHERE am.insumo_id = i.id)
            ORDER BY i.id
        """, [proyecto_id])

    def conceptos_sin_apu(self, proyecto_id):
        """Conceptos activos sin matriz APU asociada."""
        return self._lista("""
            SELECT ep.id, CAST(ep.id AS TEXT) AS clave, ep.descripcion
            FROM estructura_presupuesto ep
            WHERE ep.proyecto_id = ? AND ep.tipo = 'concepto' AND ep.activo = 1
              AND NOT EXISTS (SELECT 1 FROM apu_matrices am WHERE am.matriz_id = ep.id)
            ORDER BY ep.wbs
        """, [proyecto_id])

    def descripciones_duplicadas(self, proyecto_id):
        """Insumos que comparten hash de descripción (colisiones)."""
        return self._lista("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id
            FROM insumos i
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND i.hash IN (
                  SELECT hash FROM insumos
                  WHERE proyecto_id = ? AND activo = 1 AND hash IS NOT NULL
                  GROUP BY hash HAVING COUNT(*) > 1
              )
            ORDER BY i.hash, i.id
        """, [proyecto_id, proyecto_id])

    def costos_en_cero(self, proyecto_id):
        """Insumos con costo_final NULL o 0."""
        return self._lista("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id
            FROM insumos i
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND (i.costo_final IS NULL OR i.costo_final = 0)
            ORDER BY i.id
        """, [proyecto_id])

    def descripciones_vacias(self, proyecto_id):
        """Insumos y conceptos con descripción NULL o vacía."""
        return self._lista("""
            SELECT i.id, i.clave_opus AS clave, i.tipo_id, 'insumo' AS src
            FROM insumos i
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND (i.descripcion IS NULL OR i.descripcion = '')
            UNION ALL
            SELECT ep.id, CAST(ep.id AS TEXT), NULL, 'concepto'
            FROM estructura_presupuesto ep
            WHERE ep.proyecto_id = ? AND ep.activo = 1 AND ep.tipo = 'concepto'
              AND (ep.descripcion IS NULL OR ep.descripcion = '')
            ORDER BY 2
        """, [proyecto_id, proyecto_id])

    def auto_referencia(self, proyecto_id):
        """Insumos compuestos cuyo APU los referencia a sí mismos."""
        return self._lista("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, t.id AS tipo_id
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.es_compuesto = 1
              AND i.proyecto_id = ? AND i.activo = 1
              AND EXISTS (
                SELECT 1 FROM apu_matrices ac
                WHERE ac.matriz_id = i.id
                  AND ac.insumo_id = i.id
                  AND NOT EXISTS (
                    SELECT 1 FROM estructura_presupuesto ep
                    WHERE ep.id = ac.matriz_id AND ep.activo = 1
                  )
              )
            ORDER BY i.id
        """, [proyecto_id])

    def unidades_no_estandar(self, proyecto_id):
        """Insumos con unidad no estándar que NO se corrigen por case/alias."""
        from frontend.ventana.widgets.base import UNIDADES
        ALIASES = {
            "m2": "m²", "m³": "m³", "m3": "m³",
            "jgo": "juego",
            "lt": "L", "l": "L",
            "hor": "hr", "hr": "hr",
        }
        mapa = {u.lower(): u for u in UNIDADES}
        mapa.update(ALIASES)
        placeholders = ",".join("?" * len(UNIDADES))
        filas = self._lista(f"""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id, i.unidad
            FROM insumos i
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND i.unidad IS NOT NULL AND i.unidad != ''
              AND i.unidad NOT IN ({placeholders})
            ORDER BY i.unidad, i.id
        """, [proyecto_id] + list(UNIDADES))
        return [r for r in filas if r["unidad"].lower() not in mapa]

    def unidades_case(self, proyecto_id):
        """Insumos cuya unidad es un alias (case o abreviatura) de una estándar."""
        from frontend.ventana.widgets.base import UNIDADES
        ALIASES = {
            "m2": "m²", "m³": "m³", "m3": "m³",
            "jgo": "juego",
            "lt": "L", "l": "L",
            "hor": "hr", "hr": "hr",
        }
        mapa = {u.lower(): u for u in UNIDADES}
        mapa.update(ALIASES)
        filas = self._lista("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id, i.unidad
            FROM insumos i
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND i.unidad IS NOT NULL AND i.unidad != ''
            ORDER BY i.unidad, i.id
        """, [proyecto_id])
        return [
            {**r, "canonical": mapa[r["unidad"].lower()]}
            for r in filas
            if r["unidad"].lower() in mapa and r["unidad"] != mapa[r["unidad"].lower()]
        ]

    def estadisticas(self, proyecto_id):
        """Conteos básicos del proyecto para el diálogo de información."""
        n_nodos = self._uno("""
            SELECT COUNT(*) AS n FROM estructura_presupuesto WHERE activo = 1
              AND proyecto_id = ?
        """, [proyecto_id])["n"]
        n_conceptos = self._uno("""
            SELECT COUNT(*) AS n FROM estructura_presupuesto
            WHERE tipo = 'concepto' AND activo = 1 AND proyecto_id = ?
        """, [proyecto_id])["n"]
        n_insumos = self._uno("""
            SELECT COUNT(*) AS n FROM insumos WHERE activo = 1 AND proyecto_id = ?
        """, [proyecto_id])["n"]
        n_matrices = self._uno("""
            SELECT COUNT(*) AS n FROM apu_matrices
            WHERE matriz_id IN (
                SELECT id FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
                UNION ALL
                SELECT -id FROM insumos WHERE proyecto_id = ? AND es_compuesto = 1 AND activo = 1
            )
        """, [proyecto_id, proyecto_id])["n"]
        return {
            "n_nodos": n_nodos,
            "n_conceptos": n_conceptos,
            "n_insumos": n_insumos,
            "n_matrices": n_matrices,
        }

    def insumos_hash_desactualizado(self, proyecto_id):
        """Insumos cuyo hash no coincide con el hash generado desde su descripción."""
        from backend.database.core import generar_hash
        filas = self._lista("""
            SELECT id, descripcion, hash FROM insumos
            WHERE proyecto_id = ? AND activo = 1
              AND descripcion IS NOT NULL AND descripcion != ''
            ORDER BY id
        """, [proyecto_id])
        cambios = []
        for r in filas:
            try:
                h = generar_hash(r["descripcion"])
            except ValueError:
                continue
            if not r["hash"] or r["hash"] != h:
                cambios.append((r["id"], r["descripcion"], r["hash"] or "", h))
        return cambios

    def aplicar_hash(self, cambios):
        """Aplica una lista de (id, desc, old_hash, new_hash) como UPDATE batch."""
        self._cursor.executemany(
            "UPDATE insumos SET hash = ? WHERE id = ?",
            [(h, id_) for id_, _, _, h in cambios]
        )
        self._conn.commit()

    def nodos_huerfanos(self, proyecto_id):
        """Nodos del presupuesto cuyo padre_id apunta a un id que no existe."""
        return self._lista("""
            SELECT id, CAST(id AS TEXT) AS clave, descripcion, NULL AS tipo_id
            FROM estructura_presupuesto n
            WHERE n.proyecto_id = ? AND n.activo = 1
              AND n.padre_id IS NOT NULL
              AND n.padre_id NOT IN (
                  SELECT id FROM estructura_presupuesto WHERE activo = 1
              )
        """, [proyecto_id])

    def totales_desincronizados(self, proyecto_id):
        """Capítulos cuyo total no coincide (±$1) con la suma de sus hijos directos."""
        return self._lista("""
            SELECT id, CAST(id AS TEXT) AS clave, descripcion, NULL AS tipo_id
            FROM estructura_presupuesto n
            WHERE n.proyecto_id = ? AND n.tipo = 'capitulo' AND n.activo = 1
              AND ABS(n.total - (
                  SELECT COALESCE(SUM(COALESCE(total, 0)), 0)
                  FROM estructura_presupuesto WHERE padre_id = n.id AND activo = 1
              )) > 1.0
        """, [proyecto_id])

    def componentes_cantidad_cero(self, proyecto_id):
        """Componentes APU con valor = 0 (cantidad cero)."""
        return self._lista("""
            SELECT am.id, i.clave_opus AS clave, i.descripcion, i.tipo_id,
                   am.matriz_id
            FROM apu_matrices am
            JOIN insumos i ON i.id = am.insumo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND (am.valor IS NULL OR am.valor = 0)
            ORDER BY am.matriz_id, am.orden
        """, [proyecto_id])

    def insumos_duplicados_en_matriz(self, proyecto_id):
        """Mismo insumo_id aparece más de una vez en la misma matriz."""
        return self._lista("""
            SELECT am.id, i.clave_opus AS clave, i.descripcion, i.tipo_id,
                   am.matriz_id, dups.cnt
            FROM apu_matrices am
            JOIN insumos i ON i.id = am.insumo_id
            JOIN (
                SELECT matriz_id, insumo_id, COUNT(*) AS cnt
                FROM apu_matrices
                GROUP BY matriz_id, insumo_id
                HAVING COUNT(*) > 1
            ) dups ON dups.matriz_id = am.matriz_id
                  AND dups.insumo_id = am.insumo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
            ORDER BY am.matriz_id, am.insumo_id, am.orden
        """, [proyecto_id])

    def resumen_integridad(self, proyecto_id) -> dict:
        """Reporte agregado de integridad del proyecto. Migrado desde
        core.validar() (Fase 4, ver ARQUITECTURA_SERVICIOS.md).

        Returns:
            {
                "total_nodos":          int,
                "total_conceptos":      int,
                "conceptos_sin_apu":    int,
                "totales_ok":           bool,
                "advertencias":         list[str],
            }
        """
        total_nodos = self._uno("""
            SELECT COUNT(*) AS n FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1
        """, [proyecto_id])["n"]
        total_conceptos = self._uno("""
            SELECT COUNT(*) AS n FROM estructura_presupuesto
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
        """, [proyecto_id])["n"]

        sin_apu    = len(self.conceptos_sin_apu(proyecto_id))
        huerfanos  = len(self.nodos_huerfanos(proyecto_id))
        desincron  = self.totales_desincronizados(proyecto_id)
        totales_ok = len(desincron) == 0

        advertencias = []
        if sin_apu:
            advertencias.append(f"{sin_apu} conceptos sin componentes APU")
        if huerfanos:
            advertencias.append(f"{huerfanos} nodos con padre_id inválido")
        if not totales_ok:
            advertencias.append(f"{len(desincron)} capítulos con totales desincronizados")

        return {
            "total_nodos":       total_nodos,
            "total_conceptos":   total_conceptos,
            "conceptos_sin_apu": sin_apu,
            "totales_ok":        totales_ok,
            "advertencias":      advertencias,
        }
