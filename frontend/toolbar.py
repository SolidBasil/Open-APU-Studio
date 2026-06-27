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
    QHeaderView,
)
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor, QIcon

from frontend.temas import Temas



# =============================================================================
# UTILIDADES DE ICONO
# =============================================================================

def _icon(char, size=20, font_size=None):
    """Genera un QIcon desde un carácter (emoji/unicode) pintado sobre un pixmap transparente.
    Útil para botones de toolbar sin depender de archivos de imagen.
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setPen(QColor("#E8EDF2"))
    f = QFont("Segoe UI Symbol", font_size or size - 4)
    p.setFont(f)
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, char)
    p.end()
    return QIcon(pix)



# =============================================================================
# CONFIGURACIÓN DE LA TOOLBAR
# Estructura: { tab: [ (grupo_label, [item, ...]), ... ] }


# =============================================================================
# CONFIGURACIÓN DE LA TOOLBAR
# =============================================================================

_TOOLBAR_CFG = {
    "PROYECTO": [
        ("Archivo",      [("+", "Nuevo"), ("📂", "Abrir"), ("✕", "Cerrar")]),
        ("Guardar",      [("💾", "Guardar"), ("💾", "Guardar como")]),
        ("Gestión",      [("📋", "Duplicar"), ("✏", "Renombrar"), ("🗑", "Eliminar proyecto")]),
        ("Transferir",   [("📤", "Exportar"), ("📥", "Importar OPUS")]),
        ("Explorar",     [("📁", "Abrir carpeta BD")]),
    ],
    "INICIO": [
        ("Historial",     [[("↩", "Deshacer"), ("↪", "Rehacer")]]),
        ("Portapapeles",  [("✂", "Cortar"), [("📋", "Copiar"), ("📄", "Pegar")]]),
        ("Acciones",      [("✕", "Eliminar")]),
    ],
    "INFORMES": [
        ("Exportar", [("📄", "Generar PDF"), ("📊", "Exportar Excel")]),
        ("Vista",    [("👁", "Vista previa")]),
    ],
    "VISTA": [
        ("Datos", [
            ("↔", "Ajustar"),
            ("👁", "Mostrar"),
        ]),

        ("Presentación de datos", [
            ("▦", "Formato de columnas"),
            [("↺", "Restablecer formato"), ("📂", "Cargar formato")],
            [("☑", "Calculados"), ("👤", "Personalizados"), ("↻", "Actualizar")],
            ("🗂", "Mantener vistas"),
            ("▼", "Vista"),
        ]),

        ("Ventanas", [
            ("▣", "Pantalla completa"),
            [("◫", "Mosaico horizontal"), ("◧", "Mosaico vertical"), ("⧉", "Cascada")],
        ]),

        ("Aspecto", [("🎨", "__TEMAS__")]),

        ("Ver", [
            ("📋", "Auditoría"),
            ("🗔", "Explorador de vistas"),
            ("📑", "Explorador de reportes"),
            ("⚙", "Explorador de paramétricos"),
        ]),
    ],
    "PRINCIPAL": [
        ("Portapapeles", [("📋", "Copiar"), [("✂", "Cortar"), ("📄", "Pegar"), ("☑", "Seleccionar todo")]]),
        ("Editar",       [("+", "Agregar elemento"), ("✎", "Modificar"), ("→", "Desglosar"), ("✕", "Eliminar"), ("↩", "Deshacer")]),
        ("Estructura",   [[("◀", "Izquierda"), ("▶", "Derecha")],[("▲", "Subir"), ("▼", "Bajar")]]),
        ("Buscar",       [("📚", "En catálogos"), ("👁", "En vista")]),
        ("Desplegar",    [("1", "Primer nivel"), ("Σ", "Resumen agrupadores"), ("⊞", "Todo"), ("≡", "Nivel")]),
        ("Filtrar",      [("🌐", "Global"), ("☰", "Por columna"), ("✏", "Editor")]),
        ("Cálculo",      [("↻", "Recalcular"), ("✓", "Auditoría")]),
    ],
    "HERRAMIENTAS": [
        ("Sistema",     [("⚙", "Configuración")]),
        ("Datos",       [("📦", "Importar OPUS")]),
        ("Utilidades",  [("🔢", "Calculadora")]),
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
        for name in ["PROYECTO", "INICIO", "INFORMES", "VISTA", "PRINCIPAL", "HERRAMIENTAS"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, n=name: self._switch_tab(n))
            self._tab_btns.append(btn)
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
        from frontend.widgets.base import TreeTableWidget
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
        from frontend.widgets.base import TreeTableWidget
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
            max((len(item) if isinstance(item, list) else 1) for item in g[1])
            for g in groups
        )
        page_min_btn_h = max(56, page_max_rows * 22)

        for idx, (label, items) in enumerate(groups):
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
                gl.addWidget(self._build_theme_buttons())
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
        btn.setIcon(_icon(icon_char, 40, 22))
        btn.setToolTip(tip)
        btn.setText(tip.split()[0])
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
        btn.setIcon(_icon(icon_char, sz, fs))
        btn.setToolTip(tip)
        btn.setText(tip.split()[0])
        btn.setIconSize(QSize(sz, sz))
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._conectar_btn(btn, tip)
        self._style_toolbar_btn(btn)
        return btn

    def _conectar_btn(self, btn, tip):
        """Enruta el click del botón al handler según su tooltip.
        Marca btn._conectado = True/False para que _style_toolbar_btn decida el estilo.
        """
        conn = True
        if "Importar OPUS" in tip:
            btn.clicked.connect(self._on_importar_opus)
        elif tip == "Abrir":
            btn.clicked.connect(self._on_abrir_proyecto)
        elif "Copiar" in tip:
            btn.clicked.connect(self._on_copy_toolbar)
        elif tip == "Primer nivel":
            btn.clicked.connect(self._on_desplegar_primer_nivel)
        elif tip == "Resumen agrupadores":
            btn.clicked.connect(self._on_desplegar_resumen)
        elif tip == "Todo":
            btn.clicked.connect(self._on_desplegar_todo)
        elif tip == "Nivel":
            btn.clicked.connect(self._on_desplegar_nivel)
        elif tip == "Cerrar":
            btn.clicked.connect(self._on_cerrar_proyecto)
        elif tip == "Duplicar":
            btn.clicked.connect(self._on_copiar_proyecto)
        elif tip == "Renombrar":
            btn.clicked.connect(self._on_renombrar_proyecto)
        elif tip == "Eliminar proyecto":
            btn.clicked.connect(self._on_eliminar_proyecto)
        elif tip == "Abrir carpeta BD":
            btn.clicked.connect(self._on_abrir_carpeta_bd)
        elif tip == "Configuración":
            btn.clicked.connect(self._on_configuracion)
        elif tip == "Seleccionar todo":
            btn.clicked.connect(self._on_select_all_toolbar)
        else:
            conn = False
        btn._conectado = conn

    def _style_toolbar_btn(self, btn):
        """Aplica estilo atenuado a botones sin handler conectado."""
        if getattr(btn, "_conectado", False):
            return
        btn.setToolTip(btn.toolTip() + " (beta)")
        btn.setStyleSheet("color: #6B7884;")

    def _switch_tab(self, name):
        """Cambia la pestaña activa de la toolbar, construye la página si es necesario."""
        self._tab_activa = name
        for btn in self._tab_btns:
            btn.setChecked(btn.text() == name)
        self._build_page(name)
        self._tb.setCurrentIndex(self._tb_pages[name])

    def _update_label_colors(self):
        """Aplica el color de texto correcto a las etiquetas de grupo según el tema activo."""
        color = {"dark": "#E8EDF2", "light": "#FFFFFF", "hybrid": "#FFFFFF",
                 "rosa": "#F0E2EA", "cafe": "#EDE4D8", "verde": "#E0EDE4"}.get(
                     self._tema, "#E8EDF2")
        for lbl in self._tb_labels:
            lbl.setStyleSheet(
                f"color: {color}; background-color: transparent;"
                f"font-size: 10px; font-weight: bold; margin-top: 1px;"
            )

    # ── Temas ─────────────────────────────────────────────────────────────

    def _build_theme_buttons(self):
        """Construye una fila de botones, uno por tema registrado en Temas.OPCIONES."""
        from PySide6.QtWidgets import QToolButton
        from PySide6.QtCore import QSize
        wrap = QWidget()
        bl   = QHBoxLayout(wrap)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(2)
        bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for key, nombre in Temas.NOMBRES.items():
            btn = QToolButton()
            btn.setIcon(_icon("🎨", 28, 14))
            btn.setToolTip(nombre)
            btn.setText(nombre)
            btn.setIconSize(QSize(28, 28))
            btn.setAutoRaise(True)
            btn.setMinimumSize(68, 48)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn._conectado = True
            btn.clicked.connect(lambda checked=False, k=key: self._set_theme(k))
            bl.addWidget(btn)
        return wrap

    def _set_theme(self, key: str):
        """Cambia el tema visual en caliente y persiste la preferencia en config.json."""
        self._tema = key
        Temas.aplicar(QApplication.instance(), key)
        Temas.guardar_preferencia(key)
        self._switch_tab(self._tab_activa)
        self._update_statusbar()

