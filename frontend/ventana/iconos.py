"""
iconos.py
=========
Registry central de iconos SVG (Lucide).

Carga iconos desde assets/icons/ y los cachea como QIcon.
Totalmente cross-platform — no depende de fuentes del sistema.

Actualizado: 2026-07-19 (hora local)
"""

from __future__ import annotations

import os
from functools import lru_cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# ── Ruta base de los SVGs ────────────────────────────────────────
_ICONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "assets", "icons",
)

# ── Fallback: placeholder si no encuentra el SVG ─────────────────
_PLACEHOLDER = "○"

# Color por defecto para los iconos (texto claro sobre fondo oscuro)
_DEFAULT_COLOR = "#E8EDF2"


@lru_cache(maxsize=256)
def icono(nombre: str, size: int = 20, color: str | None = None) -> QIcon:
    """Retorna QIcon desde assets/icons/{nombre}.svg.

    Args:
        nombre: Nombre del archivo SVG sin extensión (ej. "folder-open").
        size: Tamaño en píxeles del icono.
        color: Color hex para recolorear el SVG (ej. "#E8EDF2").
               Si es None, usa el color blanco/claro por defecto.
    """
    tint = color or _DEFAULT_COLOR
    path = os.path.join(_ICONS_DIR, f"{nombre}.svg")
    if not os.path.isfile(path):
        return _fallback_icon(size, tint)

    return _tinted_icon(path, size, tint)


def _tinted_icon(path: str, size: int, color: str) -> QIcon:
    """Carga SVG y lo recolorea con el color dado."""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return _fallback_icon(size, color)

    # Paso 1: renderizar SVG (trazos negros sobre fondo transparente)
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter)
    painter.end()

    # Paso 2: crear pixmap del color sólido
    fill = QPixmap(size, size)
    fill.fill(QColor(color))

    # Paso 3: usar alfa del SVG como máscara sobre el color
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.drawPixmap(0, 0, fill)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawPixmap(0, 0, pix)
    p.end()

    return QIcon(result)


def _fallback_icon(size: int, color: str | None = None) -> QIcon:
    """Icono placeholder cuando no se encuentra el SVG."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setPen(QColor(color or "#6B7884"))
    p.setFont(QFont("sans-serif", max(size // 2, 8)))
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, _PLACEHOLDER)
    p.end()
    return QIcon(pix)
