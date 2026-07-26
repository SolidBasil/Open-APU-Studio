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
TEXT_INVERSO = "#1A1F24"   # texto sobre fondo claro (modo claro, tint por defecto)
MUTED = "#6B7884"          # texto/ícono atenuado (subtítulos, tint por defecto de íconos)
SEL_BG = "#2A4158"         # fondo de selección / hover
LINE = "#5E92B8"           # líneas de conexión
PURPURA = "#8B6FB5"        # 4ta categoría decorativa (Equipo, Matrices, capítulo raíz)

# ── Estados ──────────────────────────────────────────────────────
SUCCESS = "#5B8A72"        # verificado / correcto
WARNING = "#D5B39B"        # advertencia / cuestionado
ERROR = "#A06A6A"          # error / vino
