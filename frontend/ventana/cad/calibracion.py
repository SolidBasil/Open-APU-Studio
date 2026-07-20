"""
calibracion.py
==============
Diálogo de calibración de escala de dos clics.

El usuario marca dos puntos sobre una medida conocida del plano
y captura esa distancia real. La app calcula escala = distancia_real / distancia_en_el_dibujo.
"""

from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QGroupBox, QMessageBox,
)


class CalibrationDialog(QDialog):
    """Diálogo de calibración de escala para el visor CAD."""

    calibration_confirmed = Signal(float, str)  # (units_per_pixel, unit_label)

    def __init__(self, point_a: tuple[float, float],
                 point_b: tuple[float, float],
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibrar escala")
        self.setMinimumWidth(350)
        self.setModal(True)

        self._point_a = point_a
        self._point_b = point_b

        # Calcular distancia en pixels/world units
        dx = point_b[0] - point_a[0]
        dy = point_b[1] - point_a[1]
        self._pixel_distance = math.sqrt(dx * dx + dy * dy)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Info
        info = QLabel(
            f"Distancia en el dibujo: <b>{self._pixel_distance:.4f}</b> unidades"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info)

        # Distancia real
        grp = QGroupBox("Distancia real conocida")
        grp_layout = QHBoxLayout(grp)

        grp_layout.addWidget(QLabel("Valor:"))
        self._valor_input = QLineEdit()
        self._valor_input.setPlaceholderText("ej. 3.50")
        self._valor_input.setFixedWidth(100)
        grp_layout.addWidget(self._valor_input)

        grp_layout.addWidget(QLabel("Unidad:"))
        self._unidad_combo = QComboBox()
        self._unidad_combo.addItems(["m", "mm", "ft", "in"])
        grp_layout.addWidget(self._unidad_combo)

        layout.addWidget(grp)

        # Result preview
        self._resultado_lbl = QLabel("")
        layout.addWidget(self._resultado_lbl)

        self._valor_input.textChanged.connect(self._update_result)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(cancelar)

        confirmar = QPushButton("Confirmar")
        confirmar.setDefault(True)
        confirmar.clicked.connect(self._confirmar)
        btn_layout.addWidget(confirmar)

        layout.addLayout(btn_layout)

    def _update_result(self):
        """Muestra preview del factor de escala."""
        try:
            valor = float(self._valor_input.text().replace(",", "."))
            if valor <= 0 or self._pixel_distance <= 0:
                self._resultado_lbl.setText("")
                return
            upp = valor / self._pixel_distance
            unidad = self._unidad_combo.currentText()
            self._resultado_lbl.setText(
                f"<i>Factor: {upp:.6f} {unidad}/unidad dibujo</i>"
            )
        except ValueError:
            self._resultado_lbl.setText("")

    def _confirmar(self):
        """Valida y emite la calibración."""
        try:
            valor = float(self._valor_input.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Valor inválido", "Ingresa un número válido.")
            return

        if valor <= 0:
            QMessageBox.warning(self, "Valor inválido", "La distancia debe ser mayor a 0.")
            return

        if self._pixel_distance <= 0:
            QMessageBox.warning(self, "Error", "Los puntos de calibración son coincidentes.")
            return

        upp = valor / self._pixel_distance
        unidad = self._unidad_combo.currentText()
        self.calibration_confirmed.emit(upp, unidad)
        self.accept()

    def get_calibration(self) -> tuple[float, str]:
        """Devuelve (units_per_pixel, unit) después de accept."""
        try:
            valor = float(self._valor_input.text().replace(",", "."))
            unidad = self._unidad_combo.currentText()
            upp = valor / self._pixel_distance if self._pixel_distance > 0 else 1.0
            return upp, unidad
        except ValueError:
            return 1.0, "m"
