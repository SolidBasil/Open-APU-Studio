"""
arbol.py
========
Tabla jerárquica del presupuesto (capítulos + conceptos).

Uso:
    from frontend.widgets.arbol import TablaArbol
"""

from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import QHeaderView

from frontend.widgets.base import TreeTableWidget


COLUMNAS      = ["", "Clave", "Descripción", "Unid", "Cant", "P.U.", "Total"]
EDITABLE_COLS = frozenset({1, 2, 3, 4, 5})

COLORES_NIVEL = [
    "#8B6FB5",  # 0: púrpura  — capítulo raíz
    "#7FAFD6",  # 1: azul
    "#5E9CA0",  # 2: teal
    "#D5B39B",  # 3: beige cálido
    "#5B8A72",  # 4: verde
    "#A06A6A",  # 5+: vino
]


class TablaArbol(TreeTableWidget):
    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE_COLS, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([100, 80, 250, 50, 80, 100, 110])
        })

    def add_agrupador(self, texto, color=None, total=None, parent=None, expanded=True):
        """Inserta una fila de capítulo/subpartida con color por nivel."""
        parent = parent or self
        if color is None:
            nivel = 0
            p = parent
            while p is not None and p is not self:
                nivel += 1
                p = p.parent()
            color = COLORES_NIVEL[min(nivel, len(COLORES_NIVEL) - 1)]

        data = ["", "", texto, "", "", "",
                f"${total:,.2f}" if total else ""]
        item  = self.add_row(data, parent, editable=False)
        brush = QBrush(QColor(color))
        f     = item.font(0)
        f.setBold(True)
        for c in [1, 2, 6]:
            item.setForeground(c, brush)
            item.setFont(c, f)
        item.setExpanded(expanded)
        return item

    def add_registro(self, clave, desc, unid, cant, pu, parent=None):
        """Inserta una fila de concepto hoja."""
        parent = parent or self
        imp    = cant * pu
        data   = [
            "", clave, desc, unid,
            f"{cant:,.2f}", f"${pu:,.2f}", f"${imp:,.2f}",
        ]
        return self.add_row(data, parent, editable=True)

    def poblar(self, nodos_raiz: list[dict]):
        """
        Puebla el árbol desde la estructura devuelta por core.build_budget_tree().
        Cada nodo tiene: tipo, descripcion, subtotal, importe, clave, unidad,
                         cantidad, precio_unitario, hijos.
        """
        self.clear()
        self._poblar_nodos(nodos_raiz, None)

    def _poblar_nodos(self, nodos, parent):
        for n in nodos:
            if n["tipo"] == "capitulo":
                item = self.add_agrupador(
                    n["descripcion"],
                    total=n.get("subtotal", 0),
                    parent=parent,
                )
                self._poblar_nodos(n.get("hijos", []), item)
            else:
                self.add_registro(
                    n.get("clave", ""),
                    n.get("descripcion", ""),
                    n.get("unidad", ""),
                    n.get("cantidad") or 0,
                    n.get("precio_unitario") or 0,
                    parent=parent,
                )
