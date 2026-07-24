"""insumos.py
Repositorio del catálogo de insumos.
"""
from .base import RepoBase

class InsumoRepo(RepoBase):
    """Catálogo de insumos del proyecto: materiales, MO, equipo, etc.
    JOIN con tipos_insumo (tipo_clave, tipo_nombre), familias
    (familia_nombre) y subfamilias (subfamilia_nombre).
    """

    TABLA = "insumos"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    # Base SELECT reutilizada en todos los métodos de consulta.
    # Siempre agregar WHERE después de este bloque.
    #
    # proveedor_nombre: JOIN agregado junto con el catálogo ampliado de
    # columnas de Insumos — antes faltaba y la columna "Proveedor" de la
    # tabla siempre salía vacía sin que nada lo avisara.
    # creado_por_nombre / modificado_por_nombre: resuelven el id de usuario
    # a su nombre (mostrar el id crudo no sirve de nada en la UI).
    _SQL = """
        SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
               f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre,
               p.nombre AS proveedor_nombre,
               uc.nombre AS creado_por_nombre,
               um.nombre AS modificado_por_nombre
        FROM insumos i
        JOIN tipos_insumo t ON t.id = i.tipo_id
        LEFT JOIN familias f ON f.id = i.familia_id
        LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
        LEFT JOIN proveedores p ON p.id = i.proveedor_id
        LEFT JOIN usuarios uc ON uc.id = i.creado_por
        LEFT JOIN usuarios um ON um.id = i.modificado_por
    """

    def todos(self, proyecto_id):
        """Devuelve todos los insumos activos de un proyecto con sus joins.
        Orden: tipo de insumo → básicos antes que compuestos → alfabético.
        """
        return self._lista(self._SQL + """
            WHERE i.proyecto_id = ? AND i.activo = 1
            ORDER BY t.orden, i.es_compuesto,
                     COALESCE(i.descripcion, i.descripcion_corta) COLLATE NOCASE
        """, [proyecto_id])

    def por_tipo(self, proyecto_id, tipo_clave):
        """Devuelve los insumos de un tipo específico (clave textual).
        Orden: básicos antes que compuestos → alfabético.
        """
        return self._lista(self._SQL + """
            WHERE i.proyecto_id = ? AND t.clave = ? AND i.activo = 1
            ORDER BY i.es_compuesto,
                     COALESCE(i.descripcion, i.descripcion_corta) COLLATE NOCASE
        """, [proyecto_id, tipo_clave])

    def buscar(self, insumo_id):
        """Busca un insumo por su ID."""
        return self._uno(self._SQL + """
            WHERE i.id = ? AND i.activo = 1
        """, [insumo_id])

    def buscar_por_hash(self, hash_val, proyecto_id):
        """Busca un insumo por su hash dentro de un proyecto.
        Útil para detectar duplicados antes de insertar o renombrar.
        """
        return self._uno(self._SQL + """
            WHERE i.hash = ? AND i.proyecto_id = ? AND i.activo = 1
        """, [hash_val, proyecto_id])

    def donde_se_usa(self, insumo_id):
        """Devuelve los APU (concepto/compuesto) donde aparece un insumo.

        matriz_clave es siempre el clave_opus del insumo dueño de la fila
        (el del concepto para 'concepto', el del propio compuesto para
        'compuesto') — antes se devolvía por error el id interno de la
        fila (ep.id / ic.id), que no significa nada para el usuario.

        matriz_wbs solo aplica a 'concepto' (posición real en el árbol de
        presupuesto, wbs crudo sin formatear — el formato con puntos según
        nivel se resuelve en el frontend). Un insumo compuesto puede
        usarse en múltiples APUs distintos a la vez, así que no tiene una
        posición única en el presupuesto; antes se intentaba adivinar una
        vía subconsulta, lo que casi siempre daba NULL o un wbs de otro
        concepto sin relación real. Ahora se deja NULL a propósito.
        """
        return self._lista("""
            SELECT
                am.matriz_id,
                am.valor,
                am.operador,
                am.precio,
                CASE WHEN am.operador='*' THEN am.valor*am.precio ELSE am.precio/am.valor END AS importe,
                CASE WHEN am.matriz_id > 0
                     THEN 'concepto' ELSE 'compuesto' END         AS tipo_origen,
                COALESCE(ie.clave_opus, ic.clave_opus)           AS matriz_clave,
                COALESCE(ep.descripcion,
                         ic.descripcion)                          AS matriz_descripcion,
                CASE WHEN am.matriz_id > 0 THEN ep.wbs END       AS matriz_wbs,
                COALESCE(tc.nombre, ti.nombre)                   AS matriz_tipo,
                COALESCE(tc.id, ti.id)                           AS matriz_tipo_id
            FROM apu_matrices am
            LEFT JOIN estructura_presupuesto ep
                   ON ep.id = am.matriz_id AND am.matriz_id > 0
            LEFT JOIN insumos ic
                   ON ic.id = ABS(am.matriz_id) AND am.matriz_id < 0
            LEFT JOIN tipos_insumo tc
                   ON tc.id = ic.tipo_id AND am.matriz_id < 0
            LEFT JOIN insumos ie
                   ON ie.id = ep.insumo_id AND am.matriz_id > 0
            LEFT JOIN tipos_insumo ti
                   ON ti.id = ie.tipo_id AND am.matriz_id > 0
            WHERE am.insumo_id = ?
            ORDER BY tipo_origen DESC, matriz_wbs, matriz_clave
        """, [insumo_id])

    def ids_con_apu(self, proyecto_id):
        """Conjunto de ids de insumos compuestos (tienen APU propio)."""
        rows = self._lista("""
            SELECT id FROM insumos
            WHERE es_compuesto = 1 AND proyecto_id = ? AND activo = 1
        """, [proyecto_id])
        return {r["id"] for r in rows}

    def actualizar_unidades_batch(self, cambios: list[tuple[str, int]]) -> None:
        """Actualiza unidad para múltiples insumos en un solo execute.
        cambios: lista de (nueva_unidad, insumo_id)."""
        if cambios:
            self._cursor.executemany(
                "UPDATE insumos SET unidad = ? WHERE id = ?",
                cambios
            )


# =============================================================================
# APU COMPONENTES (antes: apu_detalle)
# =============================================================================
