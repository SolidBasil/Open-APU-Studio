"""
generador.py
============
Tabla de renglones de un generador de obra.

Hereda TreeTableWidget — mismo patrón que TablaApuDetalle.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QAbstractItemView

from frontend.ventana.widgets.base import TreeTableWidget, EMPTY_ROLE, blocked_signals
from frontend.ventana.iconos import icono
from backend.database.event_bus import GeneradorActualizado, ProyectoRecalculado

# Medidas CAD del renglón (una entrada por celda — Veces/Largo/Ancho/Alto),
# cacheadas en el propio item (col 0, cubre toda la fila) para poder
# acumular puntos de un contador o agregar la medición de OTRA celda sin
# pisar lo que ya había — ver medidas_efectivas() y aplicar_medicion().
CAD_MEDIDAS_ROLE = Qt.ItemDataRole.UserRole + 70


def medidas_efectivas(rn: dict) -> dict:
    """Combina cad_medidas (v12+: una medición independiente por cada
    celda Veces/Largo/Ancho/Alto) con las columnas legacy de una sola
    medición por renglón entero (cad_tipo_medicion/cad_geometria/
    cad_campo/cad_origen_archivo, anteriores a v12) en una sola vista
    uniforme: {"largo": {"tipo":..., "puntos":[...], "archivo":...}, ...}.

    Antes de v12 medir una celda pisaba esas 4 columnas enteras — así
    que medir Ancho después de Largo borraba el trazo de Largo, porque
    ambos vivían en la MISMA columna de la BD. v12 le da a cada celda
    su propia entrada dentro de un solo JSON, y esto es lo que unifica
    la lectura de ambos formatos para que compilador/tabla/visor no
    tengan que preocuparse por cuál usó cada renglón.

    Reusado por TablaGenerador (tabla) y VisorCadWidget (overlays del
    plano) y GeneradorMixin (al persistir una edición de nodos) — para
    no repetir este merge en tres lados.
    """
    import json
    medidas: dict = {}
    raw = rn.get("cad_medidas")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                medidas = dict(parsed)
        except (ValueError, TypeError):
            pass
    campo_legacy = rn.get("cad_campo")
    if campo_legacy and campo_legacy not in medidas:
        geom = rn.get("cad_geometria")
        puntos = []
        if geom:
            try:
                puntos = json.loads(geom)
            except (ValueError, TypeError):
                puntos = []
        medidas[campo_legacy] = {
            "tipo": rn.get("cad_tipo_medicion"),
            "puntos": puntos,
            "archivo": rn.get("cad_origen_archivo"),
        }
    return medidas

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
    renglon_seleccionado = Signal(object)  # renglon_id (int) o None — para resaltar su trazo en el plano

    _HEADER_KEY = "generador_renglones_header_state"
    _REORDER_ENABLED = True

    # Fase C: refresco remoto — otro cliente tocó generadores (o cualquier
    # recalc que afecte cantidad_total). Sin esto, el panel solo se
    # refrescaba tras writes propios del mixin. El overlay CAD lo refresca
    # el mixin en su propio poblar; aquí solo filas.
    EVENTOS_SUSCRITOS = {
        GeneradorActualizado: '_on_generador_actualizado',
        ProyectoRecalculado: '_on_generador_actualizado',
    }

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
        self.itemSelectionChanged.connect(self._on_seleccion_cambiada)

        # ── Drag and drop entre pestañas de Generadores (misma lógica
        # que APU/Presupuesto — ver TablaApuDetalle) ─────────────────
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._drop_objetivo = None  # (item, 'arriba'|'abajo') — ver paintEvent
        self._en_seleccion_programatica = False  # ver seleccionar_renglon_por_id

    def _on_seleccion_cambiada(self):
        """Emite el renglon_id de la fila seleccionada (o None) — el
        mixin lo usa para resaltar el trazo de esa medición en el plano
        CAD (traza tabla→plano). No se emite si la selección la disparó
        seleccionar_renglon_por_id (traza inversa plano→tabla), para no
        generar un eco de señales entre plano y tabla."""
        if self._en_seleccion_programatica:
            return
        items = self.selectedItems()
        rid = self._renglon_ids.get(id(items[0])) if items else None
        self.renglon_seleccionado.emit(rid)

    def seleccionar_renglon_por_id(self, renglon_id: int):
        """Selecciona en la tabla el renglón dado — traza inversa
        plano→tabla: al clickear un trazo en el visor CAD, resalta su
        fila correspondiente aquí."""
        for item_id, rid in self._renglon_ids.items():
            if rid != renglon_id:
                continue
            for i in range(self.topLevelItemCount()):
                it = self.topLevelItem(i)
                if id(it) == item_id:
                    self._en_seleccion_programatica = True
                    self.setCurrentItem(it)
                    self.scrollToItem(it)
                    self._en_seleccion_programatica = False
                    return

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

        with blocked_signals(self):
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

    def _on_generador_actualizado(self, evento) -> None:
        """Refresco remoto (Fase C): otro cliente tocó generadores o hubo
        un recalc que pudo cambiar cantidad_total.

        Filtra por generador_id cuando el evento lo trae (GeneradorActualizado);
        ProyectoRecalculado es grueso y siempre repuebla. poblar() preserva
        selección y bloquea señales — pero un editor abierto se pierde,
        igual que en TablaArbol ante recalcs remotos. El overlay CAD lo
        refresca el mixin en su siguiente poblar propio.
        """
        gid = getattr(evento, "generador_id", None)
        if gid is not None and gid != self._generador_id:
            return
        api = getattr(self, "_api", None)
        if api is None or self._generador_id is None:
            return
        try:
            self.poblar(api.generador_renglones(self._generador_id))
        except Exception:
            pass

    _NOMBRE_TIPO_CAD = {
        "linea": "Línea", "polilinea": "Polilínea", "area": "Área",
        "punto": "Punto", "contador": "Contador",
    }
    _CAMPO_A_COLUMNA = {"veces": 2, "largo": 3, "ancho": 4, "alto": 5}

    def _marcar_origen_cad(self, item, rn: dict):
        """Ícono de regla junto al número de CADA celda que tenga su
        propia medición CAD (Veces/Largo/Ancho/Alto pueden venir cada
        una de una línea distinta — ver medidas_efectivas) — para poder
        distinguir a simple vista qué dato viene del plano en vez de
        haberse tecleado a mano. El tooltip trae el detalle exacto
        (tipo de medición, archivo de origen, puntos) para poder
        auditarlo sin ir a buscar nada en la base de datos.
        """
        if rn.get("origen") != "cad":
            return
        medidas = medidas_efectivas(rn)
        item.setData(0, CAD_MEDIDAS_ROLE, medidas)
        for campo, info in medidas.items():
            col = self._CAMPO_A_COLUMNA.get(campo)
            if col is None:
                continue
            tipo = self._NOMBRE_TIPO_CAD.get(info.get("tipo"), info.get("tipo") or "?")
            detalle = f"Medido en CAD — {tipo}"
            archivo = info.get("archivo")
            if archivo:
                detalle += f"\nArchivo: {archivo}"
            puntos = info.get("puntos") or []
            if puntos:
                coords = "; ".join(f"({x:.2f}, {y:.2f})" for x, y in puntos)
                detalle += f"\nPuntos: {coords}"
            item.setIcon(col, icono("ruler", 14))
            item.setToolTip(col, detalle)

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
        with blocked_signals(self):
            item.setText(column, "" if val is None else f"{val:.4f}")

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
                          tipo_cad: str | None = None, puntos: list | None = None,
                          archivo: str | None = None, col: int | None = None) -> int | None:
        """Escribe un valor medido en el CAD dentro de una celda del
        renglón actualmente seleccionado (Veces, Largo, Ancho o Alto).

        `col`: columna destino explícita (2=Veces, 3=Largo, 4=Ancho,
        5=Alto) — la pasa el combo "Medir hacia" del panel CAD (ver
        _on_cad_measurement en mixins/generador.py). Si se omite, cae en
        currentColumn() por compatibilidad, pero eso es justo lo que
        causaba que toda medición terminara en la última celda que
        hubiera tenido el foco en la tabla ANTES de perderlo al clickear
        el visor — con `col` explícito ya no depende de ese estado.

        `modo="set"` sobrescribe (línea/polilínea/área); `modo="sumar"`
        acumula sobre el valor ya presente (punto/conteo — cada clic suma 1).
        Devuelve el renglon_id afectado, o None si no hay una celda válida
        seleccionada (para que quien llama pueda avisar al usuario que
        debe elegir una celda, o para saber a qué renglón mostrarle los
        grips de edición justo después de medir).

        `tipo_cad` + `puntos`: cuando la medición viene de una herramienta
        CAD (ver _on_cad_measurement en mixins/generador.py), además del
        valor numérico se guardan los puntos exactos de dónde se midió en
        el dibujo (origen="cad", cad_tipo_medicion, cad_geometria en JSON)
        — para poder auditar después de dónde salió cada renglón, en vez
        de solo tener un número sin rastro de su origen.

        `archivo`: nombre del DXF activo al momento de medir
        (cad_origen_archivo) — un generador solo liga un plano a la vez,
        así que si más adelante se reemplaza por otro, esto deja
        registro de en qué archivo se midió originalmente cada renglón.
        """
        item = self.currentItem()
        col = col if col is not None else self.currentColumn()
        if item is None or col not in COLUMNAS_MEDIBLES:
            return None
        if item.data(0, EMPTY_ROLE):
            return None
        renglon_id = self._renglon_ids.get(id(item))
        if renglon_id is None:
            return None

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
            # Medidas de las OTRAS celdas de este renglón (ej. si Largo ya
            # se midió antes) — se fusiona, nunca se pisa: antes de v12,
            # medir Ancho después de Largo sobrescribía la única columna
            # de geometría del renglón entero y borraba el trazo de Largo.
            medidas = dict(item.data(0, CAD_MEDIDAS_ROLE) or {})
            if tipo_cad == "contador":
                # A diferencia de línea/polilínea/área (un solo trazo que se
                # sobrescribe entero), el contador se arma de MUCHOS clics
                # sueltos sobre la misma celda — hay que ACUMULAR los puntos
                # de cada clic (si solo se guardara el último, se perdería
                # el registro de dónde estaban los elementos anteriores).
                anteriores = (medidas.get(campo) or {}).get("puntos") or []
                puntos_finales = list(anteriores) + list(puntos or [])
            else:
                puntos_finales = list(puntos or [])
            medidas[campo] = {"tipo": tipo_cad, "puntos": puntos_finales, "archivo": archivo}
            item.setData(0, CAD_MEDIDAS_ROLE, medidas)
            campos = {
                campo: nuevo,
                "origen": "cad",
                "cad_medidas": json.dumps(medidas),
            }
            # TablaGenerador nunca llama a self._api directo — siempre
            # emite y deja que el mixin (que sí lo tiene) persista. Se
            # reusa la misma señal/handler que ya usa la edición inline
            # normal (renglon_editado -> _on_renglon_editado_tab), solo
            # que aquí el dict de campos trae también los de auditoría.
            with blocked_signals(self):
                item.setText(col, texto)
            self.renglon_editado.emit(renglon_id, campos)
        else:
            item.setText(col, texto)  # dispara itemChanged → _on_item_changed → persiste
        return renglon_id
