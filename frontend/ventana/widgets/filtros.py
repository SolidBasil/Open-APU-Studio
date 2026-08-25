from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QDialog, QLabel,
    QComboBox, QLineEdit, QPushButton, QScrollArea,
    QDialogButtonBox, QStackedWidget,
)
from frontend.ventana.iconos import icono
from frontend.ventana.widgets.base import ColType

_OP_TYPES = {
    ColType.TEXT:    [("contiene", "contains"), ("no contiene", "not_contains"), ("es exactamente", "exact")],
    ColType.NUMERIC: [("es exactamente", "exact"), ("mayor que", "gt"), ("menor que", "lt")],
    ColType.CHOICE:  [("es exactamente", "exact"), ("contiene", "contains")],
    ColType.DATE:    [("contiene", "contains"), ("es exactamente", "exact")],
}


class _FilterRow(QWidget):
    """Una fila: [columna ▼] [operador ▼] [valor widget] [×]"""

    def __init__(self, parent, columns: list[tuple[int, str]], table):
        super().__init__(parent)
        self._table = table
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self._col = QComboBox()
        for idx, label in columns:
            self._col.addItem(label, idx)
        self._col.setFixedWidth(120)
        self._col.currentIndexChanged.connect(self._on_col_changed)
        layout.addWidget(self._col)

        self._op = QComboBox()
        self._op.setFixedWidth(130)
        layout.addWidget(self._op)

        self._value_stack = QStackedWidget()
        self._value_line = QLineEdit()
        self._value_line.setPlaceholderText("Valor…")
        self._value_combo = QComboBox()
        self._value_combo.setEditable(True)
        self._value_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._value_stack.addWidget(self._value_line)   # 0 = line edit
        self._value_stack.addWidget(self._value_combo)  # 1 = combo
        self._value_stack.setFixedHeight(26)
        layout.addWidget(self._value_stack, 1)

        remove_btn = QPushButton()
        remove_btn.setIcon(icono("x", 14))
        remove_btn.setFixedSize(24, 24)
        remove_btn.clicked.connect(self.deleteLater)
        layout.addWidget(remove_btn)

        self._on_col_changed(0)

    def _on_col_changed(self, idx):
        col = self._col.itemData(idx)
        info = self._table.get_column_info(col) if hasattr(self._table, 'get_column_info') else {}
        ctype = info.get("tipo", ColType.TEXT)
        choices = info.get("choices")

        ops = _OP_TYPES.get(ctype, _OP_TYPES[ColType.TEXT])
        self._op.clear()
        for label, key in ops:
            self._op.addItem(label, key)

        if ctype == ColType.CHOICE and choices:
            self._value_combo.clear()
            self._value_combo.addItems(choices)
            self._value_stack.setCurrentIndex(1)
        else:
            self._value_line.clear()
            self._value_line.setPlaceholderText("0.00" if ctype == ColType.NUMERIC else "Valor…")
            self._value_stack.setCurrentIndex(0)

    def to_filter(self) -> dict | None:
        if self._value_stack.currentIndex() == 0:
            val = self._value_line.text().strip()
        else:
            val = self._value_combo.currentText().strip()
        if not val:
            return None
        return {
            "col": self._col.currentData(),
            "op": self._op.currentData(),
            "value": val,
        }


class FilterDialog(QDialog):
    """Popup para añadir/quitar filtros por columna visible."""

    def __init__(self, parent, table):
        super().__init__(parent)
        self._table = table
        self._rows: list[_FilterRow] = []
        self._columns = [(c, table.headerItem().text(c))
                         for c in range(table.columnCount())
                         if not table.isColumnHidden(c) and table.headerItem().text(c)]

        self.setWindowTitle("Filtrar — columnas visibles")
        self.setMinimumSize(520, 320)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("Añade filtros a las columnas visibles. Se combinan con AND.")
        header.setStyleSheet("font-size: 12px;")
        layout.addWidget(header)

        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(2)
        self._scroll_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._scroll_content)
        layout.addWidget(scroll, 1)

        add_btn = QPushButton("+ Añadir filtro")
        add_btn.clicked.connect(self._add_row)
        layout.addWidget(add_btn)

        buttons = QDialogButtonBox()
        clear_btn = buttons.addButton("Limpiar todo", QDialogButtonBox.ButtonRole.ResetRole)
        clear_btn.clicked.connect(self._clear_all)

        apply_btn = buttons.addButton("Aplicar", QDialogButtonBox.ButtonRole.AcceptRole)
        apply_btn.clicked.connect(self.accept)

        cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        cancel_btn.clicked.connect(self.reject)

        layout.addWidget(buttons)

        self._add_row()

    def _add_row(self):
        row = _FilterRow(self._scroll_content, self._columns, self._table)
        self._rows.append(row)
        self._scroll_layout.insertWidget(self._scroll_layout.count() - 1, row)
        if row._value_stack.currentIndex() == 0:
            row._value_line.setFocus()
        else:
            row._value_combo.setFocus()

    def _clear_all(self):
        for row in list(self._rows):
            row.deleteLater()
        self._rows.clear()
        self._add_row()

    def get_filters(self) -> list[dict]:
        return [f for r in self._rows if (f := r.to_filter()) is not None]