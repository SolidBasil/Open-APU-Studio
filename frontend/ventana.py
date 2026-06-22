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
        ("Nuevo proyecto", [("+", "Nuevo"), ("📂", "Abrir"), ("💾", "Guardar"), ("💾", "Guardar como")]),
        ("Transferir",     [("📤", "Exportar"), ("📥", "Importar OPUS")]),
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
    "VISTA PRINCIPAL": [
        ("Portapapeles", [("📋", "Copiar"), [("✂", "Cortar"), ("📄", "Pegar"), ("☑", "Seleccionar todo")]]),
        ("Editar",       [("+", "Agregar elemento"), ("✎", "Modificar"), ("→", "Desglosar"), ("✕", "Eliminar"), ("↩", "Deshacer")]),
        ("Estructura",   [[("▲", "Subir"), ("▼", "Bajar")]]),
        ("Buscar",       [("📚", "En catálogos"), ("👁", "En vista")]),
        ("Desplegar",    [("1", "Primer nivel"), ("Σ", "Resumen agrupadores"), ("⊞", "Todo"), ("≡", "Nivel")]),
        ("Filtrar",      [("🌐", "Global"), ("☰", "Por columna"), ("✏", "Editor")]),
        ("Cálculo",      [("↻", "Recalcular"), ("✓", "Auditoría")]),
    ],
    "HERRAMIENTAS": [
        ("Sistema",     [("⚙", "Configuración")]),
        ("Datos",       [("📦", "Importar OPUS")]),
        ("Utilidades",  [("🔢", "Calculadora")]),
        ("Apariencia",  [("🌸", "Tema")]),
    ],
}


# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Open APU Studio  v0.3")
        self.resize(1400, 800)

        self._tema       = Temas.cargar_preferencia()
        self._tab_activa = "PROYECTO"
        self._tab_temp   = None
        self._db         = None

        self._init_db()
        self._build_central()
        self._build_statusbar()

    # ── Base de datos ─────────────────────────────────────────────────────

    def _init_db(self):
        """Sin carga automática — el usuario elige el proyecto desde la toolbar."""
        self._db = None

    # ── Layout central ────────────────────────────────────────────────────

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

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        splitter.setSizes([220, 1040])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(wrapper)

    # ── Barra de pestañas ─────────────────────────────────────────────────

    def _build_tab_bar(self, parent_layout):
        bar    = QWidget()
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

    # ── Barra de búsqueda ─────────────────────────────────────────────────

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
        self._search_input = inp
        layout.addWidget(inp)
        parent_layout.addWidget(bar)

    # ── Toolbar ───────────────────────────────────────────────────────────

    def _build_toolbar(self, parent_layout):
        self._tb       = QStackedWidget()
        self._tb.setObjectName("tbCustom")
        self._tb_pages  = {}
        self._tb_built  = set()
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

        groups         = _TOOLBAR_CFG[tab_name]
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
            # Solo apilados: columna vertical
            item     = items[0]
            sz, fs   = (18, 11) if len(item) == 2 else (12, 9)
            wrap     = QWidget()
            bl       = QVBoxLayout(wrap)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)
            bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for icon_char, tip in item:
                bl.addWidget(self._make_stacked_btn(icon_char, tip, sz, fs))
            wrap.setMinimumWidth(80)
            wrap.setMinimumHeight(min_height)
            return wrap

        # Solo simples: fila horizontal de botones grandes
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
        btn = QToolButton()
        btn.setIcon(_icon(icon_char, 40, 22))
        btn.setToolTip(tip)
        btn.setText(tip.split()[0])
        btn.setIconSize(QSize(40, 40))
        btn.setAutoRaise(True)
        btn.setMinimumSize(80, 56)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self._conectar_btn(btn, tip)
        return btn

    def _make_stacked_btn(self, icon_char, tip, sz, fs):
        btn = QToolButton()
        btn.setObjectName("tbStackedBtn")
        btn.setIcon(_icon(icon_char, sz, fs))
        btn.setToolTip(tip)
        btn.setText(tip.split()[0])
        btn.setIconSize(QSize(sz, sz))
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._conectar_btn(btn, tip)
        return btn

    def _conectar_btn(self, btn, tip):
        if "Tema" in tip:
            btn.clicked.connect(self._show_theme_menu)
        elif "Importar OPUS" in tip:
            btn.clicked.connect(self._on_importar_opus)
        elif tip == "Abrir":
            btn.clicked.connect(self._on_abrir_proyecto)
        elif "Copiar" in tip:
            btn.clicked.connect(self._on_copy_toolbar)

    def _switch_tab(self, name):
        self._tab_activa = name
        for btn in self._tab_btns:
            btn.setChecked(btn.text() == name)
        self._build_page(name)
        self._tb.setCurrentIndex(self._tb_pages[name])

    def _update_label_colors(self):
        color = {"dark": "#E8EDF2", "light": "#FFFFFF", "hybrid": "#FFFFFF"}.get(self._tema, "#E8EDF2")
        for lbl in self._tb_labels:
            lbl.setStyleSheet(
                f"color: {color}; background-color: transparent;"
                f"font-size: 10px; font-weight: bold; margin-top: 1px;"
            )

    # ── Temas ─────────────────────────────────────────────────────────────

    def _show_theme_menu(self):
        menu = QMenu(self)
        for key, label in [("dark", "Oscuro"), ("light", "Claro"), ("hybrid", "Híbrido")]:
            act = menu.addAction(label)
            act.triggered.connect(lambda checked=False, k=key: self._set_theme(k))
        menu.exec(QPoint(
            self._tb.mapToGlobal(self._tb.rect().topLeft()).x(),
            self._tb.mapToGlobal(self._tb.rect().bottomLeft()).y(),
        ))

    def _set_theme(self, key: str):
        self._tema = key
        Temas.aplicar(QApplication.instance(), key)
        Temas.guardar_preferencia(key)
        self._switch_tab(self._tab_activa)
        self._update_statusbar()

    # ── Sidebar ───────────────────────────────────────────────────────────

    def _build_sidebar(self):
        tree = QTreeWidget()
        tree.setHeaderLabel("Explorador")
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

    # ── Contenido central ─────────────────────────────────────────────────

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

    def _build_presupuesto(self):
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
        return tree

    def _build_sin_proyecto(self) -> QWidget:
        """Panel vacío que se muestra cuando no hay ningún proyecto cargado."""
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
            "Usa la pestaña  HERRAMIENTAS → Importar OPUS  para cargar un proyecto,\n"
            "o abre uno existente desde  PROYECTO → Abrir."
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
        return w

    # ── APU ───────────────────────────────────────────────────────────────

    def _build_apu_tab(self, clave: str, nodo_id: int):
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

        tipo_emoji = {
            1: "🧱", 2: "👷", 4: "🔧", 8: "🚜", 16: "⚙️", 32: "📄",
        }
        if self._db:
            data = get_apu(self._db.db_path, nodo_id)
            for r in data.get("detalle", []):
                tid = r.get("tipo_id", 0)
                tn  = r.get("tipo_nombre", "")
                detail.add_row([
                    f"{tipo_emoji.get(tid, '')} {tn}" if tid else tn,
                    r.get("insumo_clave", ""),
                    r.get("insumo_desc_corta") or r.get("insumo_descripcion", ""),
                    r.get("insumo_unidad", ""),
                    f"{r.get('cantidad', 0):,.3f}",
                    f"${r.get('precio', 0):,.2f}",
                    f"${r.get('importe', 0):,.2f}",
                ], editable=False)

        detail.itemDoubleClicked.connect(self._on_apu_detail_dblclick)
        return detail

    def _on_apu_detail_dblclick(self, item, column):
        if self._es_pu(item, column):
            self._abrir_apu(item.text(1).strip())

    def _on_item_dblclick(self, item, column):
        if self._es_pu(item, column):
            self._abrir_apu(item.text(0).strip() or item.text(1).strip())

    @staticmethod
    def _es_pu(item, column) -> bool:
        tw = item.treeWidget()
        if not tw:
            return False
        h = tw.headerItem().text(column).replace(".", "").upper()
        return "PU" in h or "PRECIO" in h

    def _abrir_apu(self, clave: str):
        if not clave or not self._db:
            return

        from backend.repos import NodoRepo, ApuDetalleRepo, ApuNodoRepo
        nodo = NodoRepo(self._db.conn).buscar_por_clave(clave, proyecto_id=1)
        if nodo:
            nodo_id = nodo["id"]
        else:
            apu_nodo = ApuNodoRepo(self._db.conn).buscar_por_clave(clave, proyecto_id=1)
            if not apu_nodo:
                self._sb.showMessage(f"'{clave}' no encontrado", 4000)
                return
            nodo_id = apu_nodo["id"]

        if not ApuDetalleRepo(self._db.conn).por_nodo(nodo_id):
            self._sb.showMessage(f"'{clave}' no tiene APU", 4000)
            return

        title = f"APU: {clave}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        idx = self._tabs.addTab(self._build_apu_tab(clave, nodo_id), title)
        self._tabs.setCurrentIndex(idx)

    # ── Insumos ───────────────────────────────────────────────────────────

    def _build_insumos(self, title: str):
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
            cur.execute("SELECT clave FROM apu_nodos WHERE proyecto_id=1")
            claves = {r["clave"] for r in cur.fetchall()}
            cur.execute("""
                SELECT DISTINCT n.clave FROM nodos n
                JOIN apu_detalle ad ON ad.nodo_id = n.id
                WHERE n.proyecto_id=1 AND n.clave IS NOT NULL
            """)
            claves |= {r["clave"] for r in cur.fetchall()}
            if title == "🧮 Matrices":
                insumos = [i for i in insumos if i.get("clave") in claves]
            tabla.poblar(insumos, claves)
        tabla.itemDoubleClicked.connect(self._on_item_dblclick)
        return tabla

    # ── Conceptos ─────────────────────────────────────────────────────────

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

    # ── Indirectos ────────────────────────────────────────────────────────

    def _build_indirectos(self):
        from frontend.widgets.base import TreeTableWidget
        from backend.repos import PiePreciosRepo

        t = TreeTableWidget(
            ["Renglón", "Variable", "Descripción", "Fórmula"], flat=True
        )
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([60, 100, 250, 200])
        })
        if self._db:
            repo = PiePreciosRepo(self._db.conn)
            for r in repo.por_proyecto(1):
                t.add_row([
                    str(r.get("orden", "")),
                    r.get("variable", ""),
                    r.get("descripcion", ""),
                    r.get("formula", ""),
                ], editable=False)
        return t

    # ── Importar OPUS ─────────────────────────────────────────────────────

    def _on_abrir_proyecto(self):
        """Abre un archivo .db existente desde la carpeta de proyectos."""
        from PySide6.QtWidgets import QFileDialog
        from backend.db import Database, Rutas

        db_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            str(Rutas.proyectos()),
            "Proyectos Open APU Studio (*.db)",
        )
        if not db_path:
            return

        try:
            if self._db:
                Database.cerrar()
            self._db = Database.abrir(db_path)
            self._reload_presupuesto()
            self._update_statusbar()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error al abrir proyecto", str(e))

    def _on_importar_opus(self):
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
            QMessageBox.information(
                self, "Importación exitosa",
                f"Nodos:        {result['nodos']}\n"
                f"Insumos:      {result['insumos']}\n"
                f"APU detalle:  {result['apu_detalle']}\n"
                f"APU totales:  {result['apu_totales']}\n"
                f"Auxiliares:   {result['auxiliares']}"
            )
            # Recargar el presupuesto
            self._reload_presupuesto()
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

    # ── Placeholder ───────────────────────────────────────────────────────

    def _build_placeholder(self, title):
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

    # ── Navegación ────────────────────────────────────────────────────────

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
            content = self._build_indirectos()
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

    def _on_search(self, text):
        from frontend.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if isinstance(w, TreeTableWidget):
            w.filter_rows(text)

    def _on_tab_changed(self, idx):
        self._on_search(self._search_input.text())

    # ── StatusBar ─────────────────────────────────────────────────────────

    def _build_statusbar(self):
        self._sb = QStatusBar(self)
        self._update_statusbar()
        self.setStatusBar(self._sb)

    def _update_statusbar(self):
        nombre = Temas.nombre(self._tema)
        self._sb.showMessage(
            f"Tema: {nombre}  │  v0.3"
        )
