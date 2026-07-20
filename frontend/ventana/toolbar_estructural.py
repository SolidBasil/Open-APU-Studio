"""
toolbar_estructural.py — Ribbon Toolbar para Análisis Estructural
==================================================================
Mixin de ribbon toolbar para la app de análisis estructural — misma
mecánica que frontend/ventana/toolbar.py (ToolbarMixin) de Open APU Studio:
tab bar conmutable + QStackedWidget con páginas construidas bajo demanda
desde _TOOLBAR_CFG.

Pestañas (estilo RAM Elements): INICIO / MODELADO / ANÁLISIS / PROCESO / SALIDA.

Tipos de botón:
    - Botón grande (icono arriba, texto abajo) → importancia alta
    - Columna apilada (icono junto a texto) → importancia media
    - Grid compacto de iconos → filtros de selección

⚠️ TEMPORAL: Muchos botones muestran "(pendiente)" y están grisados.
Solo unos pocos están conectados a handlers reales.
"""

from PySide6.QtCore    import Qt, QRect, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton,
    QStackedWidget, QFrame, QToolButton, QLabel, QLineEdit, QMenu,
    QApplication, QScrollArea,
)
from PySide6.QtGui import QIcon

from frontend.temas import Temas
from frontend.ventana.iconos import icono


# =============================================================================
# ICONOS — Lucide SVG (cross-platform, sin dependencia de fuentes del sistema)
# =============================================================================

_I = {
    # Archivo / Edición
    "abrir":      "folder-open",
    "guardar":    "save",
    "deshacer":   "undo-2",
    "rehacer":    "redo-2",
    "borrar":     "trash-2",
    "agregar":    "plus",
    "copiar":     "copy",
    "cortar":     "scissors",
    "pegar":      "clipboard-paste",
    "editar":     "pencil",
    "duplicar":   "copy",
    "etiqueta":   "tag",
    # Ver / Navegación
    "ver":        "eye",
    "verTodo":    "eye",
    "lista":      "list",
    "grid":       "grid-3x3",
    "buscar":     "search",
    "zoom":       "zoom-in",
    "abrirVentana": "external-link",
    # Acciones
    "config":     "settings",
    "verificar":  "check",
    "todo":       "check-square",
    "imprimir":   "printer",
    "lock":       "lock",
    "unlock":     "unlock",
    "play":       "play",
    "pausa":      "pause",
    "detener":    "square",
    "procesar":   "loader",
    "sync":       "refresh-cw",
    "refresh":    "refresh-cw",
    "docs":       "file-text",
    "pdf":        "file-down",
    "camara":     "camera",
    "mas":        "plus",
    "menos":      "minus",
    "lightbulb":  "lightbulb",
    "rayo":       "zap",
    "cortes":     "scissors",
    "herramientas": "more-horizontal",
    "construccion": "hard-hat",
    "circular":   "circle",
    # Ingeniería
    "fuerza":     "arrow-down",
    "apoyo":      "chevron-down",
    "flecha":     "chevron-right",
    "aprox":      "rotate-ccw",
    "tilde":      "waves",
    "nodo":       "circle-dot",
    "barra":      "move-horizontal",
    "area":       "square",
    "capa":       "layers",
    "diag":       "link",
    "conj":       "grid-2x2",
    "alt":        "chevrons-left",
    "triUp":      "chevron-up",
    "triDown":    "chevron-down",
    "pct":        "percent",
    "uno":        "check-square",
    "xyz":        "type",
    "linea":      "minus",
    "puntos":     "circle-dot",
    "circulo":    "circle",
    "rombo":      "diamond",
    "cuadrado":   "square",
    "cruz":       "x",
    "estrella":   "star",
    "triangulo":  "triangle",
    "lineaHoriz": "grip-horizontal",
    "lineaVert":  "grip-vertical",
}

# =============================================================================
# CONFIGURACIÓN DE LA TOOLBAR
# { tab: [ (grupo_label, [ items... ]), ... ] }
#
# Un item dentro de un grupo puede ser:
#   (icono, "Texto")        -> botón grande (icono arriba / texto abajo)
#   (icono, "Texto▾")       -> botón grande con menú desplegable
#   [(icono,tip), ...]      -> columna de 2-4 botones pequeños apilados
#   {"grid": [(icono,tip) x9]}  -> grid compacto 3x3 de iconos pequeños
#   {"row":  [(icono,tip), ...]} -> fila compacta de iconos pequeños
# =============================================================================

# =============================================================================
# FILTROS DE SELECCIÓN — grid compacto (solo lo esencial)
# =============================================================================

_GRID_SELECCION = {"grid": [
    (_I["nodo"], "Nudos"), (_I["barra"], "Barras"), (_I["area"], "Áreas"),
    (_I["apoyo"], "Apoyos"), (_I["fuerza"], "Cargas"), (_I["capa"], "Por capa"),
]}

_GRUPO_SELECCION = [(_I["todo"], "Todo"), _GRID_SELECCION]

# "Herramientas de la hoja activa" — cambia según qué pestaña del sidebar
# está seleccionada (solo las que tienen handler real)
_HERRAMIENTAS_POR_HOJA = {
    "Coordenadas": [
        (_I["puntos"], "Generación lineal de nudos"),
        (_I["grid"], "Generación cuadrangular de nudos"),
        (_I["circular"], "Generación circular"),
        (_I["linea"], "Alinear nudos en una recta"),
    ],
    "Conectividad": [
        (_I["diag"], "Conectar miembros"),
        (_I["conj"], "Generación de placas"),
        (_I["alt"], "Conectar alternado"),
    ],
    "Restricciones": [(_I["lock"], "Empotrar"), (_I["unlock"], "Liberar")],
    "Secciones": [(_I["agregar"], "Nueva sección"), (_I["duplicar"], "Duplicar sección"), (_I["borrar"], "Eliminar sección")],
    "Materiales": [(_I["agregar"], "Nuevo material"), (_I["borrar"], "Eliminar material")],
    "Cargas sobre miembros": [(_I["agregar"], "Nueva carga"), (_I["borrar"], "Eliminar carga")],
    "Cargas": [(_I["agregar"], "Nueva carga"), (_I["borrar"], "Eliminar carga")],
}

# =============================================================================
# TOOLBAR — 4 pestañas, botones grandes=importante, stacked=secundario
#
# Leyenda de tamaños:
#   ("icono", "Texto")        -> botón GRANDE (importancia 7-10)
#   [("icono","tip"), ...]    -> columna apilada de botones PEQUEÑOS (importancia 4-6)
#   {"row": [...]}            -> fila de botones PEQUEÑOS
#   {"grid": [...]}           -> grid 3x2 de iconos MINI (filtros)
# =============================================================================

_TOOLBAR_CFG = {
    # ── INICIO: Modelamiento + Datos + Cargas ────────────────────────
    "INICIO": [
        ("Datos", [
            (_I["abrir"], "Explorador"), (_I["ver"], "Hoja de cálculo"),
            [(_I["cortar"], "Cortar/copiar"), (_I["todo"], "Checks")],
        ]),
        ("Selección", _GRUPO_SELECCION),
        ("Modelamiento", [
            (_I["borrar"], "Eliminar"),
            [(_I["copiar"], "Copiar")],
        ]),
        ("Herramientas de la hoja activa", [(_I["herramientas"], "__HOJA_ACTIVA__")]),
        ("Cargas", [
            (_I["agregar"], "Agregar carga"), (_I["editar"], "Editar carga"),
            [(_I["sync"], "Generar combinaciones"), (_I["config"], "Generar")],
        ]),
        ("Bases de datos", [
            (_I["area"], "Secciones"), (_I["construccion"], "Materiales"),
        ]),
    ],

    # ── MODELADO: Herramientas para crear la estructura ────────────────
    "MODELADO": [
        ("Geometría", [
            (_I["apoyo"], "Apoyos"), (_I["fuerza"], "Cargas"),
            [(_I["xyz"], "Ejes locales"), (_I["xyz"], "Ejes principales")],
        ]),
        ("Propiedades", [
            (_I["area"], "Secciones"), (_I["construccion"], "Materiales"),
            [(_I["etiqueta"], "Propiedades▾")],
        ]),
    ],

    # ── ANÁLISIS: Ver resultados post-análisis ────────────────────────
    "ANÁLISIS": [
        ("Deformación", [
            (_I["aprox"], "Figura deformada"), (_I["tilde"], "Deflexiones"),
        ]),
        ("Momento flector", [
            (_I["flecha"], "Momento Y"), (_I["flecha"], "Momento Z"),
        ]),
        ("Cortante", [
            (_I["flecha"], "Cortante Y"), (_I["flecha"], "Cortante Z"),
        ]),
        ("Axial", [
            (_I["flecha"], "Axial"),
        ]),
        ("Reacciones", [
            (_I["triUp"], "Reacciones"),
        ]),
    ],

    # ── PROCESO: Solo lo esencial ────────────────────────────────────
    "PROCESO": [
        ("Análisis", [
            (_I["play"], "Analizar modelo"),
            (_I["construccion"], "Diseñar"),
        ]),
        ("Modelo", [
            [(_I["refresh"], "Actualizar diseño"), (_I["rayo"], "Optimizar modelo")],
            [(_I["cortes"], "Segmentar"), (_I["lightbulb"], "Depurar modelo")],
        ]),
    ],

    # ── SALIDA: Reportes + Exportar ──────────────────────────────────
    "SALIDA": [
        ("Reportes", [
            (_I["docs"], "Análisis▾"), (_I["docs"], "Datos▾"), (_I["docs"], "Diseño▾"),
        ]),
        ("Exportar", [
            (_I["abrirVentana"], "Exportar a DXF"), (_I["ver"], "Ver en pantalla"),
            [(_I["imprimir"], "Reporte"), (_I["guardar"], "Guardar vista 3D")],
        ]),
    ],
}

_TABS = ["INICIO", "MODELADO", "ANÁLISIS", "PROCESO", "SALIDA"]


class ToolbarEstructuralMixin:
    """Mixin de toolbar — se mezcla en la ventana principal, igual que
    ToolbarMixin en VentanaPrincipal de Open APU Studio."""

    # ── Tab bar ──────────────────────────────────────────────────────────

    def _build_tab_bar(self, parent_layout):
        bar    = QWidget()
        bar.setObjectName("tabBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._tab_btns = []
        for name in _TABS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, n=name: self._switch_tab(n))
            self._tab_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        parent_layout.addWidget(bar)

    # ── Barra de búsqueda (filtra el TreeTableWidget activo en self._tabs) ─

    def _build_search_bar(self, parent_layout):
        bar = QWidget()
        bar.setObjectName("searchBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(0)

        inp = QLineEdit()
        inp.setObjectName("searchInput")
        inp.setPlaceholderText("🔍  Buscar nudo/elemento…")
        inp.setClearButtonEnabled(True)
        inp.textChanged.connect(self._on_search)
        self._search_input = inp
        layout.addWidget(inp)
        parent_layout.addWidget(bar)

    def _on_search(self, text):
        from frontend.ventana.widgets.base import TreeTableWidget
        w = self._tabs.tabla_activa() if hasattr(self._tabs, "tabla_activa") else self._tabs.currentWidget()
        if isinstance(w, TreeTableWidget):
            w.filter_rows(text)

    def _on_tab_changed(self, *_args):
        # La señal currentChanged puede dispararse durante addTab(), antes
        # de que exista la search bar (se arma después del sidebar) — se
        # ignora ese primer disparo espurio.
        if not hasattr(self, "_search_input"):
            return
        self._on_search(self._search_input.text())
        # "Herramientas de la hoja activa" depende de qué pestaña del
        # sidebar está activa -> se refresca la página del ribbon.
        if hasattr(self, "_tb_built"):
            self._refrescar_pagina("INICIO")

    def _refrescar_pagina(self, tab_name: str):
        """Reconstruye una página del ribbon desde cero (usado cuando su
        contenido depende de estado externo, como la pestaña activa del
        sidebar). Reemplaza el QWidget interior del QScrollArea."""
        if tab_name not in self._tb_pages:
            return
        nuevo = QWidget()
        self._tb_content[tab_name] = nuevo
        idx_stack = self._tb_pages[tab_name]
        scroll = self._tb.widget(idx_stack)
        scroll.setWidget(nuevo)
        self._tb_built.discard(tab_name)
        self._build_page(tab_name)

    # ── Toolbar (ribbon) ───────────────────────────────────────────────────

    def _build_toolbar(self, parent_layout):
        self._tb        = QStackedWidget()
        self._tb.setObjectName("tbCustom")
        self._tb_pages   = {}
        self._tb_built   = set()
        self._tb_labels  = {}   # tab_name -> [QLabel, ...] (evita referencias a labels ya destruidos al refrescar una página)
        self._tb_content = {}   # tab_name -> QWidget interior (dentro del scroll)

        for tab_name in _TOOLBAR_CFG:
            scroll = QScrollArea()
            scroll.setObjectName("tbScroll")
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

            inner = QWidget()
            scroll.setWidget(inner)
            self._tb_content[tab_name] = inner

            self._tb_pages[tab_name] = self._tb.addWidget(scroll)

        parent_layout.addWidget(self._tb)
        self._build_page("INICIO")

    def _build_page(self, tab_name):
        page = self._tb_content[tab_name]
        if tab_name in self._tb_built:
            return
        self._tb_built.add(tab_name)
        self._tb_labels[tab_name] = []

        layout = QHBoxLayout(page)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        groups = _TOOLBAR_CFG[tab_name]
        primero = True

        for label, items in groups:
            if not items:
                continue

            es_hoja_activa = (
                isinstance(items[0], tuple) and items[0][1] == "__HOJA_ACTIVA__"
            )
            contenido = self._herramientas_hoja_activa() if es_hoja_activa else items

            # Grupo dinámico sin herramientas para la hoja activa -> se oculta
            # entero (no tiene sentido mostrar un grupo vacío con solo el label).
            if es_hoja_activa and not contenido:
                continue

            if not primero:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setObjectName("tbSep")
                sep.setFixedWidth(1)
                layout.addWidget(sep)
            primero = False

            g  = QWidget()
            g.setObjectName("tbGroup")
            gl = QVBoxLayout(g)
            gl.setContentsMargins(4, 0, 4, 0)
            gl.setSpacing(0)

            if items[0] == ("🎨", "__TEMAS__"):
                gl.addWidget(self._build_aspecto_ui())
            else:
                gl.addWidget(self._build_btn_wrap(contenido, 48))

            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tb_labels[tab_name].append(lbl)
            gl.addWidget(lbl)
            layout.addWidget(g)

        layout.addStretch()
        self._update_label_colors()

    def _herramientas_hoja_activa(self) -> list:
        """Resuelve qué botones mostrar en 'Herramientas de la hoja activa'
        según la sub-pestaña seleccionada del sidebar (p. ej. Nudos/Restricciones)."""
        tabs = getattr(self, "_tabs", None)
        if tabs is None:
            return []
        nombre = tabs.nombre_hoja_activa() if hasattr(tabs, "nombre_hoja_activa") else tabs.tabText(tabs.currentIndex())
        return _HERRAMIENTAS_POR_HOJA.get(nombre, [])

    def _build_btn_wrap(self, items: list, min_height: int) -> QWidget:
        has_stack = any(isinstance(item, list) for item in items)

        wrap = QWidget()
        bl   = QHBoxLayout(wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(4 if has_stack else 0)
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for item in items:
            if isinstance(item, list):
                # columna apilada de 2-4 botones pequeños
                col = QWidget()
                cl  = QVBoxLayout(col)
                cl.setContentsMargins(0, 0, 0, 0)
                cl.setSpacing(0)
                for icon_char, tip in item:
                    cl.addWidget(self._make_stacked_btn(icon_char, tip, 18, 11))
                bl.addWidget(col)
            elif isinstance(item, dict) and "grid" in item:
                bl.addWidget(self._build_grid_ui(item["grid"]))
            elif isinstance(item, dict) and "row" in item:
                bl.addWidget(self._build_row_ui(item["row"]))
            else:
                icon_char, tip = item
                bl.addWidget(self._make_big_btn(icon_char, tip))
        wrap.setMinimumHeight(min_height)
        return wrap

    # ── Grid de iconos pequeños (filtros de selección) ───────────────────

    def _build_grid_ui(self, items: list) -> QWidget:
        wrap = QWidget()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(2, 2, 2, 2)
        grid.setSpacing(1)
        for i, (icon_char, tip) in enumerate(items[:9]):
            fila, col = divmod(i, 3)
            grid.addWidget(self._make_mini_btn(icon_char, tip), fila, col)
        wrap.setMinimumHeight(48)
        return wrap

    # ── Fila compacta de iconos pequeños (acciones rápidas) ──────────────

    def _build_row_ui(self, items: list) -> QWidget:
        wrap = QWidget()
        rl = QVBoxLayout(wrap)
        rl.setContentsMargins(2, 2, 2, 2)
        rl.setSpacing(1)
        for icon_char, tip in items:
            rl.addWidget(self._make_stacked_btn(icon_char, tip, 16, 10))
        wrap.setMinimumHeight(48)
        return wrap

    def _make_mini_btn(self, icon_char, tip):
        btn = QToolButton()
        btn.setObjectName("tbMiniBtn")
        btn.setIcon(icono(icon_char, 16, "#E8EDF2"))
        btn.setToolTip(tip)
        btn.setIconSize(QSize(16, 16))
        btn.setAutoRaise(True)
        btn.setFixedSize(20, 20)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._conectar_btn(btn, tip)
        return btn

    def _make_big_btn(self, icon_char, tip):
        es_menu = tip.endswith("▾")
        texto   = tip[:-1].rstrip() if es_menu else tip

        btn = QToolButton()
        btn.setIcon(icono(icon_char, 32, "#E8EDF2"))
        btn.setToolTip(texto)
        btn.setText(texto)
        btn.setIconSize(QSize(32, 32))
        btn.setAutoRaise(True)
        btn.setMinimumSize(64, 44)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

        if es_menu:
            btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            menu = QMenu(btn)
            self._poblar_menu_pendiente(menu, texto)
            btn.setMenu(menu)
            btn.setToolTip(texto + " (menú)")
        else:
            self._conectar_btn(btn, tip)
        return btn

    def _make_stacked_btn(self, icon_char, tip, sz, fs):
        btn = QToolButton()
        btn.setObjectName("tbStackedBtn")
        btn.setIcon(icono(icon_char, sz, "#E8EDF2"))
        btn.setToolTip(tip)
        btn.setText(tip)
        btn.setIconSize(QSize(sz, sz))
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._conectar_btn(btn, tip)
        return btn

    def _poblar_menu_pendiente(self, menu: QMenu, texto: str):
        """Placeholder de menú desplegable — se reemplaza por las opciones
        reales de cada comando cuando se implemente su lógica."""
        accion = menu.addAction(f"{texto} (próximamente)")
        accion.setEnabled(False)

    # ── Despacho de botones -> handlers de ESTA app ─────────────────────

    def _conectar_btn(self, btn, tip):
        mapa = {
            "Analizar modelo":  self._on_analizar,
            "Ver en pantalla":  self._on_pantalla_completa,
            "Figura deformada": self._on_ver_deformada,
            "Deflexiones":      self._on_ver_deformada,
            "Momento Y":        self._on_ver_momento_y,
            "Momento Z":        self._on_ver_momento_z,
            "Cortante Y":       self._on_ver_corte_y,
            "Cortante Z":       self._on_ver_corte_z,
            "Axial":            self._on_ver_axial,
            "Reacciones":       self._on_ver_reacciones,
            "Explorador":       self._on_toggle_explorador,
            "Hoja de cálculo":  self._on_mostrar_hoja_calculo,
            "Guardar vista 3D": self._on_guardar_vista3d,
        }
        fn = mapa.get(tip)
        if fn:
            btn.clicked.connect(fn)
            btn._conectado = True
        else:
            btn._conectado = False
            btn.setToolTip(tip + " (pendiente)")
            btn.setStyleSheet("color: #6B7884;")

    # ── Cambio de pestaña ────────────────────────────────────────────────

    def _switch_tab(self, name):
        self._tab_activa = name
        for btn in self._tab_btns:
            btn.setChecked(btn.text() == name)
        self._build_page(name)
        self._tb.setCurrentIndex(self._tb_pages[name])

    def _update_label_colors(self):
        color = "#E8EDF2" if getattr(self, '_tema_modo', 'oscuro') == 'oscuro' else "#1A1F24"
        for etiquetas in self._tb_labels.values():
            for lbl in etiquetas:
                lbl.setStyleSheet(
                    f"color: {color}; background-color: transparent;"
                    f"font-size: 10px; font-weight: bold; margin-top: 1px;"
                )

    # ── Temas: acento + modo (idéntico a Open APU Studio) ───────────────

    def _build_aspecto_ui(self):
        wrap = QWidget()
        bl = QHBoxLayout(wrap)
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
            btn.clicked.connect(lambda checked=False, k=key: self._set_accent(k))
            bl.addWidget(btn)

        self._modo_btn = QToolButton()
        self._modo_btn.setIcon(icono("moon", 28, "#E8EDF2"))
        self._modo_btn.setToolTip("Modo")
        self._modo_btn.setText("Modo")
        self._modo_btn.setIconSize(QSize(28, 28))
        self._modo_btn.setAutoRaise(True)
        self._modo_btn.setMinimumSize(68, 48)
        self._modo_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._modo_btn.clicked.connect(self._toggle_mode)
        bl.addWidget(self._modo_btn)

        self._sync_modo_icon()
        return wrap

    def _sync_modo_icon(self):
        # El botón de modo vive en la página VISTA -> puede no existir aún
        # si nunca se visitó esa pestaña (p. ej. tema cambiado desde otra).
        if not hasattr(self, "_modo_btn"):
            return
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

    # ── Placeholders de handlers mínimos ─────────────────────────────────

    def _on_pantalla_completa(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
