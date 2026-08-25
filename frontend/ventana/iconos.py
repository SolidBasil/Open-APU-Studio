"""
iconos.py
=========
Registry central de iconos SVG.

Soporta dos conjuntos:
  - Lucide (assets/icons/) — monochrome, recolorable via tint
  - Icons8 Color (assets/icons8/) — flat color, sin tint

El conjunto activo se configura con set_iconos().
Totalmente cross-platform — no depende de fuentes del sistema,
ni siquiera el placeholder de fallback (círculo vectorial).

Actualizado: 2026-08-24 12:00 (hora local)
"""

from __future__ import annotations

import os
from functools import lru_cache

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QGuiApplication
from PySide6.QtSvg import QSvgRenderer

from frontend.ventana.colores import MUTED

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets")
_LUCIDE_DIR = os.path.join(_BASE, "icons")
_ICONS8_DIR = os.path.join(_BASE, "icons8")

# ── Mapping: nombre Lucide → nombre Icons8 Color ─────────────────
_ICONS8_MAP: dict[str, str] = {
    # Tipo insumo
    "building-2":   "factory",
    "hard-hat":     "businessman",
    "wrench":       "settings",
    "tractor":      "automatic",
    "cog":          "data_configuration",
    "file-text":    "document",
    "truck":        "in_transit",
    "construction": "engineering",
    # Navegación / Tree
    "folder-open":  "opened_folder",
    "folder":       "folder",
    "plus":         "plus",
    "x":            "cancel",
    "pencil":       "edit_image",
    "trash-2":      "empty_trash",
    "clipboard":    "data_sheet",
    "search":       "search",
    "settings":     "settings",
    "external-link":"external",
    # Flechas direccionales
    "arrow-up":         "up",
    "arrow-down":       "down",
    "arrow-left":       "left",
    "arrow-right":      "right",
    "arrow-up-left":    "up_left",
    "arrow-up-right":   "up_right",
    "arrow-down-left":  "down_left",
    "arrow-down-right": "down_right",
    "corner-down-right":"right_down",
    # Edición
    "edit":         "edit_image",
    "pen-line":     "edit_image",
    # Layout / grid
    "grid-2x2":     "grid",
    "layout-grid":  "grid",
    # Misc
    "component":    "puzzle",
    "trending-up":  "positive_dynamic",
    # Direccionales tipo chevron (indicadores de expandir/mover)
    "chevron-down": "down",
    "chevron-up":   "up",
    "chevron-left": "left",
    "chevron-right":"right",
    "chevrons-left":"flow_chart",
    "arrow-left-right": "money_transfer",
    "arrow-up-down":    "reuse",
    # Ingeniería / dominio estructural
    "activity":     "electrical_threshold",
    "circle-dot":   "electrical_sensor",
    "combine":      "tree_structure",
    "dot":          "like_placeholder",
    # Financiero / catálogo
    "banknote":     "currency_exchange",
    "book-open":    "library",
    # Archivo / apariencia
    "file-down":    "export",
    "move-horizontal": "data_configuration",
    "palette":      "picture",
    # Toolbar
    "undo-2":       "undo",
    "redo-2":       "redo",
    "check":        "ok",
    "check-square": "approval",
    "filter":       "filled_filter",
    "filter-x":     "clear_filters",
    "printer":      "print",
    "refresh-cw":   "synchronize",
    "lock":         "lock",
    "unlock":       "unlock",
    "play":         "start",
    "square":       "cancel",
    "loader":       "process",
    "eye":          "view_details",
    "list":         "list",
    "grid-3x3":     "grid",
    "zoom-in":      "search",
    "brush":        "edit_image",
    "moon":         "night_landscape",
    "sun":          "landscape",
    "link":         "link",
    "tag":          "bookmark",
    "zap":          "idea",
    "clipboard-paste": "data_recovery",
    # Sidebar / paneles
    "building":     "business",
    "factory":      "factory",
    "calculator":   "calculator",
    "layers":       "stack_of_photos",
    "layers-2":     "stack_of_photos",
    "bar-chart":    "bar_chart",
    "chart-line":   "line_chart",
    "sigma":        "statistics",
    "percent":      "pie_chart",
    # Diagnóstico / info
    "info":         "info",
    "alert-triangle": "high_priority",
    "check-circle": "ok",
    "alert-circle": "disclaimer",
    "help-circle":  "questions",
    # Misc
    "share-2":      "share",
    "download":     "download",
    "upload":       "upload",
    "trash":        "empty_trash",
    "package":      "package",
    "package-open": "filing_cabinet",
    "hash":         "grid",
    "globe":        "globe",
    "mail":         "sms",
    "phone":        "phone",
    "users":        "contacts",
    "user":         "businessman",
    "star":         "like_placeholder",
    "heart":        "like",
    "maximize":     "expand",
    "minimize":     "collapse",
    "move":         "cursor",
    "compass":      "radar_plot",
    "navigation":   "radar_plot",
    "crosshair":    "close_up_mode",
    "ruler":        "ruler",
    "circle":       "like_placeholder",
    "square-plus":  "add_image",
    "minus":        "minus",
    "more-horizontal": "menu",
    "menu":         "menu",
    "type":         "template",
    "rotate-ccw":   "rotate_camera",
    "refresh":      "synchronize",
    "align-left":   "list",
    "heading":      "todo_list",
    "italic":       "reading",
    "camera":       "camera",
    "video":        "camcorder",
    "music":        "music",
    "volume-2":     "speaker",
    "wifi":         "wi-fi_logo",
    "battery":      "full_battery",
    "power":        "switch_camera",
    "terminal":     "command_line",
    "code":         "circuit",
    "database":     "database",
    "server":       "data_configuration",
    "cloud":        "data_protection",
    "hard-drive":   "data_configuration",
    "cpu":          "electronics",
    "monitor":      "display",
    "smartphone":   "cell_phone",
    "tablet":       "tablet_android",
    "scanner":      "integrated_webcam",
    "mouse":        "cursor",
    "lightbulb":    "idea",
    "flame":        "electricity",
    "flag":         "high_priority",
    "bookmark":     "bookmark",

    "clock":        "alarm_clock",
    "calendar":     "calendar",
    "file":         "file",
    "image":        "image_file",
    "film":         "film",
    "mic":          "speaker",
    "headphones":   "headset",
}

# ── Estado global ─────────────────────────────────────────────────
_active_set: str = "lucide"  # "lucide" | "icons8"
_DEFAULT_TINT = "#E8EDF2"    # tint por defecto (se adapta al tema)


def set_iconos(conjunto: str) -> None:
    """Cambiar conjunto activo ('lucide' o 'icons8')."""
    global _active_set
    if conjunto in ("lucide", "icons8"):
        _active_set = conjunto
        icono.cache_clear()


def get_iconos() -> str:
    """Retorna el conjunto activo."""
    return _active_set


def set_default_tint(color: str) -> None:
    """Cambiar el tint por defecto (ej. colores.TEXT_INVERSO para modo claro)."""
    global _DEFAULT_TINT
    _DEFAULT_TINT = color
    icono.cache_clear()


def get_default_tint() -> str:
    """Retorna el tint por defecto actual."""
    return _DEFAULT_TINT


def _resolve_path(nombre: str, conjunto: str | None = None) -> tuple[str | None, str]:
    """Resuelve la ruta del SVG según el conjunto indicado (o el activo).

    Retorna (ruta, set_real) donde set_real indica de qué conjunto
    salió efectivamente la ruta ("icons8" o "lucide"), para que el
    llamador use el renderer correcto incluso cuando hay fallback.
    """
    if (conjunto or _active_set) == "icons8":
        i8_name = _ICONS8_MAP.get(nombre, nombre)
        path = os.path.join(_ICONS8_DIR, f"{i8_name}.svg")
        if os.path.isfile(path):
            return path, "icons8"
        # Fallback a Lucide si no hay mapeo o el archivo no existe
    return os.path.join(_LUCIDE_DIR, f"{nombre}.svg"), "lucide"


@lru_cache(maxsize=256)
def icono(nombre: str, size: int = 20, color: str | None = None,
          conjunto: str | None = None) -> QIcon:
    """Retorna QIcon desde el conjunto activo (o `conjunto` si se indica).

    Args:
        nombre: Nombre del icono (ej. "folder-open").
        size: Tamaño en píxeles.
        color: Color hex para tint (solo Lucide; Icons8 ignora este parámetro).
        conjunto: Fuerza un conjunto ("lucide"|"icons8") en vez del activo.
            Útil para iconos funcionales que no deben cambiar de semántica
            según el tema (ej. la "x" de cierre, que en Icons8 es un 🚫).
    """
    path, real_set = _resolve_path(nombre, conjunto)
    if not path or not os.path.isfile(path):
        return _fallback_icon(size, color or _DEFAULT_TINT)

    if real_set == "icons8":
        return _colored_icon(path, size)
    return _tinted_icon(path, size, color or _DEFAULT_TINT)


def _colored_icon(path: str, size: int) -> QIcon:
    """Carga SVG de Icons8 Color tal cual (colores ya embebidos)."""
def _dpr() -> float:
    """DevicePixelRatio de la pantalla principal (1.0 si no hay sesión gráfica).

    Renderizar a resolución física evita que Qt estire el pixmap en pantallas
    con escalado (1.25x, 1.5x, ...) — sin esto los trazos finos se ven rotos.
    """
    scr = QGuiApplication.primaryScreen()
    return scr.devicePixelRatio() if scr else 1.0


def _pix_fisico(size: int) -> tuple[QPixmap, int]:
    """QPixmap transparente de `fis` px físicos (sin etiquetar aún).

    Se rasteriza en coordenadas físicas ENTERAS: con escalas fraccionales
    (1.25x, 1.75x) pintar sobre una rejilla no entera recorta los extremos
    de los trazos (una "x" que parece "<"). El DPR se etiqueta al final,
    cuando el QPainter ya cerró.
    """
    d = _dpr()
    fis = max(round(size * d), size)
    pix = QPixmap(fis, fis)
    pix.fill(Qt.GlobalColor.transparent)
    return pix, fis


def _etiquetar(pix: QPixmap, size: int) -> QPixmap:
    """Etiqueta el pixmap con el DPR que hace su tamaño lógico = `size`."""
    pix.setDevicePixelRatio(pix.width() / size)
    return pix


def _colored_icon(path: str, size: int) -> QIcon:
    """Carga SVG de Icons8 Color tal cual (colores ya embebidos)."""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return _fallback_icon(size, _DEFAULT_TINT)

    pix, fis = _pix_fisico(size)
    pad = max(fis // 8, 1)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(pad, pad, fis - 2 * pad, fis - 2 * pad))
    painter.end()
    return QIcon(_etiquetar(pix, size))


def _tinted_icon(path: str, size: int, color: str) -> QIcon:
    """Carga SVG Lucide y lo recolorea con el color dado."""
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return _fallback_icon(size, color)

    pix, fis = _pix_fisico(size)
    pad = max(fis // 8, 1)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(pad, pad, fis - 2 * pad, fis - 2 * pad))
    painter.end()

    fill, _ = _pix_fisico(size)
    fill.fill(QColor(color))

    result, _ = _pix_fisico(size)
    p = QPainter(result)
    p.drawPixmap(0, 0, fill)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawPixmap(0, 0, pix)
    p.end()
    return QIcon(_etiquetar(result, size))


def _fallback_icon(size: int, color: str | None = None) -> QIcon:
    """Icono placeholder cuando no se encuentra el SVG: círculo vectorial.

    Se dibuja con QPainter (no con glifos de texto) para que el fallback
    no dependa de ninguna fuente del sistema.
    """
    pix, fis = _pix_fisico(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color or MUTED))
    pen.setWidthF(max(fis / 10.0, 1.0))
    p.setPen(pen)
    m = fis * 0.25
    p.drawEllipse(QRectF(m, m, fis - 2 * m, fis - 2 * m))
    p.end()
    return QIcon(_etiquetar(pix, size))


def search_input(placeholder: str = "Buscar…", object_name: str = "searchInput",
                 parent=None):
    """QWidget con icono de búsqueda + QLineEdit + clear button."""
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

    w = QWidget(parent)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    lbl = QLabel()
    lbl.setPixmap(icono("search", 16).pixmap(16, 16))
    lbl.setFixedWidth(24)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(lbl)

    inp = QLineEdit()
    inp.setObjectName(object_name)
    inp.setPlaceholderText(placeholder)
    inp.setClearButtonEnabled(True)
    lay.addWidget(inp, 1)

    return w, inp
