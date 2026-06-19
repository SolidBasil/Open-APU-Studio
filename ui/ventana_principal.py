from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtWidgets import (
    QMainWindow, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QTableView, QSplitter, QStatusBar,
    QHeaderView, QAbstractItemView, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, QMenu,
    QToolButton, QFrame, QStackedWidget,
)
from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter, QFont, QShortcut, QKeySequence

from theme_manager import ThemeManager


def _icon(char, size=20, font_size=None):
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


class _MockData:
    CAPITULOS = [
        ("INSTALACIONES HIDRÁULICAS", "#8B6FB5", [
            ("Salidas hidráulicas y sanitarias", "#5E9CA0", [
                (1282, "071515", "Salida hidráulica p/ lavabo",       "pza",  1.00, 3697.52),
                (1283, "071516", "Salida hidráulica p/ regadera",     "pza",  2.00, 4677.90),
            ]),
        ]),
        ("INSTALACIONES ELÉCTRICAS", "#8B6FB5", [
            ("Alimentación y tableros", "#5E9CA0", [
                (1284, "080101", "Centro de carga 8 circuitos",       "pza",  1.00, 6240.00),
                (1285, "080102", "Salida eléctrica c/ interrup.",     "pza", 12.00, 1850.00),
            ]),
        ]),
    ]


_TOOLBAR_CFG = {
    "PROYECTO": [
        ("Nuevo proyecto", [("+", "Nuevo"), ("📂", "Abrir"), ("💾", "Guardar"), ("💾", "Guardar como")]),
        ("Transferir", [("📤", "Exportar"), ("📥", "Importar")]),
    ],
    "INICIO": [
        ("Historial", [[("↩", "Deshacer"), ("↪", "Rehacer")]]),
        ("Portapapeles", [("✂", "Cortar"), [("📋", "Copiar"), ("📄", "Pegar")]]),
        ("Acciones", [("✕", "Eliminar")]),
    ],
    "INFORMES": [
        ("Exportar", [("📄", "Generar PDF"), ("📊", "Exportar Excel")]),
        ("Vista", [("👁", "Vista previa")]),
    ],
    "VISTA PRINCIPAL": [
        ("Portapapeles", [("📋", "Copiar"), [("✂", "Cortar"), ("📄", "Pegar"), ("☑", "Seleccionar todo")]]),
        ("Editar", [("+", "Agregar elemento"), ("✎", "Modificar"), ("→", "Desglosar"), ("✕", "Eliminar"), ("↩", "Deshacer")]),
        ("Estructura", [[("▲", "Subir"), ("▼", "Bajar")]]),
        ("Buscar", [("📚", "En catálogos"), ("👁", "En vista")]),
        ("Desplegar", [("1", "Primer nivel"), ("Σ", "Resumen agrupadores"), ("⊞", "Todo"), ("≡", "Nivel")]),
        ("Filtrar", [("🌐", "Global"), ("☰", "Por columna"), ("✏", "Editor")]),
        ("Cálculo", [("↻", "Recalcular"), ("✓", "Auditoría")]),
    ],
    "HERRAMIENTAS": [
        ("Sistema", [("⚙", "Configuración")]),
        ("Datos", [("📦", "Importar OPUS")]),
        ("Utilidades", [("🔢", "Calculadora")]),
        ("Apariencia", [("🌸", "Tema")]),
    ],
}


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Open APU Studio  v0.2")
        self.resize(1400, 800)

        self._theme = ThemeManager.load_preference()
        self._active_tab = "VISTA PRINCIPAL"
        self._temp_tab_widget = None

        self._build_central()
        self._build_statusbar()

    # ── Layout central ──

    def _build_central(self):
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_tab_bar(layout)
        self._build_toolbar(layout)
        self._switch_tab("VISTA PRINCIPAL")

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self._build_search_bar(right_layout)
        right_layout.addWidget(self._build_content(), 1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        splitter.setSizes([220, 1040])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(wrapper)

    # ── Barra de pestañas ──

    def _build_tab_bar(self, parent_layout):
        bar = QWidget()
        bar.setObjectName("tabBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(0)

        self._tab_btns = []
        for name in ["PROYECTO", "INICIO", "INFORMES", "VISTA PRINCIPAL", "HERRAMIENTAS"]:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, n=name: self._switch_tab(n))
            self._tab_btns.append(btn)
            layout.addWidget(btn)

        layout.addStretch()
        parent_layout.addWidget(bar)

    # ── Barra de búsqueda ──

    def _build_search_bar(self, parent_layout):
        from PySide6.QtWidgets import QLineEdit

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
        layout.addWidget(inp)

        parent_layout.addWidget(bar)

    # ── Toolbar ──

    def _build_toolbar(self, parent_layout):
        self._tb = QStackedWidget()
        self._tb.setObjectName("tbCustom")
        self._tb_pages = {}
        self._tb_built = set()
        self._tb_labels = []

        for tab_name in _TOOLBAR_CFG:
            page = QWidget()
            self._tb_pages[tab_name] = self._tb.addWidget(page)

        parent_layout.addWidget(self._tb)
        self._build_page("VISTA PRINCIPAL")

    def _build_page(self, tab_name):
        page = self._tb.widget(self._tb_pages[tab_name])
        if tab_name in self._tb_built:
            return
        self._tb_built.add(tab_name)

        layout = QHBoxLayout(page)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        groups = _TOOLBAR_CFG[tab_name]
        page_max_rows = max(
            max((len(item) if isinstance(item, list) else 1) for item in g[1])
            for g in groups
        )
        page_min_btn_h = max(56, page_max_rows * 22)

        for idx, group in enumerate(groups):
            label, items = group

            if idx > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.VLine)
                sep.setObjectName("tbSep")
                sep.setFixedWidth(1)
                layout.addWidget(sep)

            g = QWidget()
            g.setObjectName("tbGroup")
            gl = QVBoxLayout(g)
            gl.setContentsMargins(6, 0, 6, 0)
            gl.setSpacing(0)

            gl.addStretch()

            has_stack = any(isinstance(item, list) for item in items)
            has_single = any(not isinstance(item, list) for item in items)

            if has_stack and has_single:
                btn_wrap = QWidget()
                bl = QHBoxLayout(btn_wrap)
                bl.setContentsMargins(0, 0, 0, 0)
                bl.setSpacing(0)
                for item in items:
                    wrapper = QWidget()
                    wl = QVBoxLayout(wrapper)
                    wl.setContentsMargins(0, 0, 0, 0)
                    wl.setSpacing(0)
                    wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    if isinstance(item, list):
                        sz = 18 if len(item) == 2 else 12
                        fs = 11 if len(item) == 2 else 9
                        for icon_char, tip in item:
                            btn = QToolButton()
                            btn.setObjectName("tbStackedBtn")
                            btn.setIcon(_icon(icon_char, sz, fs))
                            btn.setToolTip(tip)
                            short = tip.split()[0]
                            btn.setText(short)
                            btn.setIconSize(QSize(sz, sz))
                            btn.setAutoRaise(True)
                            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                            if "Tema" in tip:
                                btn.clicked.connect(self._show_theme_menu)
                            wl.addWidget(btn)
                    else:
                        icon_char, tip = item
                        btn = QToolButton()
                        btn.setIcon(_icon(icon_char, 40, 22))
                        btn.setToolTip(tip)
                        short = tip.split()[0]
                        btn.setText(short)
                        btn.setIconSize(QSize(40, 40))
                        btn.setAutoRaise(True)
                        btn.setMinimumSize(80, 56)
                        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                        if "Tema" in tip:
                            btn.clicked.connect(self._show_theme_menu)
                        wl.addWidget(btn)
                    bl.addWidget(wrapper)
                btn_wrap.setMinimumHeight(page_min_btn_h)
                gl.addWidget(btn_wrap)
            elif has_stack:
                item = items[0]
                sz = 18 if len(item) == 2 else 12
                fs = 11 if len(item) == 2 else 9
                btn_wrap = QWidget()
                bl = QVBoxLayout(btn_wrap)
                bl.setContentsMargins(0, 0, 0, 0)
                bl.setSpacing(0)
                bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                for icon_char, tip in item:
                    btn = QToolButton()
                    btn.setObjectName("tbStackedBtn")
                    btn.setIcon(_icon(icon_char, sz, fs))
                    btn.setToolTip(tip)
                    short = tip.split()[0]
                    btn.setText(short)
                    btn.setIconSize(QSize(sz, sz))
                    btn.setAutoRaise(True)
                    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                    if "Tema" in tip:
                        btn.clicked.connect(self._show_theme_menu)
                    bl.addWidget(btn)
                btn_wrap.setMinimumWidth(80)
                btn_wrap.setMinimumHeight(page_min_btn_h)
                gl.addWidget(btn_wrap)
            else:
                btn_wrap = QWidget()
                bl = QHBoxLayout(btn_wrap)
                bl.setContentsMargins(0, 0, 0, 0)
                bl.setSpacing(0)
                bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                for icon_char, tip in items:
                    btn = QToolButton()
                    btn.setIcon(_icon(icon_char, 40, 22))
                    btn.setToolTip(tip)
                    short = tip.split()[0]
                    btn.setText(short)
                    btn.setIconSize(QSize(40, 40))
                    btn.setAutoRaise(True)
                    btn.setMinimumSize(80, 56)
                    btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                    if "Tema" in tip:
                        btn.clicked.connect(self._show_theme_menu)
                    bl.addWidget(btn)
                btn_wrap.setMinimumHeight(page_min_btn_h)
                gl.addWidget(btn_wrap)

            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._tb_labels.append(lbl)
            gl.addWidget(lbl)
            layout.addWidget(g)

        layout.addStretch()
        self._update_label_colors()

    def _switch_tab(self, name):
        self._active_tab = name
        for btn in self._tab_btns:
            btn.setChecked(btn.text() == name)

        self._build_page(name)
        self._tb.setCurrentIndex(self._tb_pages[name])

    def _update_label_colors(self):
        color = {"dark": "#E8EDF2", "light": "#FFFFFF", "hybrid": "#FFFFFF"}[self._theme]
        for lbl in self._tb_labels:
            lbl.setStyleSheet(
                f"color: {color}; background-color: transparent;"
                f"font-size: 10px; font-weight: bold; margin-top: 1px;"
            )

    # ── Menú de temas ──

    def _show_theme_menu(self):
        menu = QMenu(self)
        for key, label in [("dark", "Oscuro"), ("light", "Claro"), ("hybrid", "Híbrido")]:
            act = menu.addAction(label)
            act.setData(key)
            act.triggered.connect(lambda checked=False, k=key: self._set_theme(k))
        menu.exec(QPoint(
            self._tb.mapToGlobal(self._tb.rect().topLeft()).x(),
            self._tb.mapToGlobal(self._tb.rect().bottomLeft()).y(),
        ))

    def _set_theme(self, key: str):
        self._theme = key
        ThemeManager.apply(QApplication.instance(), self._theme)
        ThemeManager.save_preference(self._theme)
        self._switch_tab(self._active_tab)
        self._update_statusbar()

    # ── Explorador ──

    def _build_sidebar(self):
        from ui.widgets.tabla_presupuesto import draw_tree_connectors

        class _SidebarTree(QTreeWidget):
            def drawBranches(self, painter, rect, index):
                super().drawBranches(painter, rect, index)
                draw_tree_connectors(self, painter, rect, index)

        tree = _SidebarTree()
        tree.setHeaderLabel("Explorador")
        tree.setAnimated(True)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        section = [
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
        for nombre, hijos in section:
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

    # ── Tabs centrales ──

    def _build_content(self):
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")

        ctrl_tab = QShortcut(QKeySequence("Ctrl+Tab"), self)
        ctrl_tab.activated.connect(self._next_tab)
        ctrl_shift_tab = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        ctrl_shift_tab.activated.connect(self._prev_tab)

        return self._tabs

    def _build_presupuesto(self):
        from ui.widgets.tabla_presupuesto import TablaPresupuesto
        tree = TablaPresupuesto()

        for cap_nombre, cap_color, subs in _MockData.CAPITULOS:
            cap_total = sum(
                cant * pu
                for _, _, _, _, cant, pu in
                sum((c[2] for c in subs), [])
            )
            cap = tree.add_agrupador(cap_nombre, cap_color, cap_total)
            cap.setText(1, "Capítulo")

            for sub_nombre, sub_color, conceptos in subs:
                sub_total = sum(cant * pu for _, _, _, _, cant, pu in conceptos)
                sub = tree.add_agrupador(sub_nombre, sub_color, sub_total, cap)
                sub.setText(1, "Subpart.")

                for num, clave, desc, unid, cant, pu in conceptos:
                    tree.add_registro(num, clave, desc, unid, cant, pu, sub)

        tree.renumerar()
        return tree

    def _tab_vacia(self):
        t = QTableView()
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    # ── StatusBar ──

    # ── Navegación del explorador ──

    def _on_sidebar_click(self, item, column):
        if item.childCount() > 0:
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
        title = item.text(0)
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                widget = self._tabs.widget(i)
                if widget is self._temp_tab_widget:
                    self._temp_tab_widget = None
                self._tabs.setCurrentIndex(i)
                return
        self._open_sidebar_tab(title, temporary=False)

    def _open_sidebar_tab(self, title, temporary):
        if self._temp_tab_widget is not None:
            idx = self._tabs.indexOf(self._temp_tab_widget)
            if idx >= 0:
                self._tabs.removeTab(idx)
            self._temp_tab_widget = None

        if title == "📋 Presupuesto programable":
            content = self._build_presupuesto()
        else:
            content = self._build_placeholder(title)
        idx = self._tabs.addTab(content, title)
        self._tabs.setCurrentIndex(idx)

        if temporary:
            self._temp_tab_widget = content

    def _next_tab(self):
        i = (self._tabs.currentIndex() + 1) % self._tabs.count()
        self._tabs.setCurrentIndex(i)

    def _prev_tab(self):
        i = (self._tabs.currentIndex() - 1) % self._tabs.count()
        self._tabs.setCurrentIndex(i)

    def _on_tab_close(self, idx):
        widget = self._tabs.widget(idx)
        if widget is self._temp_tab_widget:
            self._temp_tab_widget = None
        self._tabs.removeTab(idx)

    def _build_placeholder(self, title):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("🚧")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f = QFont("Segoe UI Symbol", 48)
        icon.setFont(f)

        name = QLabel(title)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        f2 = QFont("Inter", 16)
        f2.setBold(True)
        name.setFont(f2)

        msg = QLabel("Esta sección aún no ha sido implementada.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setFont(QFont("Inter", 11))

        layout.addStretch()
        layout.addWidget(icon)
        layout.addSpacing(16)
        layout.addWidget(name)
        layout.addSpacing(8)
        layout.addWidget(msg)
        layout.addStretch()

        return w

    # ── StatusBar ──

    def _build_statusbar(self):
        self._sb = QStatusBar(self)
        self._update_statusbar()
        self.setStatusBar(self._sb)

    def _update_statusbar(self):
        name = {"dark": "Oscuro", "light": "Claro", "hybrid": "Híbrido"}[self._theme]
        self._sb.showMessage(
            f"Tema: {name}  │  Filas: 1285  │  Seleccionado: 071515  │  ⚠ Cambios sin guardar  │  v0.2"
        )
