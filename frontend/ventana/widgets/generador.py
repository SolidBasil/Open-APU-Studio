"""
generador.py
============
Tabla de renglones de un generador de obra.

Hereda TreeTableWidget — mismo patrón que TablaApuDetalle.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

from frontend.ventana.widgets.base import TreeTableWidget, EMPTY_ROLE

# Columnas: Eje, Tramo, Veces, Largo, Ancho, Alto, Subtotal, Notas
COLUMNAS = ["Eje", "Tramo", "Veces", "Largo", "Ancho", "Alto", "Subtotal", "Notas"]
EDITABLE = {0, 1, 2, 3, 4, 5, 7}  # todo excepto Subtotal (col 6)
COLUMNAS_MEDIBLES = {2, 3, 4, 5}  # Veces, Largo, Ancho, Alto — reciben mediciones CAD


class TablaGenerador(TreeTableWidget):
    """Tabla editable de renglones de un generador de obra."""

    # Señales
    renglon_editado = Signal(int, dict)   # (renglon_id, campos)
    renglon_nuevo = Signal(dict)          # (campos_iniciales)
    renglon_eliminar = Signal(list)       # (renglon_ids)
    total_actualizado = Signal(float)     # SUM(subtotal) de renglones activos
    nuevo_renglon = Signal()              # clic en fila vacía

    _HEADER_KEY = "generador_renglones_header_state"
    _REORDER_ENABLED = True

    def __init__(self, parent=None, generador_id: int | None = None):
        super().__init__(
            COLUMNAS,
            editable_cols=EDITABLE,
            flat=True,
            parent=parent,
        )
        self._generador_id = generador_id  # ver dropEvent/_on_drop_generador
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

        # ── Drag and drop entre pestañas de Generadores (misma lógica
        # que APU/Presupuesto — ver TablaApuDetalle) ─────────────────
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._drop_objetivo = None  # (item, 'arriba'|'abajo') — ver paintEvent

    def poblar(self, renglones: list[dict], seleccionar_id: int | None = None):
        """Llena la tabla con renglones del generador.
        Si seleccionar_id se omite, preserva la selección actual si existe.
        """
        sel_ids = [it.data(0, Qt.ItemDataRole.UserRole) for it in self.selectedItems()
                   if not it.data(0, EMPTY_ROLE) and it.data(0, Qt.ItemDataRole.UserRole) is not None]
        if not sel_ids:
            sel_ids = list(getattr(self, '_drag_sel_ids', []))
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

        if sel_ids:
            for i in range(self.topLevelItemCount()):
                it = self.topLevelItem(i)
                if it.data(0, Qt.ItemDataRole.UserRole) in sel_ids:
                    it.setSelected(True)

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
            ids = [it.data(0, Qt.ItemDataRole.UserRole) for it in self.selectedItems()
                   if not it.data(0, EMPTY_ROLE)]
            ids = [rid for rid in ids if rid]
            if ids:
                self.renglon_eliminar.emit(ids)
            return
        super().keyPressEvent(event)

    def _al_click_fila_vacia(self):
        self.nuevo_renglon.emit()

    def set_generador_id(self, generador_id: int | None):
        """Actualiza a qué generador está ligada esta tabla para el drag
        and drop (ver dropEvent) — necesario porque, en el panel
        original, la MISMA instancia de TablaGenerador se repuebla para
        distintos generadores según cuál se seleccione en el árbol."""
        self._generador_id = generador_id

    def _get_reorder_info(self):
        win = self.window()
        handler = getattr(win, '_on_drop_generador', None) if win else None
        return handler, self._generador_id

    # ── Drag and drop entre pestañas de Generadores ──────────────
    # Arrastrar renglones (selección múltiple incluida) y soltarlos en
    # otro renglón de esta MISMA tabla los reordena; soltarlos en OTRA
    # pestaña de Generadores abierta los mueve ahí (Ctrl los copia) —
    # ver GeneradorMixin._on_drop_generador. Misma filosofía que
    # TablaApuDetalle: tabla plana, solo "arriba"/"abajo", nunca "dentro".

    def _fila_destino_valida(self, item) -> bool:
        return item is not None and not item.data(0, EMPTY_ROLE)

    def _calcular_posicion_drop(self, item, y_evento: int) -> str:
        rect = self.visualItemRect(item)
        if rect.height() <= 0:
            return "abajo"
        return "arriba" if y_evento < rect.center().y() else "abajo"

    _DRAG_ICON = "layers"
    _DRAG_MIME_LABEL = "renglón(es) de Generador"
    _DROP_ACCEPTS_FOREIGN_CLASS = True

    def dropEvent(self, event):
        """Calcula (generador_destino=self._generador_id, antes_de_id) y
        delega en self.window()._on_drop_generador(). Los renglones
        arrastrados se leen de event.source() (no de self): si el drag
        viene de OTRA pestaña de Generadores, self.selectedItems() sería
        la selección de ESTA tabla, no la que se está arrastrando."""
        self._drop_objetivo = None
        self.viewport().update()

        origen = event.source()
        if not isinstance(origen, TablaGenerador):
            event.ignore()
            return
        item_destino = self.itemAt(event.position().toPoint())
        if not self._fila_destino_valida(item_destino):
            event.ignore()
            return

        arrastrados = [it for it in origen.selectedItems() if self._fila_destino_valida(it)]
        if not arrastrados:
            ids_arrastrados = list(getattr(origen, '_drag_sel_ids', []))
        else:
            # selectedItems() sigue el orden de selección, no el visual
            arrastrados.sort(key=lambda it: origen.visualItemRect(it).top())
            ids_arrastrados = [it.data(0, Qt.ItemDataRole.UserRole) for it in arrastrados]
        ids_arrastrados = [rid for rid in ids_arrastrados if rid is not None]
        if not ids_arrastrados:
            event.ignore()
            return
        if arrastrados and item_destino in arrastrados:
            event.ignore()
            return

        posicion = self._calcular_posicion_drop(item_destino, event.position().toPoint().y())
        hermanos_widget = [self.topLevelItem(i) for i in range(self.topLevelItemCount())
                            if self._fila_destino_valida(self.topLevelItem(i))]
        idx = hermanos_widget.index(item_destino)
        if posicion == "arriba":
            antes_de_id = item_destino.data(0, Qt.ItemDataRole.UserRole)
        else:
            siguiente = hermanos_widget[idx + 1] if idx + 1 < len(hermanos_widget) else None
            antes_de_id = siguiente.data(0, Qt.ItemDataRole.UserRole) if siguiente is not None else None

        copiar = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ventana = self.window()
        handler = getattr(ventana, '_on_drop_generador', None)
        if handler is None or self._generador_id is None:
            event.ignore()
            return
        ok = handler(ids_arrastrados, self._generador_id, antes_de_id, copiar)
        if ok:
            event.acceptProposedAction()
        else:
            event.ignore()

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
