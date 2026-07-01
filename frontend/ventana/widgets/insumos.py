"""
insumos.py
==========
Tabla plana del catálogo de insumos.

Nota sobre identificadores:
    La navegación interna (rastrear, editar, abrir APU) siempre usa el `id`
    (INTEGER PRIMARY KEY) del insumo, guardado en UserRole de la columna 0.
    La columna "Clave" muestra clave_opus — el código original de OPUS — y
    es puramente referencial: queda oculta por defecto y solo es útil para
    quien importó datos de OPUS y quiere seguir reconociendo sus códigos.

Uso:
    from frontend.widgets.insumos import TablaInsumos
"""

from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtWidgets import QHeaderView, QMenu
from frontend.ventana.widgets.base import TreeTableWidget
from backend.database.db import Config


# ── Configuración de columnas ─────────────────────────────────────

COLUMNAS = [
    "Clave", "Descripción", "Unidad", "Precio", "Tipo",
    "Familia", "Proveedor", "F. Precio", "Desc. Corta", "Costo MN", "Costo ME", "Hash",
]
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
    """Tabla plana del catálogo de insumos (sin jerarquía)."""
    _HEADER_KEY = "insumos_header_state"
    rastrear_insumo    = Signal(int)
    editar_descripcion = Signal(int, str)
    editar_precio      = Signal(int, float)

    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 120, 120, 140, 85, 140, 95, 95, 90])
        })
        self.header().setMaximumSectionSize(400)
        for c in (0, 7, 8, 9, 10, 11):
            self.setColumnHidden(c, True)
        self._search_cols = {1, 5}
        self._restore_header_state()

    def contextMenuEvent(self, event):
        items = self.selectedItems()
        if len(items) != 1:
            super().contextMenuEvent(event)
            return
        item = items[0]
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        act_rastrear = menu.addAction("\U0001f50d Rastrear uso")
        act_rastrear.triggered.connect(lambda: self._emit_rastrear(item))
        menu.addSeparator()
        act_desc   = menu.addAction("\u270f\ufe0f Editar descripción")
        act_precio = menu.addAction("\U0001f4b2 Editar precio")
        act_desc.triggered.connect(lambda: self._emit_editar_descripcion(item))
        act_precio.triggered.connect(lambda: self._emit_editar_precio(item))
        if not insumo_id:
            act_rastrear.setEnabled(False)
            act_desc.setEnabled(False)
            act_precio.setEnabled(False)
        menu.exec(event.globalPos())

    def _emit_rastrear(self, item):
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if insumo_id:
            self.rastrear_insumo.emit(insumo_id)

    def _emit_editar_descripcion(self, item):
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        desc = item.text(1).lstrip("\u25b6").strip()
        if insumo_id:
            self.editar_descripcion.emit(insumo_id, desc)

    def _emit_editar_precio(self, item):
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        precio_txt = item.text(3).replace("$", "").replace(",", "").strip()
        try:
            precio = float(precio_txt)
        except ValueError:
            precio = 0.0
        if insumo_id:
            self.editar_precio.emit(insumo_id, precio)

    def _header_context_menu(self, pos):
        super()._header_context_menu(pos)
        self._save_header_state()

    def _save_header_state(self):
        raw = self.header().saveState()
        Config.set(self._HEADER_KEY, raw.toBase64().data().decode("ascii"))

    def _restore_header_state(self):
        saved = Config.get(self._HEADER_KEY)
        if saved:
            self.header().restoreState(QByteArray.fromBase64(saved.encode("ascii")))

    def poblar(self, insumos: list[dict], ids_con_apu: set[int] | None = None):
        """Puebla la tabla. ids_con_apu antepone ▶ a insumos compuestos."""
        self.clear()
        for ins in insumos:
            insumo_id  = ins.get("id")
            clave_opus = ins.get("clave_opus") or ""
            tipo_id    = ins.get("tipo_id") or ins.get("tipo", 0)
            tipo_txt   = TIPO_NOMBRE.get(tipo_id) or ins.get("tipo_nombre") or f"Tipo {tipo_id}"
            precio     = ins.get("costo_final", 0) or 0
            desc       = ins.get("descripcion") or ins.get("descripcion_corta") or ""
            if ids_con_apu and insumo_id in ids_con_apu:
                desc = f"\u25b6 {desc}"
            row_item = self.add_row([
                clave_opus,
                desc,
                ins.get("unidad", "") or "",
                f"${precio:,.2f}",
                tipo_txt,
                (lambda f, s: f"{f} › {s}" if s else f)(
                    ins.get("familia_nombre") or "",
                    ins.get("subfamilia_nombre") or "",
                ),
                ins.get("proveedor_nombre") or "",
                ins.get("fecha_precio") or "",
                ins.get("descripcion_corta") or "",
                f"${ins.get('costo_mn', 0) or 0:,.2f}",
                f"${ins.get('costo_me', 0) or 0:,.2f}",
                ins.get("hash") or "",
            ], editable=False)
            if row_item is not None:
                row_item.setData(0, Qt.ItemDataRole.UserRole, insumo_id)
