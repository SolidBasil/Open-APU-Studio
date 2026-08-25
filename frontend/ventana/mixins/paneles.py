"""
paneles.py
==========
Mixin de paneles de contenido para VentanaPrincipal.

Contiene sidebar, presupuesto, insumos, buscador de partidas,
refresco de tabs y utilidades.

Mixins hermanos relacionados (ver mixins/): apu.py, rastreo.py, explosion.py.
"""

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QHeaderView,
)
from PySide6.QtGui import QFont, QShortcut, QKeySequence

from frontend.ventana.iconos import icono
from frontend.ventana.widgets.base import TabWidgetCerrable
from frontend.ventana.tipos_insumo import COLOR as _COLOR_TIPO
from frontend.ventana.colores import TEXT, ACCENT, PURPURA

# ── Sidebar: títulos de pestañas de insumos ──────────────────────
# El emoji se reemplaza por icono SVG; el title se usa como key en routing.
INSUMOS_ITEMS = [
    ("Todos",        None),
    ("Conceptos",   "concepto"),
    ("Materiales",  "material"),
    ("Mano de obra", "mano_obra"),
    ("Herramienta",  "herramienta"),
    ("Equipo",       "equipo"),
    ("Auxiliares",  "auxiliar"),
    ("Matrices",    None),       # flag especial, no es tipo de insumo
    ("Fletes",      "flete"),
    ("Trabajos",    "trabajo"),
]
INSUMOS_TITLES = {title for title, _ in INSUMOS_ITEMS}

# Icono SVG por cada pestaña de insumos
_INSUMOS_SVG = {
    "Todos":        "book-open",
    "Conceptos":   "file-text",
    "Materiales":  "building-2",
    "Mano de obra": "hard-hat",
    "Herramienta":  "wrench",
    "Equipo":       "tractor",
    "Auxiliares":  "cog",
    "Matrices":    "grid-3x3",
    "Fletes":      "truck",
    "Trabajos":    "construction",
}

# Colores por tipo de insumo — derivado de tipos_insumo (fuente única)
from frontend.ventana.tipos_insumo import NOMBRES as _TIPOS_NOMBRES
_INSUMOS_COLOR = {_TIPOS_NOMBRES[tid]: _COLOR_TIPO.get(tid, TEXT) for tid in _TIPOS_NOMBRES}
_INSUMOS_COLOR["Todos"] = TEXT
_INSUMOS_COLOR["Matrices"] = PURPURA


class _ExploradorTree(QTreeWidget):
    """QTreeWidget del sidebar Explorador.

    Con el mouse, un clic en un grupo (Propuesta/Insumos/Ejecución) lo
    expande o colapsa. QTreeWidget nativo no ofrece un equivalente de
    teclado para eso (Espacio no hace nada por defecto); se agrega aquí
    igual que ya existe en TreeTableWidget (ver widgets/base.py).
    """

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            item = self.currentItem()
            if item is not None and item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
                return
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Teclado-first: Enter en una hoja del sidebar abre la pestaña
            # permanente, igual que el doble clic (itemDoubleClicked).
            item = self.currentItem()
            if item is not None and item.childCount() == 0:
                self.itemDoubleClicked.emit(item, 0)
                return
        super().keyPressEvent(event)


class PanelesMixin:
    """Mixin de paneles — se mezcla en VentanaPrincipal."""

    # ── Sidebar ──────────────────────────────────────────────────────────

    # ── Panel izquierdo (contextual) ──────────────────────────────────────

    def _build_left_panel(self):
        """Columna izquierda: el explorador (sidebar) normal.

        Los generadores ya no tienen un panel lateral propio (ni árbol
        de presupuesto ni renglones ahí) — cada generador vive por
        completo en su propia pestaña de contenido, con el visor CAD y
        sus renglones en un splitter (ver GeneradorMixin en
        mixins/generador.py).
        """
        return self._build_sidebar()

    def _build_sidebar(self):
        """Construye el explorador lateral."""
        tree = _ExploradorTree()
        tree.setHeaderLabel("Explorador")
        tree.setMinimumWidth(150)
        tree.setAnimated(True)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        secciones = [
            ("Propuesta", "folder", ACCENT, [
                ("clipboard", "Presupuesto programable"),
                ("search", "Buscar partidas"),
                ("package", "Explosión de insumos"),
                ("package", "Explosión de matrices"),
                ("truck", "Programa de suministros"),
            ]),
            ("Insumos", "folder", ACCENT, [
                (_INSUMOS_SVG.get(title, "circle"), title, _INSUMOS_COLOR.get(title, TEXT))
                for title, _ in INSUMOS_ITEMS
            ]),
            ("Ejecución", "folder", ACCENT, [
                ("zap", "Fuera de presupuesto", TEXT),
                ("file-text", "Estimaciones", TEXT),
                ("plus", "Conceptos fuera de catálogo", TEXT),
                ("trending-up", "Ajustes de costos", TEXT),
            ]),
        ]
        for nombre, svg_icon, color, hijos in secciones:
            root = QTreeWidgetItem(tree, [nombre])
            root.setIcon(0, icono(svg_icon, 16, color))
            root.setExpanded(True)
            f = root.font(0)
            f.setBold(True)
            root.setFont(0, f)
            for item_data in hijos:
                svg, h = item_data[0], item_data[1]
                c = item_data[2] if len(item_data) > 2 else TEXT
                item = QTreeWidgetItem(root, [h])
                item.setIcon(0, icono(svg, 16, c))

        self._sidebar_tree = tree
        tree.itemClicked.connect(self._on_sidebar_click)
        tree.itemDoubleClicked.connect(self._on_sidebar_double_click)
        return tree

    # ── Contenido central ────────────────────────────────────────────────

    def _build_content(self):
        """Crea el QTabWidget central."""
        self._tabs = TabWidgetCerrable()
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.addTab(self._build_presupuesto(), "Presupuesto programable")

        QShortcut(QKeySequence("Ctrl+Tab"),       self).activated.connect(self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self).activated.connect(self._prev_tab)

        # Mover nodos del árbol de presupuesto con Alt+flechas — mismos
        # handlers que los botones Subir/Bajar/Izquierda/Derecha de la
        # toolbar (ver _HANDLERS en toolbar.py y HandlersMixin en
        # handlers/__init__.py). Shortcuts a nivel de ventana: operan
        # sobre la tabla activa (self._get_active_table()) sin importar
        # qué widget tenga el foco puntual dentro de la pestaña.
        QShortcut(QKeySequence("Alt+Left"),  self).activated.connect(self._on_izquierda)
        QShortcut(QKeySequence("Alt+Right"), self).activated.connect(self._on_derecha)
        QShortcut(QKeySequence("Ctrl+Insert"),   self).activated.connect(self._on_agregar_agrupador)
        QShortcut(QKeySequence("Ctrl+Z"),         self).activated.connect(self._on_deshacer)
        QShortcut(QKeySequence("Ctrl+Y"),         self).activated.connect(self._on_rehacer)
        QShortcut(QKeySequence("Ctrl+Shift+Z"),   self).activated.connect(self._on_rehacer)

        # ── Atajos teclado-first ─────────────────────────────────────────
        # Navegación y acciones globales de la ventana.
        QShortcut(QKeySequence("Ctrl+F"),       self).activated.connect(self._on_foco_busqueda)
        QShortcut(QKeySequence("/"),            self).activated.connect(self._on_foco_busqueda)
        QShortcut(QKeySequence("Ctrl+W"),       self).activated.connect(self._on_cerrar_pestana)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self).activated.connect(self._on_foco_sidebar)
        QShortcut(QKeySequence("Ctrl+P"),       self).activated.connect(self._on_paleta_comandos)
        QShortcut(QKeySequence("F1"),           self).activated.connect(self._on_mostrar_ayuda)

        # Cambiar de pestaña de la cinta con Alt+1..7.
        for i, nombre_tab in enumerate(
                ["PROYECTO", "INICIO", "INFORMES", "VISTA",
                 "PRINCIPAL", "HERRAMIENTAS", "GENERADORES"], start=1):
            QShortcut(QKeySequence(f"Alt+{i}"), self).activated.connect(
                lambda n=nombre_tab: self._switch_tab(n))

        # Aceleradores de acciones de la cinta (ver _ATAJOS en toolbar.py).
        # Los tooltips ya muestran la tecla; aquí solo se registran.
        from frontend.ventana.mixins.toolbar import _ATAJOS, _HANDLERS
        for tip, seq in _ATAJOS.items():
            nombre = _HANDLERS.get(tip)
            handler = getattr(self, nombre, None) if nombre else None
            if handler:
                QShortcut(QKeySequence(seq), self).activated.connect(handler)

        return self._tabs

    # ── Presupuesto ──────────────────────────────────────────────────────

    def _build_presupuesto(self):
        """Construye el árbol jerárquico del presupuesto."""
        from frontend.ventana.widgets.arbol import TablaArbol

        if not self._db:
            return self._build_sin_proyecto()

        tree = TablaArbol()
        try:
            nodos = self._api.presupuesto_arbol()
            tree.poblar(nodos)
        except Exception as e:
            print(f"Error cargando presupuesto: {e}")

        tree.conectar_handlers(self)
        self._arbol_presupuesto = tree
        if self._event_bus and self._api:
            tree.conectar_eventos(self._event_bus, self._api)
        QTimer.singleShot(0, self._on_ajustar_columnas)
        return tree

    def _build_extra_panel(self):
        """Árbol de conceptos fuera de presupuesto (es_extra=1)."""
        from frontend.ventana.widgets.arbol import TablaArbol
        from PySide6.QtWidgets import QVBoxLayout, QLabel

        if not self._db:
            return self._build_sin_proyecto()

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Totales informativos
        totales = QHBoxLayout()
        total_legal = self._calcular_total_extra(extra=False)
        total_extra = self._calcular_total_extra(extra=True)
        lbl_legal = QLabel(f"Presupuesto: ${total_legal:,.2f}")
        lbl_extra = QLabel(f"Extra: ${total_extra:,.2f}")
        lbl_total = QLabel(f"Total: ${total_legal + total_extra:,.2f}")
        for lbl in (lbl_legal, lbl_extra, lbl_total):
            f = lbl.font()
            f.setBold(True)
            lbl.setFont(f)
        totales.addWidget(lbl_legal)
        totales.addSpacing(16)
        totales.addWidget(lbl_extra)
        totales.addSpacing(16)
        totales.addWidget(lbl_total)
        totales.addStretch()
        layout.addLayout(totales)

        tree = TablaArbol(header_key="extra_arbol_header_state", extra=True)
        try:
            nodos = self._api.presupuesto_arbol(extra=True)
            tree.poblar(nodos)
        except Exception as e:
            print(f"Error cargando presupuesto extra: {e}")

        tree.conectar_handlers(self,
            agregar_agrupador='_on_agregar_agrupador_extra',
            agregar_concepto='_on_agregar_concepto_extra')
        self._arbol_extra = tree
        if self._event_bus and self._api:
            tree.conectar_eventos(self._event_bus, self._api)
        layout.addWidget(tree, 1)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._on_ajustar_columnas)
        return w

    def _calcular_total_extra(self, extra: bool = False) -> float:
        """Suma de totales de nodos raíz (es_extra=0|1)."""
        api = getattr(self, '_api', None)
        if not api:
            return 0.0
        try:
            raices = api.presupuesto_arbol(extra=extra)
            return sum(float(n.get("total", 0) or 0) for n in raices)
        except Exception as e:
            print(f"Error calculando total extra: {e}")
            return 0.0

    def _on_agregar_agrupador_extra(self):
        """Agrega agrupador en el árbol extra."""
        self._agregar_nodo_extra("capitulo")

    def _on_agregar_concepto_extra(self):
        """Agrega concepto en el árbol extra."""
        self._agregar_nodo_extra("concepto")

    def _agregar_nodo_extra(self, tipo: str):
        """Inserta nodo extra. Misma lógica que _agregar_nodo pero con es_extra=True."""
        from frontend.ventana.widgets.arbol import ID_ROLE, TIPO_ROLE
        from PySide6.QtCore import QTimer

        api = getattr(self, '_api', None)
        t = getattr(self, '_arbol_extra', None)
        if not t or not api:
            return

        sel = t.selectedItems()
        padre_id = None
        antes_de = None
        if sel:
            item = sel[0]
            id_actual = item.data(0, ID_ROLE)
            tipo_actual = item.data(0, TIPO_ROLE)
            if tipo_actual == "capitulo":
                padre_id = id_actual
                if item.childCount() > 0:
                    antes_de = item.child(0).data(0, ID_ROLE)
            elif tipo_actual == "concepto":
                padre_id = item.parent().data(0, ID_ROLE) if item.parent() else None
                antes_de = id_actual

        insumo_id = None
        if tipo == "concepto":
            from PySide6.QtWidgets import QDialog
            from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
            dlg = DialogoSeleccionarInsumo(api, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            insumo_id = dlg.insumo_seleccionado
            if insumo_id is None:
                return

        nuevo_id = api.agregar_nodo(
            tipo, padre_id=padre_id, antes_de=antes_de,
            insumo_id=insumo_id, es_extra=True,
        )
        edit_col = 6 if tipo == "concepto" else 4

        def _seleccionar_nuevo():
            item = t._buscar_item_por_id(nuevo_id)
            if item:
                t.setCurrentItem(item)
                if t.isColumnHidden(edit_col):
                    t.setColumnHidden(edit_col, False)
                t.editItem(item, edit_col)
        QTimer.singleShot(0, _seleccionar_nuevo)

    def _build_sin_proyecto(self) -> QWidget:
        """Placeholder cuando no hay proyecto abierto."""

        w      = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icono_lbl = QLabel()
        icono_lbl.setPixmap(icono("folder-open", 56).pixmap(56, 56))
        icono_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        titulo = QLabel("Sin proyecto abierto")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont("Segoe UI", 18)
        f.setBold(True)
        titulo.setFont(f)

        instruccion = QLabel(
            "Haz clic en cualquier parte para abrir un proyecto, o usa\n"
            "HERRAMIENTAS → Importar OPUS  para cargar uno nuevo."
        )
        instruccion.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instruccion.setFont(QFont("Segoe UI", 11))
        instruccion.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(icono_lbl)
        layout.addSpacing(16)
        layout.addWidget(titulo)
        layout.addSpacing(8)
        layout.addWidget(instruccion)
        layout.addStretch()

        w.setCursor(Qt.CursorShape.PointingHandCursor)
        self._placeholder_sin_proyecto = w

        for child in w.findChildren(QWidget):
            child.setCursor(Qt.CursorShape.PointingHandCursor)
        # Clicks y ciclo de zonas del placeholder los captura el filtro a
        # nivel aplicación (ver toolbar.py::_build_toolbar).
        return w

    # ── Insumos ──────────────────────────────────────────────────────────

    def _build_insumos(self, title: str):
        """Catálogo de insumos filtrable por tipo."""
        from frontend.ventana.widgets.insumos import TablaInsumos, EDITABLE

        tipo_map = {title: key for title, key in INSUMOS_ITEMS}
        tabla = TablaInsumos()
        tabla._insumos_tipo = tipo_map.get(title)
        tabla._insumos_matrices = (title == "Matrices")
        tabla._HEADER_KEY = "insumos_header_state"
        tabla._restore_header_state()
        ids = set()
        if self._api:
            tipo = tabla._insumos_tipo
            ids  = self._api.insumo_ids_con_apu()
            if tabla._insumos_matrices:
                insumos = self._api.insumos_con_matrices(tipo)
            else:
                insumos = self._api.insumos(tipo)
            tabla.poblar(insumos, ids)
        tabla.rastrear_insumo.connect(self._on_rastrear_insumo)
        tabla.desglozar_insumo.connect(self._abrir_apu_insumo)
        tabla.nuevo_insumo.connect(self._on_nuevo_insumo_panel)
        tabla.itemChanged.connect(self._on_insumo_editado)
        if self._event_bus and self._api:
            tabla.conectar_eventos(self._event_bus, self._api)

        def _on_insumo_dblclick(item, column):
            # ponytail: columnas editables (Descripción, Unidad, Precio)
            # deben permitir edición inline — no interceptar
            if column in EDITABLE:
                return
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            if not insumo_id:
                return
            arbol = getattr(self, '_arbol_presupuesto', None)
            if arbol:
                sel = arbol.currentItem()
                if sel:
                    from frontend.ventana.widgets.arbol import TIPO_ROLE, ID_ROLE
                    if sel.data(0, TIPO_ROLE) == 'concepto':
                        concepto_id = sel.data(0, ID_ROLE)
                        self._api.concepto_reasignar_insumo(concepto_id, insumo_id)
                        return
            if insumo_id in ids:
                self._abrir_apu_insumo(insumo_id)

        tabla.itemDoubleClicked.connect(_on_insumo_dblclick)
        return tabla

    def _on_nuevo_insumo_panel(self):
        """Abre formulario de nuevo insumo desde la pestaña de insumos."""
        from frontend.ventana.widgets.dialogs import InsumoDialog
        from frontend.ventana.tipos_insumo import CLAVE as _CLAVE
        if not self._api:
            return
        idx = self._tabs.currentIndex()
        title = self._tabs.tabText(idx) if idx >= 0 else ""
        tipo_map = {title: key for title, key in INSUMOS_ITEMS}
        tipo_clave = tipo_map.get(title)
        default_tipo = None
        if tipo_clave:
            default_tipo = next((tid for tid, c in _CLAVE.items() if c == tipo_clave), None)
        dlg = InsumoDialog(self._api, parent=self, default_tipo=default_tipo)
        if dlg.exec() == 1:  # Accepted
            self._on_tab_changed(idx)

    def _on_modificar_insumo(self, insumo_id: int):
        from frontend.ventana.widgets.dialogs import InsumoDialog
        if not self._api:
            return
        dlg = InsumoDialog(self._api, insumo_id=insumo_id, parent=self)
        dlg.exec()

    def _on_cambiar_insumo(self, nodo_id: int):
        from PySide6.QtWidgets import QDialog
        from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
        if not self._api:
            return
        dlg = DialogoSeleccionarInsumo(self._api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nuevo_id = dlg.insumo_seleccionado
            if nuevo_id is not None:
                self._api.concepto_reasignar_insumo(nodo_id, nuevo_id)

    def _on_insert_contextual(self):
        """Insert: en pestaña de insumos crea insumo; en presupuesto agrega concepto."""
        idx = self._tabs.currentIndex()
        title = self._tabs.tabText(idx) if idx >= 0 else ""
        if title in INSUMOS_TITLES:
            self._on_nuevo_insumo_panel()
        else:
            self._on_agregar_concepto()

    def _on_insumo_editado(self, item, column):
        """Persiste edición inline de insumos.

        No hace falta refrescar nada aquí a mano: DataService.actualizar()
        emite InsumoActualizado (y, si cambia el precio, ProyectoRecalculado
        tras la cascada) — cada TablaInsumos/TablaArbol abierta se suscribió
        a esos eventos en su propia construcción y se actualiza sola.
        """
        from PySide6.QtWidgets import QMessageBox
        from frontend.ventana.widgets.base import EMPTY_ROLE
        if item.data(0, EMPTY_ROLE):
            self._on_insumo_fila_vacia_editada(item, column)
            return
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not insumo_id or not self._api:
            return
        if column == 1:
            desc = item.text(column).strip()
            if not desc:
                return
            try:
                self._api.insumo_actualizar_descripcion(insumo_id, desc)
            except ValueError as e:
                QMessageBox.warning(self, "Descripción duplicada", str(e))
                actual = self._api.insumo_por_id(insumo_id) or {}
                tabla = item.treeWidget()
                tabla.blockSignals(True)
                item.setText(column, actual.get("descripcion", "") or "")
                tabla.blockSignals(False)
        elif column == 2:
            self._api.insumo_actualizar_campo(insumo_id, "unidad", item.text(column))
        elif column == 3:
            try:
                txt = item.text(column).replace("$", "").replace(",", "").strip()
                precio = float(txt)
                self._api.insumo_actualizar_precio(insumo_id, precio)
            except ValueError:
                # Antes: return silencioso. La celda se quedaba mostrando
                # el texto inválido tecleado mientras la BD seguía con el
                # precio anterior — pantalla y BD desincronizadas, sin
                # ningún aviso de que no se guardó (ver mismo fix en
                # widgets/apu.py::_on_item_editado, columna Precio).
                QMessageBox.warning(self, "Precio inválido",
                                     "Escribe un número (ej. 350.00 o $1,250.50).")
                tabla = item.treeWidget()
                if tabla:
                    tabla.blockSignals(True)
                    actual = self._api.insumo_por_id(insumo_id) or {}
                    costo = actual.get("costo_mn")
                    item.setText(column, f"${costo:,.2f}" if costo is not None else "")
                    tabla.blockSignals(False)
                return
        elif column == 4:  # Tipo
            tipo_id = item.data(column, Qt.ItemDataRole.UserRole)
            if tipo_id is not None:
                self._api.insumo_actualizar_campo(insumo_id, "tipo_id", tipo_id)
        elif column == 5:  # Familia
            familia_id = item.data(column, Qt.ItemDataRole.UserRole)
            self._api.insumo_actualizar_campo(insumo_id, "familia_id", familia_id)
            self._api.insumo_actualizar_campo(insumo_id, "subfamilia_id", None)

    def _on_insumo_fila_vacia_editada(self, item, column):
        """Convierte la fila placeholder "Nuevo insumo..." en un insumo
        real en cuanto se escribe una Descripción — comportamiento tipo
        Excel: escribir en la última fila la crea de verdad, y esa misma
        fila queda lista otra vez en blanco para seguir capturando, en vez
        de exigir un diálogo modal aparte.

        Se dispara con cualquier columna editada (Descripción, Unidad,
        Precio, Tipo, Familia), pero solo crea el insumo cuando la
        Descripción (columna 1) tiene texto — es el único campo
        obligatorio, igual que en InsumoDialog. Si el usuario primero
        cambia Tipo/Unidad y todavía no escribe Descripción, no se crea
        nada aún: el resto de los valores ya tecleados se conservan en la
        fila hasta que se complete la Descripción.

        No hace falta convertir este item a mano ni agregar uno nuevo:
        insumo_insertar() dispara NodoInsertado (EventBus.emit es
        síncrono), y _on_nodo_insertado (insumos.py) ya inserta la fila
        real bien formateada justo ANTES de este placeholder — add_row()
        siempre inserta ahí cuando encuentra una fila EMPTY_ROLE al final.
        Solo queda devolver este item a su estado en blanco original.
        """
        from PySide6.QtWidgets import QMessageBox
        from frontend.ventana.tipos_insumo import CLAVE as _CLAVE

        if column != 1 or not self._api:
            return
        desc = item.text(1).strip()
        if not desc or desc == "Nuevo insumo...":
            return

        tabla = item.treeWidget()

        # Tipo: lo que se haya elegido en la columna Tipo de esta misma
        # fila (combo) tiene prioridad; si no se tocó, se usa el tipo de
        # la pestaña de Insumos actual (Materiales, Mano de obra, etc. —
        # ver tabla._insumos_tipo en _build_insumos); si tampoco hay
        # contexto (pestaña "Todos"), Material como default razonable.
        tipo_id = item.data(4, Qt.ItemDataRole.UserRole)
        if tipo_id is None:
            tipo_clave = getattr(tabla, "_insumos_tipo", None)
            tipo_id = next((tid for tid, c in _CLAVE.items() if c == tipo_clave), None)
        if tipo_id is None:
            tipo_id = 1  # Material

        unidad = item.text(2).strip()
        familia_id = item.data(5, Qt.ItemDataRole.UserRole)

        try:
            nuevo_id = self._api.insumo_insertar(
                tipo_id=tipo_id, descripcion=desc, unidad=unidad,
                costo=0.0, costo_me=0.0, es_compuesto=0,
                familia_id=familia_id, subfamilia_id=None,
            )
        except ValueError as e:
            tabla.blockSignals(True)
            QMessageBox.warning(self, "Descripción duplicada", str(e))
            item.setText(1, "")
            tabla.blockSignals(False)
            return

        self._api.insumo_actualizar_campo(nuevo_id, "clave_usuario", f"INS-{nuevo_id}")

        # insumo_insertar()/insumo_actualizar_campo() ya dispararon
        # NodoInsertado (EventBus.emit es síncrono — ver data_service.py),
        # y _on_nodo_insertado (insumos.py) ya insertó la fila real, bien
        # formateada (_valores_fila + ícono de tipo), justo ANTES de este
        # placeholder — add_row() siempre inserta antes de la fila
        # EMPTY_ROLE. No hace falta convertir este item a mano: basta con
        # devolverlo a su estado en blanco original para que siga
        # funcionando como la fila "escribe aquí" de la próxima captura.
        tabla.blockSignals(True)
        from PySide6.QtGui import QIcon
        for c in range(item.columnCount()):
            item.setText(c, "")
            item.setIcon(c, QIcon())
        item.setText(1, "Nuevo insumo...")
        tabla.blockSignals(False)

    # ── Buscador de partidas ─────────────────────────────────────────────

    def _build_buscador_partidas(self):
        """Catálogo plano de partidas con doble clic para abrir APU."""
        from frontend.ventana.widgets.base import TreeTableWidget
        from frontend.ventana.widgets.arbol import ID_ROLE

        t = TreeTableWidget(
            ["Nivel", "Descripción", "Unidad", "Cantidad", "P.U.", "Total"],
            flat=True,
        )
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 110, 120])
        })
        t.header().setMaximumSectionSize(400)
        t._search_cols = {1}
        if self._api:
            for c in self._api.conceptos_planos():
                cant = float(c.get("cantidad") or 0)
                total = float(c.get("total") or 0)
                pu = total / cant if cant else 0
                item = t.add_row([
                    c.get("wbs", "") or "",
                    c.get("descripcion", "") or "",
                    c.get("unidad", "") or "",
                    f"{cant:,.4f}".rstrip("0").rstrip("."),
                    f"${pu:,.2f}",
                    f"${total:,.2f}",
                ], editable=False)
                nodo_id = c.get("id")
                if nodo_id:
                    item.setData(0, ID_ROLE, nodo_id)
        t.itemDoubleClicked.connect(self._on_item_dblclick)
        return t

    # ── Configuración / utilidades ───────────────────────────────────────

    def _on_configuracion(self):
        """Abre el diálogo de ajustes de la aplicación."""
        from frontend.ventana.widgets.ajustes import DialogoAjustes
        DialogoAjustes(self).exec()

    def _on_abrir_carpeta_bd(self):
        """Abre en el explorador la carpeta donde se guardan los .db."""
        from backend.database.db import Rutas
        import subprocess
        import sys
        carpeta = Rutas.proyectos()
        carpeta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(carpeta)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])
