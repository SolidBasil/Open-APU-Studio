from PySide6.QtCore import Qt, QPoint, QRect, QSize
from PySide6.QtWidgets import (
    QMainWindow, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QTableView, QSplitter, QStatusBar,
    QHeaderView, QAbstractItemView, QApplication,
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, QMenu,
    QToolButton, QFrame, QStackedWidget,
)
from PySide6.QtGui import QColor, QBrush, QIcon, QPixmap, QPainter, QFont

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
        splitter.addWidget(self._build_content())
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
        tree = QTreeWidget()
        tree.setHeaderLabel("Explorador")
        tree.setAnimated(True)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        section = [
            ("📁 Propuesta", ["Presupuesto", "Conceptos", "Indirectos"]),
            ("📁 Insumos", ["Materiales", "Mano obra", "Equipo"]),
            ("📁 Ejecución", ["Estimaciones", "Ajustes"]),
        ]
        for nombre, hijos in section:
            root = QTreeWidgetItem(tree, [nombre])
            root.setExpanded(True)
            f = root.font(0)
            f.setBold(True)
            root.setFont(0, f)
            for h in hijos:
                QTreeWidgetItem(root, [h])

        return tree

    # ── Tabs centrales ──

    def _build_content(self):
        tabs = QTabWidget()
        tabs.setTabsClosable(True)
        tabs.addTab(self._build_presupuesto(), "Presupuesto programable  ×")
        tabs.addTab(self._tab_vacia(), "APU Detalle  ×")
        return tabs

    def _build_presupuesto(self):
        cols = ["Nº", "Tipo", "Clave", "Descripción", "Unid", "Cant", "P.U.", "Total"]
        tree = QTreeWidget()
        tree.setColumnCount(len(cols))
        tree.setHeaderLabels(cols)
        tree.setAlternatingRowColors(True)
        tree.setAnimated(True)
        tree.setIndentation(20)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        h = tree.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for c in range(4, 8):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)

        for cap_nombre, cap_color, subs in _MockData.CAPITULOS:
            cap_total = sum(
                cant * pu
                for _, _, _, _, cant, pu in
                sum((c[2] for c in subs), [])
            )
            cap = QTreeWidgetItem(tree, ["", "Capítulo", "", cap_nombre, "", "", "", f"${cap_total:,.2f}"])
            cap.setForeground(0, QBrush(QColor(cap_color)))
            cap.setForeground(1, QBrush(QColor(cap_color)))
            cap.setForeground(3, QBrush(QColor(cap_color)))
            cap.setForeground(7, QBrush(QColor(cap_color)))
            f = cap.font(0)
            f.setBold(True)
            cap.setFont(0, f)
            cap.setFont(1, f)
            cap.setFont(3, f)
            cap.setFont(7, f)
            cap.setExpanded(True)

            for sub_nombre, sub_color, conceptos in subs:
                sub_total = sum(cant * pu for _, _, _, _, cant, pu in conceptos)
                sub = QTreeWidgetItem(cap, ["", "Subpart.", "", sub_nombre, "", "", "", f"${sub_total:,.2f}"])
                sub.setForeground(0, QBrush(QColor(sub_color)))
                sub.setForeground(1, QBrush(QColor(sub_color)))
                sub.setForeground(3, QBrush(QColor(sub_color)))
                sub.setForeground(7, QBrush(QColor(sub_color)))
                sub.setExpanded(True)

                for num, clave, desc, unid, cant, pu in conceptos:
                    imp = cant * pu
                    QTreeWidgetItem(sub, [
                        str(num), "Concepto", clave, desc, unid,
                        f"{cant:,.2f}", f"${pu:,.2f}", f"${imp:,.2f}",
                    ])

        return tree

    def _tab_vacia(self):
        t = QTableView()
        t.setAlternatingRowColors(True)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)
        return t

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
