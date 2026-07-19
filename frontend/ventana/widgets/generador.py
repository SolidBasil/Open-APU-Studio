"""
generador.py
============
Tabla de renglones de un generador de obra.

Hereda TreeTableWidget — mismo patrón que TablaApuDetalle.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView

from frontend.ventana.widgets.base import TreeTableWidget

# Columnas: Ubicación, Veces, Largo, Ancho, Alto, Subtotal, Notas
COLUMNAS = ["Ubicación", "Veces", "Largo", "Ancho", "Alto", "Subtotal", "Notas"]
EDITABLE = {0, 1, 2, 3, 4, 6}  # todo excepto Subtotal (col 5)


class TablaGenerador(TreeTableWidget):
    """Tabla editable de renglones de un generador de obra."""

    # Señales
    renglon_editado = Signal(int, dict)   # (renglon_id, campos)
    renglon_nuevo = Signal(dict)          # (campos_iniciales)
    renglon_eliminar = Signal(int)        # (renglon_id)

    _HEADER_KEY = "generador_renglones_header_state"

    def __init__(self, parent=None):
        super().__init__(
            COLUMNAS,
            editable_cols=EDITABLE,
            flat=True,
            parent=parent,
        )
        self.set_column_modes({
            0: (QHeaderView.ResizeMode.Interactive, 180),
            1: (QHeaderView.ResizeMode.Interactive, 70),
            2: (QHeaderView.ResizeMode.Interactive, 70),
            3: (QHeaderView.ResizeMode.Interactive, 70),
            4: (QHeaderView.ResizeMode.Interactive, 70),
            5: (QHeaderView.ResizeMode.Interactive, 90),
            6: (QHeaderView.ResizeMode.Stretch, None),
        })
        self._search_cols = {0, 6}
        self._renglon_ids: dict[int, int] = {}  # item_id → renglon_id
        self.itemChanged.connect(self._on_item_changed)

    def poblar(self, renglones: list[dict]):
        """Llena la tabla con renglones del generador."""
        self.blockSignals(True)
        try:
            self.clear()
            self._renglon_ids.clear()
            for rn in renglones:
                item = self.add_row([
                    rn.get("ubicacion", ""),
                    f"{rn.get('veces', 1):.2f}",
                    f"{rn.get('largo') or 0:.4f}" if rn.get("largo") is not None else "",
                    f"{rn.get('ancho') or 0:.4f}" if rn.get("ancho") is not None else "",
                    f"{rn.get('alto') or 0:.4f}" if rn.get("alto") is not None else "",
                    f"{rn.get('subtotal', 0):.4f}",
                    rn.get("notas", "") or "",
                ])
                rid = rn["id"]
                item_id = id(item)
                self._renglon_ids[item_id] = rid
                item.setData(0, Qt.ItemDataRole.UserRole, rid)
        finally:
            self.blockSignals(False)

    def _on_item_changed(self, item, column):
        """Persiste edición inline de renglones."""
        renglon_id = self._renglon_ids.get(id(item))
        if not renglon_id or column not in EDITABLE:
            return
        text = item.text(column).strip()
        campos = {}
        if column == 0:
            campos["ubicacion"] = text
        elif column in (1, 2, 3, 4):
            key = {1: "veces", 2: "largo", 3: "ancho", 4: "alto"}[column]
            try:
                campos[key] = float(text) if text else None
            except ValueError:
                return
        elif column == 6:
            campos["notas"] = text
        if campos:
            self.renglon_editado.emit(renglon_id, campos)
