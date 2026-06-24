"""
repos.py
========
Repositorios de acceso a datos — Open APU Studio v2.

Nomenclatura de tablas v2:
    estructura_presupuesto  ← antes: nodos
    apu_matrices.matriz_id  ← columna unica (antes: concepto_id + insumo_compuesto_id)
    apu_matrices            ← antes: apu_componentes
    apu_resumen_totales     ← antes: apu_resumen
    sobrecostos             ← antes: pie_precios
    configuracion_proyecto  ← antes: proyecto_config
    subfamilias             ← nueva

Uso:
    from backend.repos import (
        NodoRepo, InsumoRepo, ConceptoRepo,
        ApuMatricesRepo, ApuResumenTotalesRepo,
        ProyectoRepo, SobrecostosRepo,
        NotaRepo, FamiliaRepo, SubfamiliaRepo
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

    def todos(self):
        return self._lista("""
            SELECT * FROM proyectos WHERE activo = 1 ORDER BY creado_en DESC
        """)

    def buscar(self, proyecto_id):
        return self._uno("""
            SELECT * FROM proyectos WHERE id = ? AND activo = 1
        """, [proyecto_id])

    def config(self, proyecto_id):
        return self._uno("""
            SELECT * FROM configuracion_proyecto WHERE proyecto_id = ?
        """, [proyecto_id])

    def actualizar_total(self, proyecto_id):
        self._ejecutar("""
            UPDATE proyectos SET
                total_obra = (
                    SELECT COALESCE(SUM(subtotal), 0)
                    FROM estructura_presupuesto
                    WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
                ),
                modificado_en = datetime('now')
            WHERE id = ?
        """, [proyecto_id, proyecto_id])


# =============================================================================
# SOBRECOSTOS (antes: pie_precios)
# =============================================================================

class SobrecostosRepo(RepoBase):

    def por_proyecto(self, proyecto_id):
        return self._lista("""
            SELECT * FROM sobrecostos
            WHERE proyecto_id = ?
            ORDER BY orden
        """, [proyecto_id])

    def insertar(self, datos):
        return self._ejecutar("""
            INSERT INTO sobrecostos
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
            DELETE FROM sobrecostos WHERE proyecto_id = ?
        """, [proyecto_id])


# =============================================================================
# NODOS — estructura_presupuesto (capítulos y conceptos)
# =============================================================================

# Colores del semáforo — el frontend los usa para pintar la fila
ESTADO_COLOR = {
    0: "#808080",  # Sin revisar
    1: "#F5A623",  # En revisión
    2: "#4CAF7D",  # Verificado
    3: "#E05252",  # Cuestionado
}

ESTADO_NOMBRE = {
    0: "Sin revisar",
    1: "En revisión",
    2: "Verificado",
    3: "Cuestionado",
}


class NodoRepo(RepoBase):
    """Acceso a estructura_presupuesto: capítulos y conceptos del presupuesto.
    El árbol viene con padre_id correctamente resuelto desde la importación.
    """

    def todos(self, proyecto_id):
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])

    def hijos(self, padre_id):
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE padre_id = ? AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    def raices(self, proyecto_id):
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])

    def buscar(self, concepto_id):
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE id = ? AND activo = 1
        """, [concepto_id])

    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE clave = ? AND proyecto_id = ? AND activo = 1
        """, [clave, proyecto_id])

    def descendientes(self, concepto_id):
        return self._lista("""
            WITH RECURSIVE sub AS (
                SELECT * FROM estructura_presupuesto WHERE id = ? AND activo = 1
                UNION ALL
                SELECT n.* FROM estructura_presupuesto n
                JOIN sub s ON n.padre_id = s.id
                WHERE n.activo = 1
            )
            SELECT * FROM sub ORDER BY wbs
        """, [concepto_id])

    def ruta(self, concepto_id):
        return self._lista("""
            WITH RECURSIVE ruta AS (
                SELECT * FROM estructura_presupuesto WHERE id = ?
                UNION ALL
                SELECT n.* FROM estructura_presupuesto n
                JOIN ruta r ON n.id = r.padre_id
            )
            SELECT * FROM ruta ORDER BY nivel
        """, [concepto_id])

    def por_estado(self, proyecto_id, estado: int):
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND estado = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id, estado])

    def conceptos_sin_apu(self, proyecto_id):
        return self._lista("""
            SELECT ep.* FROM estructura_presupuesto ep
            LEFT JOIN apu_matrices ac ON ac.matriz_id = ep.id
            WHERE ep.proyecto_id = ? AND ep.tipo = 'concepto'
              AND ep.activo = 1 AND ac.id IS NULL
            ORDER BY ep.wbs
        """, [proyecto_id])

    def actualizar_cantidad(self, concepto_id, cantidad, usuario_id=1):
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                cantidad = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [cantidad, usuario_id, concepto_id])
        self.actualizar_subtotal(concepto_id)

    def actualizar_precio(self, concepto_id, precio, usuario_id=1):
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                precio_unitario = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [precio, usuario_id, concepto_id])
        self.actualizar_subtotal(concepto_id)

    def actualizar_estado(self, concepto_id, estado: int, usuario_id=1):
        if estado not in ESTADO_COLOR:
            return
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                estado = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [estado, usuario_id, concepto_id])

    def actualizar_subtotal(self, concepto_id):
        """Recalcula subtotal desde concepto_id hacia arriba hasta la raíz.
        importe es GENERATED (cant×pu), subtotal se actualiza en cada capítulo padre.
        """
        cur    = self._cursor
        actual = concepto_id
        while actual is not None:
            cur.execute("""
                UPDATE estructura_presupuesto SET
                    subtotal = (
                        SELECT COALESCE(SUM(
                            CASE WHEN tipo = 'concepto'
                                 THEN COALESCE(importe, 0)
                                 ELSE COALESCE(subtotal, 0)
                            END
                        ), 0)
                        FROM estructura_presupuesto
                        WHERE padre_id = ? AND activo = 1
                    ),
                    modificado_en = datetime('now')
                WHERE id = ? AND tipo = 'capitulo'
            """, (actual, actual))
            row = cur.execute(
                "SELECT padre_id FROM estructura_presupuesto WHERE id = ?", (actual,)
            ).fetchone()
            actual = row["padre_id"] if row else None
        self._conn.commit()

    def eliminar(self, concepto_id, usuario_id=1):
        desc = self.descendientes(concepto_id)
        ids  = [d["id"] for d in desc]
        if ids:
            ph = ",".join("?" for _ in ids)
            self._ejecutar(f"""
                UPDATE estructura_presupuesto SET activo = 0,
                    modificado_por = ?, modificado_en = datetime('now')
                WHERE id IN ({ph})
            """, [usuario_id] + ids)
        nodo = self.buscar(concepto_id)
        if nodo and nodo.get("padre_id"):
            self.actualizar_subtotal(nodo["padre_id"])


# =============================================================================
# CONCEPTOS — alias de conveniencia sobre NodoRepo
# =============================================================================

class ConceptoRepo(RepoBase):
    """Conveniencia sobre NodoRepo: solo nodos tipo 'concepto'."""

    def por_padre(self, padre_id):
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE padre_id = ? AND tipo = 'concepto' AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE clave = ? AND proyecto_id = ?
              AND tipo = 'concepto' AND activo = 1
        """, [clave, proyecto_id])

    def todos(self, proyecto_id):
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])


# =============================================================================
# INSUMOS
# =============================================================================

class InsumoRepo(RepoBase):
    """Catálogo de insumos del proyecto: materiales, MO, equipo, etc.
    Siempre JOIN con tipos_insumo para incluir tipo_clave y tipo_nombre.
    """

    def todos(self, proyecto_id):
        return self._lista("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
            ORDER BY t.orden, i.clave
        """, [proyecto_id])

    def por_tipo(self, proyecto_id, tipo_clave):
        return self._lista("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.proyecto_id = ? AND t.clave = ? AND i.activo = 1
            ORDER BY i.clave
        """, [proyecto_id, tipo_clave])

    def buscar(self, insumo_id):
        return self._uno("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.id = ? AND i.activo = 1
        """, [insumo_id])

    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.clave = ? AND i.proyecto_id = ? AND i.activo = 1
        """, [clave, proyecto_id])

    def buscar_texto(self, proyecto_id, texto):
        q = f"%{texto}%"
        return self._lista("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND (i.clave LIKE ? OR i.descripcion LIKE ? OR i.descripcion_corta LIKE ?)
            ORDER BY t.orden, i.clave
        """, [proyecto_id, q, q, q])

    def resumen_por_tipo(self, proyecto_id):
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
        return self._uno("""
            SELECT COUNT(ac.id) AS apariciones, SUM(ac.importe) AS importe_total
            FROM apu_matrices ac
            WHERE ac.insumo_id = ?
        """, [insumo_id])

    def actualizar_precio(self, insumo_id, precio, usuario_id=1):
        self._ejecutar("""
            UPDATE insumos SET
                costo_mn = ?, costo_final = ?,
                modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [precio, precio, usuario_id, insumo_id])

    def tipos_disponibles(self):
        return self._lista("SELECT * FROM tipos_insumo ORDER BY orden")


# =============================================================================
# APU COMPONENTES (antes: apu_detalle)
# =============================================================================

class ApuMatricesRepo(RepoBase):
    """Componentes del APU: desglose de insumos por concepto o insumo compuesto.
    matriz_id unificado: positivo para nodos del árbol, negativo para insumos compuestos.
    """

    def por_matriz(self, matriz_id):
        return self._lista("""
            SELECT ac.*,
                   i.clave             AS insumo_clave,
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
        return self._ejecutar("""
            INSERT INTO apu_matrices
                (matriz_id, insumo_id, rendimiento,
                 cantidad, precio, formula, orden, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            datos.get("matriz_id"),
            datos.get("insumo_id"),
            datos.get("rendimiento", 0),
            datos.get("cantidad", 0),
            datos.get("precio", 0),
            datos.get("formula"),
            datos.get("orden", 0),
            datos.get("creado_por", 1),
        ])

    def eliminar(self, comp_id):
        self._ejecutar("DELETE FROM apu_matrices WHERE id = ?", [comp_id])

    def limpiar(self, matriz_id):
        self._ejecutar("DELETE FROM apu_matrices WHERE matriz_id = ?", [matriz_id])


# =============================================================================
# APU RESUMEN (antes: apu_totales)
# =============================================================================

class ApuResumenTotalesRepo(RepoBase):
    """Resumen de costos por tipo de insumo para cada APU.
    Se recalcula desde apu_matrices cuando cambian precios o cantidades.
    """

    def por_matriz(self, matriz_id):
        return self._uno("""
            SELECT * FROM apu_resumen_totales WHERE matriz_id = ?
        """, [matriz_id])

    def recalcular(self, matriz_id):
        self._ejecutar("""
            INSERT OR REPLACE INTO apu_resumen_totales
                (matriz_id, materiales, mano_obra, herramienta, equipo,
                 auxiliares, subcontratos, fletes, trabajos, costo_directo,
                 modificado_en)
            SELECT
                ac.matriz_id,
                COALESCE(SUM(CASE WHEN t.clave='material'    THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='mano_obra'   THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='herramienta' THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='equipo'      THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='auxiliar'    THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='concepto'    THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='flete'       THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='trabajo'     THEN ac.importe ELSE 0 END),0),
                COALESCE(SUM(ac.importe), 0),
                datetime('now')
            FROM apu_matrices ac
            JOIN insumos i      ON i.id  = ac.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE ac.matriz_id = ?
            GROUP BY ac.matriz_id
        """, [matriz_id, matriz_id])

    def actualizar_sobrecostos(self, matriz_id,
                                indirectos_pct=0, financiamiento_pct=0,
                                utilidad_pct=0, cargo_adicional_pct=0):
        res = self.por_matriz(matriz_id)
        if not res:
            return
        cd = res["costo_directo"]
        pv = cd * (1 + (indirectos_pct + financiamiento_pct +
                        utilidad_pct + cargo_adicional_pct) / 100)
        self._ejecutar("""
            UPDATE apu_resumen_totales SET
                indirectos_pct = ?, financiamiento_pct = ?,
                utilidad_pct = ?, cargo_adicional_pct = ?,
                precio_venta = ?, modificado_en = datetime('now')
            WHERE matriz_id = ?
        """, [indirectos_pct, financiamiento_pct, utilidad_pct,
              cargo_adicional_pct, round(pv, 6), matriz_id])


# =============================================================================
# APU AUXILIARES (antes: apu_nodos)
# =============================================================================

# Migrado a v3: apu_matrices usa matriz_id unico en vez de dos columnas.


# =============================================================================
# FAMILIAS Y SUBFAMILIAS
# =============================================================================

class FamiliaRepo(RepoBase):

    def todas(self):
        return self._lista("SELECT * FROM familias WHERE activo = 1 ORDER BY nombre")

    def buscar(self, familia_id):
        return self._uno("SELECT * FROM familias WHERE id = ?", [familia_id])

    def insertar(self, nombre):
        return self._ejecutar(
            "INSERT INTO familias (nombre) VALUES (?)", [nombre])


class SubfamiliaRepo(RepoBase):

    def por_familia(self, familia_id):
        return self._lista("""
            SELECT * FROM subfamilias
            WHERE familia_id = ? AND activo = 1
            ORDER BY nombre
        """, [familia_id])

    def buscar(self, subfamilia_id):
        return self._uno("SELECT * FROM subfamilias WHERE id = ?", [subfamilia_id])

    def insertar(self, familia_id, nombre):
        return self._ejecutar(
            "INSERT INTO subfamilias (familia_id, nombre) VALUES (?, ?)",
            [familia_id, nombre])


# =============================================================================
# NOTAS
# =============================================================================

class NotaRepo(RepoBase):

    def por_nodo(self, concepto_id):
        return self._lista("""
            SELECT n.*, u.nombre AS autor
            FROM notas n
            JOIN usuarios u ON u.id = n.usuario_id
            WHERE n.concepto_id = ?
            ORDER BY n.creado_en DESC
        """, [concepto_id])

    def insertar(self, concepto_id, texto, usuario_id=1):
        return self._ejecutar("""
            INSERT INTO notas (concepto_id, usuario_id, texto) VALUES (?, ?, ?)
        """, [concepto_id, usuario_id, texto])

    def resolver(self, nota_id):
        self._ejecutar("""
            UPDATE notas SET resuelta = 1, modificado_en = datetime('now')
            WHERE id = ?
        """, [nota_id])

    def abiertas(self, proyecto_id):
        return self._lista("""
            SELECT n.*, u.nombre AS autor,
                   ep.wbs, ep.descripcion_corta
            FROM notas n
            JOIN usuarios u              ON u.id  = n.usuario_id
            JOIN estructura_presupuesto ep ON ep.id = n.concepto_id
            WHERE ep.proyecto_id = ? AND n.resuelta = 0
            ORDER BY n.creado_en DESC
        """, [proyecto_id])
