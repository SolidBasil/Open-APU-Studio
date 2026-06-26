"""
ventana.py
==========
Ventana principal de Open APU Studio.

Uso:
    from frontend.ventana import VentanaPrincipal
"""

from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtWidgets import (
    QMainWindow, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QTableView, QSplitter, QStatusBar,
    QHeaderView, QAbstractItemView, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu,
    QToolButton, QFrame, QStackedWidget, QLineEdit,
)
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QFont, QShortcut, QKeySequence

from frontend.temas import Temas


# =============================================================================
# UTILIDADES DE PRESENTACIÓN
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
# item puede ser (icon, tooltip) o [(icon, tooltip), ...] para botones apilados
# =============================================================================

_TOOLBAR_CFG = {
    "PROYECTO": [
        ("Archivo",      [("+", "Nuevo"), ("📂", "Abrir"), ("✕", "Cerrar")]),
        ("Guardar",      [("💾", "Guardar"), ("💾", "Guardar como")]),
        ("Gestión",      [("📋", "Duplicar"), ("✏", "Renombrar"), ("🗑", "Eliminar proyecto")]),
        ("Transferir",   [("📤", "Exportar"), ("📥", "Importar OPUS")]),
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


# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================

class VentanaPrincipal(QMainWindow):
    """Ventana principal de la aplicación.

    Coordina:
      - Toolbar superior con pestañas (PROYECTO, INICIO, INFORMES, VISTA, PRINCIPAL, HERRAMIENTAS)
      - Sidebar izquierdo con el explorador de secciones
      - Área central con pestañas de contenido (presupuesto, APU, insumos, etc.)
      - Barra de búsqueda y barra de estado
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Open APU Studio  v0.3")
        self.resize(1400, 800)

        self._tema       = Temas.cargar_preferencia()   # tema guardado en config.json
        self._tab_activa = "PROYECTO"                    # toolbar tab activa
        self._tab_temp   = None                          # pestaña temporal (click simple)
        self._db         = None                          # instancia de Database o None
        self._arbol_presupuesto = None                   # ref al TablaArbol activo

        self._init_db()
        self._build_central()
        self._build_statusbar()

    # ── Base de datos ─────────────────────────────────────────────────────

    def _init_db(self):
        """Inicializa la BD sin carga automática — el usuario elige el proyecto desde PROYECTO → Abrir."""
        self._db = None

    # ── Layout central ────────────────────────────────────────────────────
    # Jerarquía vertical:
    #   tab bar (PROYECTO | INICIO | …)
    #   toolbar contextual (cambia según pestaña activa)
    #   splitter horizontal:
    #     - sidebar (explorador de secciones)
    #     - área derecha: search bar + QTabWidget de contenido
    # ───────────────────────────────────────────────────────────────────────

    def _build_central(self):
        wrapper = QWidget()
        layout  = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_tab_bar(layout)
        self._build_toolbar(layout)
        self._switch_tab("PROYECTO")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())

        right        = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self._build_search_bar(right_layout)
        right_layout.addWidget(self._build_content(), 1)
        splitter.addWidget(right)

        splitter.setCollapsible(0, False)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        splitter.setSizes([220, 1040])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(wrapper)

    # ── Barra de pestañas ─────────────────────────────────────────────────
    # Botones superiores que cambian la toolbar contextual.
    # Cada botón alterna la página mostrada en el QStackedWidget de abajo.

    def _build_tab_bar(self, parent_layout):
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

    # ── Sidebar (explorador lateral) ─────────────────────────────────────
    # Construye el panel lateral izquierdo con el explorador jerárquico.
    # Las secciones (Propuesta, Insumos, Ejecución) contienen subsecciones
    # que se abren como pestañas temporales (click) o permanentes (doble click).
    # Árbol de secciones del proyecto. Click simple → pestaña temporal,
    # doble click → pestaña permanente.

    def _build_sidebar(self):
        tree = QTreeWidget()
        tree.setHeaderLabel("Explorador")
        tree.setMinimumWidth(150)
        tree.setAnimated(True)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        secciones = [
            ("📁 Propuesta", [
                "📋 Presupuesto programable", "📐 Conceptos", "💰 Cálculo de indirectos",
                "👷 Personal en indirectos", "📊 Cálculo de sobrecostos",
                "📦 Explosión de insumos", "🚚 Programa de suministros",
            ]),
            ("📁 Insumos", [
                "📚 Todos", "🧱 Materiales", "👷 Mano de obra", "🔧 Herramienta",
                "🚜 Equipo", "⚙️ Auxiliares", "🧮 Matrices", "🚛 Fletes", "🏗️ Trabajos",
            ]),
            ("📁 Ejecución", [
                "📝 Estimaciones", "➕ Conceptos fuera de catálogo", "📈 Ajustes de costos",
            ]),
        ]
        for nombre, hijos in secciones:
            root = QTreeWidgetItem(tree, [nombre])
            root.setExpanded(True)
            f = root.font(0)
            f.setBold(True)
            root.setFont(0, f)
            for h in hijos:
                QTreeWidgetItem(root, [h])

        self._sidebar_tree = tree
        tree.itemClicked.connect(self._on_sidebar_click)
        tree.itemDoubleClicked.connect(self._on_sidebar_double_click)
        return tree

    # ── Contenido central (QTabWidget) ───────────────────────────────────
    # Área de pestañas donde se muestran los datos del proyecto abierto.
    # Las pestañas se crean al navegar desde el sidebar o al abrir APU.
    # Se cierran con la X. Ctrl+Tab / Ctrl+Shift+Tab navega entre ellas.

    def _build_content(self):
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")

        QShortcut(QKeySequence("Ctrl+Tab"),       self).activated.connect(self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self).activated.connect(self._prev_tab)
        return self._tabs

    # ── Presupuesto ───────────────────────────────────────────────────────
    # Pestaña inicial. Si no hay BD abierta, muestra el placeholder clickeable.

    def _build_presupuesto(self):
        """Construye el árbol jerárquico del presupuesto.
        Lee toda la estructura del SQLite y la muestra como árbol expandible.
        """
        from frontend.widgets.arbol import TablaArbol
        from backend.core import build_budget_tree

        if not self._db:
            return self._build_sin_proyecto()

        tree = TablaArbol()
        try:
            nodos = build_budget_tree(self._db.db_path)
            tree.poblar(nodos)
        except Exception as e:
            print(f"Error cargando presupuesto: {e}")

        tree.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        tree.itemDoubleClicked.connect(self._on_item_dblclick)
        self._arbol_presupuesto = tree   # referencia para explosión de insumos
        return tree

    def _build_sin_proyecto(self) -> QWidget:
        """Placeholder mostrado cuando no hay proyecto abierto.
        Al hacer clic en cualquier parte (vía eventFilter) abre el ProjectDialog.
        """
        from PySide6.QtCore import QEvent

        w      = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icono = QLabel("📂")
        icono.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icono.setFont(QFont("Segoe UI Symbol", 56))

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
        layout.addWidget(icono)
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

    # ── APU (Análisis de Precio Unitario) ────────────────────────────────
    # Pestaña que muestra el desglose de insumos de un concepto.
    # Se abre al hacer doble clic en una celda de P.U. o Precio.

    def _build_apu_tab(self, clave: str, matriz_id: int):
        """Pestaña de desglose APU: componentes de un concepto o insumo compuesto.
        Muestra tipo, clave, descripción, cant, PU e importe de cada insumo.
        Los insumos con APU propio (▶) se pueden abrir con doble clic en P.U.
        matriz_id positivo = nodo del árbol, negativo = insumo compuesto.
        """
        from frontend.widgets.base import TreeTableWidget
        from backend.core import get_apu

        detail = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "Unidad", "Cant", "P.U.", "Importe"],
            flat=True,
        )
        detail.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([110, 90, 250, 50, 80, 100, 110])
        })
        detail.header().setMaximumSectionSize(400)

        tipo_emoji = {
            1: "🧱", 2: "👷", 4: "🔧", 8: "🚜", 16: "⚙️", 32: "📄",
        }
        claves_con_apu: set[str] = set()
        if self._db:
            cur = self._db.conn.cursor()
            cur.execute(
                "SELECT clave FROM insumos WHERE es_compuesto=1 AND proyecto_id=?",
                (1,),
            )
            claves_con_apu = {r[0] for r in cur.fetchall()}

            data = get_apu(self._db.db_path, matriz_id)
            for r in data.get("detalle", []):
                tid = r.get("tipo_id", 0)
                tn  = r.get("tipo_nombre", "")
                desc = r.get("insumo_desc_corta") or r.get("insumo_descripcion", "")
                if r.get("insumo_clave") in claves_con_apu:
                    desc = f"\u25b6 {desc}"
                detail.add_row([
                    f"{tipo_emoji.get(tid, '')} {tn}" if tid else tn,
                    r.get("insumo_clave", ""),
                    desc,
                    r.get("insumo_unidad", ""),
                    f"{r.get('cantidad', 0):,.3f}",
                    f"${r.get('precio', 0):,.2f}",
                    f"${r.get('importe', 0):,.2f}",
                ], editable=False)

        detail.itemDoubleClicked.connect(self._on_apu_detail_dblclick)
        return detail

    def _on_apu_detail_dblclick(self, item, column):
        """Doble clic en celda de P.U. en APU → abre APU del insumo compuesto.
        La columna 1 contiene la clave del insumo.
        """
        if self._es_pu(item, column):
            self._abrir_apu(item.text(1).strip())

    def _on_item_dblclick(self, item, column):
        """Doble clic en presupuesto/insumos → abre APU del concepto."""
        if self._es_pu(item, column):
            self._abrir_apu(item.text(0).strip() or item.text(1).strip())

    @staticmethod
    def _es_pu(item, column) -> bool:
        """Detecta si la columna contiene 'PU' o 'PRECIO' (case-insensitive)."""
        tw = item.treeWidget()
        if not tw:
            return False
        h = tw.headerItem().text(column).replace(".", "").upper()
        return "PU" in h or "PRECIO" in h

    def _abrir_apu(self, clave: str):
        """Busca un concepto/insumo por clave y abre su APU en una nueva pestaña.
        matriz_id es positivo si el item es un nodo del árbol, negativo si es
        un insumo compuesto (para evitar colisión de IDs entre ambas tablas).
        """
        if not clave or not self._db:
            return

        from backend.repos import NodoRepo, ApuMatricesRepo, InsumoRepo
        nodo = NodoRepo(self._db.conn).buscar_por_clave(clave, proyecto_id=1)
        if nodo:
            matriz_id = nodo["id"]
        else:
            insumo = InsumoRepo(self._db.conn).buscar_por_clave(clave, proyecto_id=1)
            if not insumo or not insumo.get("es_compuesto"):
                self._sb.showMessage(f"'{clave}' no encontrado", 4000)
                return
            matriz_id = -insumo["id"]

        rows = ApuMatricesRepo(self._db.conn).por_matriz(matriz_id)
        if not rows:
            self._sb.showMessage(f"'{clave}' no tiene APU", 4000)
            return

        title = f"APU: {clave}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        idx = self._tabs.addTab(self._build_apu_tab(clave, matriz_id), title)
        self._tabs.setCurrentIndex(idx)

    # ── Insumos ───────────────────────────────────────────────────────────
    # Catálogo completo de insumos, filtrable por tipo desde el sidebar.
    # Muestra ▶ en insumos que tienen APU (compuestos o matrices).

    def _build_insumos(self, title: str):
        """Catálogo de insumos filtrable por tipo (material, MO, equipo, etc.).
        Muestra ▶ en insumos que tienen APU (compuestos o conceptos del árbol).
        "🧮 Matrices" filtra solo los que aparecen en apu_matrices.
        """
        from frontend.widgets.insumos import TablaInsumos
        from backend.repos import InsumoRepo

        tipo_map = {
            "📚 Todos":       None,
            "🧱 Materiales":  "material",
            "👷 Mano de obra": "mano_obra",
            "🔧 Herramienta": "herramienta",
            "🚜 Equipo":      "equipo",
            "⚙️ Auxiliares":  "auxiliar",
            "🚛 Fletes":      "flete",
            "🏗️ Trabajos":    "trabajo",
        }
        tabla = TablaInsumos()
        if self._db:
            repo   = InsumoRepo(self._db.conn)
            tipo   = tipo_map.get(title)
            insumos = (repo.por_tipo(1, tipo) if tipo
                       else repo.todos(1))
            cur = self._db.conn.cursor()
            cur.execute("SELECT clave FROM insumos WHERE es_compuesto=1 AND proyecto_id=1")
            claves = {r["clave"] for r in cur.fetchall()}
            cur.execute("""
                SELECT DISTINCT n.clave FROM estructura_presupuesto n
                JOIN apu_matrices ad ON ad.matriz_id = n.id
                WHERE n.proyecto_id=1 AND n.clave IS NOT NULL
            """)
            claves |= {r["clave"] for r in cur.fetchall()}
            if title == "🧮 Matrices":
                insumos = [i for i in insumos if i.get("clave") in claves]
            tabla.poblar(insumos, claves)
        tabla.itemDoubleClicked.connect(self._on_item_dblclick)
        return tabla

    # ── Conceptos ─────────────────────────────────────────────────────────
    # Vista plana de todos los nodos de tipo 'concepto' en el presupuesto.
    # Permite navegación rápida y apertura de APU por doble clic en P.U.

    def _build_conceptos(self):
        from frontend.widgets.base import TreeTableWidget
        from backend.repos import ConceptoRepo

        t = TreeTableWidget(
            ["Clave", "Descripción", "Unidad", "Cant", "P.U.", "Total"],
            flat=True,
        )
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([80, 250, 50, 80, 100, 110])
        })
        t.header().setMaximumSectionSize(400)
        if self._db:
            repo = ConceptoRepo(self._db.conn)
            for c in repo.todos(1):
                t.add_row([
                    c.get("clave", ""),
                    c.get("descripcion", "") or "",
                    c.get("unidad", "") or "",
                    f"{c.get('cantidad', 0):,.2f}",
                    f"${c.get('precio_unitario', 0):,.2f}",
                    f"${c.get('importe', 0):,.2f}",
                ], editable=False)
        t.itemDoubleClicked.connect(self._on_item_dblclick)
        return t

    # ── Explosión de insumos ─────────────────────────────────────────────
    # Toma los conceptos seleccionados en el árbol del presupuesto,
    # muestra el diálogo de opciones y abre una pestaña con los resultados.

    def _build_explosion(self):
        """Construye y muestra la pestaña de explosión de insumos.
        Obtiene los conceptos seleccionados del árbol del presupuesto.
        Si no hay selección, usa todos los conceptos del proyecto.
        """
        from frontend.widgets.explosion import (
            DialogoExplosion, PestañaExplosion, TIPOS_INSUMO
        )
        from backend.repos import ExplosionRepo

        if not self._db:
            return self._build_placeholder("📦 Explosión de insumos")

        # ── Recopilar conceptos seleccionados del árbol
        from frontend.widgets.arbol import ID_ROLE
        concepto_ids = []
        arbol = self._arbol_presupuesto

        if arbol is not None:
            items_sel = arbol.selectedItems()
            for item in items_sel:
                # Solo hojas = conceptos (tienen ID_ROLE guardado en add_registro)
                concepto_id = item.data(0, ID_ROLE)
                if concepto_id is not None:
                    concepto_ids.append(concepto_id)

        # Si no hay selección, tomar todos los conceptos del proyecto
        if not concepto_ids:
            cur = self._db.conn.cursor()
            rows = cur.execute("""
                SELECT id FROM estructura_presupuesto
                WHERE proyecto_id = 1 AND tipo = 'concepto' AND activo = 1
            """).fetchall()
            concepto_ids = [r[0] for r in rows]

        if not concepto_ids:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Sin conceptos",
                "No hay conceptos en el presupuesto para explotar."
            )
            return None

        # ── Diálogo de opciones
        dlg = DialogoExplosion(self)
        if dlg.exec() != DialogoExplosion.DialogCode.Accepted:
            return None

        nivel     = dlg.nivel
        tipos_ids = dlg.tipos_ids

        # ── Calcular explosión
        repo           = ExplosionRepo(self._db.conn)
        filas, total_g = repo.calcular(
            proyecto_id  = 1,
            concepto_ids = concepto_ids,
            nivel        = nivel,
            tipos_ids    = tipos_ids,
        )

        if not filas:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Sin resultados",
                "No se encontraron insumos con los filtros seleccionados."
            )
            return None

        # ── Construir nombres de tipos para el encabezado
        tipo_nombre_map = {t[0]: t[1] for t in TIPOS_INSUMO}
        tipos_nombres   = ", ".join(
            tipo_nombre_map.get(tid, str(tid)) for tid in tipos_ids
        )

        resumen = {
            "nivel":        nivel,
            "n_conceptos":  len(concepto_ids),
            "tipos_nombres": tipos_nombres,
        }

        return PestañaExplosion(filas, total_g, resumen)


    # ── Gestión de proyectos (Abrir / Cerrar / Duplicar / Eliminar) ─────

    def eventFilter(self, obj, event):
        """Captura clics en el placeholder 'Sin proyecto' para abrir el ProjectDialog."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            self._on_abrir_proyecto()
            return True
        return super().eventFilter(obj, event)

    def _on_abrir_proyecto(self):
        """Selecciona y abre un proyecto .db existente.
        Cierra el proyecto actual si hay uno abierto, recarga el presupuesto
        y cambia a la pestaña PRINCIPAL con la toolbar completa.
        """
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.db import Database, Rutas
        from frontend.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Abrir proyecto",
                                    "No hay proyectos guardados.")
            return
        dlg = ProjectDialog(proyectos, "Abrir proyecto", "Abrir", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre = dlg.proyecto_seleccionado
        if not nombre:
            return
        db_path = Rutas.db_proyecto(nombre)
        if not db_path.exists():
            return
        try:
            if self._db:
                Database.cerrar()
            self._db = Database.abrir(db_path)
            self._reload_presupuesto()
            self._update_statusbar()
            self._switch_tab("PRINCIPAL")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error al abrir proyecto", str(e))

    def _on_cerrar_proyecto(self):
        """Cierra el proyecto actual con confirmación."""
        if not self._db:
            return
        from PySide6.QtWidgets import QMessageBox
        from backend.db import Database

        msg = QMessageBox(self)
        msg.setWindowTitle("Cerrar proyecto")
        msg.setText("¿Cerrar el proyecto actual?")
        msg.setInformativeText("Los datos no guardados se perderán.")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        btn_ok = msg.addButton("Cerrar", QMessageBox.ButtonRole.AcceptRole)
        msg.setDefaultButton(btn_ok)
        msg.exec()
        if msg.clickedButton() != btn_ok:
            return

        Database.cerrar()
        self._db = None
        for i in range(self._tabs.count() - 1, -1, -1):
            self._tabs.removeTab(i)
        self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")
        self._sb.showMessage("Proyecto cerrado", 3000)

    def _on_copiar_proyecto(self):
        """Duplica un proyecto existente: selecciona origen, asigna nombre, copia .db."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox
        from backend.db import Rutas
        from frontend.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Duplicar proyecto",
                                    "No hay proyectos guardados.")
            return
        actual = Path(self._db.db_path).stem if self._db and self._db.db_path else None
        dlg = ProjectDialog(proyectos, "Duplicar proyecto", "Duplicar",
                            accion_color="#5B8A72", seleccionado=actual,
                            parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        source_name = dlg.proyecto_seleccionado
        if not source_name:
            return
        original = Rutas.db_proyecto(source_name)
        name, ok = QInputDialog.getText(
            self, "Duplicar proyecto",
            "Nombre para la copia:",
            text=source_name + "_copia",
        )
        if not ok or not name.strip():
            return
        dest = Rutas.db_proyecto(name.strip())
        if dest.exists():
            QMessageBox.warning(self, "Ya existe",
                                f"'{dest.name}' ya existe.")
            return
        import shutil
        shutil.copy2(original, dest)
        self._sb.showMessage(f"Duplicado como '{dest.name}'", 4000)

    def _on_renombrar_proyecto(self):
        """Renombra un proyecto .db: selecciona, escribe nuevo nombre, renombra archivo."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox
        from backend.db import Rutas, Database
        from frontend.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Renombrar proyecto",
                                    "No hay proyectos guardados.")
            return
        dlg = ProjectDialog(proyectos, "Renombrar proyecto", "Renombrar",
                            accion_color="#D5B39B", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        source_name = dlg.proyecto_seleccionado
        if not source_name:
            return

        name, ok = QInputDialog.getText(
            self, "Renombrar proyecto",
            "Nuevo nombre:",
            text=source_name,
        )
        if not ok or not name.strip() or name.strip() == source_name:
            return
        name = name.strip()
        dest = Rutas.db_proyecto(name)
        if dest.exists():
            QMessageBox.warning(self, "Ya existe",
                                f"'{name}' ya existe.")
            return

        original = Rutas.db_proyecto(source_name)
        if self._db and self._db.db_path and Path(self._db.db_path).resolve() == original.resolve():
            Database.cerrar()
            self._db = Database.abrir(dest)
            self._update_statusbar()

        original.rename(dest)
        self._sb.showMessage(f"Renombrado a '{name}'", 4000)

    def _on_eliminar_proyecto(self):
        """Elimina permanentemente un proyecto .db con doble confirmación."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.db import Rutas, Database
        from frontend.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Eliminar proyecto",
                                    "No hay proyectos guardados.")
            return
        dlg = ProjectDialog(proyectos, "Eliminar proyecto", "Eliminar",
                            accion_color="#A06A6A", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre = dlg.proyecto_seleccionado
        if not nombre:
            return
        ruta = Rutas.db_proyecto(nombre)

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText(f"¿Eliminar permanentemente '{nombre}'?")
        msg.setInformativeText("Esta acción no se puede deshacer.")
        msg.setIcon(QMessageBox.Icon.Warning)
        btn_ok = msg.addButton("Eliminar", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() != btn_ok:
            return

        if self._db and self._db.db_path and Path(self._db.db_path).resolve() == ruta.resolve():
            Database.cerrar()
            self._db = None
            for i in range(self._tabs.count() - 1, -1, -1):
                self._tabs.removeTab(i)
            self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")
        ruta.unlink()
        self._sb.showMessage(f"'{nombre}' eliminado", 4000)

    # ── Importación OPUS ──────────────────────────────────────────────────
    # Importa proyectos completos desde formato OPUS 2010 (archivos .DBF).
    # Convierte jerarquía, insumos, APU y auxiliares a SQLite.

    def _on_importar_opus(self):
        """Flujo completo de importación OPUS:
        1. Seleccionar carpeta con archivos .DBF
        2. Si ya existe .db, pregunta: renombrar anterior o sobrescribir
        3. Ejecuta importar() que lee DBF y escribe el SQLite
        4. Abre el proyecto recién importado y recarga el presupuesto
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.db import Config, Database, Rutas
        from backend.importar import importar

        dir_path = QFileDialog.getExistingDirectory(
            self, "Seleccionar carpeta del proyecto OPUS",
            "C:/OPUSCMS/Obras"
        )
        if not dir_path:
            return

        from pathlib import Path
        nombre  = Path(dir_path).name
        db_path = Rutas.db_proyecto(nombre)

        if Path(db_path).exists():
            from datetime import datetime
            msg = QMessageBox(self)
            msg.setWindowTitle("Base de datos existente")
            msg.setText(f"Ya existe una base de datos para '{nombre}'.")
            msg.setInformativeText("¿Cómo quieres proceder?")
            btn_rename = msg.addButton("Renombrar anterior", QMessageBox.ButtonRole.ActionRole)
            btn_delete = msg.addButton("Sobrescribir", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(btn_cancel)
            msg.exec()

            if msg.clickedButton() == btn_cancel or msg.clickedButton() is None:
                return
            if msg.clickedButton() == btn_rename:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup = str(Path(db_path).parent / f"{nombre}_{ts}.db")
                Path(db_path).rename(backup)
                self._sb.showMessage(f"Anterior renombrada a {Path(backup).name}", 4000)
            else:  # sobrescribir
                Path(db_path).unlink(missing_ok=True)

        try:
            result = importar(dir_path, db_path, nombre)
            if self._db:
                Database.cerrar()
            self._db = Database.abrir(db_path)
            print(f"[import] {nombre}: nodos={result['nodos']}, insumos={result['insumos']}, "
                  f"apu_matrices={result['apu_matrices']}, apu_resumen_totales={result['apu_resumen_totales']}, "
                  f"insumos_compuestos={result['insumos_compuestos']}")
            QMessageBox.information(self, "Importación exitosa",
                                    f"'{nombre}' importado correctamente.")
            self._reload_presupuesto()
            self._switch_tab("PRINCIPAL")
        except Exception as e:
            QMessageBox.critical(self, "Error de importación", str(e))

    def _reload_presupuesto(self):
        """Recarga la pestaña de presupuesto con los datos nuevos."""
        for i in range(self._tabs.count()):
            if "Presupuesto" in self._tabs.tabText(i):
                self._tabs.removeTab(i)
                break
        self._tabs.insertTab(0, self._build_presupuesto(), "📋 Presupuesto programable")
        self._tabs.setCurrentIndex(0)

    def _on_copy_toolbar(self):
        """Delega copia al widget activo en la pestaña actual."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "copy_selection"):
            widget.copy_selection()

    def _on_select_all_toolbar(self):
        """Selecciona todas las filas visibles del widget activo.
        Busca el TreeTableWidget dentro del widget de la pestaña actual,
        ya que currentWidget() puede ser un contenedor (QWidget wrapper).
        """
        from frontend.widgets.base import TreeTableWidget
        tab = self._tabs.currentWidget()
        if tab is None:
            return
        # Si la pestaña ES directamente el TreeTableWidget
        if isinstance(tab, TreeTableWidget):
            tab.selectAll()
            return
        # Si la pestaña CONTIENE un TreeTableWidget (wrapper como PestañaExplosion)
        tree = tab.findChild(TreeTableWidget)
        if tree is not None:
            tree.selectAll()

    # ── Desplegar (Primer nivel / Resumen / Todo / Nivel) ────────────────
    # Controla la expansión y colapso del árbol del presupuesto activo.
    # Primer nivel: solo raíces. Resumen: solo agrupadores. Todo: expande completo. Nivel: hasta N.

    def _on_desplegar_primer_nivel(self):
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_primer_nivel"):
            widget.show_primer_nivel()

    def _on_desplegar_resumen(self):
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_solo_agrupadores"):
            widget.show_solo_agrupadores()

    def _on_desplegar_todo(self):
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_todo"):
            widget.show_todo()

    def _on_desplegar_nivel(self):
        """Menú contextual para elegir profundidad de expansión.
        Nivel 1 = solo raíces (collapseAll), Nivel 2 = raíces expandidas, etc.
        Convención 1-based para que sea intuitivo para el usuario.
        """
        widget = self._tabs.currentWidget()
        if not widget or not hasattr(widget, "show_nivel"):
            return
        menu = QMenu(self)
        for nivel in range(1, 11):
            act = menu.addAction(f"Nivel {nivel}")
            act.setData(nivel)
            act.triggered.connect(
                lambda checked=False, n=nivel: widget.show_nivel(n - 1)
            )
        # Mostrar el menú justo debajo del botón que lo invocó
        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        else:
            menu.exec(QPoint(
                self._tb.mapToGlobal(self._tb.rect().topLeft()).x(),
                self._tb.mapToGlobal(self._tb.rect().bottomLeft()).y(),
            ))

    # ── Placeholder ───────────────────────────────────────────────────────
    # Widget genérico para secciones no implementadas aún (MVP).
    # Muestra icono, título y mensaje "no implementado" de forma visual.

    def _build_placeholder(self, title, msg="Esta sección aún no ha sido implementada."):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = QLabel("🚧")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFont(QFont("Segoe UI Symbol", 48))
        name = QLabel(title)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f2 = QFont("Inter", 16)
        f2.setBold(True)
        name.setFont(f2)
        msg_label = QLabel(msg)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg_label.setFont(QFont("Inter", 11))
        layout.addStretch()
        layout.addWidget(icon)
        layout.addSpacing(16)
        layout.addWidget(name)
        layout.addSpacing(8)
        layout.addWidget(msg_label)
        layout.addStretch()
        return w

    # ── Navegación ────────────────────────────────────────────────────────
    # Gestiona la interacción con el sidebar: click simple (pestaña temporal),
    # doble click (permanente). También atajos de teclado Ctrl+Tab.

    def _on_sidebar_click(self, item, column):
        if item.childCount() > 0:
            return
        if not self._db:
            return
        title = item.text(0)
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        self._open_sidebar_tab(title, temporary=True)

    def _on_sidebar_double_click(self, item, column):
        if item.childCount() > 0:
            return
        if not self._db:
            return
        title = item.text(0)
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                widget = self._tabs.widget(i)
                if widget is self._tab_temp:
                    self._tab_temp = None
                self._tabs.setCurrentIndex(i)
                return
        self._open_sidebar_tab(title, temporary=False)

    def _open_sidebar_tab(self, title, temporary):
        if self._tab_temp is not None:
            idx = self._tabs.indexOf(self._tab_temp)
            if idx >= 0:
                self._tabs.removeTab(idx)
            self._tab_temp = None

        insumos_titles = {
            "📚 Todos", "🧱 Materiales", "👷 Mano de obra",
            "🔧 Herramienta", "🚜 Equipo", "⚙️ Auxiliares",
            "🧮 Matrices", "🚛 Fletes", "🏗️ Trabajos",
        }
        if title == "📋 Presupuesto programable":
            content = self._build_presupuesto()
        elif title == "📐 Conceptos":
            content = self._build_conceptos()
        elif title == "💰 Cálculo de indirectos":
            content = self._build_placeholder(title, "En desarrollo")
        elif title == "📦 Explosión de insumos":
            content = self._build_explosion()
            if content is None:
                return   # usuario canceló el diálogo
        elif title in insumos_titles:
            content = self._build_insumos(title)
        else:
            content = self._build_placeholder(title)

        idx = self._tabs.addTab(content, title)
        self._tabs.setCurrentIndex(idx)
        if temporary:
            self._tab_temp = content

    def _next_tab(self):
        self._tabs.setCurrentIndex((self._tabs.currentIndex() + 1) % self._tabs.count())

    def _prev_tab(self):
        self._tabs.setCurrentIndex((self._tabs.currentIndex() - 1) % self._tabs.count())

    def _on_tab_close(self, idx):
        widget = self._tabs.widget(idx)
        if widget is self._tab_temp:
            self._tab_temp = None
        self._tabs.removeTab(idx)

    # ── Búsqueda ──────────────────────────────────────────────────────────
    # Filtro en tiempo real sobre el TreeTableWidget activo.
    # Se re-ejecuta al escribir o al cambiar de pestaña.

    def _on_search(self, text):
        from frontend.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if isinstance(w, TreeTableWidget):
            w.filter_rows(text)

    def _on_tab_changed(self, idx):
        self._on_search(self._search_input.text())

    # ── StatusBar ─────────────────────────────────────────────────────────
    # Barra de estado inferior que muestra información del tema activo
    # y la versión de la aplicación.

    def _build_statusbar(self):
        self._sb = QStatusBar(self)
        self._update_statusbar()
        self.setStatusBar(self._sb)

    def _update_statusbar(self):
        nombre = Temas.nombre(self._tema)
        self._sb.showMessage(
            f"Tema: {nombre}  │  v0.3"
        )
