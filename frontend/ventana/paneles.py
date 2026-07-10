"""
paneles.py
==========
Mixin de paneles de contenido para VentanaPrincipal.

Contiene sidebar, presupuesto, insumos, buscador de partidas,
refresco de tabs y utilidades.

Sub-paquete apu/:
    apu.py       — pestañas APU y edición
    rastreo.py   — rastreo de insumos
    explosion.py — explosión de insumos/matrices y sobrecostos
"""

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QHeaderView, QTabWidget,
)
from PySide6.QtGui import QFont, QShortcut, QKeySequence


class PanelesMixin:
    """Mixin de paneles — se mezcla en VentanaPrincipal."""

    # ── Sidebar ──────────────────────────────────────────────────────────

    def _build_sidebar(self):
        """Construye el explorador lateral."""
        tree = QTreeWidget()
        tree.setHeaderLabel("Explorador")
        tree.setMinimumWidth(150)
        tree.setAnimated(True)
        tree.setIndentation(16)
        tree.setRootIsDecorated(True)
        tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        secciones = [
            ("📁 Propuesta", [
                "📋 Presupuesto programable", "🔍 Buscar partidas",
                "📦 Explosión de insumos", "📦 Explosión de matrices",
                "🚚 Programa de suministros",
            ]),
            ("📁 Sobrecostos", [
                "💰 Cálculo de indirectos",
                "👷 Personal en indirectos",
                "📊 Cálculo de sobrecostos",
            ]),
            ("📁 Insumos", [
                "📚 Todos","📐 Conceptos", "🧱 Materiales", "👷 Mano de obra", "🔧 Herramienta",
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

    # ── Contenido central ────────────────────────────────────────────────

    def _build_content(self):
        """Crea el QTabWidget central."""
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._on_tab_close)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")

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
        QShortcut(QKeySequence("Delete"),    self).activated.connect(self._on_eliminar)
        QShortcut(QKeySequence("Insert"),    self).activated.connect(self._on_agregar_concepto)

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

        tree.itemChanged.connect(self._on_concepto_editado)
        tree.itemDoubleClicked.connect(self._on_item_dblclick)
        tree.rastrear_insumo.connect(self._on_rastrear_insumo)
        tree.desglozar_nodo.connect(self._abrir_apu_por_id)
        tree.agregar_agrupador.connect(self._on_agregar_agrupador)
        tree.agregar_concepto.connect(self._on_agregar_concepto)
        tree.eliminar_seleccion.connect(self._on_eliminar)
        self._arbol_presupuesto = tree
        if self._event_bus and self._api:
            tree.conectar_eventos(self._event_bus, self._api)
        QTimer.singleShot(0, self._on_ajustar_columnas)
        return tree

    def _build_sin_proyecto(self) -> QWidget:
        """Placeholder cuando no hay proyecto abierto."""
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

    # ── Insumos ──────────────────────────────────────────────────────────

    def _build_insumos(self, title: str):
        """Catálogo de insumos filtrable por tipo."""
        from frontend.ventana.widgets.insumos import TablaInsumos

        tipo_map = {
            "📚 Todos":       None,
            "📐 Conceptos":   "concepto",
            "🧱 Materiales":  "material",
            "👷 Mano de obra": "mano_obra",
            "🔧 Herramienta": "herramienta",
            "🚜 Equipo":      "equipo",
            "⚙️ Auxiliares":  "auxiliar",
            "🚛 Fletes":      "flete",
            "🏗️ Trabajos":    "trabajo",
        }
        tabla = TablaInsumos()
        tabla._insumos_tipo = tipo_map.get(title)
        tabla._insumos_matrices = (title == "🧮 Matrices")
        tabla._HEADER_KEY = "insumos_header_state_" + (tabla._insumos_tipo or "todos")
        tabla._restore_header_state()  # re-restaurar con la clave correcta por tipo
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
        tabla.itemChanged.connect(self._on_insumo_editado)
        if self._event_bus and self._api:
            tabla.conectar_eventos(self._event_bus, self._api)

        def _on_insumo_dblclick(item, column):
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
            desc = item.text(column).lstrip("\u25b6").strip()
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

    # ── Buscador de partidas ─────────────────────────────────────────────

    def _build_buscador_partidas(self):
        """Catálogo plano de partidas con doble clic para abrir APU."""
        from frontend.ventana.widgets.base import TreeTableWidget
        from frontend.ventana.widgets.arbol import ID_ROLE

        t = TreeTableWidget(
            ["WBS", "Descripción", "Unidad", "Cantidad", "P.U.", "Total"],
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
        import subprocess, sys
        carpeta = Rutas.proyectos()
        carpeta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(carpeta)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])
