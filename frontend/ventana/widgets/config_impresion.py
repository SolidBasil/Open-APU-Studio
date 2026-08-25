"""
config_impresion.py
====================
Diálogo de configuración de impresión del reporte de presupuesto (y, a
futuro, de los demás reportes LaTeX): orientación de hoja, márgenes y
ancho de columnas al imprimir.

Los valores se persisten vía Config bajo la clave CONFIG_KEY como un
dict:
    {
        "orientacion":    "vertical" | "horizontal",
        "margen_sup_cm":  float,
        "margen_inf_cm":  float,
        "margen_izq_cm":  float,
        "margen_der_cm":  float,
        "anchos_cm":      {"<campo>": float, ...},  # override por columna;
                                                     # ausente = automático
    }

config_actual() rellena con DEFAULTS lo que falte, así que llamarlo
siempre da un dict completo. Lo consume
backend/exportar/informe_pdf/latex.py::ReportePresupuesto (ver
frontend/ventana/mixins/informes.py).

Uso:
    from frontend.ventana.widgets.config_impresion import DialogoConfigImpresion
    dlg = DialogoConfigImpresion(self, columnas_actuales=arbol.columnas_para_reporte())
    dlg.exec()
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QFrame, QPushButton,
    QRadioButton, QButtonGroup, QDoubleSpinBox, QFormLayout, QScrollArea,
)

from frontend.ventana.widgets.base import crear_header_dialogo, crear_footer_dialogo
from backend.database.db import Config

CONFIG_KEY = "impresion_presupuesto"

DEFAULTS = {
    "orientacion":   "vertical",
    "margen_sup_cm": 2.0,
    "margen_inf_cm": 2.0,
    "margen_izq_cm": 2.0,
    "margen_der_cm": 2.0,
    "anchos_cm":     {},
}


def config_actual() -> dict:
    """Config de impresión persistida, con DEFAULTS para lo que falte."""
    guardado = Config.get(CONFIG_KEY, {}) or {}
    cfg = {**DEFAULTS, **guardado}
    cfg["anchos_cm"] = dict(guardado.get("anchos_cm") or {})
    return cfg


# =============================================================================
# DIÁLOGO
# =============================================================================

class DialogoConfigImpresion(QDialog):
    """Orientación, márgenes y anchos de columna para el reporte impreso."""

    def __init__(self, parent=None, columnas_actuales: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de impresión")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setMinimumHeight(420)
        self.setObjectName("dlgConfigImpresion")

        self._columnas = columnas_actuales or []
        self._cfg = config_actual()
        self._spins_anchos: dict[str, QDoubleSpinBox] = {}

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
        return crear_header_dialogo("printer", "Configuración de impresión")

    def _build_sep(self) -> QFrame:
        sep = QFrame()
        sep.setObjectName("dlgSep")
        sep.setFrameShape(QFrame.Shape.HLine)
        return sep

    def _build_body(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget()
        vbox = QVBoxLayout(body)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(16)

        vbox.addWidget(self._build_seccion_orientacion())
        vbox.addWidget(self._build_seccion_margenes())
        if self._columnas:
            vbox.addWidget(self._build_seccion_columnas())
        vbox.addStretch()

        scroll.setWidget(body)
        return scroll

    def _build_seccion_orientacion(self) -> QFrame:
        card = QFrame()
        card.setObjectName("dlgCard")
        v = QVBoxLayout(card)
        v.setSpacing(8)
        v.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Orientación de hoja")
        title.setObjectName("dlgCardTitle")
        v.addWidget(title)

        fila = QHBoxLayout()
        self._rb_vertical = QRadioButton("Vertical")
        self._rb_horizontal = QRadioButton("Horizontal")
        grupo = QButtonGroup(self)
        grupo.addButton(self._rb_vertical)
        grupo.addButton(self._rb_horizontal)
        if self._cfg["orientacion"] == "horizontal":
            self._rb_horizontal.setChecked(True)
        else:
            self._rb_vertical.setChecked(True)
        fila.addWidget(self._rb_vertical)
        fila.addWidget(self._rb_horizontal)
        fila.addStretch()
        v.addLayout(fila)
        return card

    def _build_seccion_margenes(self) -> QFrame:
        card = QFrame()
        card.setObjectName("dlgCard")
        v = QVBoxLayout(card)
        v.setSpacing(8)
        v.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Márgenes de hoja")
        title.setObjectName("dlgCardTitle")
        v.addWidget(title)

        form = QFormLayout()
        self._spin_sup = self._crear_spin_margen(self._cfg["margen_sup_cm"])
        self._spin_inf = self._crear_spin_margen(self._cfg["margen_inf_cm"])
        self._spin_izq = self._crear_spin_margen(self._cfg["margen_izq_cm"])
        self._spin_der = self._crear_spin_margen(self._cfg["margen_der_cm"])
        form.addRow("Superior", self._spin_sup)
        form.addRow("Inferior", self._spin_inf)
        form.addRow("Izquierdo", self._spin_izq)
        form.addRow("Derecho", self._spin_der)
        v.addLayout(form)
        return card

    def _build_seccion_columnas(self) -> QFrame:
        card = QFrame()
        card.setObjectName("dlgCard")
        v = QVBoxLayout(card)
        v.setSpacing(8)
        v.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Ancho de columnas al imprimir")
        title.setObjectName("dlgCardTitle")
        v.addWidget(title)

        msg = QLabel(
            "Por defecto cada columna reparte el espacio disponible en la "
            "hoja proporcional al ancho que tiene en pantalla. Ajusta un "
            "valor aquí solo si quieres forzar un ancho distinto en el "
            "reporte impreso; deja \"Auto\" para el resto."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet(
            "color: palette(mid); font-style: italic; background: transparent; border: none;"
        )
        v.addWidget(msg)

        form = QFormLayout()
        anchos_guardados = self._cfg["anchos_cm"]
        for col in self._columnas:
            campo = col["campo"]
            valor_guardado = anchos_guardados.get(campo)
            spin = self._crear_spin_ancho(valor_guardado)
            self._spins_anchos[campo] = spin
            form.addRow(col["label"], spin)
        v.addLayout(form)
        return card

    def _crear_spin_margen(self, valor: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(0.5, 5.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        spin.setSuffix(" cm")
        spin.setValue(valor)
        return spin

    def _crear_spin_ancho(self, valor: float | None) -> QDoubleSpinBox:
        """0.0 (mínimo del rango) se muestra como "Auto" — significa que
        esa columna no tiene override y se reparte proporcionalmente."""
        spin = QDoubleSpinBox()
        spin.setRange(0.0, 10.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.1)
        spin.setSuffix(" cm")
        spin.setSpecialValueText("Auto")
        spin.setValue(valor if valor else 0.0)
        return spin

    def _build_footer(self) -> QFrame:
        btn_restablecer = QPushButton("Restablecer")
        btn_restablecer.clicked.connect(self._restablecer)
        return crear_footer_dialogo(self, on_guardar=self._guardar,
                                    botones_extra=[btn_restablecer])

    # ── Acciones ─────────────────────────────────────────────────

    def _restablecer(self):
        self._rb_vertical.setChecked(True)
        self._spin_sup.setValue(DEFAULTS["margen_sup_cm"])
        self._spin_inf.setValue(DEFAULTS["margen_inf_cm"])
        self._spin_izq.setValue(DEFAULTS["margen_izq_cm"])
        self._spin_der.setValue(DEFAULTS["margen_der_cm"])
        for spin in self._spins_anchos.values():
            spin.setValue(0.0)

    def _guardar(self):
        anchos_cm = {
            campo: spin.value()
            for campo, spin in self._spins_anchos.items()
            if spin.value() > 0.0
        }
        cfg = {
            "orientacion":   "horizontal" if self._rb_horizontal.isChecked() else "vertical",
            "margen_sup_cm": self._spin_sup.value(),
            "margen_inf_cm": self._spin_inf.value(),
            "margen_izq_cm": self._spin_izq.value(),
            "margen_der_cm": self._spin_der.value(),
            "anchos_cm":     anchos_cm,
        }
        Config.set(CONFIG_KEY, cfg)
        self.accept()
