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

from frontend.theme_manager import ThemeManager


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


class _EmptyState:
    def __init__(self):
        pass


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
        self._db = None

        self._init_db()
        self._build_central()
        self._build_statusbar()

    def _init_db(self):
        import os
        from backend.db.conexion import DatabaseManager
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(base, "CASA EG.presup")
        opus_dir = os.path.join(base, "Ejemplo opus CASA EG")
        if os.path.exists(db_path):
            self._db = DatabaseManager.abrir(db_path)
        elif os.path.exists(opus_dir):
            from backend.servicios.importador_opus import importar_opus
            result = importar_opus(opus_dir, db_path)
            self._db = DatabaseManager.abrir(db_path)

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
                            elif "Importar OPUS" in tip:
                                btn.clicked.connect(self._on_importar_opus)
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
        from frontend.ui.widgets.tabla_presupuesto import TablaPresupuesto

        tree = TablaPresupuesto()

        opus_db = self._find_opus_db()
        if opus_db:
            self._populate_from_opus(tree, opus_db)
        elif self._db:
            self._populate_from_repos(tree)

        tree.setEditTriggers(QAbstractItemView.EditTrigger.EditKeyPressed)
        tree.itemDoubleClicked.connect(self._on_presupuesto_dblclick)

        return tree

    def _on_presupuesto_dblclick(self, item, column):
        if column != 5:
            return
        clave = item.text(1).strip()
        if not clave:
            return
        self._open_apu_tab(clave)

    def _open_apu_tab(self, clave):
        from frontend.ui.widgets.tabla_base import TreeTableWidget
        from PySide6.QtWidgets import QHeaderView

        tipo_nombre = {1: "🧱 Material", 2: "👷 Mano obra", 4: "🔧 Herramienta",
                       8: "🚜 Equipo", 16: "⚙️ Auxiliar", 32: "📄 Concepto"}

        detail = TreeTableWidget(
            ["Componente", "Descripción", "Unidad", "Cant", "P.U.", "Total", "Tipo"],
            flat=True,
        )
        detail.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 50, 80, 100, 110, 120])
        })

        if self._db:
            rows = self._db.conn.execute("""
                SELECT ac.insumo_clave, i.descripcion, i.unidad,
                       ac.cantidad_total, ac.precio_unitario, ac.tipo_insumo
                FROM apu_componentes ac
                JOIN insumos i ON i.clave = ac.insumo_clave
                WHERE ac.concepto_clave = ?
                ORDER BY ac.tipo_insumo, ac.insumo_clave
            """, (clave,)).fetchall()
            for r in rows:
                imp = r[3] * r[4]
                tn = tipo_nombre.get(r[5], f"Tipo {r[5]}")
                detail.add_row([
                    r[0], r[1] or "", r[2] or "",
                    f"{r[3]:,.2f}", f"${r[4]:,.2f}",
                    f"${imp:,.2f}", tn,
                ], editable=False)
        elif opus_db := self._find_opus_db():
            import sqlite3
            conn = sqlite3.connect(opus_db)
            rows = conn.execute("""
                SELECT f.COMPONENTE, p.DESCRIPCIO, p.UNIDAD,
                       f.CANTIDAD, f.COSTO, COALESCE(p.PREFIJO, f.PREF)
                FROM D60JALISCOTF f
                LEFT JOIN D60JALISCOTP p ON p.NOMBRE = f.COMPONENTE AND p._deleted=0
                WHERE f.NOMBRE = ? AND f._deleted = 0
                ORDER BY f.PREF, f.COMPONENTE
            """, (clave,)).fetchall()
            conn.close()
            for r in rows:
                imp = r[3] * r[4]
                tn = tipo_nombre.get(r[5], f"Tipo {r[5]}")
                detail.add_row([
                    r[0], r[1] or "", r[2] or "",
                    f"{r[3]:,.2f}", f"${r[4]:,.2f}",
                    f"${imp:,.2f}", tn,
                ], editable=False)

        title = f"APU: {clave}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return

        idx = self._tabs.addTab(detail, title)
        self._tabs.setCurrentIndex(idx)

    def _find_opus_db(self):
        import os
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dbs = [
            os.path.join(base, "Conversor de opus", "D60JALISCOT.sqlite"),
            os.path.join(base, "Conversor de opus", "D60JALISCOT.db"),
        ]
        for p in dbs:
            if os.path.exists(p):
                return p
        return None

    def _populate_from_opus(self, tree, db_path):
        from backend.opus.core import build_budget_tree
        root_nodes = build_budget_tree(db_path)
        self._opus_add_nodes(tree, root_nodes, None)

    def _opus_add_nodes(self, tree, nodes, parent):
        for node in nodes:
            if node["es_capitulo"]:
                item = tree.add_agrupador(
                    node["desc"],
                    total=node["importe"],
                    parent=parent,
                )
                self._opus_add_nodes(tree, node["hijos"], item)
            else:
                tree.add_registro(
                    node["clave"], node["desc"],
                    node["unidad"], node["cantidad"] or 0, node["precio"] or 0,
                    parent=parent,
                )

    def _populate_from_repos(self, tree):
        from backend.db.repos.partidas import PartidaRepo
        from backend.db.repos.conceptos import ConceptoRepo

        partida_repo = PartidaRepo(self._db.conn)
        concepto_repo = ConceptoRepo(self._db.conn)
        partidas = partida_repo.todas()

        for p in partidas:
            cap = tree.add_agrupador(p["nombre"], parent=None)
            conceptos = concepto_repo.por_partida(p["id"])
            total = 0
            for c in conceptos:
                tree.add_registro(
                    c["clave"], c["descripcion"],
                    c["unidad"], c["cantidad"], c["precio_unitario"],
                    cap,
                )
                total += c["cantidad"] * c["precio_unitario"]
            cap.setText(6, f"${total:,.2f}")

    def _build_conceptos(self):
        from PySide6.QtWidgets import QHeaderView
        from frontend.ui.widgets.tabla_base import TreeTableWidget
        from backend.db.repos.conceptos import ConceptoRepo
        t = TreeTableWidget(["Clave", "Descripción", "Unidad", "Cant", "P.U.", "Total"], flat=True)
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([80, 250, 50, 80, 100, 110])
        })
        if self._db:
            repo = ConceptoRepo(self._db.conn)
            for c in repo.todos():
                t.add_row([
                    c["clave"], c["descripcion"] or "", c["unidad"] or "",
                    f"{c['cantidad']:,.2f}", f"${c['precio_unitario']:,.2f}",
                    f"${c['importe']:,.2f}",
                ], editable=False)
        elif opus_db := self._find_opus_db():
            import sqlite3
            conn = sqlite3.connect(opus_db)
            rows = conn.execute("""
                SELECT p.NOMBRE, p.DESCRIPCIO, p.UNIDAD,
                       SUM(t1.PRE_VOL) as cant, p.PRECIO
                FROM D60JALISCOTP p
                JOIN D60JALISCOT1 t1 ON t1.PRE_COM = p.NOMBRE AND t1._deleted=0
                WHERE p.PREFIJO=32 AND p._deleted=0
                GROUP BY p.NOMBRE
                ORDER BY p.NOMBRE
            """).fetchall()
            for r in rows:
                t.add_row([
                    r[0], r[1] or "", r[2] or "",
                    f"{r[3]:,.2f}", f"${r[4]:,.2f}",
                    f"${r[3] * r[4]:,.2f}",
                ], editable=False)
            conn.close()
        return t

    def _build_indirectos(self):
        from PySide6.QtWidgets import QHeaderView
        from frontend.ui.widgets.tabla_base import TreeTableWidget
        t = TreeTableWidget(["Renglón", "Variable", "Descripción", "Fórmula"], flat=True)
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([60, 100, 250, 200])
        })
        if not self._db:
            return t
        for r in self._db.conn.execute("SELECT * FROM indirectos ORDER BY renglon"):
            t.add_row([str(r["renglon"]), r["variable"], r["descripcion"], r["formula"]], editable=False)
        return t

    def _on_importar_opus(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.db.conexion import DatabaseManager
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta del proyecto OPUS")
        if not dir_path:
            return
        import os
        from backend.servicios.importador_opus import importar_opus
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        nombre = os.path.basename(dir_path.rstrip("/\\"))
        db_path = os.path.join(base, f"{nombre}.presup")
        try:
            result = importar_opus(dir_path, db_path)
            if self._db:
                self._db.close()
            self._db = DatabaseManager.abrir(db_path)
            QMessageBox.information(self, "Importación exitosa",
                f"Insumos: {result['insumos']}\nConceptos: {result['conceptos']}\n"
                f"APU componentes: {result['apu_componentes']}\n"
                f"Capítulos: {result['capitulos']}")
        except Exception as e:
            QMessageBox.critical(self, "Error de importación", str(e))

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
        elif title == "📐 Conceptos":
            content = self._build_conceptos()
        elif title == "💰 Cálculo de indirectos":
            content = self._build_indirectos()
        elif title in ("📚 Todos", "🧱 Materiales", "👷 Mano de obra",
                       "🔧 Herramienta", "🚜 Equipo", "⚙️ Auxiliares",
                       "🧮 Matrices", "🚛 Fletes", "🏗️ Trabajos"):
            content = self._build_insumos(title)
        else:
            content = self._build_placeholder(title)
        idx = self._tabs.addTab(content, title)
        self._tabs.setCurrentIndex(idx)

        if temporary:
            self._temp_tab_widget = content

    def _build_insumos(self, title):
        from frontend.ui.widgets.tabla_insumos import TablaInsumos
        from backend.db.repos.insumos import InsumoRepo
        tipo_map = {
            "📚 Todos": None,
            "🧱 Materiales": 1,
            "👷 Mano de obra": 2,
            "🔧 Herramienta": 4,
            "🚜 Equipo": 8,
            "⚙️ Auxiliares": 16,
        }
        if self._db:
            tabla = TablaInsumos()
            repo = InsumoRepo(self._db.conn)
            tipo = tipo_map.get(title)
            if tipo:
                insumos = repo.por_tipo(tipo)
            else:
                insumos = repo.todos()
            tabla.poblar(insumos)
            return tabla

        tipo = tipo_map.get(title)
        if tipo is None and title != "📚 Todos":
            return TablaInsumos()

        from PySide6.QtWidgets import QHeaderView
        from frontend.ui.widgets.tabla_base import TreeTableWidget
        if not (opus_db := self._find_opus_db()):
            return TablaInsumos()

        import sqlite3
        conn = sqlite3.connect(opus_db)
        tipo_label = {1: "🧱 Materiales", 2: "👷 Mano de obra", 4: "🔧 Herramienta",
                      8: "🚜 Equipo", 16: "⚙️ Auxiliares", 32: "📄 Conceptos"}

        if tipo is not None:
            where = "p._deleted=0 AND p.PREFIJO=?"
            params = [tipo]
        else:
            where = "p._deleted=0 AND p.PREFIJO IN (1,2,4,8,16,32)"
            params = []

        rows = conn.execute(f"""
            SELECT p.NOMBRE, p.DESCRIPCIO, p.UNIDAD, p.PRECIO, p.PREFIJO
            FROM D60JALISCOTP p
            WHERE {where}
            ORDER BY p.PREFIJO, p.NOMBRE
        """, params).fetchall()
        conn.close()

        t = TreeTableWidget(["Clave", "Descripción", "Unidad", "P.U.", "Tipo"], flat=True)
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 130])
        })
        for r in rows:
            precio = f"${r[3]:,.2f}" if r[3] else ""
            tn = tipo_label.get(r[4], f"Tipo {r[4]}")
            t.add_row([r[0], r[1] or "", r[2] or "", precio, tn], editable=False)
        return t

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
