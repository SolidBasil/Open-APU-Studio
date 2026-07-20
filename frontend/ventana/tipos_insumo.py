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

# ── Iconos Lucide SVG (para UI con QIcon real, no emoji de texto) ────
# Misma asignación que frontend/ventana/widgets/arbol.py _ICONOS_TIPO_SVG —
# fuente única de verdad para quien necesite el nombre de icono por tipo.
ICONO_SVG = {
    1:   "building-2",   # Material
    2:   "hard-hat",     # Mano de obra
    4:   "wrench",       # Herramienta
    8:   "tractor",      # Equipo
    16:  "cog",          # Auxiliar
    32:  "file-text",    # Concepto
    64:  "truck",        # Flete
    128: "construction", # Trabajo
}

# ── Colores por tipo de insumo (fuente única) ──────────────────────
# Usado en sidebar, árboles, tablas, explosión, rastreo, diálogos.
COLOR = {
    1:   "#7FAFD6",  # Material    — azul
    2:   "#D5B39B",  # Mano de obra — café
    4:   "#5B8A72",  # Herramienta — verde
    8:   "#8B6FB5",  # Equipo      — púrpura
    16:  "#4E9298",  # Auxiliar    — teal
    32:  "#E8EDF2",  # Concepto    — blanco
    64:  "#5E92B8",  # Flete       — azul claro
    128: "#5A9A7A",  # Trabajo     — verde oscuro
}
