"""
paneles.py
==========
Mixin de paneles de contenido para VentanaPrincipal.

Contiene los builders de todas las pestañas del área de trabajo:
sidebar, presupuesto, APU, rastrear insumo, insumos, conceptos,
explosión de insumos y placeholder.
"""

from PySide6.QtCore    import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QHeaderView, QMenu, QSplitter, QTabWidget,
)
from PySide6.QtGui import QFont, QShortcut, QKeySequence


class PanelesMixin:
    """Mixin de paneles — se mezcla en VentanaPrincipal.

    Nota: `self` siempre es la instancia de VentanaPrincipal.
    Los atributos como self._api, self._tabs, self._sb, self._db
    se definen en VentanaPrincipal.__init__ o en otros mixins.
    """

    # ── Sidebar (explorador lateral) ─────────────────────────────────────
    # Construye el panel lateral izquierdo con el explorador jerárquico.
    # Las secciones (Propuesta, Insumos, Ejecución) contienen subsecciones
    # que se abren como pestañas temporales (click) o permanentes (doble click).
    # Árbol de secciones del proyecto. Click simple → pestaña temporal,
    # doble click → pestaña permanente.

    def _build_sidebar(self):
        """Construye el explorador lateral (Propuesta / Insumos / Ejecución) conéctado a _on_sidebar_click/double_click."""
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
        """Crea el QTabWidget central con Ctrl+Tab, Ctrl+Shift+Tab y pestaña inicial de presupuesto."""
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

        if not self._db:
            return self._build_sin_proyecto()

        tree = TablaArbol()
        try:
            nodos = self._api.presupuesto_arbol()
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

    def _build_apu_tab(self, clave: str, matriz_id: int, descripcion: str = ""):
        """Pestaña de desglose APU: componentes de un concepto o insumo compuesto.
        Muestra tipo, clave, descripción, cant, PU e importe de cada insumo.
        Los insumos con APU propio (▶) se pueden abrir con doble clic en P.U.
        matriz_id positivo = nodo del árbol, negativo = insumo compuesto.
        """
        from frontend.widgets.base import TreeTableWidget

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header con descripción
        lbl = QLabel(
            f"<b>{clave}</b> — {descripcion}"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(lbl)
        layout.addSpacing(2)

        detail = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "Unidad", "Cant", "P.U.", "Importe"],
            flat=True,
        )
        detail.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([110, 90, 250, 50, 80, 100, 110])
        })
        detail.header().setMaximumSectionSize(400)

        if self._api:
            resultado = self._api.apu(clave)
            if resultado:
                for r in resultado["detalle"]:
                    tid = r["tipo_id"]
                    tn  = r["tipo_nombre"]
                    detail.add_row([
                        f"{r['tipo_emoji']} {tn}".strip() if r["tipo_emoji"] else tn,
                        r["insumo_clave"],
                        r["descripcion"],
                        r["insumo_unidad"],
                        f"{r['cantidad']:,.3f}",
                        f"${r['precio']:,.2f}",
                        f"${r['importe']:,.2f}",
                    ], editable=False)

        # menú contextual → rastrear uso del insumo
        detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        detail.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(detail, pos))

        detail.itemDoubleClicked.connect(self._on_apu_detail_dblclick)
        layout.addWidget(detail)
        return container

    def _on_apu_detail_dblclick(self, item, column):
        """Doble clic en cualquier celda del APU → abre sub-APU si el insumo es compuesto.
        Solo abre si la clave (columna 1) corresponde a un insumo con APU propio.
        """
        clave = item.text(1).strip()
        if clave and self._api and self._api.insumo_es_compuesto(clave):
            self._abrir_apu(clave)

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

        if not self._api:
            return
        resultado = self._api.apu(clave)
        if not resultado:
            self._sb.showMessage(f"'{clave}' no tiene matriz relacionada", 4000)
            return
        matriz_id   = resultado["matriz_id"]
        descripcion = resultado["descripcion"]

        title = f"APU: {clave}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        idx = self._tabs.addTab(self._build_apu_tab(clave, matriz_id, descripcion), title)
        self._tabs.setCurrentIndex(idx)

    # ── Rastrear insumo ──────────────────────────────────────────────────
    # Muestra en una pestaña las matrices (conceptos/compuestos) que usan
    # un insumo. Doble clic en cualquier columna abre el APU de la matriz.

    def _on_rastrear_insumo(self, clave: str):
        """Busca insumo por clave y abre pestaña con todas las matrices donde se usa."""
        if not clave or not self._api:
            return
        insumo = self._api.insumo_por_clave(clave)
        if not insumo:
            self._sb.showMessage(f"Insumo '{clave}' no encontrado", 4000)
            return
        title = f"\U0001f50d Uso: {clave}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        filas = self._api.rastrear_insumo(insumo["id"])
        idx = self._tabs.addTab(
            self._build_rastrear_tab(clave, filas), title
        )
        self._tabs.setCurrentIndex(idx)

    def _build_rastrear_tab(self, clave: str, filas: list):
        """Construye tabla plana con las matrices que consumen un insumo, menú contextual y doble clic."""
        from frontend.widgets.base import TreeTableWidget
        from PySide6.QtWidgets import QHeaderView, QMenu

        tabla = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "WBS", "Cantidad", "P.U.", "Importe"],
            flat=True,
        )
        tabla.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([80, 90, 250, 100, 80, 100, 110])
        })
        tabla.header().setMaximumSectionSize(400)

        for r in filas:
            tipo = "📄 Concepto" if r["tipo_origen"] == "concepto" else "\u2699 Compuesto"
            tabla.add_row([
                tipo,
                r.get("matriz_clave", ""),
                r.get("matriz_descripcion", ""),
                r.get("matriz_wbs", ""),
                f"{r.get('cantidad', 0):,.3f}",
                f"${r.get('precio', 0):,.2f}",
                f"${r.get('importe', 0):,.2f}",
            ], editable=False)

        if not filas:
            tabla.add_row([
                "", f"\u2716 '{clave}' no se usa en ninguna matriz", "", "", "", "", ""
            ], editable=False)
            return tabla

        # menú contextual → rastrear uso de la matriz
        tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabla.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(tabla, pos))

        # doble clic → abre APU de la matriz
        tabla.itemDoubleClicked.connect(
            lambda item, col: self._abrir_apu(item.text(1).strip())
        )
        return tabla

    def _on_rastrear_context_menu(self, tabla, pos):
        """Menú contextual sobre tabla de rastreo: ofrece 'Rastrear uso' para el insumo de la fila."""
        item = tabla.itemAt(pos)
        if not item:
            return
        clave = item.text(1).strip()
        if not clave:
            return
        menu = QMenu(self)
        act = menu.addAction("\U0001f50d Rastrear uso")
        act.triggered.connect(lambda: self._on_rastrear_insumo(clave))
        menu.exec(tabla.mapToGlobal(pos))

    # ── Insumos ───────────────────────────────────────────────────────────
    # Catálogo completo de insumos, filtrable por tipo desde el sidebar.
    # Muestra ▶ en insumos que tienen APU (compuestos o matrices).

    def _build_insumos(self, title: str):
        """Catálogo de insumos filtrable por tipo (material, MO, equipo, etc.).
        Muestra ▶ en insumos que tienen APU (compuestos o conceptos del árbol).
        "🧮 Matrices" filtra solo los que aparecen en apu_matrices.
        """
        from frontend.widgets.insumos import TablaInsumos

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
        if self._api:
            tipo   = tipo_map.get(title)
            claves = self._api.claves_con_apu()
            if title == "🧮 Matrices":
                insumos = self._api.insumos_con_matrices(tipo)
            else:
                insumos = self._api.insumos(tipo)
            tabla.poblar(insumos, claves)
        tabla.rastrear_insumo.connect(self._on_rastrear_insumo)

        # Doble clic en cualquier columna abre el APU si el insumo es compuesto
        def _on_insumo_dblclick(item, column):
            clave = item.text(0).strip()
            if clave and clave in claves:
                self._abrir_apu(clave)

        tabla.itemDoubleClicked.connect(_on_insumo_dblclick)
        return tabla

    # ── Conceptos ─────────────────────────────────────────────────────────
    # Vista plana de todos los nodos de tipo 'concepto' en el presupuesto.
    # Permite navegación rápida y apertura de APU por doble clic en P.U.

    def _build_conceptos(self):
        """Construye tabla plana de todos los conceptos del presupuesto con doble clic para APU."""
        from frontend.widgets.base import TreeTableWidget

        t = TreeTableWidget(
            ["Clave", "Descripción", "Unidad", "Cant", "P.U.", "Total"],
            flat=True,
        )
        t.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([80, 250, 50, 80, 100, 110])
        })
        t.header().setMaximumSectionSize(400)
        if self._api:
            for c in self._api.conceptos_planos():
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
            concepto_ids = self._api.todos_concepto_ids()

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
        filas, total_g = self._api.explotar(
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
        tipos_nombres = self._api.resumen_tipos_explosion(tipos_ids)

        resumen = {
            "nivel":        nivel,
            "n_conceptos":  len(concepto_ids),
            "tipos_nombres": tipos_nombres,
        }

        return PestañaExplosion(
            filas, total_g, resumen,
            on_apu_click=self._abrir_apu,
            on_rastrear=self._on_rastrear_insumo,
        )


    def _on_configuracion(self):
        """Abre el diálogo de ajustes de la aplicación."""
        from frontend.widgets.ajustes import DialogoAjustes
        DialogoAjustes(self).exec()

    def _on_abrir_carpeta_bd(self):
        """Abre en el explorador la carpeta donde se guardan los .db."""
        from backend.db import Rutas
        import subprocess, sys
        carpeta = Rutas.proyectos()
        carpeta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(carpeta)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])

