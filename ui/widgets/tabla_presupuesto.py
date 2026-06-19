from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QApplication, QStyledItemDelegate,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QColor, QBrush, QFont, QKeySequence, QPainter, QPen,
)


COLUMNS = ["Nº", "Tipo", "Clave", "Descripción", "Unid", "Cant", "P.U.", "Total"]

LINE_COLOR = QColor("#2A4158")


def draw_tree_connectors(tree, painter, rect, index, line_color=LINE_COLOR):
    info = []
    idx = index
    while True:
        parent = idx.parent()
        total = idx.model().rowCount(parent)
        row = idx.row()
        info.append({
            "has_below": row < total - 1,
            "has_children": idx.model().hasChildren(idx),
        })
        if not parent.isValid():
            break
        idx = parent

    cur_depth = len(info) - 1
    indent = tree.indentation()
    mid_y = rect.top() + rect.height() // 2
    pen = QPen(line_color, 1)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(pen)

    for k in range(1, len(info)):
        if not info[k]["has_below"]:
            continue
        d = cur_depth - k
        x = rect.left() + d * indent + indent // 2
        painter.drawLine(x, rect.top(), x, rect.bottom())

    has_below = info[0]["has_below"]
    x = rect.left() + cur_depth * indent + indent // 2

    if cur_depth > 0 or index.row() > 0:
        painter.drawLine(x, rect.top(), x, mid_y)
    painter.drawLine(x, mid_y, rect.right(), mid_y)
    if has_below:
        painter.drawLine(x, mid_y, x, rect.bottom())

    painter.restore()

#: Columns that accept user editing
_EDITABLE_COLS = frozenset({2, 3, 4, 5, 6})


class _Delegate(QStyledItemDelegate):
    """Only allow editing on designated columns."""

    def createEditor(self, parent, option, index):
        if index.column() in _EDITABLE_COLS:
            editor = super().createEditor(parent, option, index)
            return editor
        return None


class TablaPresupuesto(QTreeWidget):
    """Hierarchical editable table for budget data.

    Supports multi-row selection, per-column editing via double-click,
    and Excel-compatible copy/paste (tab-separated values).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMNS))
        self.setHeaderLabels(COLUMNS)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setIndentation(20)
        self.setRootIsDecorated(True)
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.setMouseTracking(True)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setItemDelegate(_Delegate(self))

        h = self.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for c in range(4, 8):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

    # ── Row builders ──

    def add_agrupador(self, text, color, total=None, parent=None, expanded=True):
        """Add a group-header row (Agrupador)."""
        parent = parent or self
        row = ["", "Agrupador", "", text, "", "", "", f"${total:,.2f}" if total else ""]
        item = QTreeWidgetItem(parent, row)
        brush = QBrush(QColor(color))
        for c in [0, 1, 3, 7]:
            item.setForeground(c, brush)
        f = item.font(0)
        f.setBold(True)
        for c in [0, 1, 3, 7]:
            item.setFont(c, f)
        item.setExpanded(expanded)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def add_registro(self, num, clave, desc, unid, cant, pu, parent=None):
        """Add a data row (Registro)."""
        parent = parent or self
        imp = cant * pu
        item = QTreeWidgetItem(parent, [
            str(num), "Concepto", clave, desc, unid,
            f"{cant:,.2f}", f"${pu:,.2f}", f"${imp:,.2f}",
        ])
        for c in range(self.columnCount()):
            fl = item.flags() | Qt.ItemFlag.ItemIsEditable
            item.setFlags(fl)
        return item

    # ── Tree connector lines ──

    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        draw_tree_connectors(self, painter, rect, index)

    # ── Hierarchical numbering ──

    def renumerar(self):
        """Assign hierarchical numbers (1, 1.1, 1.1.1…) to agrupadores in column 0."""
        root = self.invisibleRootItem()

        def walk(parent, prefix):
            for i in range(parent.childCount()):
                child = parent.child(i)
                tipo = child.text(1)
                if tipo != "Concepto":
                    num = f"{prefix}{i + 1}"
                    child.setText(0, num)
                    walk(child, f"{num}.")

        walk(root, "")

    # ── Clipboard (Excel-compatible TSV) ──

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self._paste()
        else:
            super().keyPressEvent(event)

    def _copy(self):
        item = self.currentItem()
        col = self.currentColumn()
        if not item or col < 0:
            return
        QApplication.clipboard().setText(item.text(col))

    def _paste(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        item = self.currentItem()
        col = self.currentColumn()
        if not item or col < 0:
            return
        if col not in _EDITABLE_COLS:
            return
        lines = text.strip().split("\n")
        item.setText(col, lines[0].strip())
