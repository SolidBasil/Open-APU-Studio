"""
tipos_insumo.py
==============
Datos maestros de tipos de insumo — una sola fuente de verdad.

Antes: 6 copias inconsistentes dispersas en api.py, arbol.py,
dialogs.py, explosion.py, insumos.py, exportar_plantillas.py.
Ahora: este módulo define los datos canónicos, el resto importa.

Actualizado: 2026-07-11 (hora local)
"""

# ── Datos canónicos ──────────────────────────────────────────────
# (emoji, nombre_singular, nombre_plural, clave_opus, descripcion)

TIPOS = {
    1:   ("🧱", "Material",    "Materiales",     "material",    "Materiales y artículos fundamentales del proyecto."),
    2:   ("👷", "Mano de obra", "Mano de obra",   "mano_obra",   "Mano de obra directa e indirecta."),
    4:   ("🔧", "Herramienta", "Herramienta",    "herramienta", "Herramienta menor y especializada."),
    8:   ("🚜", "Equipo",      "Equipo",         "equipo",      "Maquinaria y equipo de construcción."),
    16:  ("⚙️", "Auxiliar",   "Auxiliares",     "auxiliar",    "Insumos auxiliares de apoyo."),
    32:  ("📄", "Concepto",   "Conceptos",      "concepto",    "Conceptos generales y administrativos."),
    64:  ("🚛", "Flete",      "Fletes",         "flete",       "Transporte y fletes de materiales."),
    128: ("🏗️", "Trabajo",   "Trabajos",       "trabajo",     "Trabajos y subcontratos."),
}

# ── Vistas derivadas (generadas, no editadas a mano) ─────────────

ICONO = {tid: v[0] for tid, v in TIPOS.items()}
NOMBRE = {tid: v[1] for tid, v in TIPOS.items()}
NOMBRES = {tid: v[2] for tid, v in TIPOS.items()}
CLAVE = {tid: v[3] for tid, v in TIPOS.items()}
DESC = {tid: v[4] for tid, v in TIPOS.items()}

# Formato tuple-list para filtros y tablas: [(id, emoji, nombre)]
FILTROS = [(tid, v[0], v[2]) for tid, v in TIPOS.items()]

# Formato tuple-list para OPUS export: [(id, nombre_plural)]
OPUS_ROWS = [{"PREFIJO": tid, "STRTIPO": v[2]} for tid, v in TIPOS.items()]

# Formato tuple-list para tabs/filtros: [(id, nombre_plural, clave)]
TIPOS_INSUMO = [(tid, v[2], v[3]) for tid, v in TIPOS.items()]

# Formato emoji+nombre para celdas de tabla: {id: "emoji nombre"}
ICONO_NOMBRE = {tid: f"{v[0]} {v[1]}" for tid, v in TIPOS.items()}
