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
        """Inicializa el repositorio con una conexión SQLite."""
        self._conn   = conn
        self._cursor = conn.cursor()

    def _uno(self, sql, params=None):
        """Ejecuta una consulta y devuelve la primera fila como dict, o None."""
        row = self._cursor.execute(sql, params or []).fetchone()
        return dict(row) if row else None

    def _lista(self, sql, params=None):
        """Ejecuta una consulta y devuelve todas las filas como lista de dicts."""
        return [dict(r) for r in self._cursor.execute(sql, params or []).fetchall()]

    def _ejecutar(self, sql, params=None):
        """Ejecuta una sentencia INSERT/UPDATE/DELETE y hace commit."""
        self._cursor.execute(sql, params or [])
        self._conn.commit()
        return self._cursor.lastrowid

    def _muchos(self, sql, seq):
        """Ejecuta una inserción masiva con executemany y hace commit."""
        self._cursor.executemany(sql, seq)
        self._conn.commit()


# =============================================================================
# PROYECTO
# =============================================================================

class ProyectoRepo(RepoBase):

    def todos(self):
        """Devuelve todos los proyectos activos ordenados por fecha descendente."""
        return self._lista("""
            SELECT * FROM proyectos WHERE activo = 1 ORDER BY creado_en DESC
        """)

    def buscar(self, proyecto_id):
        """Busca un proyecto por su ID."""
        return self._uno("""
            SELECT * FROM proyectos WHERE id = ? AND activo = 1
        """, [proyecto_id])

    def config(self, proyecto_id):
        """Devuelve la configuración de un proyecto."""
        return self._uno("""
            SELECT * FROM configuracion_proyecto WHERE proyecto_id = ?
        """, [proyecto_id])

    def actualizar_total(self, proyecto_id):
        """Recalcula y actualiza el total_obra del proyecto desde sus raíces."""
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
        """Devuelve los sobrecostos de un proyecto ordenados por orden."""
        return self._lista("""
            SELECT * FROM sobrecostos
            WHERE proyecto_id = ?
            ORDER BY orden
        """, [proyecto_id])

    def insertar(self, datos):
        """Inserta un nuevo sobrecosto en el proyecto."""
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
        """Elimina todos los sobrecostos de un proyecto."""
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
        """Devuelve todos los nodos activos del presupuesto ordenados por wbs."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])

    def hijos(self, padre_id):
        """Devuelve los hijos directos de un nodo."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE padre_id = ? AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    def raices(self, proyecto_id):
        """Devuelve los nodos raíz (capítulos) de un proyecto."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
            ORDER BY wbs
        """, [proyecto_id])

    def buscar(self, concepto_id):
        """Busca un nodo por su ID."""
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE id = ? AND activo = 1
        """, [concepto_id])

    def buscar_por_clave(self, clave, proyecto_id):
        """Busca un nodo por su clave dentro de un proyecto."""
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE clave = ? AND proyecto_id = ? AND activo = 1
        """, [clave, proyecto_id])

    def descendientes(self, concepto_id):
        """Devuelve todos los descendientes de un nodo mediante CTE recursiva."""
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
        """Devuelve la ruta desde un nodo hasta la raíz mediante CTE recursiva."""
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
        """Devuelve los nodos con un estado específico (semáforo)."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE proyecto_id = ? AND estado = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id, estado])

    def conceptos_sin_apu(self, proyecto_id):
        """Devuelve los conceptos que no tienen APU asociado."""
        return self._lista("""
            SELECT ep.* FROM estructura_presupuesto ep
            LEFT JOIN apu_matrices ac ON ac.matriz_id = ep.id
            WHERE ep.proyecto_id = ? AND ep.tipo = 'concepto'
              AND ep.activo = 1 AND ac.id IS NULL
            ORDER BY ep.wbs
        """, [proyecto_id])

    def actualizar_cantidad(self, concepto_id, cantidad, usuario_id=1):
        """Actualiza la cantidad de un concepto y recalcula subtotales."""
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                cantidad = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [cantidad, usuario_id, concepto_id])
        self.actualizar_subtotal(concepto_id)

    def actualizar_precio(self, concepto_id, precio, usuario_id=1):
        """Actualiza el precio unitario de un concepto y recalcula subtotales."""
        self._ejecutar("""
            UPDATE estructura_presupuesto SET
                precio_unitario = ?, modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [precio, usuario_id, concepto_id])
        self.actualizar_subtotal(concepto_id)

    def actualizar_estado(self, concepto_id, estado: int, usuario_id=1):
        """Actualiza el estado (semáforo) de un nodo."""
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
        """Marca un nodo y sus descendientes como inactivos (borrado lógico)."""
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
        """Devuelve los conceptos hijos directos de un capítulo."""
        return self._lista("""
            SELECT * FROM estructura_presupuesto
            WHERE padre_id = ? AND tipo = 'concepto' AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    def buscar_por_clave(self, clave, proyecto_id):
        """Busca un concepto por su clave dentro de un proyecto."""
        return self._uno("""
            SELECT * FROM estructura_presupuesto
            WHERE clave = ? AND proyecto_id = ?
              AND tipo = 'concepto' AND activo = 1
        """, [clave, proyecto_id])

    def todos(self, proyecto_id):
        """Devuelve todos los conceptos de un proyecto."""
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
    JOIN con tipos_insumo (tipo_clave, tipo_nombre), familias
    (familia_nombre) y subfamilias (subfamilia_nombre).
    """

    def todos(self, proyecto_id):
        """Devuelve todos los insumos activos de un proyecto con sus joins."""
        return self._lista("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
                   f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN familias f ON f.id = i.familia_id
            LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
            WHERE i.proyecto_id = ? AND i.activo = 1
            ORDER BY t.orden, i.clave
        """, [proyecto_id])

    def por_tipo(self, proyecto_id, tipo_clave):
        """Devuelve los insumos de un tipo específico (clave textual)."""
        return self._lista("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
                   f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN familias f ON f.id = i.familia_id
            LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
            WHERE i.proyecto_id = ? AND t.clave = ? AND i.activo = 1
            ORDER BY i.clave
        """, [proyecto_id, tipo_clave])

    def buscar(self, insumo_id):
        """Busca un insumo por su ID."""
        return self._uno("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
                   f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN familias f ON f.id = i.familia_id
            LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
            WHERE i.id = ? AND i.activo = 1
        """, [insumo_id])

    def buscar_por_clave(self, clave, proyecto_id):
        """Busca un insumo por su clave dentro de un proyecto."""
        return self._uno("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
                   f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN familias f ON f.id = i.familia_id
            LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
            WHERE i.clave = ? AND i.proyecto_id = ? AND i.activo = 1
        """, [clave, proyecto_id])

    def buscar_texto(self, proyecto_id, texto):
        """Busca insumos por texto en clave, descripción o descripción corta."""
        q = f"%{texto}%"
        return self._lista("""
            SELECT i.*, t.clave AS tipo_clave, t.nombre AS tipo_nombre,
                   f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            LEFT JOIN familias f ON f.id = i.familia_id
            LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
            WHERE i.proyecto_id = ? AND i.activo = 1
              AND (i.clave LIKE ? OR i.descripcion LIKE ? OR i.descripcion_corta LIKE ?)
            ORDER BY t.orden, i.clave
        """, [proyecto_id, q, q, q])

    def resumen_por_tipo(self, proyecto_id):
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
            SELECT COUNT(ac.id) AS apariciones, SUM(ac.cantidad * ac.precio) AS importe_total
            FROM apu_matrices ac
            WHERE ac.insumo_id = ?
        """, [insumo_id])

    def donde_se_usa(self, insumo_id):
        """Devuelve los APU (concepto/compuesto) donde aparece un insumo."""
        return self._lista("""
            SELECT
                am.matriz_id,
                am.cantidad,
                am.precio,
                am.cantidad * am.precio                           AS importe,
                CASE WHEN am.matriz_id > 0
                     THEN 'concepto' ELSE 'compuesto' END         AS tipo_origen,
                COALESCE(ep.clave,  ic.clave)                     AS matriz_clave,
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
        """Actualiza el costo_mn y costo_final de un insumo."""
        self._ejecutar("""
            UPDATE insumos SET
                costo_mn = ?, costo_final = ?,
                modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [precio, precio, usuario_id, insumo_id])

    def tipos_disponibles(self):
        """Devuelve todos los tipos de insumo ordenados."""
        return self._lista("SELECT * FROM tipos_insumo ORDER BY orden")


# =============================================================================
# APU COMPONENTES (antes: apu_detalle)
# =============================================================================

class ApuMatricesRepo(RepoBase):
    """Componentes del APU: desglose de insumos por concepto o insumo compuesto.
    matriz_id unificado: positivo para nodos del árbol, negativo para insumos compuestos.
    """

    def por_matriz(self, matriz_id):
        """Devuelve los componentes del APU de una matriz (concepto o compuesto)."""
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
        """Inserta un componente en la matriz APU."""
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
        """Recalcula el resumen de costos de un APU desde apu_matrices."""
        self._ejecutar("""
            INSERT OR REPLACE INTO apu_resumen_totales
                (matriz_id, materiales, mano_obra, herramienta, equipo,
                 auxiliares, subcontratos, fletes, trabajos, costo_directo,
                 modificado_en)
            SELECT
                ac.matriz_id,
                COALESCE(SUM(CASE WHEN t.clave='material'    THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='mano_obra'   THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='herramienta' THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='equipo'      THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='auxiliar'    THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='concepto'    THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='flete'       THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(CASE WHEN t.clave='trabajo'     THEN ac.cantidad*ac.precio ELSE 0 END),0),
                COALESCE(SUM(ac.cantidad * ac.precio), 0),
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
        """Actualiza los porcentajes de sobrecostos y el precio de venta de un APU."""
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
        """Devuelve todas las familias activas ordenadas por nombre."""
        return self._lista("SELECT * FROM familias WHERE activo = 1 ORDER BY nombre")

    def buscar(self, familia_id):
        """Busca una familia por su ID."""
        return self._uno("SELECT * FROM familias WHERE id = ?", [familia_id])

    def insertar(self, nombre):
        """Inserta una nueva familia."""
        return self._ejecutar(
            "INSERT INTO familias (nombre) VALUES (?)", [nombre])


class SubfamiliaRepo(RepoBase):

    def por_familia(self, familia_id):
        """Devuelve las subfamilias activas de una familia."""
        return self._lista("""
            SELECT * FROM subfamilias
            WHERE familia_id = ? AND activo = 1
            ORDER BY nombre
        """, [familia_id])

    def buscar(self, subfamilia_id):
        """Busca una subfamilia por su ID."""
        return self._uno("SELECT * FROM subfamilias WHERE id = ?", [subfamilia_id])

    def insertar(self, familia_id, nombre):
        """Inserta una nueva subfamilia dentro de una familia."""
        return self._ejecutar(
            "INSERT INTO subfamilias (familia_id, nombre) VALUES (?, ?)",
            [familia_id, nombre])


# =============================================================================
# NOTAS
# =============================================================================

class NotaRepo(RepoBase):

    def por_nodo(self, concepto_id):
        """Devuelve las notas de un nodo ordenadas por fecha descendente."""
        return self._lista("""
            SELECT n.*, u.nombre AS autor
            FROM notas n
            JOIN usuarios u ON u.id = n.usuario_id
            WHERE n.concepto_id = ?
            ORDER BY n.creado_en DESC
        """, [concepto_id])

    def insertar(self, concepto_id, texto, usuario_id=1):
        """Inserta una nota en un nodo."""
        return self._ejecutar("""
            INSERT INTO notas (concepto_id, usuario_id, texto) VALUES (?, ?, ?)
        """, [concepto_id, usuario_id, texto])

    def resolver(self, nota_id):
        """Marca una nota como resuelta."""
        self._ejecutar("""
            UPDATE notas SET resuelta = 1, modificado_en = datetime('now')
            WHERE id = ?
        """, [nota_id])

    def abiertas(self, proyecto_id):
        """Devuelve las notas no resueltas de un proyecto."""
        return self._lista("""
            SELECT n.*, u.nombre AS autor,
                   ep.wbs, ep.descripcion_corta
            FROM notas n
            JOIN usuarios u              ON u.id  = n.usuario_id
            JOIN estructura_presupuesto ep ON ep.id = n.concepto_id
            WHERE ep.proyecto_id = ? AND n.resuelta = 0
            ORDER BY n.creado_en DESC
        """, [proyecto_id])


# =============================================================================
# EXPLOSIÓN DE INSUMOS
# =============================================================================

class ExplosionRepo(RepoBase):
    """Calcula la explosión de insumos para un conjunto de conceptos.

    Niveles:
        'basico'       — bottom-up: desde cada insumo hoja rastrea todas las
                          rutas hacia arriba hasta el presupuesto. Cada rama es
                          independiente, no omite duplicados.
        'compuesto'    — solo insumos compuestos del APU directo
        'primer_nivel' — todos los insumos del APU directo (sin bajar)

    Herramienta: usa am.importe (% × subtotal_MO del APU), no cantidad × costo_final.
    """

    TIPO_ID_HERRAMIENTA = 4
    TIPO_ID_MO          = 2

    # ── Helpers internos ─────────────────────────────────────────────────

    def _postprocesar(self, filas: list[dict], tipos_set: set) -> tuple[list[dict], float]:
        """Filtra por tipos, calcula pct_mo para herramienta, % global y ordena."""
        filas = [f for f in filas if f.get("tipo_id") in tipos_set]

        total_global = sum(f.get("total") or 0 for f in filas)
        total_mo     = sum(f["total"] for f in filas if f["tipo_id"] == self.TIPO_ID_MO)

        for f in filas:
            f["pct"] = (f["total"] / total_global * 100) if total_global else 0
            if f["tipo_id"] == self.TIPO_ID_HERRAMIENTA:
                f.setdefault("pct_mo", f["total"] / total_mo if total_mo else None)
            else:
                f.setdefault("pct_mo", None)

        filas.sort(key=lambda f: (f.get("tipo_orden") or 99, -(f.get("total") or 0)))
        return filas, total_global

    # ── Niveles básico / compuesto: bottom-up (cada ruta insumo→presupuesto es independiente) ──

    def _calcular_basico_bottom_up(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        tipos_ids: list[int],
        ph_conceptos: str,
        decimales: int | None = None,
        solo_compuestos: bool = False,
    ) -> tuple[list[dict], float]:
        """
        Bottom-up: para cada insumo, rastrea hacia arriba todas las rutas
        hasta llegar a un concepto del presupuesto. Cada rama es independiente
        — no se omiten duplicados aunque el mismo compuesto aparezca varias veces.

        solo_compuestos=False → insumos hoja (es_compuesto=0)
        solo_compuestos=True  → insumos compuestos (es_compuesto=1)
        """
        tipos_set = set(tipos_ids)

        def rd(v):
            return round(v, decimales) if decimales is not None else v

        # ── 1. Budget concepts ──
        rows = self._lista(f"""
            SELECT id, cantidad FROM estructura_presupuesto
            WHERE id IN ({ph_conceptos}) AND tipo='concepto' AND activo=1
        """, concepto_ids)
        budget_cant = {r["id"]: r["cantidad"] for r in rows if r["cantidad"]}

        # ── 2. All insumos del proyecto ──
        insumos = self._lista(f"""
            SELECT i.id, i.clave,
                   COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                   i.unidad, i.costo_final, i.es_compuesto, i.tipo_id,
                   ti.nombre AS tipo_nombre, ti.orden AS tipo_orden
            FROM insumos i
            JOIN tipos_insumo ti ON ti.id = i.tipo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
        """, [proyecto_id])
        insumos_map = {r["id"]: r for r in insumos}
        clave_a_insumo: dict[str, int] = {r["clave"]: r["id"] for r in insumos if r["clave"]}

        # ── 2b. All conceptos -> insumo_id mapping (for intermedios) ──
        conceptos = self._lista(f"""
            SELECT id, clave FROM estructura_presupuesto
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
        """, [proyecto_id])
        concepto_a_insumo: dict[int, int] = {}
        for r in conceptos:
            ins_id = clave_a_insumo.get(r["clave"])
            if ins_id is not None:
                concepto_a_insumo[r["id"]] = ins_id

        # ── 3. All APU matrices (reverse index) ──
        matrices = self._lista(f"""
            SELECT am.matriz_id, am.insumo_id, am.cantidad, am.precio
            FROM apu_matrices am
            JOIN insumos i ON i.id = am.insumo_id
            WHERE i.proyecto_id = ? AND i.activo = 1
        """, [proyecto_id])

        # Reverse: insumo_id -> [padres]
        reverse: dict[int, list[dict]] = {}
        for row in matrices:
            iid = row["insumo_id"]
            reverse.setdefault(iid, []).append(row)

        # ── 4. Caché de multiplicadores bottom-up ──
        #   _mult_cache[matriz_id] = cantidad_total_acumulada_hasta_presupuesto
        #   Para conceptos en budget_cant: devuelve cantidad del presupuesto
        #   Para conceptos intermedios: rastrea su insumo en el índice reverso
        #   Para compuestos (mid<0): suma de (cantidad × multiplicador del padre)
        _mult_cache: dict[int, float] = {}
        _visitando: set = set()

        def _calc_mult(matriz_id: int) -> float:
            """Multiplicador desde matriz_id hasta el presupuesto (suma de todas las rutas)."""
            if matriz_id in _visitando:
                return 0.0  # ciclo
            if matriz_id in _mult_cache:
                return _mult_cache[matriz_id]
            if matriz_id > 0:
                if matriz_id in budget_cant:
                    return budget_cant[matriz_id]
                # Concepto intermedio (usado como componente de otro APU)
                ins_id = concepto_a_insumo.get(matriz_id)
                if ins_id is None:
                    return 0.0
                _visitando.add(matriz_id)
                total = 0.0
                for p in reverse.get(ins_id, []):
                    total += (p["cantidad"] or 0) * _calc_mult(p["matriz_id"])
                _visitando.discard(matriz_id)
                _mult_cache[matriz_id] = total
                return total

            _visitando.add(matriz_id)
            total = 0.0
            for p in reverse.get(-matriz_id, []):
                total += (p["cantidad"] or 0) * _calc_mult(p["matriz_id"])
            _visitando.discard(matriz_id)
            _mult_cache[matriz_id] = total
            return total

        # ── 5. Procesar cada insumo ──
        acumulado: dict[int, dict] = {}

        for insumo_id, info in insumos_map.items():
            if info["tipo_id"] not in tipos_set:
                continue
            if solo_compuestos:
                if not info["es_compuesto"]:
                    continue
            else:
                if info["es_compuesto"]:
                    continue
            is_herr = (info["tipo_id"] == self.TIPO_ID_HERRAMIENTA)
            parents = reverse.get(insumo_id, [])
            if not parents:
                continue

            qty_total = 0.0
            herr_importe = 0.0

            for p in parents:
                mult = _calc_mult(p["matriz_id"])
                if mult == 0.0:
                    continue
                if is_herr:
                    herr_importe += rd((p["cantidad"] or 0) * (p["precio"] or 0) * mult)
                else:
                    qty_total += rd((p["cantidad"] or 0) * mult)

            pu = info.get("costo_final") or 0
            if is_herr:
                if herr_importe:
                    acumulado[insumo_id] = {
                        "tipo_id":        info["tipo_id"],
                        "tipo_nombre":    info["tipo_nombre"],
                        "tipo_orden":     info["tipo_orden"],
                        "clave":          info["clave"],
                        "descripcion":    info["descripcion"] or "",
                        "unidad":         info["unidad"] or "",
                        "pu":             None,
                        "cantidad_total": 0.0,
                        "total":          0.0,
                        "importe_herr":   herr_importe,
                    }
            else:
                if qty_total:
                    acumulado[insumo_id] = {
                        "tipo_id":        info["tipo_id"],
                        "tipo_nombre":    info["tipo_nombre"],
                        "tipo_orden":     info["tipo_orden"],
                        "clave":          info["clave"],
                        "descripcion":    info["descripcion"] or "",
                        "unidad":         info["unidad"] or "",
                        "pu":             pu,
                        "cantidad_total": qty_total,
                        "total":          rd(qty_total * pu),
                        "importe_herr":   0.0,
                    }

        # ── 6. Convertir a lista ──
        filas = []
        for entry in acumulado.values():
            es_herr = (entry["tipo_id"] == self.TIPO_ID_HERRAMIENTA)
            filas.append({**entry, "total": entry["importe_herr"] if es_herr else entry["total"]})

        return self._postprocesar(filas, tipos_set)

    # ── Niveles primer_nivel / compuesto: vía SQL ─────────────────────────

    def _calcular_sql(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        tipos_ids: list[int],
        ph_conceptos: str,
        filtro_nivel: str,
    ) -> tuple[list[dict], float]:
        """Niveles 'primer_nivel' o 'compuesto': resuelve por SQL agregado."""
        tipos_set      = set(tipos_ids)
        tipos_normales = [t for t in tipos_ids if t != self.TIPO_ID_HERRAMIENTA]
        filas_normales = []

        if tipos_normales:
            ph_tipos = ",".join("?" * len(tipos_normales))
            sql = f"""
                SELECT
                    i.tipo_id,
                    ti.nombre           AS tipo_nombre,
                    ti.orden            AS tipo_orden,
                    i.clave,
                    COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                    i.unidad,
                    i.costo_final       AS pu,
                    SUM(am.cantidad * ep.cantidad) AS cantidad_total,
                    SUM(am.cantidad * ep.cantidad) * i.costo_final AS total
                FROM estructura_presupuesto ep
                JOIN apu_matrices am ON am.matriz_id = ep.id
                JOIN insumos i       ON i.id = am.insumo_id
                JOIN tipos_insumo ti ON ti.id = i.tipo_id
                WHERE ep.id         IN ({ph_conceptos})
                  AND ep.tipo        = 'concepto'
                  AND ep.activo      = 1
                  AND ep.proyecto_id = ?
                  AND i.proyecto_id  = ?
                  AND i.tipo_id      IN ({ph_tipos})
                  AND i.activo       = 1
                  {filtro_nivel}
                GROUP BY i.id
            """
            filas_normales = self._lista(sql, concepto_ids + [proyecto_id, proyecto_id] + tipos_normales)

        filas_herr = []
        if self.TIPO_ID_HERRAMIENTA in tipos_ids:
            sql_h = f"""
                SELECT
                    i.tipo_id,
                    ti.nombre           AS tipo_nombre,
                    ti.orden            AS tipo_orden,
                    i.clave,
                    COALESCE(i.descripcion, i.descripcion_corta, '') AS descripcion,
                    i.unidad,
                    SUM(am.cantidad * am.precio * ep.cantidad) AS total,
                    SUM(am.cantidad * am.precio * ep.cantidad) /
                    NULLIF(SUM(am.precio * ep.cantidad), 0) AS pct_mo
                FROM estructura_presupuesto ep
                JOIN apu_matrices am ON am.matriz_id = ep.id
                JOIN insumos i       ON i.id = am.insumo_id
                JOIN tipos_insumo ti ON ti.id = i.tipo_id
                WHERE ep.id         IN ({ph_conceptos})
                  AND ep.tipo        = 'concepto'
                  AND ep.activo      = 1
                  AND ep.proyecto_id = ?
                  AND i.proyecto_id  = ?
                  AND i.tipo_id      = {self.TIPO_ID_HERRAMIENTA}
                  AND i.activo       = 1
                  {filtro_nivel}
                GROUP BY i.id
            """
            params_h = [proyecto_id, proyecto_id]
            filas_herr = self._lista(sql_h, concepto_ids + params_h)

        return self._postprocesar(filas_normales + filas_herr, tipos_set)

    # ── API pública ───────────────────────────────────────────────────────

    def calcular(
        self,
        proyecto_id: int,
        concepto_ids: list[int],
        nivel: str,
        tipos_ids: list[int],
        decimales: int | None = None,
    ) -> tuple[list[dict], float]:
        """
        Devuelve (filas, total_global).
        filas — lista de dicts con tipo_id, tipo_nombre, tipo_orden, clave,
                descripcion, unidad, pu, cantidad_total, total, pct, pct_mo.
        Ordenada por tipo_orden asc, total desc dentro de cada tipo.

        nivel     — 'basico' | 'compuesto' | 'primer_nivel'
        decimales — None = precisión flotante completa
                    2    = redondea como OPUS (para comparación)
        """
        if not concepto_ids or not tipos_ids:
            return [], 0.0

        ph = ",".join("?" * len(concepto_ids))

        if nivel == "compuesto":
            return self._calcular_basico_bottom_up(proyecto_id, concepto_ids, tipos_ids, ph, decimales,
                                                   solo_compuestos=True)
        elif nivel == "basico":
            return self._calcular_basico_bottom_up(proyecto_id, concepto_ids, tipos_ids, ph, decimales)
        else:  # primer_nivel
            return self._calcular_sql(proyecto_id, concepto_ids, tipos_ids, ph, "")
