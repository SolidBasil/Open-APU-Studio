"""
toolbar.py
==========
Mixin de toolbar para VentanaPrincipal.

Contiene toda la lógica de construcción y gestión de la toolbar superior:
pestañas (PROYECTO/INICIO/…), botones, temas visuales y barra de búsqueda.
"""

from PySide6.QtCore    import Qt, QRect, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QFrame, QToolButton, QLabel, QLineEdit, QMenu,
    QApplication,
)
from PySide6.QtGui import QIcon

from frontend.temas import Temas
from frontend.ventana.iconos import icono



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
    "Izquierda":         "_on_izquierda",
    "Derecha":           "_on_derecha",
    "Subir":             "_on_subir",
    "Bajar":             "_on_bajar",
    "Información proyecto": "_on_info_proyecto",
    "Parámetros proyecto": "_on_info_proyecto",
    "Presupuesto":       "_on_generar_presupuesto",
    "Compilar PDF":      "_on_compilar_pdf",
    "Vista previa":      "_on_vista_previa",
    "Eliminar":          "_on_eliminar",
    "Agregar agrupador": "_on_agregar_agrupador",
    "Agregar concepto":  "_on_agregar_concepto",
    "Deshacer":          "_on_deshacer",
    "Rehacer":           "_on_rehacer",
    "Cálculo de indirectos": "_on_indirectos",
    "Personal en indirectos": "_on_personal_indirectos",
    "Cálculo de sobrecostos": "_on_sobrecostos",
    "Generadores":        "_on_abrir_generadores",
    "Abrir DXF":          "_on_cad_abrir",
    "Seleccionar":        "_on_cad_tool_select",
    "Línea":              "_on_cad_tool_line",
    "Polígono":           "_on_cad_tool_polygon",
    "Punto":              "_on_cad_tool_point",
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
        ("CAD", [("ruler", "Generadores")]),
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

        ("Ver", [
            ("search", "Filtro"),
        ]),
    ],
    "PRINCIPAL": [
        ("Historial",    [[("undo-2", "Deshacer"), ("redo-2", "Rehacer")]]),
        ("Portapapeles", [("clipboard", "Copiar"), [("scissors", "Cortar"), ("file-text", "Pegar"), ("check-square", "Seleccionar todo")]]),
        ("Editar",       [[("square-plus", "Agregar agrupador"), ("plus", "Agregar concepto")], ("pen-line", "Modificar"), ("corner-down-right", "Desglosar"), ("x", "Eliminar")]),
        ("Estructura",   [[("chevron-left", "Izquierda"), ("chevron-right", "Derecha")],[("chevron-up", "Subir"), ("chevron-down", "Bajar")]]),
        ("Buscar",       [("book-open", "En catálogos"), ("eye", "En vista")]),
        ("Desplegar",    [("hash", "Primer nivel"), ("sigma", "Resumen agrupadores"), ("square-plus", "Todo"), ("align-left", "Nivel")]),
        ("Rastreo",      [("search", "Rastrear uso")]),
        ("Cálculo",      [("refresh-cw", "Recalcular")]),
    ],
    "HERRAMIENTAS": [
        ("Sistema",     [("settings", "Configuración")]),
        ("Proyecto",    [("folder", "Abrir carpeta BD"), ("paperclip", "Adjuntar archivo"),
                         ("folder-open", "Ver adjuntos"),
                         ("wrench", "Depurar catálogos"), ("tag", "Homologar hash")]),
        ("Utilidades",  [("calculator", "Calculadora")]),
    ],
    "GENERADORES": [
        ("Archivo",      [("folder-open", "Abrir DXF")]),
        ("Herramientas", [("arrow-up-left", "Seleccionar"), ("slash", "Línea"), ("hexagon", "Polígono"),
                          ("circle", "Punto"), ("hash", "Contar")]),
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
        bar = QWidget()
        bar.setObjectName("searchBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        inp = QLineEdit()
        inp.setObjectName("searchInput")
        inp.setPlaceholderText("🔍  Buscar en el proyecto…")
        inp.setClearButtonEnabled(True)
        inp.textChanged.connect(self._on_search)
        inp.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        inp.customContextMenuRequested.connect(self._on_search_context_menu)
        self._search_input = inp
        layout.addWidget(inp)
        parent_layout.addWidget(bar)

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
        page_min_btn_h = max(56, page_max_rows * 22)

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

        layout.addStretch()
        self._update_label_colors()

    def _build_btn_wrap(self, items: list, min_height: int) -> QWidget:
        """
        Construye el contenedor de botones de un grupo de toolbar.
        Hay tres casos según la composición de items:
          - Solo simples (icon, tip)         → fila horizontal de botones grandes
          - Solo apilados [(icon,tip), ...]  → columna vertical de botones pequeños
          - Mixto                            → fila horizontal, cada item en su columna
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
                    sz, fs = (18, 11) if len(item) == 2 else (12, 9)
                    for icon_char, tip in item:
                        cl.addWidget(self._make_stacked_btn(icon_char, tip, sz, fs))
                else:
                    icon_char, tip = item
                    cl.addWidget(self._make_big_btn(icon_char, tip))
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
                sz, fs = (18, 11) if len(item) == 2 else (12, 9)
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
        for icon_char, tip in items:
            bl.addWidget(self._make_big_btn(icon_char, tip))
        wrap.setMinimumHeight(min_height)
        return wrap

    def _make_big_btn(self, icon_char, tip):
        """Botón grande con icono arriba y texto abajo (ToolButtonTextUnderIcon)."""
        btn = QToolButton()
        btn.setIcon(icono(icon_char, 40, "#E8EDF2"))
        btn.setToolTip(tip)
        btn.setText(tip)
        btn.setIconSize(QSize(40, 40))
        btn.setAutoRaise(True)
        btn.setMinimumSize(80, 56)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._conectar_btn(btn, tip)
        self._style_toolbar_btn(btn)
        return btn

    def _make_stacked_btn(self, icon_char, tip, sz, fs):
        """Botón pequeño para grupos apilados (ToolButtonTextBesideIcon)."""
        btn = QToolButton()
        btn.setObjectName("tbStackedBtn")
        btn.setIcon(icono(icon_char, sz, "#E8EDF2"))
        btn.setToolTip(tip)
        btn.setText(tip)
        btn.setIconSize(QSize(sz, sz))
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
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
        """Aplica estilo atenuado a botones sin handler conectado."""
        if getattr(btn, "_conectado", False):
            return
        btn.setToolTip(btn.toolTip() + " (beta)")
        btn.setStyleSheet("color: #6B7884;")

    def _switch_tab(self, name):
        """Cambia la pestaña activa de la toolbar, construye la página si es necesario."""
        if not hasattr(self, "_tb_pages") or name not in self._tb_pages:
            return
        self._tab_activa = name
        for btn in self._tab_btns:
            btn.setChecked(btn.text() == name)
        self._build_page(name)
        self._tb.setCurrentIndex(self._tb_pages[name])
        # Al cambiar al ribbon GENERADORES, abrir la pestaña de contenido si no está abierta
        if name == "GENERADORES" and hasattr(self, "_focus_or_open_tab"):
            self._focus_or_open_tab("Generadores de obra", temporary=False)

    def _update_label_colors(self):
        from frontend.ventana.colores import TEXT
        color = TEXT if getattr(self, '_tema_modo', 'oscuro') == 'oscuro' else "#1A1F24"
        for lbl in self._tb_labels:
            lbl.setStyleSheet(
                f"color: {color}; background-color: transparent;"
                f"font-size: 10px; font-weight: bold; margin-top: 1px;"
            )

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
            btn.setIcon(icono("brush", 28, "#E8EDF2"))
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
        self._modo_btn.setIcon(icono("moon", 28, "#E8EDF2"))
        self._modo_btn.setToolTip("Modo")
        self._modo_btn.setText("Modo")
        self._modo_btn.setIconSize(QSize(28, 28))
        self._modo_btn.setAutoRaise(True)
        self._modo_btn.setMinimumSize(68, 48)
        self._modo_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._modo_btn._conectado = True
        self._modo_btn.clicked.connect(self._toggle_mode)
        bl.addWidget(self._modo_btn)

        self._sync_modo_icon()
        return wrap

    def _sync_modo_icon(self):
        modo = getattr(self, '_tema_modo', 'oscuro')
        icon = "moon" if modo == 'oscuro' else "sun"
        self._modo_btn.setIcon(icono(icon, 28, "#E8EDF2"))

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