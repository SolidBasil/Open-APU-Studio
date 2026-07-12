"""
colores.py
==========
Constantes de color del tema oscuro — una sola fuente de verdad.

Antes: hex hardcodeados en 5+ archivos.
Ahora: este módulo define los colores semánticos, el resto importa.

Actualizado: 2026-07-11 (hora local)
"""

# ── Semánticos ───────────────────────────────────────────────────
ACCENT = "#7FAFD6"        # acento azul (toolbar, selección, tabs)
TEXT = "#E8EDF2"           # texto principal
TEXT_SEC = "#B7C0C8"       # texto secundario
SEL_BG = "#2A4158"         # fondo de selección / hover
LINE = "#5E92B8"           # líneas de conexión

# ── Estados ──────────────────────────────────────────────────────
SUCCESS = "#5B8A72"        # verificado / correcto
WARNING = "#D5B39B"        # advertencia / cuestionado
ERROR = "#A06A6A"          # error / vino
