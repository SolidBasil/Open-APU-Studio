"""
toolbar.py
==========
Mixin de toolbar para VentanaPrincipal.

Contiene toda la lógica de construcción y gestión de la toolbar superior:
pestañas (PROYECTO/INICIO/…), botones, temas visuales y barra de búsqueda.
"""

from PySide6.QtCore    import Qt, QSize
from PySide6.QtGui     import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QFrame, QToolButton, QLabel, QMenu,
    QApplication,
)

from frontend.temas import Temas
from frontend.ventana.iconos import icono
from frontend.ventana.colores import TEXT, TEXT_INVERSO, MUTED



# =============================================================================
# CONFIGURACIÓN DE LA TOOLBAR
# Estructura: { tab: [ (grupo_label, [item, ...]), ... ] }


# =============================================================================
# CONFIGURACIÓN DE LA TOOLBAR
# =============================================================================

# Mapa tooltip → nombre del método handler.
# Todo botón añadido a _TOOLBAR_CFG debe tener entrada aquí; si no, aparecerá
# atenuado como "(beta)".
_HANDLERS = {
    "Nuevo":             "_on_nuevo_proyecto",
    "Importar OPUS":     "_on_importar_opus",
    "Abrir":             "_on_abrir_proyecto",
    "Copiar":            "_on_copy_toolbar",
    "Primer nivel":      "_on_desplegar_primer_nivel",
    "Resumen agrupadores": "_on_desplegar_resumen",
    "Todo":              "_on_desplegar_todo",
    "Nivel":             "_on_desplegar_nivel",
    "Cerrar":            "_on_cerrar_proyecto",
    "Duplicar":          "_on_copiar_proyecto",
    "Renombrar":         "_on_renombrar_proyecto",
    "Eliminar proyecto": "_on_eliminar_proyecto",
    "Abrir carpeta BD":  "_on_abrir_carpeta_bd",
    "Configuración":     "_on_configuracion",
    "Configuración general": "_on_configuracion",
    "Seleccionar todo":  "_on_select_all_toolbar",
    "Modificar":         "_on_modificar_toolbar",
    "Desglosar":         "_on_desglozar_toolbar",
    "Adjuntar archivo":  "_on_adjuntar_archivo",
    "Ver adjuntos":      "_on_ver_adjuntos",
    "Depurar catálogos": "_on_depurar_catalogos",
    "Homologar hash":    "_on_homologar_hash",
    "Calculadora":       "_on_calculadora",
    "Ajustar":           "_on_ajustar_columnas",
    "Mostrar/Ocultar":   "_on_mostrar_ocultar",
    "Restablecer":       "_on_restablecer_formato",
    "Pantalla completa": "_on_pantalla_completa",
    "Recalcular":        "_on_recalcular",
    "Renumerar":         "_on_renumerar",
    "Izquierda":         "_on_izquierda",
    "Derecha":           "_on_derecha",
    "Subir":             "_on_subir",
    "Bajar":             "_on_bajar",
    "Información proyecto": "_on_info_proyecto",
    "Parámetros proyecto": "_on_info_proyecto",
    "Presupuesto":       "_on_generar_presupuesto",
    "Compilar PDF":      "_on_compilar_pdf",
    "Configurar impresión": "_on_config_impresion",
    "Vista previa":      "_on_vista_previa",
    "Eliminar":          "_on_eliminar",
    "Agregar agrupador": "_on_agregar_agrupador",
    "Agregar concepto":  "_on_agregar_concepto",
    "Deshacer":          "_on_deshacer",
    "Rehacer":           "_on_rehacer",
    "Cálculo de indirectos": "_on_indirectos",
    "Personal en indirectos": "_on_personal_indirectos",
    "Cálculo de sobrecostos": "_on_sobrecostos",
    "Variables de fórmula": "_on_variables_formula",
    "Nuevo generador":    "_on_abrir_generadores",
    "Fuera de presupuesto": "_on_abrir_extra",
    "Abrir DXF":          "_on_cad_abrir",
    "Seleccionar":        "_on_cad_tool_select",
    "Volver al presupuesto": "_on_volver_presupuesto",
    "Línea":              "_on_cad_tool_line",
    "Polilínea":          "_on_cad_tool_polyline",
    "Área":               "_on_cad_tool_polygon",
    "Contar":             "_on_cad_tool_count",
    "Calibrar":           "_on_cad_calibrar",
    "Ajustar vista":      "_on_cad_fit",
    "Capas":              "_on_cad_capas",
    "Cuantificar":        "_on_cad_cuantificar",
    "Exportar PDF (CAD)": "_on_cad_export_pdf",
    "Exportar Excel (CAD)": "_on_cad_export_excel",
    "Deshacer CAD":       "_on_cad_undo",
    "Rehacer CAD":        "_on_cad_redo",
    "Cortar":             "_on_cortar_toolbar",
    "Pegar":              "_on_pegar_toolbar",
    "Filtro":             "_on_filtro_toolbar",
    "Rastrear uso":       "_on_rastrear_uso_toolbar",
    "Filtrar":            "_on_filtro_menu",
    "Limpiar filtros":    "_on_limpiar_filtros",
    "Atajos de teclado":  "_on_mostrar_ayuda",
}

# Atajos de teclado para acciones de la cinta (tip → tecla).
# Se registran como WindowShortcut en paneles.py y se muestran en el
# tooltip del botón. Acciones ya cubiertas por atajos existentes
# (Deshacer/Rehacer, Copiar/Cortar/Pegar, Alt+flechas, Insert/Delete/F2/F5)
# no van aquí para no crear QShortcut duplicados/ambiguos.
_ATAJOS = {
    "Filtrar":             "Ctrl+Shift+F",
    "Limpiar filtros":     "Ctrl+Shift+D",
    "Recalcular":          "Ctrl+R",
    "Ajustar":             "Ctrl+=",
}

_TOOLBAR_CFG = {
    "PROYECTO": [
        ("Archivo",      [("plus", "Nuevo"), ("folder-open", "Abrir"), ("x", "Cerrar")]),
        ("Gestión",      [("clipboard", "Duplicar"), ("pencil", "Renombrar"), ("trash-2", "Eliminar proyecto")]),
        ("Transferir",   [("upload", "Exportar"), ("download", "Importar OPUS")]),
        ("Explorar",     []),
    ],
    "INICIO": [
        ("Proyecto", [("settings", "Parámetros proyecto"), ("info", "Información proyecto")]),
        ("Sobrecostos", [("banknote", "Cálculo de indirectos"), ("hard-hat", "Personal en indirectos"), ("bar-chart", "Cálculo de sobrecostos")]),
        ("Fórmulas", [("sigma", "Variables de fórmula")]),
        ("CAD", [("ruler", "Nuevo generador")]),
        ("Extra", [("zap", "Fuera de presupuesto")]),
        ("Sistema",  [("settings", "Configuración general"), ("users", "Usuarios")]),
    ],
    "INFORMES": [
        ("Generar", [
            ("file-text", "Presupuesto"),
            ("clipboard", "APU"),
            ("package", "Explosión"),
            ("book-open", "Catálogo"),
        ]),
        ("Exportar", [
            ("upload", "Compilar PDF"),
            ("eye", "Vista previa"),
        ]),
        ("Plantilla", [
            ("brush", "Tema LaTeX"),
            ("printer", "Configurar impresión"),
        ]),
    ],
    "VISTA": [
        ("Columnas", [
            ("move-horizontal", "Ajustar"),
            ("eye", "Mostrar/Ocultar"),
        ]),

        ("Presentación", [
            ("layout-grid", "Formato columnas"),
            ("refresh-cw", "Restablecer"),
        ]),

        ("Ventana", [
            ("maximize", "Pantalla completa"),
        ]),

        ("Aspecto", [("brush", "__TEMAS__")]),

        ("Ayuda", [
            ("help-circle", "Atajos de teclado"),
        ]),

        ("Ver", [
            ("search", "Filtro"),
        ]),
    ],
    "PRINCIPAL": [
        ("Historial",    [[("undo-2", "Deshacer"), ("redo-2", "Rehacer")]]),
        ("Portapapeles", [("clipboard", "Copiar"), [("scissors", "Cortar"), ("file-text", "Pegar"), ("check-square", "Seleccionar todo")]]),
        ("Editar",       [[("square-plus", "Agregar agrupador"), ("plus", "Agregar concepto")], ("pen-line", "Modificar"), [("corner-down-right", "Desglosar"), ("search", "Rastrear uso")], ("x", "Eliminar")]),
        ("Estructura",   [[("chevron-left", "Izquierda"), ("chevron-right", "Derecha")],[("chevron-up", "Subir"), ("chevron-down", "Bajar")]]),
        ("Filtros", [
            ("filter", "Filtrar"),
            ("filter-x", "Limpiar filtros"),
        ]),
        ("Desplegar",    [("hash", "Primer nivel"), ("sigma", "Resumen agrupadores"), ("square-plus", "Todo"), ("align-left", "Nivel")]),
        ("Cálculo",      [("refresh-cw", "Recalcular"), ("list", "Renumerar")]),
    ],
    "HERRAMIENTAS": [
        ("Sistema",     [("settings", "Configuración")]),
        ("Proyecto",    [("folder", "Abrir carpeta BD"), ("paperclip", "Adjuntar archivo"),
                         ("folder-open", "Ver adjuntos"),
                         ("wrench", "Depurar catálogos"), ("tag", "Homologar hash")]),
        ("Utilidades",  [("calculator", "Calculadora")]),
    ],
    "GENERADORES": [
        ("Salir",         [("chevron-left", "Volver al presupuesto")]),
        ("Archivo",      [("folder-open", "Abrir DXF")]),
        ("Herramientas", [("arrow-up-left", "Seleccionar"), ("slash", "Línea"),
                          ("corner-down-right", "Polilínea"), ("hexagon", "Área"),
                          ("hash", "Contar")]),
        ("Vista",        [("triangle", "Calibrar"), ("move", "Ajustar vista"), ("eye", "Capas")]),
        ("Datos",        [("sigma", "Cuantificar"), ("file-text", "Exportar PDF (CAD)"),
                          ("bar-chart", "Exportar Excel (CAD)")]),
        ("Edición",      [[("undo-2", "Deshacer CAD"), ("redo-2", "Rehacer CAD")]]),
    ],
}


class ToolbarMixin:
    """Mixin de toolbar — se mezcla en VentanaPrincipal.

    Nota: `self` siempre es la instancia de VentanaPrincipal.
    Los atributos como self._tab_activa, self._stacked, self._tab_btns
    se definen en VentanaPrincipal.__init__ o en otros mixins.
    """

    def _build_tab_bar(self, parent_layout):
        """Crea fila de botones de pestañas (PROYECTO, INICIO, …, HERRAMIENTAS) conmutables."""
        bar    = QWidget()
        bar.setObjectName("tabBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._tab_btns = []
        self._tab_btns_by_name = {}
        for name in ["PROYECTO", "INICIO", "INFORMES", "VISTA", "PRINCIPAL", "HERRAMIENTAS", "GENERADORES"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, n=name: self._switch_tab(n))
            self._tab_btns.append(btn)
            self._tab_btns_by_name[name] = btn
            layout.addWidget(btn)

        layout.addStretch()
        parent_layout.addWidget(bar)

    # ── Barra de búsqueda ─────────────────────────────────────────────────
    # Filtro de texto que se aplica al TreeTableWidget activo.
    # Conectado a TreeTableWidget.filter_rows().

    def _build_search_bar(self, parent_layout):
        """Crea barra de búsqueda con QLineEdit y menú contextual de columnas."""
        from frontend.ventana.iconos import search_input
        bar = QWidget()
        bar.setObjectName("searchBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        wrapper, inp = search_input("Buscar en el proyecto…", "searchInput")
        inp.textChanged.connect(self._on_search)
        inp.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        inp.customContextMenuRequested.connect(self._on_search_context_menu)
        self._search_input = inp
        # Escape con el foco en la búsqueda: vuelve a la tabla activa
        # (la tecla queda libre para la tabla, que la usa para cancelar cortes).
        sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self._search_input)
        sc_esc.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_esc.activated.connect(self._on_salir_busqueda)
        layout.addWidget(wrapper)
        parent_layout.addWidget(bar)

    def _on_salir_busqueda(self):
        """Escape desde la barra de búsqueda: devuelve el foco a la tabla
        activa conservando el filtro aplicado (para navegar los resultados)."""
        t = self._get_active_table()
        if t:
            t.setFocus()
        else:
            self._search_input.clearFocus()

    def _on_search_context_menu(self, pos):
        """Menú contextual de la barra de búsqueda: checkboxes por columna.
        Solo muestra columnas visibles. Usa triggered (no toggled) para
        evitar que setChecked() durante la construcción dispare el filtro.
        """
        from frontend.ventana.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if not isinstance(w, TreeTableWidget):
            return
        searchable = [(c, l) for c, l in w.get_searchable_columns() if not w.isColumnHidden(c)]
        if not searchable:
            return
        all_cols = {c for c, _ in searchable}
        menu = QMenu(self._search_input)
        current = w.get_search_columns()
        for idx, label in searchable:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(current is None or idx in current)
            act.triggered.connect(lambda checked, c=idx, a=all_cols:
                                  self._on_search_col_toggle(c, checked, a))
        menu.exec(self._search_input.mapToGlobal(pos))

    def _on_search_col_toggle(self, col: int, checked: bool, all_cols: set[int]):
        """Activa/desactiva una columna del filtro de búsqueda."""
        from frontend.ventana.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if not isinstance(w, TreeTableWidget):
            return
        current = w.get_search_columns()
        if current is None:
            cols = all_cols - {col} if not checked else all_cols
        else:
            cols = set(current)
            if checked:
                cols.add(col)
            else:
                cols.discard(col)
            if cols == all_cols:
                cols = None
        w.set_search_columns(cols)
        self._on_search(self._search_input.text())

    # ── Toolbar ───────────────────────────────────────────────────────────
    # QStackedWidget con una página por pestaña.
    # Cada página se construye bajo demanda (lazy) desde _TOOLBAR_CFG.
    # ───────────────────────────────────────────────────────────────────────

    def _build_toolbar(self, parent_layout):
        """Crea el QStackedWidget y reserva una página vacía por cada tab en _TOOLBAR_CFG."""
        self._tb       = QStackedWidget()
        self._tb.setObjectName("tbCustom")
        self._tb_pages  = {}
        self._tb_built  = set()
        self._tb_labels = []

        for tab_name in _TOOLBAR_CFG:
            page = QWidget()
            self._tb_pages[tab_name] = self._tb.addWidget(page)

        parent_layout.addWidget(self._tb)
        self._build_page("PRINCIPAL")

        # Ciclo de zonas (Tab/Shift+Tab) a nivel APLICACIÓN: un filtro por
        # widget dejaba fugas — la barra de búsqueda, las tablas y el bar de
        # pestañas no lo tenían y el Shift+Tab pasaba por ellos con el
        # traversal nativo. El guard `obj.window() is not self` de
        # _navegar_cinta excluye diálogos y popups; los filtros de los
        # editores de celda (delegado) corren antes que este y consumen
        # sus propias teclas.
        if not getattr(self, "_filtro_zonas_instalado", False):
            QApplication.instance().installEventFilter(self)
            self._filtro_zonas_instalado = True

    def _build_page(self, tab_name):
        """Construye (una sola vez) la página de toolbar para tab_name."""
        page = self._tb.widget(self._tb_pages[tab_name])
        if tab_name in self._tb_built:
            return
        self._tb_built.add(tab_name)

        layout = QHBoxLayout(page)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        groups         = _TOOLBAR_CFG[tab_name]
        # Altura mínima: entre más items apilados, más alto el botón
        page_max_rows  = max(
            (max((len(item) if isinstance(item, list) else 1) for item in g[1])
             if g[1] else 0)
            for g in groups
        ) if any(g[1] for g in groups) else 1
        page_min_btn_h = max(56, page_max_rows * 26)

        for idx, (label, items) in enumerate(groups):
            if not items:
                continue
            if idx > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setObjectName("tbSep")
                sep.setFixedWidth(1)
                layout.addWidget(sep)

            g  = QWidget()
            g.setObjectName("tbGroup")
            gl = QVBoxLayout(g)
            gl.setContentsMargins(6, 0, 6, 0)
            gl.setSpacing(0)
            gl.addStretch()
            if label == "Aspecto":
                gl.addWidget(self._build_aspecto_ui())
            else:
                gl.addWidget(self._build_btn_wrap(items, page_min_btn_h))

            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tb_labels.append(lbl)
            gl.addWidget(lbl)
            layout.addWidget(g)
            # Sin esto, cada grupo se estira a SU propia altura natural
            # dentro de la fila (el grupo "Aspecto", por ejemplo, no pasa
            # por page_min_btn_h como los demás — ver el if de arriba), y
            # como la etiqueta está anclada al fondo de cada grupo vía
            # addStretch() al inicio de su propio QVBoxLayout, grupos de
            # distinta altura natural terminan con la etiqueta a una
            # altura distinta. Alinear cada grupo al fondo de la fila
            # normaliza el punto de referencia: todas las etiquetas
            # quedan a la misma altura sin importar cuánto mida el
            # contenido de arriba en cada grupo.
            layout.setAlignment(g, Qt.AlignmentFlag.AlignBottom)

        layout.addStretch()
        self._update_label_colors()

    def _build_btn_wrap(self, items: list, min_height: int) -> QWidget:
        """
        Construye el contenedor de botones de un grupo de toolbar.
        Hay tres casos según la composición de items:
          - Solo simples (icon, tip)         → fila horizontal de botones grandes
          - Solo apilados [(icon,tip), ...]  → columna vertical de botones pequeños
          - Mixto                            → fila horizontal, cada item en su columna
        Un item simple también puede ser un item de menú: (icon, label, [(icon,tip),...])
        — un solo botón que despliega las acciones agrupadas en un QMenu, para
        grupos donde varias acciones son variantes de la misma decisión
        (ver "Desplegar" en PRINCIPAL). Se distingue del simple por tener 3
        elementos en vez de 2.
        """
        has_stack  = any(isinstance(item, list) for item in items)
        has_single = any(not isinstance(item, list) for item in items)

        if has_stack and has_single:
            # Mixto: columna por cada item
            wrap = QWidget()
            bl   = QHBoxLayout(wrap)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)
            for item in items:
                col = QWidget()
                cl  = QVBoxLayout(col)
                cl.setContentsMargins(0, 0, 0, 0)
                cl.setSpacing(0)
                cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if isinstance(item, list):
                    sz, fs = (22, 11) if len(item) == 2 else (16, 9)
                    for icon_char, tip in item:
                        cl.addWidget(self._make_stacked_btn(icon_char, tip, sz, fs))
                else:
                    cl.addWidget(self._make_item_btn(item))
                bl.addWidget(col)
            wrap.setMinimumHeight(min_height)
            return wrap

        if has_stack:
            # Solo apilados: fila horizontal, cada grupo en su columna
            wrap = QWidget()
            bl   = QHBoxLayout(wrap)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(4)
            for item in items:
                col = QWidget()
                cl  = QVBoxLayout(col)
                cl.setContentsMargins(0, 0, 0, 0)
                cl.setSpacing(0)
                cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sz, fs = (22, 11) if len(item) == 2 else (16, 9)
                for icon_char, tip in item:
                    cl.addWidget(self._make_stacked_btn(icon_char, tip, sz, fs))
                bl.addWidget(col)
            wrap.setMinimumHeight(min_height)
            return wrap

        # Solo simples: fila horizontal de botones grandes (texto bajo icono)
        wrap = QWidget()
        bl   = QHBoxLayout(wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for item in items:
            bl.addWidget(self._make_item_btn(item))
        wrap.setMinimumHeight(min_height)
        return wrap

    def _make_item_btn(self, item):
        """Despacha un item 'simple' de toolbar a botón normal o botón-menú
        según su forma: (icon, tip) → _make_big_btn; (icon, label, submenu) → _make_menu_btn."""
        if len(item) == 3:
            icon_char, label, submenu = item
            return self._make_menu_btn(icon_char, label, submenu)
        icon_char, tip = item
        return self._make_big_btn(icon_char, tip)

    def _make_big_btn(self, icon_char, tip):
        """Botón grande con icono arriba y texto abajo (ToolButtonTextUnderIcon)."""
        btn = QToolButton()
        btn.setIcon(icono(icon_char, 40))
        btn.setToolTip(self._tip_con_atajo(tip))
        btn.setText(tip)
        btn.setIconSize(QSize(40, 40))
        btn.setAutoRaise(True)
        btn.setMinimumSize(80, 56)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._conectar_btn(btn, tip)
        self._style_toolbar_btn(btn)
        return btn

    def _make_menu_btn(self, icon_char, label, submenu):
        """Botón grande igual a _make_big_btn, pero que despliega un QMenu
        con las acciones de `submenu` (lista de (icon, tip)) en vez de
        disparar un único handler al hacer clic.

        Se usa para colapsar grupos de botones que son variantes de una
        misma decisión (ej. "Desplegar": Primer nivel / Resumen agrupadores /
        Todo / Nivel) en un solo botón, sin tocar _HANDLERS ni los métodos
        _on_* existentes: cada acción del menú sigue enrutando al mismo
        handler que tenía su botón individual.
        """
        btn = QToolButton()
        btn.setIcon(icono(icon_char, 40))
        btn.setToolTip(label)
        btn.setText(label)
        btn.setIconSize(QSize(40, 40))
        btn.setAutoRaise(True)
        btn.setMinimumSize(80, 56)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        # _conectado = True a mano: _make_menu_btn no pasa por _conectar_btn
        # (no dispara un único handler al click, sino un QMenu), pero SÍ
        # está funcionalmente conectado — cada acción del menú enruta a su
        # propio handler más abajo. Sin esto, _style_toolbar_btn lo pintaría
        # atenuado con sufijo "(beta)" como si no tuviera handler.
        btn._conectado = True
        if not hasattr(self, "_tb_buttons_by_tip"):
            self._tb_buttons_by_tip = {}
        self._tb_buttons_by_tip[label] = btn
        self._style_toolbar_btn(btn)

        menu = QMenu(btn)
        for icon_sub, tip in submenu:
            act = menu.addAction(icono(icon_sub, 20), self._tip_con_atajo(tip))
            handler_name = _HANDLERS.get(tip)
            handler = getattr(self, handler_name, None) if handler_name else None
            if handler:
                act.triggered.connect(handler)
            else:
                act.setEnabled(False)
        btn.setMenu(menu)
        return btn

    def _tip_con_atajo(self, tip):
        """Tooltip con el atajo de teclado si la acción tiene uno."""
        seq = _ATAJOS.get(tip)
        return f"{tip} ({seq})" if seq else tip


    def _make_stacked_btn(self, icon_char, tip, sz, fs):
        """Botón pequeño para grupos apilados (ToolButtonTextBesideIcon)."""
        btn = QToolButton()
        btn.setObjectName("tbStackedBtn")
        btn.setIcon(icono(icon_char, sz))
        btn.setToolTip(self._tip_con_atajo(tip))
        btn.setText(tip)
        btn.setIconSize(QSize(sz, sz))
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        btn.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._conectar_btn(btn, tip)
        self._style_toolbar_btn(btn)
        return btn

    def _conectar_btn(self, btn, tip):
        """Enruta el click del botón al handler según _HANDLERS dict.
        Marca btn._conectado = True/False para que _style_toolbar_btn decida el estilo.
        """
        if not hasattr(self, "_tb_buttons_by_tip"):
            self._tb_buttons_by_tip = {}
        self._tb_buttons_by_tip[tip] = btn
        handler_name = _HANDLERS.get(tip)
        if handler_name:
            handler = getattr(self, handler_name, None)
            if handler:
                btn.clicked.connect(handler)
                btn._conectado = True
                return
        btn._conectado = False

    def _style_toolbar_btn(self, btn):
        """Deshabilita y atenúa botones sin handler conectado.

        Antes solo se atenuaba el color y se le agregaba "(beta)" al
        tooltip, pero el botón seguía completamente clicable — sin
        setEnabled(False), hacer clic en él no hacía absolutamente nada,
        en silencio, sin ningún error ni mensaje. Alguien que no se
        detuviera a leer el tooltip completo no tenía otra forma de
        enterarse de que ese botón no hace nada; un botón deshabilitado
        de verdad lo comunica solo, sin necesidad de leer nada.
        """
        if getattr(btn, "_conectado", False):
            return
        btn.setToolTip(btn.toolTip() + " (beta)")
        btn.setStyleSheet(f"color: {MUTED};")
        btn.setEnabled(False)

    def _switch_tab(self, name):
        """Cambia la pestaña activa de la toolbar, construye la página si es necesario.

        También sincroniza self._central_stack (ver _build_central en
        ventana.py): GENERADORES muestra su propio espacio de trabajo
        (self._tabs_generadores + self._renglones_stack); cualquier otra
        pestaña muestra el espacio normal (sidebar + self._tabs) — así,
        clicar cualquier pestaña del ribbon que no sea GENERADORES ya
        regresa sola al espacio normal, sin quedar en un estado
        mezclado (ribbon de un lado, contenido del otro).
        """
        if not hasattr(self, "_tb_pages") or name not in self._tb_pages:
            return
        anterior = getattr(self, "_tab_activa", None)
        if name == "GENERADORES" and anterior != "GENERADORES":
            # Recordado para "Volver al presupuesto" (ver
            # _on_volver_presupuesto en mixins/generador.py).
            self._tab_antes_generadores = anterior or "PRINCIPAL"
        self._tab_activa = name
        for btn in self._tab_btns:
            btn.setChecked(btn.text() == name)
        self._build_page(name)
        self._tb.setCurrentIndex(self._tb_pages[name])
        if hasattr(self, "_central_stack"):
            self._central_stack.setCurrentIndex(1 if name == "GENERADORES" else 0)

    def _update_label_colors(self):
        color = TEXT if getattr(self, '_tema_modo', 'oscuro') == 'oscuro' else TEXT_INVERSO
        for lbl in self._tb_labels:
            lbl.setStyleSheet(
                f"color: {color}; background-color: transparent;"
                f"font-size: 10px; font-weight: bold; margin-top: 1px;"
            )

    # ── Navegación por teclado entre las 4 zonas ──────────────────────────
    # El programa se usa solo con teclado en 4 zonas:
    #   cinta (pestañas PROYECTO/INICIO/…) · herramientas (botones) ·
    #   panel (sidebar) · area (pestañas de contenido)
    # Tab / Shift+Tab ciclan las zonas; dentro de cada zona las flechas
    # navegan (nativo en árboles/tablas, espacial en la cinta).
    # Enter/Espacio en una pestaña de cinta cambia de cinta.
    _ZONAS = ["cinta", "herramientas", "panel", "area"]

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress and self._navegar_cinta(obj, event):
            return True
        return super().eventFilter(obj, event)

    def _navegar_cinta(self, obj, event):
        """Maneja Tab/Shift+Tab (ciclo de zonas, desde cualquier widget) y
        flechas (dentro de la cinta). True si consumió la tecla."""
        # Solo dentro de la ventana principal: los diálogos modales (hijos
        # de esta ventana) y los popups tienen su propio ciclo de Tab.
        if getattr(obj, "window", lambda: None)() is not self:
            return False
        key = event.key()
        if (key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab)
                and not (event.modifiers() & (Qt.KeyboardModifier.ControlModifier
                                             | Qt.KeyboardModifier.AltModifier
                                             | Qt.KeyboardModifier.MetaModifier))):
            actual = self._zona_de(obj) or self._zona_de(QApplication.focusWidget())
            self._ciclar_zona(actual, backward=key == Qt.Key.Key_Backtab)
            return True
        dirs = {
            Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1),
        }
        if obj in self._tab_btns:
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                self._switch_tab(obj.text())
                return True
            if key in dirs:
                self._mover_foco_cinta(*dirs[key])
                return True
        elif isinstance(obj, QToolButton) and self._es_de_cinta(obj):
            if key in dirs:
                self._mover_foco_cinta(*dirs[key])
                return True
        return False

    def _zona_de(self, widget):
        """Devuelve la zona a la que pertenece `widget` (o None)."""
        if not widget:
            return None
        cur = widget
        while cur is not None:
            if cur in self._tab_btns:
                return "cinta"
            if isinstance(cur, QToolButton) and self._es_de_cinta(cur):
                return "herramientas"
            if cur is getattr(self, "_sidebar_tree", None):
                return "panel"
            if cur is getattr(self, "_search_input", None):
                return "area"
            if cur is getattr(self, "_tabs", None):
                return "area"
            cur = cur.parent()
        return None

    def _ciclar_zona(self, actual, backward=False):
        """Lleva el foco a la siguiente (o anterior) zona de _ZONAS."""
        if actual not in self._ZONAS:
            actual = self._ZONAS[0]
        idx = self._ZONAS.index(actual)
        delta = -1 if backward else 1
        for _ in range(len(self._ZONAS)):
            idx = (idx + delta) % len(self._ZONAS)
            if self._foco_zona(self._ZONAS[idx]):
                return

    def _foco_zona(self, zona):
        """Pone el foco en el primer widget útil de la zona. True si pudo."""
        if zona == "cinta":
            btn = self._tab_btns_by_name.get(self._tab_activa)
            if btn:
                btn.setFocus()
                return True
            return False
        if zona == "herramientas":
            pagina = self._tb.currentWidget()
            btns = [b for b in pagina.findChildren(QToolButton) if b.isVisible()] if pagina else []
            if btns:
                btns[0].setFocus()
                return True
            return False
        if zona == "panel":
            tree = getattr(self, "_sidebar_tree", None)
            if tree:
                # OJO: setFocus() hace que Qt auto-asigne currentItem al
                # primer ítem (el header de sección) — por eso el chequeo
                # es sobre selectedItems() y no sobre currentItem().
                tree.setFocus()
                if not tree.selectedItems() and tree.topLevelItemCount() > 0:
                    raiz = tree.topLevelItem(0)
                    # Primer elemento útil (hijo de la sección), no el header
                    primero = raiz.child(0) if raiz.childCount() > 0 else raiz
                    tree.setCurrentItem(primero)
                    # setCurrentItem marca CURRENT pero no SELECTED: sin
                    # setSelected no hay resaltado visible.
                    primero.setSelected(True)
                return True
            return False
        if zona == "area":
            t = self._get_active_table()
            if t:
                t.setFocus()
                # Mismo criterio que "panel": primera fila con selección
                # visible si no había nada.
                if not t.selectedItems() and t.topLevelItemCount() > 0:
                    primero = t.topLevelItem(0)
                    t.setCurrentItem(primero)
                    primero.setSelected(True)
                return True
            if hasattr(self, "_tabs"):
                self._tabs.setFocus()
                return True
        return False

    def _es_de_cinta(self, widget):
        cur = widget.parent()
        while cur is not None:
            if cur is self._tb:
                return True
            cur = cur.parent()
        return False

    def _candidatos_cinta(self, zona=None):
        """Candidatos para navegación espacial con flechas. Si se da `zona`,
        solo devuelve widgets de esa zona — sin este filtro, un botón al
        borde de "herramientas" podía brincar por distancia al botón más
        cercano de "cinta" (zona distinta), rompiendo el principio de que
        las flechas navegan DENTRO de la zona actual y Tab es lo único que
        cambia de zona."""
        if zona == "cinta":
            return list(self._tab_btns)
        if zona == "herramientas":
            return [b for b in self._tb.findChildren(QToolButton) if b.isVisible()]
        cands = list(self._tab_btns)
        cands += [b for b in self._tb.findChildren(QToolButton) if b.isVisible()]
        return cands

    def _mover_foco_cinta(self, dx, dy):
        """Lleva el foco al botón más cercano en la dirección (dx, dy),
        sin salir de la zona (cinta o herramientas) del widget con foco."""
        origen = QApplication.focusWidget()
        if origen is None:
            return

        def centro(w):
            return w.mapTo(self, w.rect().center())

        oc = centro(origen)
        zona_origen = self._zona_de(origen)
        mejor, mejor_score = None, None
        for b in self._candidatos_cinta(zona_origen):
            if b is origen or not b.isVisible():
                continue
            v = centro(b) - oc
            along = v.x() * dx + v.y() * dy
            if along <= 0:
                continue
            perp = v.x() * -dy + v.y() * dx
            score = along + abs(perp) * 3.0
            if mejor_score is None or score < mejor_score:
                mejor, mejor_score = b, score
        if mejor is not None:
            mejor.setFocus()

    # ── Temas: Acendente + Modo ─────────────────────────────────────

    def _build_aspecto_ui(self):
        """Fila única: 4 botones de acento + toggle modo."""
        wrap = QWidget()
        bl   = QHBoxLayout(wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(2)
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for key in Temas.ACENTOS:
            btn = QToolButton()
            btn.setIcon(icono("brush", 28))
            btn.setToolTip(Temas.nombre_acento(key))
            btn.setText(Temas.nombre_acento(key))
            btn.setIconSize(QSize(28, 28))
            btn.setAutoRaise(True)
            btn.setMinimumSize(68, 48)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn._conectado = True
            btn.clicked.connect(lambda checked=False, k=key: self._set_accent(k))
            bl.addWidget(btn)

        # Toggle modo
        self._modo_btn = QToolButton()
        self._modo_btn.setIcon(icono("moon", 28))
        self._modo_btn.setToolTip("Modo")
        self._modo_btn.setText("Modo")
        self._modo_btn.setIconSize(QSize(28, 28))
        self._modo_btn.setAutoRaise(True)
        self._modo_btn.setMinimumSize(68, 48)
        self._modo_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._modo_btn._conectado = True
        self._modo_btn.clicked.connect(self._toggle_mode)
        bl.addWidget(self._modo_btn)

        # Selector de conjunto de iconos
        self._iconos_btn = QToolButton()
        self._iconos_btn.setIcon(icono("layers", 28))
        self._iconos_btn.setToolTip("Conjunto de iconos")
        self._iconos_btn.setText("Iconos")
        self._iconos_btn.setIconSize(QSize(28, 28))
        self._iconos_btn.setAutoRaise(True)
        self._iconos_btn.setMinimumSize(68, 48)
        self._iconos_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._iconos_btn._conectado = True
        self._iconos_btn.clicked.connect(self._show_iconos_menu)
        bl.addWidget(self._iconos_btn)

        self._sync_modo_icon()
        return wrap

    def _sync_modo_icon(self):
        from frontend.ventana.iconos import set_default_tint
        modo = getattr(self, '_tema_modo', 'oscuro')
        icon = "moon" if modo == 'oscuro' else "sun"
        self._modo_btn.setIcon(icono(icon, 28))
        set_default_tint(TEXT if modo == 'oscuro' else TEXT_INVERSO)

    def _set_accent(self, acento: str):
        app = QApplication.instance()
        modo = getattr(self, '_tema_modo', 'oscuro')
        self._tema_acento = acento
        Temas.aplicar(app, modo, acento)
        Temas.guardar_preferencia(acento=acento)
        self._switch_tab(self._tab_activa)
        self._update_statusbar()

    def _toggle_mode(self):
        app = QApplication.instance()
        modo = getattr(self, '_tema_modo', 'oscuro')
        nuevo = "claro" if modo == "oscuro" else "oscuro"
        self._tema_modo = nuevo
        acento = getattr(self, '_tema_acento', 'azul')
        Temas.aplicar(app, nuevo, acento)
        Temas.guardar_preferencia(modo=nuevo)
        self._sync_modo_icon()
        self._switch_tab(self._tab_activa)
        self._update_statusbar()

    def _show_iconos_menu(self):
        """Mini menu para elegir conjunto de iconos."""
        from frontend.ventana.iconos import get_iconos
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self._iconos_btn)
        actual = get_iconos()
        opciones = [
            ("Lucide", "lucide"),
            ("Icons8 Color", "icons8"),
        ]
        for label, key in opciones:
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == actual)
            act.triggered.connect(lambda checked=False, k=key: self._on_iconos_change(k))
        menu.exec(self._iconos_btn.mapToGlobal(self._iconos_btn.rect().bottomLeft()))

    def _on_iconos_change(self, conjunto: str):
        from frontend.ventana.iconos import set_iconos
        set_iconos(conjunto)
        from backend.database.db import Config
        Config.set("iconos", conjunto)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Conjunto de iconos",
            "Reinicia la aplicación para que los cambios surtan efecto."
        )

    # ── Handlers de toolbar recién cableados ────────────────────────

    def _on_cortar_toolbar(self):
        w = self._tabs.currentWidget()
        if hasattr(w, '_cut'):
            w._cut()

    def _on_pegar_toolbar(self):
        w = self._tabs.currentWidget()
        if hasattr(w, '_paste'):
            w._paste()

    def _on_filtro_toolbar(self):
        self._search_input.setVisible(not self._search_input.isVisible())

    def _on_filtro_menu(self):
        from PySide6.QtWidgets import QDialog
        from frontend.ventana.widgets.filtros import FilterDialog
        t = self._get_active_table()
        if not t:
            self._sb.showMessage("No hay una tabla activa para filtrar.", 3000)
            return
        dlg = FilterDialog(self, t)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            filters = dlg.get_filters()
            t.set_filters(filters)
            t.filter_rows(self._search_input.text())

    def _on_limpiar_filtros(self):
        t = self._get_active_table()
        if t:
            t.set_filters([])
            t.filter_rows(self._search_input.text())

    def _on_rastrear_uso_toolbar(self):
        """Rastrea el insumo seleccionado en la tabla/árbol activo."""
        from frontend.ventana.widgets.arbol import INSUMO_ROLE, TIPO_ROLE
        w = self._tabs.currentWidget()
        if w is None:
            return
        items = w.selectedItems() if hasattr(w, 'selectedItems') else []
        if not items:
            ci = w.currentItem() if hasattr(w, 'currentItem') else None
            if ci:
                items = [ci]
        if not items:
            return
        item = items[0]
        insumo_id = None
        tipo = item.data(0, TIPO_ROLE)
        if tipo:
            if tipo == "concepto":
                insumo_id = item.data(0, INSUMO_ROLE)
        else:
            matriz_id = item.data(0, Qt.ItemDataRole.UserRole)
            es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if es_compuesto is not None:
                insumo_id = matriz_id
            elif matriz_id and matriz_id < 0:
                insumo_id = -matriz_id
        if insumo_id:
            self._on_rastrear_insumo(insumo_id)
