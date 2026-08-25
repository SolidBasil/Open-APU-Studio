"""
generador.py
============
Tabla de renglones de un generador de obra.

Hereda TreeTableWidget — mismo patrón que TablaApuDetalle.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

from frontend.ventana.widgets.base import TreeTableWidget, EMPTY_ROLE
from frontend.ventana.iconos import icono

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
    delete_solicitado = Signal(list)      # (renglon_ids) — tecla Delete, pide confirmación antes de eliminar
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
                self._marcar_origen_cad(item, rn)
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

    _NOMBRE_TIPO_CAD = {
        "linea": "Línea", "polilinea": "Polilínea", "area": "Área",
        "punto": "Punto", "contador": "Contador",
    }

    def _marcar_origen_cad(self, item, rn: dict):
        """Ícono de regla en Eje (col 0) para renglones medidos con una
        herramienta CAD (ver aplicar_medicion / _on_cad_measurement en
        mixins/generador.py) — para poder distinguir a simple vista un
        renglón medido del dibujo de uno tecleado a mano, y el tooltip
        trae el detalle exacto (tipo de medición + los puntos del
        dibujo donde se tomó) para poder auditarlo sin tener que ir a
        buscar nada en la base de datos.
        """
        if rn.get("origen") != "cad":
            return
        item.setIcon(0, icono("ruler", 16))
        tipo = self._NOMBRE_TIPO_CAD.get(rn.get("cad_tipo_medicion"), rn.get("cad_tipo_medicion") or "?")
        detalle = f"Medido en CAD — {tipo}"
        geom = rn.get("cad_geometria")
        if geom:
            import json
            try:
                puntos = json.loads(geom)
                coords = "; ".join(f"({x:.2f}, {y:.2f})" for x, y in puntos)
                detalle += f"\nPuntos: {coords}"
            except (ValueError, TypeError):
                pass
        item.setToolTip(0, detalle)

    def _add_empty_row(self):
        item = self.add_row(
            ["", "", "", "", "", "", "", ""],
            editable=True,
        )
        item.setData(0, EMPTY_ROLE, True)
        item.setToolTip(0, "Escribe cualquier dato de la fila (Eje, Tramo, "
                            "Veces, Largo, Ancho, Alto o Notas) para "
                            "agregar un renglón nuevo")
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
                # Antes: emitía renglon_eliminar directo, sin confirmar
                # (a diferencia de otras tablas de la app, donde eliminar
                # siempre pide confirmación — ver _on_delete_solicitado_tab
                # en mixins/generador.py). Se resuelve pidiendo esa misma
                # confirmación acá, en vez de emitir directo a la
                # eliminación.
                self.delete_solicitado.emit(ids)
            return
        super().keyPressEvent(event)

    def _al_click_fila_vacia(self):
        """No-op: con la fila vacía editable (ver _add_empty_row), un clic
        simple solo selecciona la celda — ya no crea un renglón en blanco
        aparte. Escribir cualquier dato es lo que agrega el renglón (ver
        _on_fila_vacia_editada)."""
        pass

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

    @staticmethod
    def _campo_desde_columna(column: int, texto: str):
        """Traduce (columna, texto de la celda) -> (nombre_campo, valor)
        para generador_renglon_guardar(). None si la columna no mapea a
        ningún campo (Subtotal, col 6, es calculado). Compartido entre
        _on_item_changed (fila real) y _on_fila_vacia_editada (fila
        vacía) para no repetir este mapeo dos veces.
        """
        if column == 0:
            return "eje", texto
        if column == 1:
            return "tramo", texto
        if column in (2, 3, 4, 5):
            key = {2: "veces", 3: "largo", 4: "ancho", 5: "alto"}[column]
            try:
                return key, (float(texto) if texto else None)
            except ValueError:
                return None
        if column == 7:
            return "notas", texto
        return None

    def _on_item_changed(self, item, column):
        """Persiste edición inline de renglones."""
        if item.data(0, EMPTY_ROLE):
            self._on_fila_vacia_editada(item, column)
            return
        renglon_id = self._renglon_ids.get(id(item))
        if not renglon_id or column not in EDITABLE:
            return
        texto = item.text(column).strip()
        resultado = self._campo_desde_columna(column, texto)
        if resultado is None and column in (2, 3, 4, 5) and texto:
            # Antes: nada. La celda se quedaba mostrando el texto
            # inválido tecleado (ej. "abc" en Largo) mientras la BD
            # seguía con el valor anterior — pantalla y BD
            # desincronizadas, sin ningún aviso de que no se guardó
            # (mismo fix que en widgets/apu.py e insumos, ver ahí).
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self.window(), "Valor inválido",
                                 "Escribe un número (ej. 3.5).")
            self._revertir_celda_numerica(item, renglon_id, column)
            return
        campos = dict([resultado]) if resultado else {}
        if campos:
            self.renglon_editado.emit(renglon_id, campos)

    def _revertir_celda_numerica(self, item, renglon_id: int, column: int):
        """Devuelve el texto de una celda numérica (Veces/Largo/Ancho/Alto)
        a lo que de verdad tiene la BD, tras un error de validación."""
        campo = {2: "veces", 3: "largo", 4: "ancho", 5: "alto"}.get(column)
        if not campo:
            return
        renglones = self._api.generador_renglones(self._generador_id)
        actual = next((r for r in renglones if r.get("id") == renglon_id), None)
        if actual is None:
            return
        val = actual.get(campo)
        self.blockSignals(True)
        item.setText(column, "" if val is None else f"{val:.4f}")
        self.blockSignals(False)

    def _on_fila_vacia_editada(self, item, column):
        """Escribir cualquier dato en la fila vacía final agrega un
        renglón nuevo — comportamiento tipo Excel, mismo patrón que
        Insumos/Presupuesto/APU (ver paneles.py / mixins/apu.py).

        A diferencia de esas tablas, aquí no hay ningún campo "obligatorio"
        ni ninguna referencia a un catálogo — un renglón es solo medidas
        (Eje, Tramo, Veces, Largo, Ancho, Alto, Notas), así que basta con
        que CUALQUIER columna tenga contenido para crear el renglón.

        Se difiere con QTimer.singleShot(0) — y no solo el lado del mixin
        (ver _on_renglon_nuevo_tab) — porque escribir varias columnas de
        la misma fila en sucesión rápida (ej. pegar varias celdas) dispara
        itemChanged una vez por columna: sin este diferido + guard por
        item, cada columna creaba SU PROPIO renglón por separado (2-3
        renglones duplicados en vez de uno con todos los campos juntos).
        Al diferir el escaneo, se lee el estado final del item una sola
        vez, después de que todas las columnas ya se escribieron.
        """
        if column not in EDITABLE:
            return
        if getattr(self, "_fila_vacia_programada", None) is item:
            return  # ya hay un envío programado para este mismo item
        self._fila_vacia_programada = item
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda it=item: self._emitir_fila_vacia(it))

    def _emitir_fila_vacia(self, item):
        self._fila_vacia_programada = None
        campos = {}
        for col in EDITABLE:
            texto = item.text(col).strip()
            if not texto:
                continue
            resultado = self._campo_desde_columna(col, texto)
            if resultado:
                campos[resultado[0]] = resultado[1]
        if campos:
            self.renglon_nuevo.emit(campos)

    def aplicar_medicion(self, valor: float, modo: str = "set", *,
                          tipo_cad: str | None = None, puntos: list | None = None) -> bool:
        """Escribe un valor medido en el CAD dentro de la celda actualmente
        seleccionada (Veces, Largo, Ancho o Alto).

        `modo="set"` sobrescribe (línea/polilínea/área); `modo="sumar"`
        acumula sobre el valor ya presente (punto/conteo — cada clic suma 1).
        Devuelve False si no hay una celda válida seleccionada, para que
        quien llama pueda avisar al usuario que debe elegir una celda.

        `tipo_cad` + `puntos`: cuando la medición viene de una herramienta
        CAD (ver _on_cad_measurement en mixins/generador.py), además del
        valor numérico se guardan los puntos exactos de dónde se midió en
        el dibujo (origen="cad", cad_tipo_medicion, cad_geometria en JSON)
        — para poder auditar después de dónde salió cada renglón, en vez
        de solo tener un número sin rastro de su origen.
        """
        item = self.currentItem()
        col = self.currentColumn()
        if item is None or col not in COLUMNAS_MEDIBLES:
            return False
        if item.data(0, EMPTY_ROLE):
            return False
        renglon_id = self._renglon_ids.get(id(item))
        if renglon_id is None:
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

        campo = {2: "veces", 3: "largo", 4: "ancho", 5: "alto"}.get(col)
        if campo and tipo_cad:
            import json
            campos = {
                campo: nuevo,
                "origen": "cad",
                "cad_tipo_medicion": tipo_cad,
                "cad_geometria": json.dumps(puntos or []),
            }
            # TablaGenerador nunca llama a self._api directo — siempre
            # emite y deja que el mixin (que sí lo tiene) persista. Se
            # reusa la misma señal/handler que ya usa la edición inline
            # normal (renglon_editado -> _on_renglon_editado_tab), solo
            # que aquí el dict de campos trae también los de auditoría.
            self.blockSignals(True)
            item.setText(col, texto)
            self.blockSignals(False)
            self.renglon_editado.emit(renglon_id, campos)
        else:
            item.setText(col, texto)  # dispara itemChanged → _on_item_changed → persiste
        return True
