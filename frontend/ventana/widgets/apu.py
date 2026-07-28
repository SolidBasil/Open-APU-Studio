"""
apu.py (widgets)
=================
TablaApuDetalle: árbol de desglose de un APU — los componentes de un
concepto o de un insumo compuesto.

Extraída de ApuMixin._build_apu_tab() (ver docs/PLAN_REPARACION.md #21).
Antes esta tabla no era una clase propia: se armaba con un QWidget inline
lleno de funciones internas (closures) que capturaban `self` del mixin, y
desconectar_eventos() se inyectaba como atributo dinámico
(`detail.desconectar_eventos = _desconectar`) en vez de vivir como método
de clase.

conectar_eventos()/desconectar_eventos() ahora viven en
TreeTableWidget (widgets/base.py) y se activan declarando
EVENTOS_SUSCRITOS — el mismo mecanismo que usan TablaArbol y
TablaInsumos. Aquí varios eventos comparten un solo método (_on_evento)
porque a los tres les toca la misma reacción: refresco diferido +
reselección de la celda activa.

Sigue el ciclo de vida estándar (ver GUIA_INTERFAZ.md §7.6):

    crear → poblar(resultado) → conectar_eventos(bus, api) → ... → desconectar_eventos()

El widget contenedor (encabezado con título/total + botón "abrir
presupuesto en popup") sigue viviendo en ApuMixin._build_apu_tab(), igual
que antes — no se necesitó envolver esta tabla en un "PestañaApuDetalle"
al estilo PestañaExplosion porque solo hay un único call site que la
construye (a diferencia de explosión, que tiene dos builders distintos
compartiendo el mismo widget).
"""

from PySide6.QtCore import Qt, QTimer, Signal, QPoint
from PySide6.QtWidgets import QComboBox, QDialog, QHeaderView, QMessageBox, QAbstractItemView
from PySide6.QtGui import QColor

from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef, UNIDADES, FORMULA_ROLE, EMPTY_ROLE
from backend.database.event_bus import (
    ApuComponenteActualizado, InsumoActualizado, ProyectoRecalculado,
)
from frontend.ventana.iconos import icono
from frontend.ventana.tipos_insumo import COLOR as _COLOR_TIPO
from frontend.ventana.colores import ACCENT

_TIPO_ID_ROLE = Qt.ItemDataRole.UserRole + 2

# ponytail: mapping totales dict key → tipo_id, mirrors recalculo.py keys
_TOTALES_CLAVE_TIPO = {
    "materiales": 1, "mano_obra": 2, "herramienta": 4,
    "equipo": 8, "auxiliares": 16, "subcontratos": 32,
    "fletes": 64, "trabajos": 128,
}
_TIPO_ID_TO_TOTALES_CLAVE = {v: k for k, v in _TOTALES_CLAVE_TIPO.items()}

COLUMNAS = ["Tipo", "Clave", "Descripción", "Unidad", "P.U.", "Op", "Valor", "Importe",
            "Fórmula", "Creado", "Modificado"]

ANCHOS = [110, 90, 250, 50, 100, 40, 80, 110, 160, 130, 130]

COLUMNAS_CATALOGO = [
    ColumnaDef(0, "Tipo",        "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(1, "Clave",       "Identificación", favorita_default=False, visible_default=False),
    ColumnaDef(2, "Descripción", "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(3, "Unidad",      "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(4, "P.U.",        "Costos",         favorita_default=True,  visible_default=True),
    ColumnaDef(5, "Op",          "Cálculo",        favorita_default=True,  visible_default=True),
    ColumnaDef(6, "Valor",       "Cálculo",        favorita_default=True,  visible_default=True),
    ColumnaDef(7, "Importe",     "Cálculo",        favorita_default=True,  visible_default=True),
    ColumnaDef(8, "Fórmula",     "Cálculo", favorita_default=False, visible_default=False),
    ColumnaDef(9, "Creado",      "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(10, "Modificado", "Auditoría",      favorita_default=False, visible_default=False),
]


def _editable_cols_detalle(item):
    # Descripción y unidad se editan vía popup (doble clic), no inline —
    # misma filosofía que el árbol de presupuesto.
    # Col 6 (Valor) edita la fórmula — el delegado muestra formula via FORMULA_ROLE
    if item.data(0, Qt.ItemDataRole.UserRole + 1):
        return {5, 6}
    return {4, 5, 6}


def _combo_operador(parent):
    combo = QComboBox(parent)
    combo.setEditable(False)
    combo.addItems(["*", "/"])
    return combo


def _combo_unidad(parent):
    combo = QComboBox(parent)
    combo.setEditable(False)
    combo.addItems(UNIDADES)
    return combo


class TablaApuDetalle(TreeTableWidget):
    """Árbol de componentes de un APU (concepto o insumo compuesto).

    A diferencia de TablaArbol/TablaInsumos, esta tabla siempre vuelve a
    consultar api.apu() completo ante cada evento relevante en vez de
    mutar filas in-place — el total del encabezado y el importe de cada
    fila deben quedar consistentes con lo que de verdad recalculó
    RecalculoRepo (incluyendo casos como herramienta, cuyo importe NO es
    valor×precio sino un % del subtotal de mano de obra).
    """

    _HEADER_KEY = "apu_header_state"
    _CATALOGO_KEY = "apu_columnas_favoritas"
    COLUMNAS_CATALOGO = COLUMNAS_CATALOGO
    _search_cols = {1, 2}

    resumen_actualizado = Signal(str)  # texto enriquecido para el encabezado del contenedor
    tipos_actualizados = Signal(object)  # dict[int, float] — Signal(dict) no convierte en PySide6
    total_actualizado = Signal(float)    # costo_directo
    agregar_componente = Signal(int)     # matriz_id — emitido al hacer clic en la fila vacía
    EVENTOS_SUSCRITOS = {
        ApuComponenteActualizado: '_on_evento',
        InsumoActualizado:        '_on_evento',
        ProyectoRecalculado:      '_on_evento',
    }

    def __init__(self, matriz_id: int, descripcion: str = "", on_apu_click=None, parent=None):
        """matriz_id positivo = concepto; negativo = insumo compuesto (ver api.apu()).
        on_apu_click(insumo_id): callback para abrir el APU de un sub-insumo compuesto
        al hacer doble clic en P.U. — mismo patrón que PestañaExplosion.on_apu_click.
        """
        super().__init__(
            COLUMNAS, flat=True,
            editable_cols=frozenset({5, 6}),
            editable_cols_fn=_editable_cols_detalle,
            column_editors={3: _combo_unidad, 5: _combo_operador},
            paste_col_fn={1: self._resolver_insumo_pegado, 2: self._resolver_insumo_pegado},
            parent=parent,
        )
        self._matriz_id = matriz_id
        self._descripcion = descripcion
        self._on_apu_click = on_apu_click
        self._api = None        # inyectado por conectar_eventos()
        self._event_bus = None  # inyectado por conectar_eventos()

        # ── Drag and drop entre matrices (misma lógica que Presupuesto,
        # ver TablaArbol) ─────────────────────────────────────────────
        # A diferencia de Presupuesto, esta tabla es plana (sin
        # capítulos) y puede recibir un drop desde OTRA instancia — otra
        # pestaña de APU abierta al mismo tiempo, ver dragEnterEvent —
        # para mover/copiar un componente de una matriz a otra.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._drop_objetivo = None  # (item, 'arriba'|'abajo') — ver paintEvent

        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate(ANCHOS)
        })
        self.header().setMaximumSectionSize(400)
        self._applying_modes = True
        for col in COLUMNAS_CATALOGO:
            self.setColumnHidden(col.idx, not col.visible_default)
        self._applying_modes = False
        self._restore_header_state()

        self.itemChanged.connect(self._on_item_editado)
        self.itemDoubleClicked.connect(self._on_item_dblclick)

    # ── Ciclo de vida (ver GUIA_INTERFAZ.md §7.6) ────────────────────────

    def poblar(self, resultado: dict | None):
        """Repuebla filas + total desde un resultado ya consultado.
        Puro: solo clear + add_rows + empty_row.
        El restore de selección/scroll vive en _refrescar_seguro.
        """
        total = 0.0
        if resultado:
            totales = resultado.get("totales")
            if totales and totales.get("costo_directo") is not None:
                total = totales["costo_directo"]
            else:
                total = sum(r.get("importe", 0) or 0 for r in resultado.get("detalle", []))
        titulo = self._descripcion or f"Matriz #{self._matriz_id}"
        self.resumen_actualizado.emit(f"<b>{titulo}</b> — Total: ${total:,.2f}")

        self.blockSignals(True)
        try:
            self.clear()
            if resultado:
                for r in resultado["detalle"]:
                    tn = r["tipo_nombre"]
                    es_compuesto = bool(r.get("tiene_sub_apu"))
                    row_item = self.add_row([
                        tn,
                        "",
                        r["descripcion"],
                        r["insumo_unidad"],
                        f"${r['precio']:,.2f}",
                        r["operador"],
                        f"{r['valor']:,.8f}".rstrip("0").rstrip("."),
                        f"${r['importe']:,.2f}",
                        r.get("formula") or "",
                        r.get("creado_en") or "",
                        r.get("modificado_en") or "",
                    ], editable=True)
                    row_item.setIcon(0, icono(r.get("tipo_icono", "file-text"), 16, _COLOR_TIPO.get(r.get("tipo_id"))))
                    if es_compuesto:
                        row_item.setIcon(2, icono("combine", 16))
                    row_item.setData(0, Qt.ItemDataRole.UserRole, r.get("insumo_id"))
                    row_item.setData(0, Qt.ItemDataRole.UserRole + 1, es_compuesto)
                    row_item.setData(0, _TIPO_ID_ROLE, r.get("tipo_id"))
                    row_item.setData(5, Qt.ItemDataRole.UserRole, r.get("id"))
                    row_item.setData(6, FORMULA_ROLE, r.get("formula") or "")
        finally:
            self.blockSignals(False)

        # Emit tipos detected for filter bar
        tipos_ids: set[int] = set()
        subtotales: dict[int, float] = {}
        if resultado:
            for r in resultado.get("detalle", []):
                tid = r.get("tipo_id")
                if tid:
                    tipos_ids.add(tid)
            totales_data = resultado.get("totales") or {}
            for tid in tipos_ids:
                clave = _TIPO_ID_TO_TOTALES_CLAVE.get(tid)
                if clave:
                    subtotales[tid] = totales_data.get(clave, 0)
        self.tipos_actualizados.emit(subtotales)
        self.total_actualizado.emit(total)
        self._add_empty_row()

    def _consultar(self):
        if not self._api:
            return None
        return self._api.apu(nodo_id=self._matriz_id) if self._matriz_id > 0 \
            else self._api.apu(insumo_id=-self._matriz_id)

    def _add_empty_row(self):
        item = self.add_row(
            ["", "Nuevo componente...", "", "", "", "", "", "", "", "", ""],
            editable=False,
        )
        item.setData(0, EMPTY_ROLE, True)
        self._estilizar_fila_vacia(item)

    def _al_click_fila_vacia(self):
        self.agregar_componente.emit(self._matriz_id)

    # ── Drag and drop framework ──────────────────────────
    # Uses base class TreeTableWidget drag/drop framework.
    # Subclass overrides _fila_destino_valida and
    # _calcular_posicion_drop for APu-specific behavior;
    # dropEvent stays here because APu reads foreign source
    # tables and maps column 5 as the ID column.

    _DROP_FLAT = True
    _DROP_CAN_INSIDE = False
    _DROP_ACCEPTS_FOREIGN_CLASS = True
    _REORDER_ENABLED = True

    def _get_reorder_info(self):
        win = self.window()
        handler = getattr(win, '_on_drop_apu', None) if win else None
        return handler, self._matriz_id

    def _fila_destino_valida(self, item) -> bool:
        return item is not None and not item.data(0, EMPTY_ROLE)

    def _calcular_posicion_drop(self, item, y_evento: int) -> str:
        rect = self.visualItemRect(item)
        if rect.height() <= 0:
            return "abajo"
        return "arriba" if y_evento < rect.center().y() else "abajo"

    def _item_id(self, item) -> int | None:
        return item.data(5, Qt.ItemDataRole.UserRole) if item is not None else None

    def dropEvent(self, event):
        """Calcula (matriz_destino=self._matriz_id, antes_de_id) y
        delega en self.window()._on_drop_apu(). Los renglones arrastrados
        se leen de event.source() (no de self): si el drag viene de OTRA
        pestaña de APU, self.selectedItems() sería la selección de ESTA
        tabla, no la que de verdad se está arrastrando."""
        self._drop_objetivo = None
        self.viewport().update()

        origen = event.source()
        if not isinstance(origen, TablaApuDetalle):
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
            ids_arrastrados = [it.data(5, Qt.ItemDataRole.UserRole) for it in arrastrados]
        ids_arrastrados = [cid for cid in ids_arrastrados if cid is not None]
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
            antes_de_id = item_destino.data(5, Qt.ItemDataRole.UserRole)
        else:
            siguiente = hermanos_widget[idx + 1] if idx + 1 < len(hermanos_widget) else None
            antes_de_id = siguiente.data(5, Qt.ItemDataRole.UserRole) if siguiente is not None else None

        copiar = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ventana = self.window()
        handler = getattr(ventana, '_on_drop_apu', None)
        if handler is None:
            event.ignore()
            return
        ok = handler(ids_arrastrados, self._matriz_id, antes_de_id, copiar)
        if ok:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _refrescar(self):
        """Vuelve a consultar la fuente de verdad y repuebla. Solo tiene
        efecto una vez conectado — antes de conectar_eventos() self._api
        es None y _consultar() devuelve None sin tronar."""
        self.poblar(self._consultar())

    def _on_evento(self, evento):
        """Refresco compartido para ApuComponenteActualizado, InsumoActualizado
        y ProyectoRecalculado (ver EVENTOS_SUSCRITOS).

        Captura la selección ANTES de programar el timer (no dentro de
        poblar) porque Qt puede haberla reducido al último item clickeado
        durante un drag. Usa selectedItems() como fuente primaria (captura
        toda la multi-selección actual), con _drag_sel_ids como fallback
        cuando Qt ha limpiado la selección (tras drag&drop).

        El refresco se difiere con QTimer.singleShot(0) para no destruir
        el item que Qt sigue procesando dentro de una cadena itemChanged.
        """
        try:
            if self._api is None:
                return
            scroll_y = self.verticalScrollBar().value()
            current = self.currentItem()
            id_actual = current.data(5, Qt.ItemDataRole.UserRole) if current else None
            col_actual = self.currentColumn() if current else 0
            ids_seleccionados = {
                it.data(5, Qt.ItemDataRole.UserRole) for it in self.selectedItems()
                if it.data(5, Qt.ItemDataRole.UserRole) is not None
            }
            if not ids_seleccionados:
                ids_seleccionados = set(getattr(self, '_drag_sel_ids', []))

            def _refrescar_seguro():
                try:
                    resultado = self._consultar()
                    self.poblar(resultado)
                    self.verticalScrollBar().setValue(scroll_y)
                    if id_actual is not None:
                        for i in range(self.topLevelItemCount()):
                            it = self.topLevelItem(i)
                            if it.data(5, Qt.ItemDataRole.UserRole) == id_actual:
                                self.setCurrentItem(it, col_actual)
                                break
                    if ids_seleccionados:
                        for i in range(self.topLevelItemCount()):
                            it = self.topLevelItem(i)
                            if it.data(5, Qt.ItemDataRole.UserRole) in ids_seleccionados:
                                it.setSelected(True)
                except Exception as e:
                    print(f"[eventbus] _refrescar_seguro: {type(e).__name__}: {e}")
            QTimer.singleShot(0, _refrescar_seguro)
        except Exception as e:
            print(f"[eventbus] _on_evento: {type(e).__name__}: {e}")

    # ── Filtro por tipo ──────────────────────────────────────────────

    def filtrar_por_tipo(self, tipo_id: int | None):
        """Muestra solo filas cuyo tipo_id coincide; si tipo_id es None, muestra todas."""
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if tipo_id is None:
                item.setHidden(False)
            else:
                item.setHidden(item.data(0, _TIPO_ID_ROLE) != tipo_id)

    # ── Interacción ───────────────────────────────────────────────────

    def _on_item_dblclick(self, item, column):
        """Doble clic: Descripción → selector de insumo (como en presupuesto); P.U. → sub-APU."""
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not insumo_id:
            return

        if column == 2:  # Descripción → reasignar insumo (mismo diálogo que el árbol)
            from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
            dlg = DialogoSeleccionarInsumo(self._api, self.window(), default_tipos={1, 2})
            if dlg.exec() == QDialog.DialogCode.Accepted:
                nuevo_id = dlg.insumo_seleccionado
                comp_id = item.data(5, Qt.ItemDataRole.UserRole)
                if nuevo_id is not None and comp_id:
                    self._api.apu_reasignar_componente(comp_id, nuevo_id)
            return

        if column == 4:  # P.U.
            es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if es_compuesto and self._on_apu_click:
                self._on_apu_click(insumo_id)

    def _on_item_editado(self, item, column):
        """Persiste edición: Precio (col 4), Operador (col 5) o Valor como fórmula (col 6).

        Col 6 (Valor) edita la fórmula — el delegado muestra formula via FORMULA_ROLE.

        No hace falta recalcular nada a mano aquí: api.apu_actualizar_*()
        emite ApuComponenteActualizado/InsumoActualizado de forma SÍNCRONA
        (antes de que este método siquiera retorne), y conectar_eventos()
        ya suscribió _refrescar() a esos eventos — repuebla filas y total
        desde la fuente de verdad. Por eso NO se debe tocar `item` después
        de llamar a self._api.apu_actualizar_*(): _refrescar() ya lo borró
        y recreó (self.clear()), y seguir usándolo revienta con
        RuntimeError: libshiboken...already deleted.
        """
        if column not in (1, 2, 4, 5, 6) or not self._api:
            return
        comp_id = item.data(5, Qt.ItemDataRole.UserRole)

        if column in (1, 2):
            # Pegado sobre Clave/Descripción (ver _resolver_insumo_pegado):
            # UserRole trae el insumo_id resuelto — re-liga el componente,
            # igual que el diálogo de doble clic (_on_item_dblclick).
            insumo_id = item.data(column, Qt.ItemDataRole.UserRole)
            if insumo_id and comp_id:
                self._api.apu_reasignar_componente(comp_id, insumo_id)
            return

        if column == 5:
            op = item.text(column).strip()
            if op not in ('*', '/'):
                item.setText(column, '*')
                return
            if comp_id:
                self._api.apu_actualizar_operador(comp_id, op)
            return

        if column == 6:
            if not comp_id:
                return
            texto = item.text(column).strip()
            try:
                self._api.apu_actualizar_valor(comp_id, valor=0, formula=texto or None)
            except ValueError as e:
                QMessageBox.warning(self.window(), "Fórmula inválida", str(e))
                tw = item.treeWidget()
                if tw:
                    tw.blockSignals(True)
                    row = self._api.campo_valor("apu_matrices", "valor", comp_id)
                    old = (row or {}).get("valor")
                    if old is not None:
                        txt = f"{old:,.8f}".rstrip("0").rstrip(".")
                        item.setText(6, txt)
                    item.setData(6, FORMULA_ROLE, texto)
                    tw.blockSignals(False)
                    QTimer.singleShot(0, lambda t=tw, i=item, c=column: t.editItem(i, c))
            return

        if column == 4:
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            if not insumo_id:
                return
            try:
                texto = item.text(column).replace("$", "").replace(",", "").strip()
                precio = float(texto)
            except ValueError:
                return
            try:
                self._api.apu_actualizar_precio_componente(insumo_id, precio)
            except ValueError as e:
                QMessageBox.warning(self.window(), "Precio inválido", str(e))
                self._revertir_item(item, column, "insumos", insumo_id, "costo_mn", "$:,.2f")

    def _resolver_insumo_pegado(self, item, col: int, valor: str):
        """paste_col_fn compartido de Clave (1) y Descripción (2): pegar
        cualquiera de las dos re-liga el componente a otro insumo — misma
        lógica que TablaArbol._resolver_insumo_pegado (ver arbol.py),
        necesaria porque Clave está oculta por defecto y Descripción no es
        editable a mano (se relíe vía el diálogo de doble clic o, ahora,
        vía pegado).

        Reconoce el valor pegado, en orden: id de insumo puro (dígitos,
        vía COPY_ROLE de Clave), hash de deduplicación tal cual (columna
        Hash del Catálogo de Insumos), o el propio texto pegado hasheado
        con el mismo algoritmo que usa el catálogo para deduplicar —esto
        resuelve pegar la Descripción de una fila copiada de Presupuesto,
        de otro APU, o del Catálogo de Insumos. Si nada coincide, no se
        toca la celda."""
        if item.data(0, EMPTY_ROLE):
            return None
        v = (valor or "").strip()
        if not v:
            return None
        api = getattr(self, '_api', None)
        if api is None:
            return None
        ins = None
        if v.isdigit():
            ins = api.campo_valor("insumos", "id", int(v))
        if ins is None:
            ins = api.insumo_por_hash(v)
        if ins is None:
            from backend.database.core import generar_hash
            ins = api.insumo_por_hash(generar_hash(v))
        if ins is None:
            return None
        insumo_id = ins.get("id")
        if col == 1:
            return (ins.get("clave_opus") or v, insumo_id)
        return (ins.get("descripcion") or "", insumo_id)

    def _revertir_item(self, item, column: int, tabla: str, reg_id: int, campo: str, fmt: str):
        """Revierte el texto de un item al valor real de la DB tras error de validación."""
        tw = item.treeWidget()
        if not tw:
            return
        tw.blockSignals(True)
        row = self._api.campo_valor(tabla, campo, reg_id)
        if row:
            val = row[campo]
            if val is None:
                txt = ""
            elif isinstance(val, str):
                txt = val
            elif "$" in fmt:
                txt = f"${val:,.2f}"
            else:
                txt = f"{val:,.8f}".rstrip("0").rstrip(".")
            item.setText(column, txt)
        tw.blockSignals(False)
