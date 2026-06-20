from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QApplication, QStyledItemDelegate,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor, QFont, QKeySequence, QPainter, QPen,
)


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


class _Delegate(QStyledItemDelegate):
    def __init__(self, parent, editable_cols):
        super().__init__(parent)
        self._editable_cols = editable_cols

    def createEditor(self, parent, option, index):
        if index.column() in self._editable_cols:
            return super().createEditor(parent, option, index)
        return None


class TreeTableWidget(QTreeWidget):
    def __init__(self, columns, editable_cols=frozenset(), flat=False,
                 line_color=None, parent=None):
        super().__init__(parent)
        self._flat = flat
        self._line_color = line_color or LINE_COLOR
        self._editable_cols = editable_cols

        self.setColumnCount(len(columns))
        self.setHeaderLabels(columns)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setIndentation(20 if not flat else 0)
        self.setRootIsDecorated(not flat)
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
        self.setItemDelegate(_Delegate(self, editable_cols))

        h = self.header()
        h.setStretchLastSection(False)
        for c in range(len(columns)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)

    def set_column_modes(self, modes):
        h = self.header()
        for c, (mode, width) in modes.items():
            h.setSectionResizeMode(c, mode)
            if width is not None:
                h.resizeSection(c, width)

    # ── Row builder ──

    def add_row(self, data, parent=None, editable=True):
        parent = parent or self
        item = QTreeWidgetItem(parent, data)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    # ── Tree connector lines ──

    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        if not self._flat:
            draw_tree_connectors(self, painter, rect, index, self._line_color)

    # ── Hierarchical numbering ──

    def renumerar(self, skip_col=1, skip_values=None):
        if self._flat:
            return
        skip = skip_values or frozenset()
        root = self.invisibleRootItem()

        def walk(parent, prefix):
            for i in range(parent.childCount()):
                child = parent.child(i)
                if child.text(skip_col) not in skip:
                    num = f"{prefix}{i + 1}"
                    child.setText(0, num)
                    walk(child, f"{num}.")

        walk(root, "")

    # ── Clipboard ──

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
        if col not in self._editable_cols:
            return
        lines = text.strip().split("\n")
        item.setText(col, lines[0].strip())
