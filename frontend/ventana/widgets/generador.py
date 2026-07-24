"""
generador.py
============
Tabla de renglones de un generador de obra.

Hereda TreeTableWidget — mismo patrón que TablaApuDetalle.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView

from frontend.ventana.widgets.base import TreeTableWidget

EMPTY_ROLE = Qt.ItemDataRole.UserRole + 60

# Columnas: Eje, Tramo, Veces, Largo, Ancho, Alto, Subtotal, Notas
COLUMNAS = ["Eje", "Tramo", "Veces", "Largo", "Ancho", "Alto", "Subtotal", "Notas"]
EDITABLE = {0, 1, 2, 3, 4, 5, 7}  # todo excepto Subtotal (col 6)
COLUMNAS_MEDIBLES = {2, 3, 4, 5}  # Veces, Largo, Ancho, Alto — reciben mediciones CAD


class TablaGenerador(TreeTableWidget):
    """Tabla editable de renglones de un generador de obra."""

    # Señales
    renglon_editado = Signal(int, dict)   # (renglon_id, campos)
    renglon_nuevo = Signal(dict)          # (campos_iniciales)
    renglon_eliminar = Signal(int)        # (renglon_id)
    total_actualizado = Signal(float)     # SUM(subtotal) de renglones activos
    nuevo_renglon = Signal()              # clic en fila vacía

    _HEADER_KEY = "generador_renglones_header_state"

    def __init__(self, parent=None):
        super().__init__(
            COLUMNAS,
            editable_cols=EDITABLE,
            flat=True,
            parent=parent,
        )
        self.set_column_modes({
            0: (QHeaderView.ResizeMode.Interactive, 100),
            1: (QHeaderView.ResizeMode.Interactive, 100),
            2: (QHeaderView.ResizeMode.Interactive, 70),
            3: (QHeaderView.ResizeMode.Interactive, 70),
            4: (QHeaderView.ResizeMode.Interactive, 70),
            5: (QHeaderView.ResizeMode.Interactive, 70),
            6: (QHeaderView.ResizeMode.Interactive, 90),
            7: (QHeaderView.ResizeMode.Stretch, None),
        })
        self._search_cols = {0, 1, 7}
        self._renglon_ids: dict[int, int] = {}  # item_id → renglon_id
        self.itemChanged.connect(self._on_item_changed)
        self.itemClicked.connect(self._on_item_clicked)

    def poblar(self, renglones: list[dict], seleccionar_id: int | None = None):
        """Llena la tabla con renglones del generador.
        Si seleccionar_id se omite, preserva la selección actual si existe.
        """
        cur_item = self.currentItem()
        sel_renglon_id = seleccionar_id
        if sel_renglon_id is None and cur_item is not None:
            sel_renglon_id = cur_item.data(0, Qt.ItemDataRole.UserRole)
        col = self.currentColumn()

        self.blockSignals(True)
        try:
            self.clear()
            self._renglon_ids.clear()
            for rn in renglones:
                item = self.add_row([
                    rn.get("eje", ""),
                    rn.get("tramo", ""),
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

        total = sum(rn.get("subtotal", 0) or 0 for rn in renglones)
        self.total_actualizado.emit(total)
        self._add_empty_row()

        if sel_renglon_id is not None:
            for i in range(self.topLevelItemCount()):
                it = self.topLevelItem(i)
                if it.data(0, Qt.ItemDataRole.UserRole) == sel_renglon_id:
                    self.setCurrentItem(it, col if col >= 0 else 0)
                    break

    def _add_empty_row(self):
        item = self.add_row(
            ["", "Nuevo renglón...", "", "", "", "", "", ""],
            editable=False,
        )
        item.setData(0, EMPTY_ROLE, True)
        self._estilizar_fila_vacia(item)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Insert:
            self.nuevo_renglon.emit()
            return
        if event.key() == Qt.Key.Key_Delete:
            item = self.currentItem()
            if item and not item.data(0, EMPTY_ROLE):
                rid = item.data(0, Qt.ItemDataRole.UserRole)
                if rid:
                    self.renglon_eliminar.emit(rid)
            return
        super().keyPressEvent(event)

    def _on_item_clicked(self, item, column):
        if item.data(0, EMPTY_ROLE):
            self.nuevo_renglon.emit()

    def _on_item_changed(self, item, column):
        """Persiste edición inline de renglones."""
        if item.data(0, EMPTY_ROLE):
            return
        renglon_id = self._renglon_ids.get(id(item))
        if not renglon_id or column not in EDITABLE:
            return
        text = item.text(column).strip()
        campos = {}
        if column == 0:
            campos["eje"] = text
        elif column == 1:
            campos["tramo"] = text
        elif column in (2, 3, 4, 5):
            key = {2: "veces", 3: "largo", 4: "ancho", 5: "alto"}[column]
            try:
                campos[key] = float(text) if text else None
            except ValueError:
                return
        elif column == 7:
            campos["notas"] = text
        if campos:
            self.renglon_editado.emit(renglon_id, campos)

    def aplicar_medicion(self, valor: float, modo: str = "set") -> bool:
        """Escribe un valor medido en el CAD dentro de la celda actualmente
        seleccionada (Veces, Largo, Ancho o Alto).

        `modo="set"` sobrescribe (línea/área); `modo="sumar"` acumula sobre
        el valor ya presente (punto/conteo — cada clic suma 1).
        Devuelve False si no hay una celda válida seleccionada, para que
        quien llama pueda avisar al usuario que debe elegir una celda.
        """
        item = self.currentItem()
        col = self.currentColumn()
        if item is None or col not in COLUMNAS_MEDIBLES:
            return False
        if item.data(0, EMPTY_ROLE):
            return False
        if id(item) not in self._renglon_ids:
            return False

        if modo == "sumar":
            try:
                actual = float(item.text(col).strip() or 0)
            except ValueError:
                actual = 0.0
            nuevo = actual + valor
        else:
            nuevo = valor

        texto = f"{nuevo:.2f}" if col == 2 else f"{nuevo:.4f}"
        item.setText(col, texto)  # dispara itemChanged → _on_item_changed → persiste
        return True
