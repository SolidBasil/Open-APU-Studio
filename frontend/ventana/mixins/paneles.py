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
    QAbstractItemView, QHeaderView, QTabWidget,
)
from PySide6.QtGui import QFont, QShortcut, QKeySequence

from frontend.ventana.iconos import icono
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

# Colores por tipo de insumo — derivado de tipos_insumo.COLOR (fuente única)
from frontend.ventana.tipos_insumo import TIPOS as _TIPOS_DATA
_INSUMOS_COLOR = {v[2]: _COLOR_TIPO.get(tid, TEXT) for tid, v in _TIPOS_DATA.items()}
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
        super().keyPressEvent(event)


class PanelesMixin:
    """Mixin de paneles — se mezcla en VentanaPrincipal."""

    # ── Sidebar ──────────────────────────────────────────────────────────

    # ── Panel izquierdo (contextual) ──────────────────────────────────────

    def _build_left_panel(self):
        """Envuelve el sidebar normal y paneles contextuales (p.ej. el de
        generadores) en un QStackedWidget, para poder cambiar qué se
        muestra en la columna izquierda según la pestaña activa.
        """
        from PySide6.QtWidgets import QStackedWidget
        self._left_stack = QStackedWidget()
        self._left_stack.addWidget(self._build_sidebar())          # índice 0: normal
        self._left_stack.addWidget(self._build_generadores_lateral())  # índice 1
        return self._left_stack

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
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
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
        QShortcut(QKeySequence("Alt+Up"),    self).activated.connect(self._on_subir)
        QShortcut(QKeySequence("Alt+Down"),  self).activated.connect(self._on_bajar)
        QShortcut(QKeySequence("Alt+Left"),  self).activated.connect(self._on_izquierda)
        QShortcut(QKeySequence("Alt+Right"), self).activated.connect(self._on_derecha)
        QShortcut(QKeySequence("Ctrl+Insert"),   self).activated.connect(self._on_agregar_agrupador)
        QShortcut(QKeySequence("Ctrl+Z"),         self).activated.connect(self._on_deshacer)
        QShortcut(QKeySequence("Ctrl+Y"),         self).activated.connect(self._on_rehacer)
        QShortcut(QKeySequence("Ctrl+Shift+Z"),   self).activated.connect(self._on_rehacer)

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
        w.installEventFilter(self)

        for child in w.findChildren(QWidget):
            child.setCursor(Qt.CursorShape.PointingHandCursor)
            child.installEventFilter(self)
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
                return
        elif column == 4:  # Tipo
            tipo_id = item.data(column, Qt.ItemDataRole.UserRole)
            if tipo_id is not None:
                self._api.insumo_actualizar_campo(insumo_id, "tipo_id", tipo_id)
        elif column == 5:  # Familia
            familia_id = item.data(column, Qt.ItemDataRole.UserRole)
            self._api.insumo_actualizar_campo(insumo_id, "familia_id", familia_id)
            self._api.insumo_actualizar_campo(insumo_id, "subfamilia_id", None)

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
