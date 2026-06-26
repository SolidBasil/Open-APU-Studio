"""
ajustes.py
==========
Diálogo de configuración general de Open APU Studio.

Secciones:
    Cálculo   — precisión de decimales para la explosión de insumos
    (extensible a futuro con más secciones)

Uso:
    from frontend.widgets.ajustes import DialogoAjustes
    dlg = DialogoAjustes(parent=self)
    dlg.exec()
"""

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSpinBox, QDialogButtonBox, QWidget,
    QFrame,
)

from backend.db import Config

# ── Claves de Config ─────────────────────────────────────────────
KEY_DECIMALES_EXPLOSION = "explosion_decimales"   # int | None (None = precisión completa)
DECIMALES_DEFAULT       = None                    # precisión completa por defecto


def get_decimales_explosion() -> int | None:
    """Lee la preferencia de decimales para la explosión.
    Devuelve None si está en modo precisión completa.
    """
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
        self.setMinimumWidth(380)
        self._build_ui()
        self._cargar_valores()

    # ── Construcción ─────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 12)

        # ── Sección: Cálculo
        layout.addWidget(self._build_seccion_calculo())

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # ── Botones
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.accepted.connect(self._guardar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _build_seccion_calculo(self) -> QWidget:
        grp = QGroupBox("Cálculo")
        vbox = QVBoxLayout(grp)
        vbox.setSpacing(10)

        # Descripción
        desc = QLabel(
            "Precisión de decimales usada en la <b>Explosión de insumos</b>.<br>"
            "OPUS 2010 trabaja con 2 decimales por operación. "
            "Usa más decimales para mayor exactitud matemática."
        )
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.TextFormat.RichText)
        vbox.addWidget(desc)

        # Control
        row = QHBoxLayout()
        row.setSpacing(8)

        lbl = QLabel("Decimales por operación:")
        row.addWidget(lbl)

        self._spin_decimales = QSpinBox()
        self._spin_decimales.setRange(2, 10)
        self._spin_decimales.setValue(2)
        self._spin_decimales.setSpecialValueText("Completa (sin redondeo)")
        # El valor mínimo del spinbox = 2; usaremos 1 como señal de "sin redondeo"
        # Rango real: 1 = sin redondeo (special text), 2..10 = N decimales
        self._spin_decimales.setRange(1, 10)
        self._spin_decimales.setFixedWidth(170)
        row.addWidget(self._spin_decimales)
        row.addStretch()
        vbox.addLayout(row)

        nota = QLabel(
            "<i>Valor 1 = precisión completa (flotante). "
            "Valor 2 = modo OPUS. "
            "Valores mayores aumentan precisión intermedia.</i>"
        )
        nota.setWordWrap(True)
        nota.setTextFormat(Qt.TextFormat.RichText)
        vbox.addWidget(nota)

        return grp

    # ── Carga / guardado ─────────────────────────────────────────

    def _cargar_valores(self):
        val = get_decimales_explosion()
        # None → 1 (special text "Completa")
        self._spin_decimales.setValue(1 if val is None else val)

    def _guardar(self):
        val = self._spin_decimales.value()
        # 1 = precisión completa → guardar None
        if val == 1:
            Config.set(KEY_DECIMALES_EXPLOSION, None)
        else:
            Config.set(KEY_DECIMALES_EXPLOSION, val)
        self.accept()
