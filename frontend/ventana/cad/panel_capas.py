"""
panel_capas.py
==============
Selector de capas del visor CAD, como dropdown compacto.

Muestra un botón "Capas (n/m)" que al hacer click despliega un menú con
checkbox por capa, búsqueda por nombre, y mostrar/ocultar todas.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit,
    QPushButton, QMenu, QWidgetAction, QSizePolicy,
)
from PySide6.QtGui import QColor, QIcon, QPixmap, QAction


def _color_icon(hex_color: str, size: int = 10) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(QColor(hex_color))
    return QIcon(pix)


class PanelCapas(QWidget):
    """Selector de capas en formato dropdown, con filtro y toggles."""

    layer_toggled = Signal(str, bool)
    show_all = Signal()
    hide_all = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._btn = QPushButton("Capas")
        self._btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn.setStyleSheet(
            "QPushButton { padding: 4px 8px; border: 1px solid #555; border-radius: 3px; "
            "text-align: left; }"
        )
        self._btn.clicked.connect(self._toggle_menu)
        layout.addWidget(self._btn)

        self._menu = QMenu(self)
        self._menu.setStyleSheet(
            "QMenu { background: #1B2330; border: 1px solid #555; }"
            "QMenu::item { padding: 3px 20px; }"
            "QMenu::item:selected { background: #2A3A50; }"
        )

        # Buscador
        search_wrap = QWidget()
        sl = QHBoxLayout(search_wrap)
        sl.setContentsMargins(6, 4, 6, 4)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar capas...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_changed)
        sl.addWidget(self._search)
        search_action = QWidgetAction(self._menu)
        search_action.setDefaultWidget(search_wrap)
        self._menu.addAction(search_action)

        # Mostrar todas / Ocultar todas
        header_wrap = QWidget()
        hl = QHBoxLayout(header_wrap)
        hl.setContentsMargins(6, 0, 6, 4)
        btn_all_on = QPushButton("Mostrar todas")
        btn_all_on.setFlat(True)
        btn_all_on.setStyleSheet("color: #4A9EFF; font-size: 10px; border: none; text-align: left;")
        btn_all_on.clicked.connect(self.show_all.emit)
        hl.addWidget(btn_all_on)
        btn_all_off = QPushButton("Ocultar todas")
        btn_all_off.setFlat(True)
        btn_all_off.setStyleSheet("color: #4A9EFF; font-size: 10px; border: none; text-align: left;")
        btn_all_off.clicked.connect(self.hide_all.emit)
        hl.addWidget(btn_all_off)
        header_action = QWidgetAction(self._menu)
        header_action.setDefaultWidget(header_wrap)
        self._menu.addAction(header_action)
        self._menu.addSeparator()

        # State
        self._layers: list[dict] = []
        self._visible: set[str] = set()
        self._layer_actions: dict[str, QAction] = {}

    def _toggle_menu(self):
        pos = self._btn.mapToGlobal(self._btn.rect().bottomLeft())
        self._menu.exec(pos)

    def set_layers(self, layers: list[dict]):
        self._layers = layers
        self._visible = {l["name"] for l in layers if l.get("visible", True)}
        self._rebuild_menu()

    def set_layer_visibility(self, name: str, visible: bool):
        if visible:
            self._visible.add(name)
        else:
            self._visible.discard(name)
        action = self._layer_actions.get(name)
        if action is not None:
            action.blockSignals(True)
            action.setChecked(visible)
            action.blockSignals(False)
        self._update_button_label()

    def _filter_changed(self, _text):
        self._rebuild_menu()

    def _update_button_label(self):
        total = len(self._layers)
        visibles = len(self._visible)
        self._btn.setText(f"Capas ({visibles}/{total})" if total else "Capas")

    def _rebuild_menu(self):
        for action in list(self._layer_actions.values()):
            self._menu.removeAction(action)
        self._layer_actions.clear()

        q = self._search.text().strip().lower()
        for layer in self._layers:
            name = layer["name"]
            if q and q not in name.lower():
                continue
            color = layer.get("color", 7)
            if isinstance(color, int):
                from backend.cad.lector_dxf import ACI_COLORS
                hex_color = ACI_COLORS.get(color, "#CCCCCC")
            else:
                hex_color = str(color)
            count = layer.get("entity_count", 0)
            label = f"{name}  ({count})" if count else name

            action = self._menu.addAction(_color_icon(hex_color), label)
            action.setCheckable(True)
            action.setChecked(name in self._visible)
            action.toggled.connect(lambda checked, n=name: self._on_action_toggled(n, checked))
            self._layer_actions[name] = action

        self._update_button_label()

    def _on_action_toggled(self, name: str, visible: bool):
        self.layer_toggled.emit(name, visible)
