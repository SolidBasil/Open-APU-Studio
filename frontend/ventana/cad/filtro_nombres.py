"""
filtro_nombres.py
=================
Filtro de nombres de entidades para el visor CAD.

Agrupa entidades por nombre de visualización (block_name para INSERT,
tipo de entidad para el resto) y permite toggle de visibilidad por nombre.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem,
)
from PySide6.QtGui import QFont


TOP_N = 8


def entity_display_name(entity) -> str:
    """Nombre legible de una entidad para el filtro."""
    if hasattr(entity, "type"):
        etype = entity.type
        block = getattr(entity, "block_name", None)
        text = getattr(entity, "text", None)
    else:
        etype = entity.get("type", "")
        block = entity.get("block_name")
        text = entity.get("text")

    if etype == "INSERT" and block:
        return block
    if etype == "HATCH":
        return "HATCH"
    if etype == "TEXT" and text:
        trimmed = text.strip()
        return trimmed[:30] + "..." if len(trimmed) > 30 else trimmed
    return etype


class FiltroNombres(QWidget):
    """Filtro de nombres de entidades."""

    name_toggled = Signal(str, bool)  # name, visible
    show_all = Signal()
    hide_all = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QHBoxLayout()
        lbl = QLabel("Nombres")
        f = QFont()
        f.setBold(True)
        f.setPointSize(10)
        lbl.setFont(f)
        header.addWidget(lbl)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #888; font-size: 10px;")
        header.addWidget(self._count_lbl)
        header.addStretch()

        btn_all_on = QPushButton("All on")
        btn_all_on.setFlat(True)
        btn_all_on.setStyleSheet("color: #888; font-size: 10px; border: none;")
        btn_all_on.clicked.connect(self.show_all.emit)
        header.addWidget(btn_all_on)

        sep = QLabel("/")
        sep.setStyleSheet("color: #888; font-size: 10px;")
        header.addWidget(sep)

        btn_all_off = QPushButton("All off")
        btn_all_off.setFlat(True)
        btn_all_off.setStyleSheet("color: #888; font-size: 10px; border: none;")
        btn_all_off.clicked.connect(self.hide_all.emit)
        header.addWidget(btn_all_off)

        layout.addLayout(header)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar nombres...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._filter_changed)
        self._search.setStyleSheet(
            "QLineEdit { padding: 2px 4px; font-size: 11px; border: 1px solid #555; border-radius: 3px; }"
        )
        layout.addWidget(self._search)

        # List
        self._list = QListWidget()
        self._list.setSpacing(1)
        self._list.setMaximumHeight(300)
        self._list.setStyleSheet(
            "QListWidget { border: none; background: transparent; }"
            "QListWidget::item { padding: 2px 4px; border-radius: 3px; }"
            "QListWidget::item:hover { background: #333; }"
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list, 1)

        # Show all button
        self._show_more_btn = QPushButton()
        self._show_more_btn.setFlat(True)
        self._show_more_btn.setStyleSheet("color: #4A9EFF; font-size: 10px; border: none;")
        self._show_more_btn.clicked.connect(self._toggle_show_all)
        self._show_more_btn.setVisible(False)
        layout.addWidget(self._show_more_btn)

        # State
        self._name_groups: list[tuple[str, int]] = []  # [(name, count)]
        self._visible: set[str] = set()
        self._expanded = False

    def set_entities(self, entities):
        """Rebuild name groups from entities."""
        from collections import Counter
        counts = Counter()
        for e in entities:
            name = entity_display_name(e)
            counts[name] += 1
        self._name_groups = sorted(counts.items(), key=lambda x: -x[1])
        self._visible = {name for name, _ in self._name_groups}
        self._expanded = False
        self._rebuild_list()

    def set_name_visibility(self, name: str, visible: bool):
        if visible:
            self._visible.add(name)
        else:
            self._visible.discard(name)
        self._rebuild_list()

    def _filter_changed(self, _text):
        self._rebuild_list()

    def _toggle_show_all(self):
        self._expanded = not self._expanded
        self._rebuild_list()

    def _rebuild_list(self):
        self._list.clear()
        q = self._search.text().strip().lower()

        groups = self._name_groups
        if q:
            groups = [(n, c) for n, c in groups if q in n.lower()]

        self._count_lbl.setText(f"({len(self._name_groups)})")

        if not q and not self._expanded and len(groups) > TOP_N:
            display = groups[:TOP_N]
            self._show_more_btn.setText(f"Mostrar todos ({len(groups)})")
            self._show_more_btn.setVisible(True)
        else:
            display = groups
            self._show_more_btn.setVisible(False)

        for name, count in display:
            item = QListWidgetItem()
            visible = name in self._visible
            icon = "●" if visible else "○"
            item.setText(f"{icon}  {name}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        if not name:
            return
        visible = name not in self._visible
        self.name_toggled.emit(name, visible)
