"""
ajustes.py
==========
Diálogo de configuración general de Open APU Studio.

Secciones navegables por sidebar:
    General    — información del proyecto (próximamente)
    Red        — (próximamente)
    Apariencia — (próximamente)

Uso:
    from frontend.widgets.ajustes import DialogoAjustes
    dlg = DialogoAjustes(parent=self)
    dlg.exec()
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QWidget, QFrame, QListWidget, QListWidgetItem,
    QStackedWidget,
)

from frontend.ventana.iconos import icono
from frontend.ventana.widgets.base import crear_header_dialogo, crear_footer_dialogo


# ── Categorías de la sidebar (nombre de icono Lucide, no emoji) ──
_CATEGORIAS = [
    ("clipboard", "General"),
    ("globe", "Red"),
    ("palette", "Apariencia"),
]


# =============================================================================
# DIÁLOGO
# =============================================================================

class DialogoAjustes(QDialog):
    """Ventana de configuración general de la aplicación."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setMinimumHeight(380)
        self.setObjectName("dlgAjustes")
        self._build_ui()

    # ── Construcción ─────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_sep())
        layout.addWidget(self._build_body(), 1)
        layout.addWidget(self._build_sep())
        layout.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        return crear_header_dialogo("settings", "Ajustes")

    def _build_sep(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("dlgSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        return sep

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setObjectName("dlgAjustesBody")
        row = QHBoxLayout(body)
        row.setSpacing(0)
        row.setContentsMargins(0, 0, 0, 0)

        # Sidebar de navegación
        self._nav = QListWidget()
        self._nav.setObjectName("dlgAjustesNav")
        self._nav.setFixedWidth(150)
        self._nav.setSpacing(0)

        for svg_name, nombre in _CATEGORIAS:
            pix = icono(svg_name, 16).pixmap(16, 16)
            item = QListWidgetItem(pix, f"  {nombre}")
            item.setSizeHint(item.sizeHint())
            self._nav.addItem(item)

        row.addWidget(self._nav)

        # Separador vertical
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setObjectName("dlgVSep")
        row.addWidget(vsep)

        # Stack de páginas de contenido
        self._stack = QStackedWidget()
        self._stack.setObjectName("dlgAjustesStack")

        self._stack.addWidget(self._build_page_general())
        self._stack.addWidget(self._build_page_red())
        self._stack.addWidget(self._build_page_apariencia())

        row.addWidget(self._stack, 1)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._nav.setCurrentRow(0)

        return body

    # ── Páginas de contenido ─────────────────────────────────────

    def _build_page_general(self) -> QWidget:
        return self._build_placeholder("General",
            "Información general del proyecto y preferencias básicas.\n\n"
            "Esta sección estará disponible en una versión futura.")

    def _build_page_red(self) -> QWidget:
        return self._build_placeholder("Red",
            "Configuración de red, proxies y conexión a servicios externos.\n\n"
            "Esta sección estará disponible en una versión futura.")

    def _build_page_apariencia(self) -> QWidget:
        return self._build_placeholder("Apariencia",
            "Personalización de temas, fuentes y disposición de la interfaz.\n\n"
            "Esta sección estará disponible en una versión futura.")

    def _build_placeholder(self, titulo: str, mensaje: str) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        card = QFrame()
        card.setObjectName("dlgCard")
        cvbox = QVBoxLayout(card)
        cvbox.setSpacing(8)
        cvbox.setContentsMargins(12, 12, 12, 12)

        title = QLabel(titulo)
        title.setObjectName("dlgCardTitle")
        cvbox.addWidget(title)

        msg = QLabel(mensaje)
        msg.setWordWrap(True)
        msg.setStyleSheet("color: palette(mid); font-style: italic; background: transparent; border: none;")
        cvbox.addWidget(msg)

        vbox.addWidget(card)
        vbox.addStretch()
        return page

    # ── Footer ──────────────────────────────────────────────────

    def _build_footer(self) -> QFrame:
        return crear_footer_dialogo(self)
