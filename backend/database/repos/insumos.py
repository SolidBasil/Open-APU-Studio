"""insumos.py
Repositorio del catálogo de insumos.
"""
from .base import RepoBase, generar_hash

class InsumoRepo(RepoBase):
    """Catálogo de insumos del proyecto: materiales, MO, equipo, etc.
    JOIN con tipos_insumo (tipo_clave, tipo_nombre), familias
    (familia_nombre) y subfamilias (subfamilia_nombre).
    """

    # Base SELECT reutilizada en todos los métodos de consulta.
    # Siempre agregar WHERE después de este bloque.
    _SQL = """
        SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
               f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
        FROM insumos i
        JOIN tipos_insumo t ON t.id = i.tipo_id
        LEFT JOIN familias f ON f.id = i.familia_id
        LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
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

    def buscar_texto(self, proyecto_id, texto):
        """Busca insumos por texto en clave, descripción o descripción corta."""
        q = f"%{texto}%"
        return self._lista(self._SQL + """
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND (i.clave_opus LIKE ? OR i.descripcion LIKE ? OR i.descripcion_corta LIKE ?)
            ORDER BY t.orden, i.id
        """, [proyecto_id, q, q, q])

    def buscar_por_hash(self, hash_val, proyecto_id):
        """Busca un insumo por su hash dentro de un proyecto.
        Útil para detectar duplicados antes de insertar o renombrar.
        """
        return self._uno(self._SQL + """
            WHERE i.hash = ? AND i.proyecto_id = ? AND i.activo = 1
        """, [hash_val, proyecto_id])

        """Devuelve un resumen de cantidad y costo total agrupado por tipo de insumo."""
        return self._lista("""
            SELECT t.id, t.clave, t.nombre,
                   COUNT(i.id) AS total, SUM(i.costo_final) AS costo_total
            FROM tipos_insumo t
            LEFT JOIN insumos i
                ON i.tipo_id = t.id AND i.proyecto_id = ? AND i.activo = 1
            GROUP BY t.id
            ORDER BY t.orden
        """, [proyecto_id])

    def uso_en_proyecto(self, insumo_id):
        """Devuelve el número de apariciones y el importe total de un insumo en APUs."""
        return self._uno("""
            SELECT COUNT(ac.id) AS apariciones,
                   SUM(CASE WHEN ac.operador='*' THEN ac.valor*ac.precio ELSE ac.precio/ac.valor END) AS importe_total
            FROM apu_matrices ac
            WHERE ac.insumo_id = ?
        """, [insumo_id])

    def donde_se_usa(self, insumo_id):
        """Devuelve los APU (concepto/compuesto) donde aparece un insumo."""
        return self._lista("""
            SELECT
                am.matriz_id,
                am.valor,
                am.operador,
                am.precio,
                CASE WHEN am.operador='*' THEN am.valor*am.precio ELSE am.precio/am.valor END AS importe,
                CASE WHEN am.matriz_id > 0
                     THEN 'concepto' ELSE 'compuesto' END         AS tipo_origen,
                COALESCE(CAST(ep.id AS TEXT),  CAST(ic.id AS TEXT))  AS matriz_clave,
                COALESCE(ep.descripcion,
                         ic.descripcion)                          AS matriz_descripcion,
                ep.wbs                                            AS matriz_wbs
            FROM apu_matrices am
            LEFT JOIN estructura_presupuesto ep
                   ON ep.id = am.matriz_id AND am.matriz_id > 0
            LEFT JOIN insumos ic
                   ON ic.id = ABS(am.matriz_id) AND am.matriz_id < 0
            WHERE am.insumo_id = ?
            ORDER BY matriz_wbs, matriz_clave
        """, [insumo_id])

    def actualizar_precio(self, insumo_id, precio, usuario_id=1):
        """Actualiza costo_mn, costo_directo y costo_final de un insumo."""
        self._ejecutar("""
            UPDATE insumos SET
                costo_mn = ?, costo_directo = ?, costo_final = ?,
                modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [precio, precio, precio, usuario_id, insumo_id])



    def actualizar_descripcion(self, insumo_id, descripcion, proyecto_id, usuario_id=1):
        """Actualiza la descripción de un insumo y regenera su hash.

        Verifica antes de escribir que el hash nuevo no colisione con otro
        insumo del mismo proyecto. Si hay colisión, lanza ValueError con el
        id y descripción del insumo existente para que la UI informe al usuario.
        """
        nuevo_hash = generar_hash(descripcion)
        existente  = self.buscar_por_hash(nuevo_hash, proyecto_id)
        if existente and existente["id"] != insumo_id:
            raise ValueError(
                f"Ya existe un insumo con esa descripción: "
                f"[{existente['id']}] {existente['descripcion']}"
            )
        self._ejecutar("""
            UPDATE insumos SET
                descripcion     = ?,
                hash            = ?,
                modificado_por  = ?,
                modificado_en   = datetime('now')
            WHERE id = ?
        """, [descripcion, nuevo_hash, usuario_id, insumo_id])

    def insertar(self, proyecto_id, tipo_id, descripcion,
                 descripcion_corta=None, unidad=None, costo=0.0,
                 es_compuesto=0, clave_opus=None, usuario_id=1):
        """Inserta un insumo creado desde la app (no importado).

        Genera el hash automáticamente desde la descripción — es la llave
        funcional para deduplicación. clave_opus es opcional y puramente
        referencial (queda NULL salvo que el insumo provenga de OPUS).
        Verifica duplicados por hash antes de insertar. Si hay colisión
        lanza ValueError igual que actualizar_descripcion.

        Devuelve el id (rowid) del insumo insertado.
        """
        nuevo_hash = generar_hash(descripcion) if descripcion else None
        if nuevo_hash:
            existente = self.buscar_por_hash(nuevo_hash, proyecto_id)
            if existente:
                raise ValueError(
                    f"Ya existe un insumo con esa descripción: "
                    f"[{existente['id']}] {existente['descripcion']}"
                )
        return self._ejecutar("""
            INSERT INTO insumos
                (proyecto_id, tipo_id, descripcion, descripcion_corta,
                 unidad, costo_mn, costo_directo, costo_final, es_compuesto,
                 hash, clave_opus, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [proyecto_id, tipo_id, descripcion, descripcion_corta,
               unidad, costo, costo, costo, es_compuesto,
               nuevo_hash, clave_opus, usuario_id])

    def tipos_disponibles(self):
        """Devuelve todos los tipos de insumo ordenados."""
        return self._lista("SELECT * FROM tipos_insumo ORDER BY orden")


# =============================================================================
# APU COMPONENTES (antes: apu_detalle)
# =============================================================================
