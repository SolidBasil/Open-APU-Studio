"""
core.py
=======
Lógica de negocio pura para Open APU Studio.
No sabe nada de presentación (sin HTML, sin PyQt, sin Flask).

Expone funciones que leen el SQLite generado por el importador
y devuelven estructuras Python puras (listas de dicts anidados).

Uso:
    from backend.core import build_budget_tree, count_nodes, count_concepts

    tree = build_budget_tree("proyecto.db")
    print(count_nodes(tree))     # 172
    print(count_concepts(tree))  # 148
"""

import sqlite3


# =============================================================================
# ÁRBOL DEL PRESUPUESTO
# =============================================================================

# ── construir árbol jerárquico del presupuesto ──
def build_budget_tree(db_path: str, proyecto_id: int = 1) -> list[dict]:
    """
    Lee el árbol de presupuesto desde el SQLite y lo devuelve como lista
    de nodos raíz con sus hijos anidados en el campo 'hijos'.

    El árbol ya viene con padre_id correctamente resuelto desde la
    importación (algoritmo WBS) — no se necesita reconstrucción adicional.

    Estructura de cada nodo:
        {
            "id":               int,
            "padre_id":         int | None,
            "wbs":              str,        # "1", "11", "111", "11101"
            "nivel":            int,        # 0=raíz, 1=capítulo...
            "tipo":             str,        # "capitulo" | "concepto"
            "clave":            str | None, # código OPUS, solo en conceptos
            "descripcion":      str,
            "descripcion_corta": str | None,
            "unidad":           str | None,
            "cantidad":         float | None,
            "precio_unitario":  float | None,
            "importe":          float | None,  # columna GENERATED: cant × pu
            "subtotal":         float,          # acumulado de hijos
            "notas_rapidas":    str | None,
            "modificado_en":    str | None,
            "creado_en":        str | None,
            "estado_nombre":    str,            # "Verificado", etc.
            "estado_color":     str,            # "#4CAF7D"
            "hijos":            list[dict],     # recursivo
        }

    Args:
        db_path:     Ruta al archivo .db generado por importador_opus.py
        proyecto_id: ID del proyecto a cargar (default=1)

    Returns:
        Lista de nodos raíz. Cada nodo tiene 'hijos' con sus descendientes.
        Lista vacía si no hay nodos o el proyecto no existe.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    try:
        cur = con.cursor()
        cur.execute("""
            SELECT
                n.id,
                n.padre_id,
                n.wbs,
                n.nivel,
                n.tipo,
                n.clave,
                n.descripcion,
                n.descripcion_corta,
                n.unidad,
                n.cantidad,
                n.precio_unitario,
                n.importe,
                n.subtotal,
                n.notas_rapidas,
                n.modificado_en,
                n.creado_en,
                e.nombre  AS estado_nombre,
                e.color   AS estado_color,
                e.clave   AS estado_clave
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.proyecto_id = ? AND n.activo = 1
            ORDER BY n.wbs
        """, (proyecto_id,))

        filas = [dict(r) for r in cur.fetchall()]
    finally:
        con.close()

    if not filas:
        return []

    # Construir árbol en memoria
    # ORDER BY wbs garantiza que los padres siempre se procesan antes que sus hijos
    by_id  = {f["id"]: f for f in filas}
    raices = []

    for f in filas:
        f["hijos"] = []
        pid = f["padre_id"]
        if pid and pid in by_id:
            by_id[pid]["hijos"].append(f)
        else:
            raices.append(f)

    return raices


# ── obtener metadatos del proyecto ──
def get_proyecto(db_path: str, proyecto_id: int = 1) -> dict | None:
    """
    Devuelve los metadatos del proyecto (nombre, total, config).

    Returns:
        Dict con campos de 'proyectos' + 'proyecto_config', o None si no existe.
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("""
            SELECT p.*, pc.horas_dia, pc.tasa_seguro, pc.tasa_interes,
                   pc.decimales_costo, pc.decimales_cantidad
            FROM proyectos p
            LEFT JOIN proyecto_config pc ON pc.proyecto_id = p.id
            WHERE p.id = ? AND p.activo = 1
        """, (proyecto_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        con.close()


# ── obtener APU completo de un concepto ──
def get_apu(db_path: str, nodo_id: int) -> dict:
    """
    Devuelve el APU completo de un concepto.

    Returns:
        {
            "detalle":  list[dict],   # componentes con insumo completo
            "totales":  dict | None,  # subtotales por tipo
        }
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()

        cur.execute("""
            SELECT
                ad.id,
                ad.orden,
                ad.rendimiento,
                ad.cantidad,
                ad.precio,
                ad.importe,
                ad.formula,
                i.es_compuesto      AS insumo_es_compuesto,
                i.clave             AS insumo_clave,
                i.descripcion       AS insumo_descripcion,
                i.descripcion_corta AS insumo_desc_corta,
                i.unidad            AS insumo_unidad,
                t.clave             AS tipo_clave,
                t.nombre            AS tipo_nombre,
                t.id                AS tipo_id
            FROM apu_detalle ad
            JOIN insumos i      ON i.id  = ad.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE (ad.nodo_id = ? OR ad.apu_nodo_id = ?)
            ORDER BY ad.orden
        """, (nodo_id, nodo_id))
        detalle = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT * FROM apu_totales WHERE (nodo_id = ? OR apu_nodo_id = ?)
        """, (nodo_id, nodo_id))
        row = cur.fetchone()
        totales = dict(row) if row else None

        return {"detalle": detalle, "totales": totales}
    finally:
        con.close()


# =============================================================================
# MÉTRICAS DEL ÁRBOL
# =============================================================================

# ── contar todos los nodos del árbol ──
def count_nodes(nodes: list[dict]) -> int:
    """Cuenta todos los nodos del árbol (recursivo)."""
    total = len(nodes)
    for n in nodes:
        total += count_nodes(n.get("hijos", []))
    return total


# ── contar solo nodos tipo concepto ──
def count_concepts(nodes: list[dict]) -> int:
    """Cuenta solo los nodos de tipo 'concepto' (recursivo)."""
    total = sum(1 for n in nodes if n["tipo"] == "concepto")
    for n in nodes:
        total += count_concepts(n.get("hijos", []))
    return total


# ── suma de subtotales de nodos raíz ──
def total_obra(nodes: list[dict]) -> float:
    """Suma los subtotales de los nodos raíz."""
    return sum(n.get("subtotal") or n.get("importe") or 0 for n in nodes)


# ── aplanar árbol a lista secuencial ──
def flatten(nodes: list[dict]) -> list[dict]:
    """
    Aplana el árbol en una lista ordenada por WBS.
    Útil para exportar a Excel o para vistas tabulares.
    Cada nodo conserva su campo 'hijos' pero no está anidado.
    """
    resultado = []
    for n in nodes:
        resultado.append(n)
        resultado.extend(flatten(n.get("hijos", [])))
    return resultado


# =============================================================================
# VALIDACIÓN DE INTEGRIDAD
# =============================================================================

# ── validar integridad del proyecto ──
def validar(db_path: str, proyecto_id: int = 1) -> dict:
    """
    Corre checks de integridad sobre el proyecto y devuelve un reporte.
    Útil para detectar problemas después de la importación.

    Returns:
        {
            "total_nodos":          int,
            "total_conceptos":      int,
            "conceptos_sin_apu":    int,
            "subtotales_ok":        bool,   # subtotales == suma de hijos
            "advertencias":         list[str],
        }
    """
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    advertencias = []

    try:
        cur = con.cursor()

        # Conteos básicos
        cur.execute("""
            SELECT COUNT(*) FROM nodos
            WHERE proyecto_id = ? AND activo = 1
        """, (proyecto_id,))
        total_nodos = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM nodos
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
        """, (proyecto_id,))
        total_conceptos = cur.fetchone()[0]

        # Conceptos sin APU
        cur.execute("""
            SELECT COUNT(*) FROM nodos n
            LEFT JOIN apu_detalle ad ON ad.nodo_id = n.id
            WHERE n.proyecto_id = ? AND n.tipo = 'concepto'
              AND n.activo = 1 AND ad.id IS NULL
        """, (proyecto_id,))
        sin_apu = cur.fetchone()[0]
        if sin_apu:
            advertencias.append(f"{sin_apu} conceptos sin componentes APU")

        # Nodos huérfanos (padre_id apunta a un id que no existe)
        cur.execute("""
            SELECT COUNT(*) FROM nodos n
            WHERE n.proyecto_id = ? AND n.activo = 1
              AND n.padre_id IS NOT NULL
              AND n.padre_id NOT IN (
                  SELECT id FROM nodos WHERE activo = 1
              )
        """, (proyecto_id,))
        huerfanos = cur.fetchone()[0]
        if huerfanos:
            advertencias.append(f"{huerfanos} nodos con padre_id inválido")

        # Verificar subtotales (diff > $1 = posible desincronización)
        cur.execute("""
            SELECT COUNT(*) FROM nodos n
            WHERE n.proyecto_id = ? AND n.tipo = 'capitulo' AND n.activo = 1
              AND ABS(n.subtotal - (
                  SELECT COALESCE(SUM(
                      CASE WHEN tipo='concepto'
                           THEN COALESCE(importe, 0)
                           ELSE COALESCE(subtotal, 0)
                      END
                  ), 0)
                  FROM nodos WHERE padre_id = n.id AND activo = 1
              )) > 1.0
        """, (proyecto_id,))
        subtotales_mal = cur.fetchone()[0]
        subtotales_ok = subtotales_mal == 0
        if not subtotales_ok:
            advertencias.append(
                f"{subtotales_mal} capítulos con subtotales desincronizados"
            )

        return {
            "total_nodos":       total_nodos,
            "total_conceptos":   total_conceptos,
            "conceptos_sin_apu": sin_apu,
            "subtotales_ok":     subtotales_ok,
            "advertencias":      advertencias,
        }

    finally:
        con.close()
