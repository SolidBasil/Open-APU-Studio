"""
insumos.py
==========
Tabla plana del catálogo de insumos.

Uso:
    from frontend.widgets.insumos import TablaInsumos
"""

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QHeaderView
from frontend.widgets.base import TreeTableWidget
from backend.db import Config


# ── Configuración de columnas ─────────────────────────────────────

COLUMNAS = [
    "Clave", "Descripción", "Unidad", "Precio", "Tipo",
    "Familia", "Proveedor", "F. Precio", "Desc. Corta", "Costo MN", "Costo ME",
]
EDITABLE = frozenset()

# ── Mapeo tipo_id → nombre ───────────────────────────────────────

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


# ── Tabla plana de insumos ────────────────────────────────────────

class TablaInsumos(TreeTableWidget):
    _HEADER_KEY = "insumos_header_state"

    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 120, 120, 140, 85, 140, 95, 95])
        })
        # columnas de detalle ocultas por defecto
        for c in (7, 8, 9, 10):
            self.setColumnHidden(c, True)
        self._restore_header_state()

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

    # ── Poblado de la tabla ───────────────────────────────────────

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
                ins.get("familia_nombre") or "",
                ins.get("proveedor_nombre") or "",
                ins.get("fecha_precio") or "",
                ins.get("descripcion_corta") or "",
                f"${ins.get('costo_mn', 0) or 0:,.2f}",
                f"${ins.get('costo_me', 0) or 0:,.2f}",
            ], editable=False)
