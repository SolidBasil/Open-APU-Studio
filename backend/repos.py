"""
repos.py
========
Repositorios de acceso a datos para Open APU Studio.
Centraliza todos los repos en un solo archivo — reemplaza la carpeta
backend/db/repos/ y sus 5 archivos individuales.

Uso:
    from backend.repos import (
        NodoRepo, InsumoRepo, ConceptoRepo,
        ApuDetalleRepo, ApuTotalesRepo, AuxiliarRepo,
        ProyectoRepo, PiePreciosRepo, NotaRepo
    )
"""

# =============================================================================
# BASE
# =============================================================================

class RepoBase:
    def __init__(self, conn):
        self._conn   = conn
        self._cursor = conn.cursor()

    def _uno(self, sql, params=None):
        row = self._cursor.execute(sql, params or []).fetchone()
        return dict(row) if row else None

    def _lista(self, sql, params=None):
        return [dict(r) for r in self._cursor.execute(sql, params or []).fetchall()]

    def _ejecutar(self, sql, params=None):
        self._cursor.execute(sql, params or [])
        self._conn.commit()
        return self._cursor.lastrowid

    def _muchos(self, sql, seq):
        self._cursor.executemany(sql, seq)
        self._conn.commit()


# =============================================================================
# PROYECTO
# =============================================================================

class ProyectoRepo(RepoBase):

    # ── lista de proyectos activos ──
    def todos(self):
        return self._lista("""
            SELECT * FROM proyectos WHERE activo = 1 ORDER BY creado_en DESC
        """)

    # ── buscar proyecto por ID ──
    def buscar(self, proyecto_id):
        return self._uno("""
            SELECT * FROM proyectos WHERE id = ? AND activo = 1
        """, [proyecto_id])

    # ── configuración del proyecto ──
    def config(self, proyecto_id):
        return self._uno("""
            SELECT * FROM proyecto_config WHERE proyecto_id = ?
        """, [proyecto_id])

    def actualizar_total(self, proyecto_id):
        """Recalcula y guarda el total de obra desde los nodos raíz."""
        self._ejecutar("""
            UPDATE proyectos SET
                total_obra = (
                    SELECT COALESCE(SUM(subtotal), 0)
                    FROM nodos
                    WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
                ),
                modificado_en = datetime('now')
            WHERE id = ?
        """, [proyecto_id, proyecto_id])


# =============================================================================
# PIE DE PRECIOS (sobrecostos / indirectos)
# =============================================================================

class PiePreciosRepo(RepoBase):

    def por_proyecto(self, proyecto_id):
        return self._lista("""
            SELECT * FROM pie_precios
            WHERE proyecto_id = ?
            ORDER BY orden
        """, [proyecto_id])

    def insertar(self, datos):
        return self._ejecutar("""
            INSERT INTO pie_precios
                (proyecto_id, orden, variable, descripcion, formula,
                 porcentaje_mn, porcentaje_me, suma_en_total,
                 es_egreso_financ, es_ingreso_financ, se_imprime, tipo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            datos.get("proyecto_id"),
            datos.get("orden", 0),
            datos.get("variable", ""),
            datos.get("descripcion", ""),
            datos.get("formula"),
            datos.get("porcentaje_mn", 0),
            datos.get("porcentaje_me", 0),
            datos.get("suma_en_total", 1),
            datos.get("es_egreso_financ", 0),
            datos.get("es_ingreso_financ", 0),
            datos.get("se_imprime", 1),
            datos.get("tipo", "formula_porcentaje"),
        ])

    def limpiar(self, proyecto_id):
        self._ejecutar("""
            DELETE FROM pie_precios WHERE proyecto_id = ?
        """, [proyecto_id])


# =============================================================================
# NODOS (árbol del presupuesto — capítulos y conceptos)
# Reemplaza PartidaRepo + ConceptoRepo
# =============================================================================

class NodoRepo(RepoBase):

    def todos(self, proyecto_id):
        """Árbol completo ordenado por WBS, con estado del semáforo."""
        return self._lista("""
            SELECT
                n.*,
                e.nombre  AS estado_nombre,
                e.color   AS estado_color
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.proyecto_id = ? AND n.activo = 1
            ORDER BY n.wbs
        """, [proyecto_id])

    def hijos(self, padre_id):
        """Hijos directos de un nodo."""
        return self._lista("""
            SELECT n.*, e.nombre AS estado_nombre, e.color AS estado_color
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.padre_id = ? AND n.activo = 1
            ORDER BY n.wbs
        """, [padre_id])

    def raices(self, proyecto_id):
        """Nodos sin padre (nivel superior del proyecto)."""
        return self._lista("""
            SELECT n.*, e.nombre AS estado_nombre, e.color AS estado_color
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.proyecto_id = ? AND n.padre_id IS NULL AND n.activo = 1
            ORDER BY n.wbs
        """, [proyecto_id])

    # ── buscar nodo por ID ──
    def buscar(self, nodo_id):
        return self._uno("""
            SELECT n.*, e.nombre AS estado_nombre, e.color AS estado_color
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.id = ? AND n.activo = 1
        """, [nodo_id])

    def buscar_por_clave(self, clave, proyecto_id):
        """Busca un concepto por su clave OPUS (ej. '0201002')."""
        return self._uno("""
            SELECT * FROM nodos
            WHERE clave = ? AND proyecto_id = ? AND activo = 1
        """, [clave, proyecto_id])

    def descendientes(self, nodo_id):
        """Todos los hijos, nietos, etc. (CTE recursiva)."""
        return self._lista("""
            WITH RECURSIVE sub AS (
                SELECT * FROM nodos WHERE id = ? AND activo = 1
                UNION ALL
                SELECT n.* FROM nodos n
                JOIN sub s ON n.padre_id = s.id
                WHERE n.activo = 1
            )
            SELECT * FROM sub ORDER BY wbs
        """, [nodo_id])

    def ruta(self, nodo_id):
        """Breadcrumb: del nodo hasta la raíz, ordenado de raíz a hoja."""
        return self._lista("""
            WITH RECURSIVE ruta AS (
                SELECT * FROM nodos WHERE id = ?
                UNION ALL
                SELECT n.* FROM nodos n
                JOIN ruta r ON n.id = r.padre_id
            )
            SELECT * FROM ruta ORDER BY nivel
        """, [nodo_id])

    def conceptos_sin_apu(self, proyecto_id):
        """Conceptos que no tienen ningún componente APU registrado."""
        return self._lista("""
            SELECT n.* FROM nodos n
            LEFT JOIN apu_detalle ad ON ad.nodo_id = n.id
            WHERE n.proyecto_id = ? AND n.tipo = 'concepto'
              AND n.activo = 1 AND ad.id IS NULL
            ORDER BY n.wbs
        """, [proyecto_id])

    def por_estado(self, proyecto_id, estado_clave):
        """Filtra nodos por estado del semáforo (ej. 'cuestionado')."""
        return self._lista("""
            SELECT n.*, e.nombre AS estado_nombre, e.color AS estado_color
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.proyecto_id = ? AND e.clave = ? AND n.activo = 1
            ORDER BY n.wbs
        """, [proyecto_id, estado_clave])

    # ── actualizar cantidad y propagar subtotal ──
    def actualizar_cantidad(self, nodo_id, cantidad, usuario_id=1):
        self._ejecutar("""
            UPDATE nodos SET
                cantidad = ?,
                modificado_por = ?,
                modificado_en  = datetime('now')
            WHERE id = ?
        """, [cantidad, usuario_id, nodo_id])
        self.actualizar_subtotal(nodo_id)

    # ── actualizar precio unitario y propagar subtotal ──
    def actualizar_precio(self, nodo_id, precio, usuario_id=1):
        self._ejecutar("""
            UPDATE nodos SET
                precio_unitario = ?,
                modificado_por  = ?,
                modificado_en   = datetime('now')
            WHERE id = ?
        """, [precio, usuario_id, nodo_id])
        self.actualizar_subtotal(nodo_id)

    # ── cambiar semáforo del nodo ──
    def actualizar_estado(self, nodo_id, estado_clave, usuario_id=1):
        estado = self._uno("""
            SELECT id FROM estados_nodo WHERE clave = ?
        """, [estado_clave])
        if not estado:
            return
        self._ejecutar("""
            UPDATE nodos SET
                estado_id      = ?,
                modificado_por = ?,
                modificado_en  = datetime('now')
            WHERE id = ?
        """, [estado["id"], usuario_id, nodo_id])

    def actualizar_subtotal(self, nodo_id):
        """
        Recalcula subtotal bottom-up desde nodo_id hasta la raíz.
        Llamar después de cualquier cambio en cantidad o precio_unitario.
        """
        cur    = self._cursor
        actual = nodo_id
        while actual is not None:
            cur.execute("""
                UPDATE nodos SET
                    subtotal = (
                        SELECT COALESCE(SUM(
                            CASE WHEN tipo = 'concepto'
                                 THEN COALESCE(importe, 0)
                                 ELSE COALESCE(subtotal, 0)
                            END
                        ), 0)
                        FROM nodos
                        WHERE padre_id = ? AND activo = 1
                    ),
                    modificado_en = datetime('now')
                WHERE id = ? AND tipo = 'capitulo'
            """, (actual, actual))
            row = cur.execute(
                "SELECT padre_id FROM nodos WHERE id = ?", (actual,)
            ).fetchone()
            actual = row["padre_id"] if row else None
        self._conn.commit()

    def eliminar(self, nodo_id, usuario_id=1):
        """Soft-delete: marca el nodo y sus descendientes como inactivos."""
        # Primero marcar todos los descendientes
        descendientes = self.descendientes(nodo_id)
        ids = [d["id"] for d in descendientes]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            self._ejecutar(f"""
                UPDATE nodos SET activo = 0,
                    modificado_por = ?, modificado_en = datetime('now')
                WHERE id IN ({placeholders})
            """, [usuario_id] + ids)
        # Luego recalcular el padre
        nodo = self.buscar(nodo_id)
        if nodo and nodo.get("padre_id"):
            self.actualizar_subtotal(nodo["padre_id"])


# =============================================================================
# CONCEPTOS — alias de conveniencia sobre NodoRepo
# =============================================================================

class ConceptoRepo(RepoBase):
    """
    Acceso rápido a nodos de tipo 'concepto'.
    Para operaciones de árbol completo usar NodoRepo.
    """

    # ── conceptos hijos de un capítulo ──
    def por_padre(self, padre_id):
        return self._lista("""
            SELECT * FROM nodos
            WHERE padre_id = ? AND tipo = 'concepto' AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    # ── buscar concepto por clave OPUS ──
    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno("""
            SELECT * FROM nodos
            WHERE clave = ? AND proyecto_id = ? AND tipo = 'concepto' AND activo = 1
        """, [clave, proyecto_id])

    # ── todos los conceptos del proyecto ──
    def todos(self, proyecto_id):
        return self._lista("""
            SELECT * FROM nodos
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])


# =============================================================================
# INSUMOS
# =============================================================================

class InsumoRepo(RepoBase):

    def _select_sql(self):
        return """
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
                   f.nombre AS familia_nombre, p.nombre AS proveedor_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN familias f ON f.id = i.familia_id
            LEFT JOIN proveedores p ON p.id = i.proveedor_id
        """

    # ── todos los insumos del proyecto ──
    def todos(self, proyecto_id):
        return self._lista(
            self._select_sql() + " WHERE i.proyecto_id = ? AND i.activo = 1 ORDER BY t.orden, i.clave",
            [proyecto_id])

    def por_tipo(self, proyecto_id, tipo_clave):
        """tipo_clave: 'material', 'mano_obra', 'herramienta', 'equipo', 'auxiliar'"""
        return self._lista(
            self._select_sql() + " WHERE i.proyecto_id = ? AND t.clave = ? AND i.activo = 1 ORDER BY i.clave",
            [proyecto_id, tipo_clave])

    # ── buscar insumo por ID ──
    def buscar(self, insumo_id):
        return self._uno(
            self._select_sql() + " WHERE i.id = ? AND i.activo = 1",
            [insumo_id])

    # ── buscar insumo por clave ──
    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno(
            self._select_sql() + " WHERE i.clave = ? AND i.proyecto_id = ? AND i.activo = 1",
            [clave, proyecto_id])

    def buscar_texto(self, proyecto_id, texto):
        """Búsqueda libre en clave y descripción."""
        q = f"%{texto}%"
        return self._lista(
            self._select_sql() + " WHERE i.proyecto_id = ? AND i.activo = 1 AND (i.clave LIKE ? OR i.descripcion LIKE ? OR i.descripcion_corta LIKE ?) ORDER BY t.orden, i.clave",
            [proyecto_id, q, q, q])

    def resumen_por_tipo(self, proyecto_id):
        """Conteo y costo total por tipo de insumo."""
        return self._lista("""
            SELECT
                t.id, t.clave, t.nombre,
                COUNT(i.id)        AS total,
                SUM(i.costo_final) AS costo_total
            FROM tipos_insumo t
            LEFT JOIN insumos i
                ON i.tipo_id = t.id
               AND i.proyecto_id = ?
               AND i.activo = 1
            GROUP BY t.id
            ORDER BY t.orden
        """, [proyecto_id])

    def uso_en_proyecto(self, insumo_id):
        """En cuántos APUs aparece este insumo y cuánto suma."""
        return self._uno("""
            SELECT
                COUNT(ad.id)    AS apariciones,
                SUM(ad.importe) AS importe_total
            FROM apu_detalle ad
            WHERE ad.insumo_id = ?
        """, [insumo_id])

    # ── actualizar precio del insumo ──
    def actualizar_precio(self, insumo_id, precio, usuario_id=1):
        self._ejecutar("""
            UPDATE insumos SET
                costo_mn      = ?,
                costo_final   = ?,
                modificado_por = ?,
                modificado_en  = datetime('now')
            WHERE id = ?
        """, [precio, precio, usuario_id, insumo_id])

    def tipos_disponibles(self):
        """Catálogo de tipos de insumo (semilla del sistema)."""
        return self._lista("""
            SELECT * FROM tipos_insumo ORDER BY orden
        """)


# =============================================================================
# APU DETALLE
# =============================================================================

class ApuDetalleRepo(RepoBase):

    def por_nodo(self, nodo_id):
        """Componentes del APU con descripción e insumo completo."""
        return self._lista("""
            SELECT
                ad.*,
                i.clave              AS insumo_clave,
                i.descripcion        AS insumo_descripcion,
                i.descripcion_corta  AS insumo_desc_corta,
                i.unidad             AS insumo_unidad,
                t.clave              AS tipo_clave,
                t.nombre             AS tipo_nombre
            FROM apu_detalle ad
            JOIN insumos i      ON i.id  = ad.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE (ad.nodo_id = ? OR ad.apu_nodo_id = ?)
            ORDER BY ad.orden
        """, [nodo_id, nodo_id])

    # ── insertar componente al APU ──
    def insertar(self, datos):
        return self._ejecutar("""
            INSERT INTO apu_detalle
                (nodo_id, apu_nodo_id, insumo_id, rendimiento, cantidad,
                 precio, formula, orden, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            datos.get("nodo_id"),
            datos.get("apu_nodo_id"),
            datos.get("insumo_id"),
            datos.get("rendimiento", 0),
            datos.get("cantidad", 0),
            datos.get("precio", 0),
            datos.get("formula"),
            datos.get("orden", 0),
            datos.get("creado_por", 1),
        ])

    # ── cambiar cantidad de un componente ──
    def actualizar_cantidad(self, detalle_id, cantidad, usuario_id=1):
        self._ejecutar("""
            UPDATE apu_detalle SET
                cantidad       = ?,
                modificado_por = ?,
                modificado_en  = datetime('now')
            WHERE id = ?
        """, [cantidad, usuario_id, detalle_id])

    # ── cambiar precio de un componente ──
    def actualizar_precio(self, detalle_id, precio, usuario_id=1):
        self._ejecutar("""
            UPDATE apu_detalle SET
                precio         = ?,
                modificado_por = ?,
                modificado_en  = datetime('now')
            WHERE id = ?
        """, [precio, usuario_id, detalle_id])

    # ── eliminar un componente del APU ──
    def eliminar(self, detalle_id):
        self._ejecutar("""
            DELETE FROM apu_detalle WHERE id = ?
        """, [detalle_id])

    # ── eliminar todos los componentes de un nodo ──
    def limpiar(self, nodo_id):
        self._ejecutar("""
            DELETE FROM apu_detalle WHERE (nodo_id = ? OR apu_nodo_id = ?)
        """, [nodo_id, nodo_id])


# =============================================================================
# APU NODOS (sintéticos para insumos compuestos fuera del árbol)
# =============================================================================

class ApuNodoRepo(RepoBase):

    # ── buscar APU sintético por clave ──
    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno("""
            SELECT * FROM apu_nodos
            WHERE clave = ? AND proyecto_id = ?
        """, [clave, proyecto_id])

    # ── todos los APU sintéticos del proyecto ──
    def todos(self, proyecto_id):
        return self._lista("""
            SELECT * FROM apu_nodos WHERE proyecto_id = ? ORDER BY clave
        """, [proyecto_id])


# =============================================================================
# APU TOTALES
# =============================================================================

class ApuTotalesRepo(RepoBase):

    # ── totales por tipo de un APU ──
    def por_nodo(self, nodo_id):
        return self._uno("""
            SELECT * FROM apu_totales WHERE (nodo_id = ? OR apu_nodo_id = ?)
        """, [nodo_id, nodo_id])

    def recalcular(self, nodo_id):
        """
        Recalcula los totales por tipo desde apu_detalle y los guarda.
        Llamar después de cualquier cambio en apu_detalle.
        """
        self._ejecutar("""
            INSERT OR REPLACE INTO apu_totales
                (nodo_id, apu_nodo_id, materiales, mano_obra, herramienta,
                 equipo, auxiliares, subcontratos, costo_directo,
                 modificado_en)
            SELECT
                ?,
                ?,
                COALESCE(SUM(CASE WHEN t.clave = 'material'    THEN ad.importe ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN t.clave = 'mano_obra'   THEN ad.importe ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN t.clave = 'herramienta' THEN ad.importe ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN t.clave = 'equipo'      THEN ad.importe ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN t.clave = 'auxiliar'    THEN ad.importe ELSE 0 END), 0),
                0,
                COALESCE(SUM(ad.importe), 0),
                datetime('now')
            FROM apu_detalle ad
            JOIN insumos i      ON i.id  = ad.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE (ad.nodo_id = ? OR ad.apu_nodo_id = ?)
            GROUP BY COALESCE(ad.nodo_id, ad.apu_nodo_id)
        """, [nodo_id, nodo_id, nodo_id, nodo_id])

    def actualizar_sobrecostos(self, nodo_id, indirectos_pct=0,
                                financiamiento_pct=0, utilidad_pct=0,
                                cargo_adicional_pct=0):
        totales = self.por_nodo(nodo_id)
        if not totales:
            return
        cd = totales["costo_directo"]
        pv = cd * (1 + (indirectos_pct + financiamiento_pct +
                        utilidad_pct + cargo_adicional_pct) / 100)
        self._ejecutar("""
            UPDATE apu_totales SET
                indirectos_pct      = ?,
                financiamiento_pct  = ?,
                utilidad_pct        = ?,
                cargo_adicional_pct = ?,
                precio_venta        = ?,
                modificado_en       = datetime('now')
            WHERE (nodo_id = ? OR apu_nodo_id = ?)
        """, [indirectos_pct, financiamiento_pct, utilidad_pct,
                cargo_adicional_pct, round(pv, 6), nodo_id, nodo_id])


# =============================================================================
# AUXILIARES
# =============================================================================

class AuxiliarRepo(RepoBase):

    # ── componentes auxiliares de un insumo ──
    def por_insumo(self, insumo_id):
        return self._lista("""
            SELECT a.*, i.clave AS comp_clave, i.descripcion AS comp_desc
            FROM auxiliares a
            JOIN insumos i ON i.id = a.componente_id
            WHERE a.insumo_id = ?
        """, [insumo_id])

    # ── todos los auxiliares del proyecto ──
    def todos(self, proyecto_id):
        return self._lista("""
            SELECT a.*,
                   i.clave AS insumo_clave,
                   c.clave AS comp_clave, c.descripcion AS comp_desc
            FROM auxiliares a
            JOIN insumos i ON i.id = a.insumo_id
            JOIN insumos c ON c.id = a.componente_id
            WHERE a.proyecto_id = ?
        """, [proyecto_id])


# =============================================================================
# NOTAS (colaboración)
# =============================================================================

class NotaRepo(RepoBase):

    # ── notas de un nodo ──
    def por_nodo(self, nodo_id):
        return self._lista("""
            SELECT n.*, u.nombre AS autor
            FROM notas n
            JOIN usuarios u ON u.id = n.usuario_id
            WHERE n.nodo_id = ?
            ORDER BY n.creado_en DESC
        """, [nodo_id])

    # ── agregar nota a un nodo ──
    def insertar(self, nodo_id, texto, usuario_id=1):
        return self._ejecutar("""
            INSERT INTO notas (nodo_id, usuario_id, texto)
            VALUES (?, ?, ?)
        """, [nodo_id, usuario_id, texto])

    # ── marcar nota como resuelta ──
    def resolver(self, nota_id):
        self._ejecutar("""
            UPDATE notas SET resuelta = 1, modificado_en = datetime('now')
            WHERE id = ?
        """, [nota_id])

    def abiertas(self, proyecto_id):
        """Todas las notas sin resolver del proyecto."""
        return self._lista("""
            SELECT n.*, u.nombre AS autor, nd.wbs, nd.descripcion_corta
            FROM notas n
            JOIN usuarios u ON u.id = n.usuario_id
            JOIN nodos nd   ON nd.id = n.nodo_id
            WHERE nd.proyecto_id = ? AND n.resuelta = 0
            ORDER BY n.creado_en DESC
        """, [proyecto_id])
