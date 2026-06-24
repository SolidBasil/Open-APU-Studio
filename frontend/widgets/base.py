"""
base.py
=======
Widget base reutilizable: TreeTableWidget con conectores visuales,
filtrado, edición y clipboard.

Uso:
    from frontend.widgets.base import TreeTableWidget
"""

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QApplication, QStyledItemDelegate, QMenu,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen

import re


# ── Expresiones regulares ──────────────────────────────────────────

SISTEMA_PREFIJOS = re.compile(rf"^[{re.escape('▶🧱👷🔧🚜⚙️📄📚')}]\s?")


# ── Constantes de conectores ──────────────────────────────────────

LINE_COLOR = QColor("#5E92B8")
LINE_WIDTH  = 1.5


# ── Utilidades de texto ───────────────────────────────────────────

def _strip_icons(text: str) -> str:
    """Quita prefijos del sistema (▶ y emojis de tipo) sin afectar datos del usuario.
    Necesario para copiar/exportar datos limpios sin marcadores visuales.
    """
    return SISTEMA_PREFIJOS.sub("", text)


# ── Dibujado de conectores jerárquicos ────────────────────────────

def draw_tree_connectors(tree, painter, rect, index, line_color=LINE_COLOR):
    """Dibuja conectores visuales entre nodos jerárquicos.
    Por cada nivel dibuja una línea vertical si hay nodos debajo,
    y una línea horizontal hacia el contenido del nodo actual.
    """
    info = []
    idx  = index
    while True:
        parent = idx.parent()
        total  = idx.model().rowCount(parent)
        row    = idx.row()
        info.append({
            "has_below":    row < total - 1,
            "has_children": idx.model().hasChildren(idx),
        })
        if not parent.isValid():
            break
        idx = parent

    cur_depth = len(info) - 1
    indent    = tree.indentation()
    mid_y     = rect.top() + rect.height() // 2
    pen       = QPen(line_color, LINE_WIDTH)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(pen)

    for k in range(1, len(info)):
        if not info[k]["has_below"]:
            continue
        d = cur_depth - k
        x = d * indent + indent // 2
        painter.drawLine(x, rect.top(), x, rect.bottom())

    x            = cur_depth * indent + indent // 2
    branch_right = (cur_depth + 1) * indent

    if cur_depth > 0 or index.row() > 0:
        painter.drawLine(x, rect.top(), x, mid_y)
    painter.drawLine(x, mid_y, branch_right, mid_y)
    if info[0]["has_below"]:
        painter.drawLine(x, mid_y, x, rect.bottom())

    painter.restore()


# ── Delegado de edición ───────────────────────────────────────────

class _Delegate(QStyledItemDelegate):
    def __init__(self, parent, editable_cols):
        super().__init__(parent)
        self._editable_cols = editable_cols

    def createEditor(self, parent, option, index):
        if index.column() in self._editable_cols:
            return super().createEditor(parent, option, index)
        return None


# ── Widget tabla base ─────────────────────────────────────────────

class TreeTableWidget(QTreeWidget):

    # ── Constructor ───────────────────────────────────────────────

    def __init__(self, columns, editable_cols=frozenset(), flat=False,
                 line_color=None, parent=None):
        super().__init__(parent)
        self._flat         = flat
        self._line_color   = line_color or LINE_COLOR
        self._editable_cols = editable_cols

        self.setColumnCount(len(columns))
        self.setHeaderLabels(columns)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setIndentation(24 if not flat else 0)
        self.setRootIsDecorated(not flat)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setMouseTracking(True)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setItemDelegate(_Delegate(self, editable_cols))

        h = self.header()
        h.setStretchLastSection(False)
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(self._header_context_menu)
        for c in range(len(columns)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)

    # ── Modos de columna ──────────────────────────────────────────

    def set_column_modes(self, modes):
        h = self.header()
        for c, (mode, width) in modes.items():
            h.setSectionResizeMode(c, mode)
            if width is not None:
                h.resizeSection(c, width)

    # ── Menú contextual de cabecera ───────────────────────────────

    def _header_context_menu(self, pos):
        menu = QMenu(self)
        for c in range(self.columnCount()):
            name = self.headerItem().text(c)
            if not name:
                continue
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(not self.isColumnHidden(c))
            act.toggled.connect(lambda checked, col=c: self.setColumnHidden(col, not checked))
        menu.exec(self.header().mapToGlobal(pos))

    # ── Inserción de filas ────────────────────────────────────────

    def add_row(self, data, parent=None, editable=True):
        parent = parent or self
        item   = QTreeWidgetItem(parent, data)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    # ── Dibujado de ramas ─────────────────────────────────────────

    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        if not self._flat:
            draw_tree_connectors(self, painter, rect, index, self._line_color)

    # ── Control de expansión / visibilidad ────────────────────────

    def show_primer_nivel(self):
        self._show_all()
        self.collapseAll()

    def show_solo_agrupadores(self):
        self._show_all()
        self.expandAll()
        for i in range(self.topLevelItemCount()):
            self._hide_leaves(self.topLevelItem(i))

    def show_todo(self):
        self._show_all()
        self.expandAll()

    def show_nivel(self, depth: int):
        """Expande items hasta profundidad N (recorrido manual del árbol).
        depth=0 → solo raíces colapsadas (igual que Primer nivel)
        depth=1 → raíces expandidas (hijos visibles)
        depth=2 → + nietos visibles
        etc.
        """
        self._show_all()
        self.collapseAll()
        for i in range(self.topLevelItemCount()):
            self._expand_depth(self.topLevelItem(i), depth, 0)

    @staticmethod
    def _expand_depth(item, max_depth, current):
        """Expande item y sus hijos recursivamente hasta max_depth.
        Reemplaza a expandToDepth() de Qt que da resultados inconsistentes
        entre versiones cuando hay items raíz múltiples (nivel 0 + nivel 1).
        """
        if current >= max_depth:
            return
        item.setExpanded(True)
        for i in range(item.childCount()):
            TreeTableWidget._expand_depth(item.child(i), max_depth, current + 1)

    @staticmethod
    def _hide_leaves(item):
        if item.childCount() == 0:
            item.setHidden(True)
        else:
            for i in range(item.childCount()):
                TreeTableWidget._hide_leaves(item.child(i))

    # ── Filtrado de filas ─────────────────────────────────────────

    def filter_rows(self, text):
        desc_col = 2
        for c in range(self.columnCount()):
            if "descrip" in self.headerItem().text(c).lower():
                desc_col = c
                break
        if not text:
            self._show_all()
            return
        text = text.lower()
        for i in range(self.topLevelItemCount()):
            self._filter_item(self.topLevelItem(i), text, desc_col)

    # ── Mostrar todo / filtrar internos ───────────────────────────

    def _show_all(self, parent=None):
        items = ([self.topLevelItem(i) for i in range(self.topLevelItemCount())]
                 if parent is None
                 else [parent.child(i) for i in range(parent.childCount())])
        for item in items:
            item.setHidden(False)
            if item.childCount():
                self._show_all(item)

    def _filter_item(self, item, text, col):
        match = text in item.text(col).lower()
        any_child_visible = False
        for i in range(item.childCount()):
            if self._filter_item(item.child(i), text, col):
                any_child_visible = True
        visible = match or any_child_visible
        item.setHidden(not visible)
        return visible

    # ── Manejo de teclado ─────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self._paste()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def _item_sort_key(item):
        path = []
        while item:
            parent = item.parent()
            idx = parent.indexOfChild(item) if parent else item.treeWidget().indexOfTopLevelItem(item)
            path.append(idx)
            item = parent
        return tuple(reversed(path))

    # ── Portapapeles (copiar / pegar) ─────────────────────────────

    def copy_selection(self) -> bool:
        """
        Copy selected rows as TSV (tab-separated values) to clipboard.
        Returns True if something was copied.
        Called by Ctrl+C and toolbar 'Copiar' button.
        Only copies visible columns — hidden columns (like Desc. Corta, Creado, etc.)
        are excluded from the output.
        """
        items = self.selectedItems()
        if not items:
            return False

        items.sort(key=self._item_sort_key)

        cols = [c for c in range(self.columnCount()) if not self.isColumnHidden(c)]
        header = [_strip_icons(self.headerItem().text(c)) for c in cols]
        lines = ["\t".join(header)]
        for item in items:
            lines.append("\t".join(_strip_icons(item.text(c)) for c in cols))

        QApplication.clipboard().setText("\n".join(lines))
        return True

    def _copy(self):
        if self.copy_selection():
            return
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0:
            return
        QApplication.clipboard().setText(_strip_icons(item.text(col)))

    def _paste(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0 or col not in self._editable_cols:
            return
        item.setText(col, text.strip().split("\n")[0].strip())
