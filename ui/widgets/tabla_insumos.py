from PySide6.QtWidgets import QHeaderView

from ui.widgets.tabla_base import TreeTableWidget


COLUMNAS = ["Clave", "Descripción", "Unidad", "Precio", "Tipo"]
EDITABLE = frozenset()


class TablaInsumos(TreeTableWidget):
    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 130])
        })

    def poblar(self, insumos):
        self.clear()
        tipo_nombre = {1: "Material", 2: "Mano de obra", 4: "Herramienta",
                       8: "Equipo", 16: "Auxiliar", 32: "Concepto"}
        for ins in insumos:
            t = tipo_nombre.get(ins["tipo"], f"Tipo {ins['tipo']}")
            self.add_row([
                ins["clave"],
                ins["descripcion"] or ins["descripcion_corta"] or "",
                ins["unidad"] or "",
                f"${ins['precio']:,.2f}" if ins["precio"] else "",
                t,
            ], editable=False)
