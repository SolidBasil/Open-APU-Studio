from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import QHeaderView

from frontend.ui.widgets.tabla_base import TreeTableWidget


COLUMNS = ["", "Clave", "Descripción", "Unid", "Cant", "P.U.", "Total"]
EDITABLE_COLS = frozenset({1, 2, 3, 4, 5})

LEVEL_COLORS = [
    "#8B6FB5",  # 0: purple (partidas)
    "#7FAFD6",  # 1: blue accent
    "#5E9CA0",  # 2: teal (subpartidas)
    "#D5B39B",  # 3: warm beige
    "#5B8A72",  # 4: green
    "#A06A6A",  # 5+: red/wine
]


class TablaPresupuesto(TreeTableWidget):
    def __init__(self, parent=None):
        super().__init__(COLUMNS, EDITABLE_COLS, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([100, 80, 250, 50, 80, 100, 110])
        })

    def add_agrupador(self, text, color=None, total=None, parent=None, expanded=True):
        parent = parent or self
        if color is None:
            level = 0
            p = parent
            while p is not None and p is not self:
                level += 1
                p = p.parent()
            color = LEVEL_COLORS[min(level, len(LEVEL_COLORS) - 1)]
        data = ["", "", text, "", "", "",
                f"${total:,.2f}" if total else ""]
        item = self.add_row(data, parent, editable=False)
        brush = QBrush(QColor(color))
        for c in [1, 2, 6]:
            item.setForeground(c, brush)
        f = item.font(0)
        f.setBold(True)
        for c in [1, 2, 6]:
            item.setFont(c, f)
        item.setExpanded(expanded)
        return item

    def add_registro(self, clave, desc, unid, cant, pu, parent=None):
        parent = parent or self
        imp = cant * pu
        data = [
            "", clave, desc, unid,
            f"{cant:,.2f}", f"${pu:,.2f}", f"${imp:,.2f}",
        ]
        return self.add_row(data, parent, editable=True)
