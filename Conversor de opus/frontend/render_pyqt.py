"""
frontend/render_pyqt.py — adapta el MISMO árbol que usa render_html.py
a un QAbstractItemModel, para usarlo con QTreeView en la app de escritorio.

No toca SQL ni DBF — recibe el árbol ya construido por
backend.core.build_budget_tree() y lo envuelve en nodos de Qt.

⚠️ Requiere PyQt5 o PySide6 instalado (no disponible en el entorno donde
se generó este código, así que está escrito y documentado pero no
ejecutado/probado aquí — pruébalo en tu máquina antes de confiar en él).

Uso típico (en tu app):
    from backend.core import build_budget_tree
    from frontend.render_pyqt import PresupuestoModel

    tree = build_budget_tree("D60JALISCOT.sqlite")
    modelo = PresupuestoModel(tree)

    vista = QTreeView()
    vista.setModel(modelo)
    vista.expandAll()
"""
from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex
from PyQt5.QtGui import QFont, QBrush, QColor

COLUMNS = ["Clave", "Descripción", "Unidad", "Cantidad", "P.U.", "Importe"]

# Mismos colores que el CSS del HTML, para que ambas presentaciones luzcan igual
COLOR_CAPITULO_BG = [QColor("#dde6f0"), QColor("#eaf0f7"), QColor("#f4f7fa")]
COLOR_IMPORTE_CAP = QColor("#1d6b3f")


class _Node:
    """Envoltorio liviano de cada nodo del árbol + referencia a su padre,
    que es justo lo que QAbstractItemModel necesita para navegar índices."""

    __slots__ = ("data", "parent", "children", "row_in_parent", "depth")

    def __init__(self, data, parent=None, row_in_parent=0, depth=0):
        self.data = data  # el dict tal cual lo entrega presupuesto_builder
        self.parent = parent
        self.row_in_parent = row_in_parent
        self.depth = depth
        self.children = [
            _Node(child, self, i, depth + 1)
            for i, child in enumerate(data.get("hijos", []))
        ]


def _fmt_money(v):
    return "" if v is None else f"${v:,.2f}"


def _fmt_qty(v):
    return "" if v is None else f"{v:,g}"


class PresupuestoModel(QAbstractItemModel):
    """QAbstractItemModel de solo lectura sobre el árbol de presupuesto."""

    def __init__(self, tree, parent=None):
        super().__init__(parent)
        # Nodo raíz virtual (no se muestra) cuyos hijos son los capítulos de nivel 0
        self._root = _Node({"hijos": tree, "desc": "__root__"})

    # --- métodos requeridos por QAbstractItemModel ---

    def rowCount(self, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self._root
        return len(node.children)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def index(self, row, column, parent=QModelIndex()):
        node = parent.internalPointer() if parent.isValid() else self._root
        if row < 0 or row >= len(node.children):
            return QModelIndex()
        return self.createIndex(row, column, node.children[row])

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = index.internalPointer()
        if node.parent is None or node.parent is self._root:
            return QModelIndex()
        return self.createIndex(node.parent.row_in_parent, 0, node.parent)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        node = index.internalPointer()
        d = node.data
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return d.get("clave", "")
            if col == 1:
                return d.get("desc", "")
            if col == 2:
                return d.get("unidad", "")
            if col == 3:
                return _fmt_qty(d.get("cantidad"))
            if col == 4:
                return _fmt_money(d.get("precio"))
            if col == 5:
                return _fmt_money(d.get("importe"))

        if role == Qt.TextAlignmentRole and col >= 3:
            return Qt.AlignRight | Qt.AlignVCenter

        if role == Qt.FontRole and d.get("es_capitulo"):
            f = QFont()
            f.setBold(True)
            return f

        if role == Qt.BackgroundRole and d.get("es_capitulo"):
            idx = min(node.depth, len(COLOR_CAPITULO_BG) - 1)
            return QBrush(COLOR_CAPITULO_BG[idx])

        if role == Qt.ForegroundRole and col == 5 and d.get("es_capitulo"):
            return QBrush(COLOR_IMPORTE_CAP)

        return None

    # --- utilidades propias (no son parte de la API de Qt) ---

    def node_matches(self, node, texto):
        texto = texto.lower()
        d = node.data
        return texto in (d.get("clave", "") or "").lower() or texto in (d.get("desc", "") or "").lower()


# Nota sobre filtrado/búsqueda (equivalente al buscador del HTML):
#
# Para reproducir el comportamiento del buscador del HTML (filtra filas y
# expande ancestros), lo más simple en PyQt es usar QSortFilterProxyModel
# con filterAcceptsRow sobreescrito para que un nodo "pase" si él MISMO
# o alguno de sus descendientes hace match — así QTreeView solo muestra
# las ramas relevantes, igual que el buscador en HTML.
#
# class PresupuestoFilterProxy(QSortFilterProxyModel):
#     def filterAcceptsRow(self, row, parent):
#         idx = self.sourceModel().index(row, 0, parent)
#         node = idx.internalPointer()
#         if self.sourceModel().node_matches(node, self.filterRegExp().pattern()):
#             return True
#         return any(self.sourceModel().node_matches(c, self.filterRegExp().pattern())
#                    for c in node.children)  # simplificado; en árboles profundos
#                                              # conviene recursión completa, no solo 1 nivel
