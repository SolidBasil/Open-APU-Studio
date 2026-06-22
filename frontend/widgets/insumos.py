"""
insumos.py
==========
Tabla plana del catálogo de insumos.

Uso:
    from frontend.widgets.insumos import TablaInsumos
"""

from PySide6.QtWidgets import QHeaderView
from frontend.widgets.base import TreeTableWidget


COLUMNAS = ["Clave", "Descripción", "Unidad", "Precio", "Tipo"]
EDITABLE = frozenset()

TIPO_NOMBRE = {
    1:  "🧱 Material",
    2:  "👷 Mano de obra",
    4:  "🔧 Herramienta",
    8:  "🚜 Equipo",
    16: "⚙️ Auxiliar",
    32: "📄 Concepto",
    64: "🚛 Flete",
    128:"🏗️ Trabajo",
}


class TablaInsumos(TreeTableWidget):
    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 130])
        })

    def poblar(self, insumos: list[dict], claves_con_apu: set[str] | None = None):
        """
        Puebla la tabla desde una lista de dicts devuelta por InsumoRepo.
        Si claves_con_apu se provee, antepone ▶ a la descripción de compuestos.
        """
        self.clear()
        for ins in insumos:
            clave     = ins.get("clave", "")
            tipo_id   = ins.get("tipo_id") or ins.get("tipo", 0)
            tipo_txt  = TIPO_NOMBRE.get(tipo_id) or ins.get("tipo_nombre") or f"Tipo {tipo_id}"
            precio    = ins.get("costo_final", 0) or 0
            desc      = ins.get("descripcion") or ins.get("descripcion_corta") or ""
            if claves_con_apu and clave in claves_con_apu:
                desc = f"\u25b6 {desc}"
            self.add_row([
                clave,
                desc,
                ins.get("unidad", "") or "",
                f"${precio:,.2f}",
                tipo_txt,
            ], editable=False)
