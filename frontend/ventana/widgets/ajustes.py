"""
ajustes.py
==========
Diálogo de configuración general de Open APU Studio.

Secciones navegables por sidebar:
    General    — información del proyecto (próximamente)
    Cálculo    — precisión de decimales para la explosión de insumos
    Red        — (próximamente)
    Apariencia — (próximamente)

Uso:
    from frontend.widgets.ajustes import DialogoAjustes
    dlg = DialogoAjustes(parent=self)
    dlg.exec()
"""

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QWidget, QFrame, QPushButton, QListWidget, QListWidgetItem,
    QStackedWidget,
)

from backend.database.db import Config


# ── Claves de Config ─────────────────────────────────────────────
KEY_DECIMALES_EXPLOSION = "explosion_decimales"
DECIMALES_DEFAULT       = None

# ── Categorías de la sidebar ─────────────────────────────────────
_CATEGORIAS = [
    ("📋", "General"),
    ("🧮", "Cálculo"),
    ("🌐", "Red"),
    ("🎨", "Apariencia"),
]


def get_decimales_explosion() -> int | None:
    val = Config.get(KEY_DECIMALES_EXPLOSION, None)
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


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
        self._cargar_valores()

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
        hdr = QFrame()
        hdr.setObjectName("dlgAjustesHeader")
        hdr.setFixedHeight(48)
        row = QHBoxLayout(hdr)
        row.setContentsMargins(16, 0, 16, 0)

        icon = QLabel("⚙")
        icon.setObjectName("dlgIcon")
        row.addWidget(icon)

        title = QLabel("Ajustes")
        title.setObjectName("dlgHeader")
        row.addWidget(title)
        row.addStretch()
        return hdr

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

        for icono, nombre in _CATEGORIAS:
            item = QListWidgetItem(f"  {icono}  {nombre}")
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
        self._stack.addWidget(self._build_page_calculo())
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

    def _build_page_calculo(self) -> QWidget:
        page = QWidget()
        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)

        card = QFrame()
        card.setObjectName("dlgCard")
        cvbox = QVBoxLayout(card)
        cvbox.setSpacing(10)
        cvbox.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Cálculo")
        title.setObjectName("dlgCardTitle")
        cvbox.addWidget(title)

        desc = QLabel(
            "Precisión de decimales usada en la <b>Explosión de insumos</b>.<br>"
            "OPUS 2010 trabaja con 2 decimales por operación. "
            "Usa más decimales para mayor exactitud matemática."
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.TextFormat.RichText)
        cvbox.addWidget(desc)

        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("Decimales por operación:")
        row.addWidget(lbl)

        self._spin_decimales = QSpinBox()
        self._spin_decimales.setRange(1, 10)
        self._spin_decimales.setValue(2)
        self._spin_decimales.setSpecialValueText("Completa (sin redondeo)")
        self._spin_decimales.setFixedWidth(170)
        row.addWidget(self._spin_decimales)
        row.addStretch()
        cvbox.addLayout(row)

        nota = QLabel(
            "<i>Valor 1 = precisión completa (flotante). "
            "Valor 2 = modo OPUS. "
            "Valores mayores aumentan precisión intermedia.</i>"
        )
        nota.setWordWrap(True)
        nota.setTextFormat(Qt.TextFormat.RichText)
        cvbox.addWidget(nota)

        vbox.addWidget(card)
        vbox.addStretch()
        return page

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
        footer = QFrame()
        footer.setObjectName("dlgAjustesFooter")
        row = QHBoxLayout(footer)
        row.setContentsMargins(16, 10, 16, 10)

        row.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("dlgCancel")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)

        btn_save = QPushButton("Guardar")
        btn_save.setObjectName("btnPrimario")
        btn_save.clicked.connect(self._guardar)
        row.addWidget(btn_save)

        return footer

    # ── Carga / guardado ─────────────────────────────────────────

    def _cargar_valores(self):
        val = get_decimales_explosion()
        self._spin_decimales.setValue(1 if val is None else val)

    def _guardar(self):
        val = self._spin_decimales.value()
        if val == 1:
            Config.set(KEY_DECIMALES_EXPLOSION, None)
        else:
            Config.set(KEY_DECIMALES_EXPLOSION, val)
        self.accept()
