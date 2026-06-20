from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import QHeaderView

from ui.widgets.tabla_base import TreeTableWidget


COLUMNS = ["Nº", "Tipo", "Clave", "Descripción", "Unid", "Cant", "P.U.", "Total"]
EDITABLE_COLS = frozenset({2, 3, 4, 5, 6})


class TablaPresupuesto(TreeTableWidget):
    def __init__(self, parent=None):
        super().__init__(COLUMNS, EDITABLE_COLS, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([30, 70, 80, 250, 50, 80, 100, 110])
        })

    def add_agrupador(self, text, color, total=None, parent=None, expanded=True):
        parent = parent or self
        data = ["", "Agrupador", "", text, "", "", "",
                f"${total:,.2f}" if total else ""]
        item = self.add_row(data, parent, editable=False)
        brush = QBrush(QColor(color))
        for c in [0, 1, 3, 7]:
            item.setForeground(c, brush)
        f = item.font(0)
        f.setBold(True)
        for c in [0, 1, 3, 7]:
            item.setFont(c, f)
        item.setExpanded(expanded)
        return item

    def add_registro(self, num, clave, desc, unid, cant, pu, parent=None):
        parent = parent or self
        imp = cant * pu
        data = [
            str(num), "Concepto", clave, desc, unid,
            f"{cant:,.2f}", f"${pu:,.2f}", f"${imp:,.2f}",
        ]
        return self.add_row(data, parent, editable=True)

    def renumerar(self):
        super().renumerar(skip_values={"Concepto"})
