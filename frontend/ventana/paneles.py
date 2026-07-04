"""
paneles.py
==========
Mixin de paneles de contenido para VentanaPrincipal.

Contiene los builders de todas las pestañas del área de trabajo:
sidebar, presupuesto, APU, rastrear insumo, insumos, conceptos,
explosión de insumos y placeholder.
"""

from PySide6.QtCore    import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QHeaderView, QMenu, QTabWidget,
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
        self._arbol_presupuesto = tree   # referencia para explosión de insumos
        QTimer.singleShot(0, self._on_ajustar_columnas)
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

    def _build_apu_tab(self, matriz_id: int, descripcion: str = ""):
        """Pestaña de desglose APU: componentes de un concepto o insumo compuesto.
        Muestra tipo, descripción, cant, PU e importe de cada insumo, con el
        costo directo total en el encabezado.
        Los insumos con APU propio (▶) se abren con doble clic (no son editables
        inline — el doble clic navega al sub-APU, no debe abrir un editor a la vez).
        matriz_id positivo = nodo del árbol, negativo = insumo compuesto.
        """
        from frontend.ventana.widgets.base import TreeTableWidget

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        resultado = None
        if self._api:
            resultado = self._api.apu(nodo_id=matriz_id) if matriz_id > 0 else self._api.apu(insumo_id=-matriz_id)

        # Total del APU (costo_directo si ya está calculado, si no, suma de importes)
        total = 0.0
        if resultado:
            totales = resultado.get("totales")
            if totales and totales.get("costo_directo") is not None:
                total = totales["costo_directo"]
            else:
                total = sum(r.get("importe", 0) or 0 for r in resultado.get("detalle", []))

        # Header: antes mostraba el nombre dos veces (una en negritas, otra
        # normal) porque "clave" terminaba siendo la misma descripción. Ahora
        # muestra la descripción una sola vez y el total del APU.
        lbl = QLabel(
            f"<b>{descripcion or f'Matriz #{matriz_id}'}</b> — Total: ${total:,.2f}"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(lbl)
        layout.addSpacing(2)

        # Las filas de insumos compuestos (tienen sub-APU propio) no son
        # editables: el doble clic sobre ellas navega al sub-APU, y si además
        # fueran editables, ese mismo doble clic (DoubleClicked es trigger de
        # edición) abría un editor de "Op" al mismo tiempo que la pestaña del
        # sub-APU — confuso y no tenía sentido editar algo que en realidad
        # se administra desde adentro de su propio APU.
        def _editable_cols_detalle(item):
            if item.data(0, Qt.ItemDataRole.UserRole + 1):  # es_compuesto
                return set()
            return {4, 5, 6}  # P.U., Op, Valor

        detail = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "Unidad", "P.U.", "Op", "Valor", "Importe"],
            flat=True,
            editable_cols=frozenset({5}),  # fallback (no debería usarse, siempre hay fn)
            editable_cols_fn=_editable_cols_detalle,
        )
        detail.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([110, 90, 250, 50, 100, 40, 80, 110])
        })
        detail.header().setMaximumSectionSize(400)

        if resultado:
            for r in resultado["detalle"]:
                tid = r["tipo_id"]
                tn  = r["tipo_nombre"]
                es_compuesto = bool(r.get("tiene_sub_apu"))
                row_item = detail.add_row([
                    f"{r['tipo_emoji']} {tn}".strip() if r["tipo_emoji"] else tn,
                    "",  # columna Clave: ya no se usa para navegación, el insumo_id va en UserRole
                    r["descripcion"],
                    r["insumo_unidad"],
                    f"${r['precio']:,.2f}",
                    r["operador"],
                    f"{r['valor']:,.4f}",
                    f"${r['importe']:,.2f}",
                ], editable=not es_compuesto)
                row_item.setData(0, Qt.ItemDataRole.UserRole, r.get("insumo_id"))
                row_item.setData(0, Qt.ItemDataRole.UserRole + 1, es_compuesto)
                # Guardar comp_id para edición de operador
                row_item.setData(5, Qt.ItemDataRole.UserRole, r.get("id"))

        detail.itemChanged.connect(self._on_apu_detalle_editado)

        # menú contextual → rastrear uso del insumo
        detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        detail.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(detail, pos))

        detail.itemDoubleClicked.connect(self._on_apu_detail_dblclick)
        layout.addWidget(detail)
        # Se guarda para que _refrescar_tab_activa pueda reconstruir esta
        # pestaña en el momento (editar Precio, Valor u Op aquí mismo cambia
        # el total de esta misma matriz, y también puede afectar a otras
        # pestañas de APU abiertas que compartan el mismo insumo).
        container.setProperty("apu_matriz_id", matriz_id)
        return container

    def _on_apu_detail_dblclick(self, item, column):
        """Doble clic en la columna P.U. → abre sub-APU si el insumo es compuesto.
        Antes se abría con doble clic en cualquier columna de la fila, lo que
        además chocaba con la edición inline de Valor/Op al doble-clickear esas
        columnas en una fila no compuesta. Ahora es exclusivo de P.U. (col 4),
        igual que en el árbol de presupuesto (_es_pu / _on_item_dblclick).
        """
        if column != 4:
            return
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if insumo_id and es_compuesto:
            self._abrir_apu_insumo(insumo_id)

    def _on_apu_detalle_editado(self, item, column):
        """itemChanged de la tabla de detalle del APU — persiste edición de
        Precio (P.U., col 4), Operador (Op, col 5) o Cantidad (Valor, col 6).

        Las filas de insumo compuesto nunca llegan aquí editadas: no son
        editables (ver _editable_cols_detalle en _build_apu_tab), así que no
        hay riesgo de chocar con la navegación al sub-APU por doble clic.
        """
        if column not in (4, 5, 6) or not self._api:
            return
        comp_id = item.data(5, Qt.ItemDataRole.UserRole)

        if column == 5:  # Op
            op = item.text(column).strip()
            if op not in ('*', '/'):
                item.setText(column, '*')
                return
            if comp_id:
                self._api.apu_actualizar_operador(comp_id, op)
                self._refrescar_tab_activa()
            return

        if column == 6:  # Valor (cantidad de este componente en esta matriz)
            try:
                texto = item.text(column).replace(",", "").strip()
                valor = float(texto)
            except ValueError:
                return
            if not comp_id:
                return
            from PySide6.QtWidgets import QMessageBox
            try:
                self._api.apu_actualizar_valor(comp_id, valor)
            except ValueError as e:
                QMessageBox.warning(self, "Cantidad inválida", str(e))
            self._refrescar_tab_activa()
            return

        if column == 4:  # P.U. — vive en el insumo del catálogo, no en esta fila
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            if not insumo_id:
                return
            try:
                texto = item.text(column).replace("$", "").replace(",", "").strip()
                precio = float(texto)
            except ValueError:
                return
            self._api.apu_actualizar_precio_componente(insumo_id, precio)
            self._refrescar_tab_activa()

    def _on_item_dblclick(self, item, column):
        """Doble clic en presupuesto/insumos → abre APU del concepto."""
        from frontend.ventana.widgets.arbol import ID_ROLE
        if self._es_pu(item, column):
            nodo_id = item.data(0, ID_ROLE)
            if nodo_id:
                self._abrir_apu_por_id(nodo_id)

    def _abrir_apu_por_id(self, nodo_id: int):
        """Abre el APU de un concepto del árbol de presupuesto (por id de estructura_presupuesto)."""
        if not nodo_id or not self._api:
            return
        resultado = self._api.apu(nodo_id=nodo_id)
        self._abrir_apu_resultado(resultado, referencia=f"Concepto #{nodo_id}",
                                   id_fallback=f"#{nodo_id}")

    def _on_concepto_editado(self, item, column):
        """itemChanged del árbol del presupuesto — persiste edición inline.

        Col 4 = Descripción (capítulos: directo; conceptos: vía insumo)
        Col 5 = Unidad      (conceptos: vía insumo)
        Col 6 = Cant        (conceptos)

        P.U. (col 7) NO se edita desde aquí — bloqueado a propósito. El árbol
        solo tiene insumo_id, no si el insumo es compuesto, así que no se
        podía replicar el mismo bloqueo que ya funciona dentro del APU
        (donde si tiene sub-APU, no se deja editar). Para cambiar un precio:
        desde Insumos, o desde dentro del APU del concepto.
        """
        from frontend.ventana.widgets.arbol import ID_ROLE
        nodo_id = item.data(0, ID_ROLE)
        if nodo_id is None:
            return
        tipo = item.text(2)

        if column == 6:  # Cant
            try:
                texto = item.text(column).strip().replace("$", "")
                if texto.count(",") == 1 and texto.count(".") == 0:
                    texto = texto.replace(",", ".")
                else:
                    texto = texto.replace(",", "")
                cantidad = float(texto)
            except ValueError:
                return
            self._api.concepto_actualizar_cantidad(nodo_id, cantidad)

        elif column == 4:  # Descripción
            if tipo == "Capítulo":
                self._api.agrupador_actualizar_descripcion(nodo_id, item.text(column))
            else:
                # Descripción del concepto vive en insumos.descripcion (catálogo
                # compartido) — puede rechazar el cambio si colisiona con otro
                # insumo ya existente (mismo hash). Sin este try/except el error
                # se propagaba sin avisar al usuario y la celda quedaba
                # mostrando un texto que nunca se guardó.
                from PySide6.QtWidgets import QMessageBox
                try:
                    self._api.concepto_actualizar_descripcion(nodo_id, item.text(column))
                except ValueError as e:
                    QMessageBox.warning(self, "Descripción duplicada", str(e))
                    self._refrescar_tab_activa()
                    return

        elif column == 5:  # Unidad
            if tipo == "Concepto":
                self._api.concepto_actualizar_unidad(nodo_id, item.text(column))

        self._refrescar_tab_activa()

    @staticmethod
    def _es_pu(item, column) -> bool:
        """Detecta si la columna contiene 'PU' o 'PRECIO' (case-insensitive)."""
        tw = item.treeWidget()
        if not tw:
            return False
        h = tw.headerItem().text(column).replace(".", "").upper()
        return "PU" in h or "PRECIO" in h

    def _abrir_apu_insumo(self, insumo_id: int):
        """Abre el APU de un insumo compuesto del catálogo (por id de insumos)."""
        if not insumo_id or not self._api:
            return
        resultado = self._api.apu(insumo_id=insumo_id)
        self._abrir_apu_resultado(resultado, referencia=f"Insumo #{insumo_id}",
                                   id_fallback=f"#{insumo_id}")

    def _abrir_apu_resultado(self, resultado, *, referencia: str, id_fallback: str):
        """Único punto que arma o enfoca la pestaña de un APU ya resuelto.

        Antes _abrir_apu_por_id y _abrir_apu_insumo (y una tercera, _abrir_apu
        por 'clave' de texto, ya eliminada) duplicaban esta lógica cada una a
        su manera — con pequeñas diferencias (chequeo de self._db, formato de
        título, texto de encabezado sin fallback) que hacían que el mismo APU
        se comportara distinto según si se abría desde Presupuesto o desde
        Insumos. Ahora todas las vías de entrada terminan aquí.
        """
        if not resultado:
            self._sb.showMessage(f"{referencia} no tiene matriz relacionada", 4000)
            return
        matriz_id   = resultado["matriz_id"]
        descripcion = resultado.get("descripcion", "") or ""
        title = f"APU: {descripcion[:30]}" if descripcion else f"APU: {id_fallback}"

        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        idx = self._tabs.addTab(self._build_apu_tab(matriz_id, descripcion), title)
        self._tabs.setCurrentIndex(idx)

    # ── Rastrear insumo ──────────────────────────────────────────────────
    # Muestra en una pestaña las matrices (conceptos/compuestos) que usan
    # un insumo. Doble clic en cualquier columna abre el APU de la matriz.

    def _on_rastrear_insumo(self, insumo_id: int):
        """Busca insumo por id y abre pestaña con todas las matrices donde se usa."""
        if not insumo_id or not self._api:
            return
        insumo = self._api.insumo_por_id(insumo_id)
        if not insumo:
            self._sb.showMessage(f"Insumo #{insumo_id} no encontrado", 4000)
            return
        desc  = insumo.get("descripcion") or insumo.get("descripcion_corta") or f"#{insumo_id}"
        title = f"\U0001f50d Uso: {desc[:30]}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        filas = self._api.rastrear_insumo(insumo_id)
        idx = self._tabs.addTab(
            self._build_rastrear_tab(desc, filas), title
        )
        self._tabs.setCurrentIndex(idx)

    def _build_rastrear_tab(self, descripcion: str, filas: list):
        """Construye tabla plana con las matrices que consumen un insumo, menú contextual y doble clic.

        La columna "Clave" se conserva solo para conceptos del árbol (matriz_clave
        viene de estructura_presupuesto.clave). Para insumos compuestos queda vacía
        y la navegación usa el matriz_id guardado en UserRole.
        """
        from frontend.ventana.widgets.base import TreeTableWidget
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
            es_concepto = r["tipo_origen"] == "concepto"
            tipo = "📄 Concepto" if es_concepto else "\u2699 Compuesto"
            row_item = tabla.add_row([
                tipo,
                r.get("matriz_clave", "") if es_concepto else "",
                r.get("matriz_descripcion", ""),
                r.get("matriz_wbs", ""),
                f"{r.get('cantidad', 0):,.3f}",
                f"${r.get('precio', 0):,.2f}",
                f"${r.get('importe', 0):,.2f}",
            ], editable=False)
            # matriz_id: positivo (concepto, navegar por clave) o negativo (compuesto, navegar por id)
            row_item.setData(0, Qt.ItemDataRole.UserRole, r.get("matriz_id"))

        if not filas:
            tabla.add_row([
                "", "", f"\u2716 '{descripcion}' no se usa en ninguna matriz", "", "", "", ""
            ], editable=False)
            return tabla

        tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabla.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(tabla, pos))

        tabla.itemDoubleClicked.connect(
            lambda item, col: self._abrir_matriz_desde_rastreo(item)
        )
        return tabla

    def _abrir_matriz_desde_rastreo(self, item):
        """Abre el APU de una fila de rastreo, distinguiendo concepto (id positivo,
        matriz_id == nodo_id de estructura_presupuesto) de compuesto (id negativo,
        matriz_id == -insumo_id)."""
        matriz_id = item.data(0, Qt.ItemDataRole.UserRole)
        if matriz_id is None:
            return
        if matriz_id > 0:
            self._abrir_apu_por_id(matriz_id)
        else:
            self._abrir_apu_insumo(-matriz_id)

    def _on_rastrear_context_menu(self, tabla, pos):
        """Menú contextual sobre tabla de rastreo: ofrece 'Rastrear uso' del insumo de la fila.
        Solo aplica a filas tipo 'Compuesto', ya que ahí matriz_id == -insumo_id.
        """
        item = tabla.itemAt(pos)
        if not item:
            return
        matriz_id = item.data(0, Qt.ItemDataRole.UserRole)
        if matriz_id is None or matriz_id > 0:
            return  # los conceptos del árbol no tienen "rastrear uso" de insumo aquí
        insumo_id = -matriz_id
        menu = QMenu(self)
        act = menu.addAction("\U0001f50d Rastrear uso")
        act.triggered.connect(lambda: self._on_rastrear_insumo(insumo_id))
        menu.exec(tabla.mapToGlobal(pos))

    # ── Insumos ───────────────────────────────────────────────────────────
    # Catálogo completo de insumos, filtrable por tipo desde el sidebar.
    # Muestra ▶ en insumos que tienen APU (compuestos o matrices).

    def _build_insumos(self, title: str):
        """Catálogo de insumos filtrable por tipo (material, MO, equipo, etc.).
        Muestra ▶ en insumos que tienen APU (compuestos o conceptos del árbol).
        "🧮 Matrices" filtra solo los que aparecen en apu_matrices.
        """
        from frontend.ventana.widgets.insumos import TablaInsumos

        tipo_map = {
            "📚 Todos":       None,
            "📐 Conceptos":   "concepto",     # insumos.tipo_id 32 "Concepto compuesto"
            "🧱 Materiales":  "material",
            "👷 Mano de obra": "mano_obra",
            "🔧 Herramienta": "herramienta",
            "🚜 Equipo":      "equipo",
            "⚙️ Auxiliares":  "auxiliar",
            "🚛 Fletes":      "flete",
            "🏗️ Trabajos":    "trabajo",
        }
        tabla = TablaInsumos()
        # Guardar el filtro de tipo en el widget para que _refrescar_tab_activa lo recupere
        tabla._insumos_tipo = tipo_map.get(title)
        tabla._insumos_matrices = (title == "🧮 Matrices")
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
        tabla.itemChanged.connect(self._on_insumo_editado)

        # Doble clic en cualquier columna abre el APU si el insumo es compuesto
        def _on_insumo_dblclick(item, column):
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            if insumo_id and insumo_id in ids:
                self._abrir_apu_insumo(insumo_id)

        tabla.itemDoubleClicked.connect(_on_insumo_dblclick)
        return tabla

    def _on_insumo_editado(self, item, column):
        """itemChanged de la tabla de insumos — persiste edición inline."""
        from PySide6.QtWidgets import QMessageBox
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not insumo_id or not self._api:
            return
        if column == 1:  # Descripción
            desc = item.text(column).lstrip("\u25b6").strip()
            if not desc:
                return
            try:
                self._api.insumo_actualizar_descripcion(insumo_id, desc)
            except ValueError as e:
                QMessageBox.warning(self, "Descripción duplicada", str(e))
        elif column == 2:  # Unidad
            self._api.insumo_actualizar_campo(insumo_id, "unidad", item.text(column))
        elif column == 3:  # Precio
            try:
                txt = item.text(column).replace("$", "").replace(",", "").strip()
                precio = float(txt)
                self._api.insumo_actualizar_precio(insumo_id, precio)
            except ValueError:
                return
        self._refrescar_tab_activa()

    def _refrescar_tabla_insumos(self, tabla):
        """Recarga una tabla de insumos puntual preservando su filtro, scroll y selección.
        Cada pestaña de Insumos (Materiales, Mano de obra, etc.) es una instancia
        distinta con su propio _insumos_tipo/_insumos_matrices, así que hay que
        refrescarlas una por una."""
        scroll_y = tabla.verticalScrollBar().value()
        current = tabla.currentItem()
        row_key = current.data(0, Qt.ItemDataRole.UserRole) if current else None

        tabla.blockSignals(True)
        tipo = getattr(tabla, '_insumos_tipo', None)
        ids = self._api.insumo_ids_con_apu()
        if getattr(tabla, '_insumos_matrices', False):
            insumos = self._api.insumos_con_matrices(tipo)
        else:
            insumos = self._api.insumos(tipo)
        tabla.poblar(insumos, ids)
        tabla.blockSignals(False)

        tabla.verticalScrollBar().setValue(scroll_y)
        if row_key is not None:
            for i in range(tabla.topLevelItemCount()):
                if tabla.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == row_key:
                    tabla.setCurrentItem(tabla.topLevelItem(i))
                    break

    def _refrescar_tab_activa(self):
        """Recarga TODAS las tablas de datos abiertas (insumos y presupuesto),
        no solo la pestaña activa — así una edición hecha desde Presupuesto se
        refleja de inmediato en cualquier pestaña de Insumos ya abierta, y
        viceversa, sin depender de cuál esté visible en ese momento."""
        if getattr(self, '_refreshing', False):
            return
        self._refreshing = True
        try:
            from frontend.ventana.widgets.insumos import TablaInsumos

            # ── Insumos: todas las pestañas abiertas, no solo la activa ──────
            if self._api:
                for i in range(self._tabs.count()):
                    w = self._tabs.widget(i)
                    tabla = w if isinstance(w, TablaInsumos) else (w.findChild(TablaInsumos) if w else None)
                    if tabla is not None:
                        self._refrescar_tabla_insumos(tabla)

            # ── Presupuesto ─────────────────────────────────────────────────
            if self._arbol_presupuesto is not None and self._api:
                tree = self._arbol_presupuesto
                scroll_y = tree.verticalScrollBar().value()
                current = tree.currentItem()
                row_key = (current.data(0, Qt.ItemDataRole.UserRole),
                           current.data(1, Qt.ItemDataRole.UserRole)) if current else None

                tree.blockSignals(True)
                nodos = self._api.presupuesto_arbol()
                tree.poblar(nodos)
                tree.blockSignals(False)

                tree.verticalScrollBar().setValue(scroll_y)
                if row_key is not None:
                    for i in range(tree.topLevelItemCount()):
                        item = tree.topLevelItem(i)
                        if (item.data(0, Qt.ItemDataRole.UserRole),
                            item.data(1, Qt.ItemDataRole.UserRole)) == row_key:
                            tree.setCurrentItem(item)
                            break

            # ── Pestañas de APU abiertas ──────────────────────────────────────
            # Editar Precio/Valor/Op dentro de un APU cambia su propio total y,
            # por la cascada de recálculo, puede afectar a OTRAS pestañas de
            # APU abiertas que compartan el mismo insumo (p. ej. un compuesto
            # usado en varios conceptos). Antes esto no se refrescaba y la
            # propia pestaña donde acababas de editar se quedaba con el
            # importe/total viejo hasta cerrarla y volver a abrirla.
            if self._api:
                idx_activo = self._tabs.currentIndex()
                for i in range(self._tabs.count()):
                    w = self._tabs.widget(i)
                    matriz_id = w.property("apu_matriz_id") if w else None
                    if matriz_id is None:
                        continue
                    resultado = (self._api.apu(nodo_id=matriz_id) if matriz_id > 0
                                 else self._api.apu(insumo_id=-matriz_id))
                    descripcion = (resultado.get("descripcion", "") or "") if resultado else ""
                    nuevo_title = f"APU: {descripcion[:30]}" if descripcion else f"APU: #{abs(matriz_id)}"
                    self._tabs.removeTab(i)
                    self._tabs.insertTab(i, self._build_apu_tab(matriz_id, descripcion), nuevo_title)
                if 0 <= idx_activo < self._tabs.count():
                    self._tabs.setCurrentIndex(idx_activo)

            # Re-aplicar filtro de búsqueda activo tras el refresh
            if hasattr(self, '_search_input') and hasattr(self, '_on_search'):
                self._on_search(self._search_input.text())
        finally:
            self._refreshing = False

    # ── Buscador de partidas ─────────────────────────────────────────────
    # Vista plana de todos los nodos de tipo 'concepto' en el presupuesto
    # (estructura_presupuesto), no del catálogo de insumos. Permite
    # navegación rápida y apertura de APU por doble clic.
    # No confundir con "📐 Conceptos" en Insumos, que filtra insumos.tipo='concepto'
    # ("Concepto compuesto", tipo_id 32) — un insumo del catálogo que a su vez
    # es un compuesto reutilizable, no una partida del presupuesto.

    def _build_buscador_partidas(self):
        """Catálogo plano de partidas (conceptos del presupuesto) con doble clic para abrir APU."""
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

    # ── Explosión de insumos ─────────────────────────────────────────────
    # Toma los conceptos seleccionados en el árbol del presupuesto,
    # muestra el diálogo de opciones y abre una pestaña con los resultados.

    def _build_explosion(self):
        """Construye y muestra la pestaña de explosión de insumos.
        Obtiene los conceptos seleccionados del árbol del presupuesto.
        Si no hay selección, usa todos los conceptos del proyecto.
        """
        from frontend.ventana.widgets.explosion import (
            DialogoExplosion, PestañaExplosion, TIPOS_INSUMO
        )

        if not self._db:
            return self._build_placeholder("📦 Explosión de insumos")

        # ── Recopilar conceptos seleccionados del árbol
        from frontend.ventana.widgets.arbol import ID_ROLE
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
            on_apu_click=self._abrir_apu_insumo,
            on_rastrear=self._on_rastrear_insumo,
        )

    # ── Explosión de matrices ────────────────────────────────────────────
    # Muestra el APU de uno o más conceptos como árbol expandible.
    # Cada concepto es raíz; hijos = componentes directos.
    # Si un componente es compuesto, se expande perezosamente.

    def _build_matriz_explosion(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QAbstractItemView, QHeaderView, QMessageBox, QTreeWidgetItem
        from PySide6.QtGui import QBrush, QColor, QFont
        from frontend.ventana.widgets.base import TreeTableWidget
        from frontend.ventana.widgets.arbol import COLORES_NIVEL, ID_ROLE
        from backend.database.core import get_apu

        _DEPTH_ROLE = ID_ROLE + 1

        if not self._db:
            return self._build_placeholder("📦 Explosión de matrices")


        concepto_ids = []
        arbol = self._arbol_presupuesto
        if arbol is not None:
            for item in arbol.selectedItems():
                cid = item.data(0, ID_ROLE)
                if cid is not None:
                    concepto_ids.append(cid)
        if not concepto_ids:
            concepto_ids = self._api.todos_concepto_ids()
        if not concepto_ids:
            QMessageBox.information(self, "Sin conceptos",
                                    "No hay conceptos en el presupuesto.")
            return None

        db_path = self._db.db_path
        conn = self._db.conn
        cur = conn.cursor()

        cols = ["Nivel", "Clave", "Descripción", "Unidad", "P.U.", "Op", "Valor", "Importe", "Tipo"]
        tree = TreeTableWidget(cols)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        tree.set_column_modes({
            0: (QHeaderView.ResizeMode.Interactive, 60),
            1: (QHeaderView.ResizeMode.Interactive, 90),
            2: (QHeaderView.ResizeMode.Stretch, 250),
            3: (QHeaderView.ResizeMode.Interactive, 55),
            4: (QHeaderView.ResizeMode.Interactive, 80),
            5: (QHeaderView.ResizeMode.Interactive, 40),
            6: (QHeaderView.ResizeMode.Interactive, 80),
            7: (QHeaderView.ResizeMode.Interactive, 95),
            8: (QHeaderView.ResizeMode.Interactive, 110),
        })

        total_conceptos = 0
        for cid in concepto_ids:
            cur.execute("""
                SELECT ep.descripcion, ep.total
                FROM estructura_presupuesto ep
                WHERE ep.id = ? AND ep.activo = 1
            """, [cid])
            row = cur.fetchone()
            if not row:
                continue
            total = row["total"] or 0
            raiz = QTreeWidgetItem(tree, [
                "", "", row["descripcion"],
                "", "", "", "",
                f"{total:,.2f}",
                "",
            ])
            color = QBrush(QColor(COLORES_NIVEL[0]))
            f = QFont()
            f.setBold(True)
            for c in range(tree.columnCount()):
                raiz.setForeground(c, color)
                raiz.setFont(c, f)

            apu = get_apu(db_path, cid)
            for comp in apu["detalle"]:
                item = self._add_comp_row(raiz, comp, "", 1, _DEPTH_ROLE)
                if comp["insumo_es_compuesto"]:
                    QTreeWidgetItem(item, [""] * len(cols))
                total_conceptos += 1
            raiz.setExpanded(True)

            # Separador entre APUs
            QTreeWidgetItem(tree, [""] * len(cols))

        if total_conceptos == 0:
            QMessageBox.information(self, "Sin APU",
                                    "Los conceptos seleccionados no tienen APU.")
            return None

        def _on_expanded(item):
            if item.childCount() == 1 and not item.child(0).text(1):
                # Placeholder — replace with real data
                placeholder = item.child(0)
                item.removeChild(placeholder)
                insumo_id = item.data(0, ID_ROLE)
                if insumo_id is None:
                    return
                depth = item.data(0, _DEPTH_ROLE) or 0
                apu = get_apu(db_path, -insumo_id)
                for comp in apu["detalle"]:
                    sub = self._add_comp_row(item, comp, "", depth + 1, _DEPTH_ROLE)
                    if comp["insumo_es_compuesto"]:
                        QTreeWidgetItem(sub, [""] * len(cols))

        tree.itemExpanded.connect(_on_expanded)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        lbl = QLabel(f"<b>Explosión de matrices</b> — {len(concepto_ids)} conceptos")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)
        layout.addWidget(tree)

        return w

    def _build_sobrecostos(self):
        """Pestaña de factores de sobrecosto del proyecto.
        5 spinboxes porcentuales, guarda y recalcula el factor_total."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QGridLayout, QLabel,
            QDoubleSpinBox, QPushButton, QGroupBox
        )
        from PySide6.QtCore import Qt
        from backend.database.repos import FactoresSobrecostoRepo

        pid = self._api.proyecto_actual_id()
        if not pid:
            return self._build_placeholder("Sin proyecto activo")

        repo = FactoresSobrecostoRepo(self._db.conn)
        datos = repo.obtener(pid) or {}

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl = QLabel("<b>Factores de sobrecosto</b>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)

        # Formulario en grid
        grupo = QGroupBox("Porcentajes")
        grid = QGridLayout(grupo)
        grid.setSpacing(8)

        campos = [
            ("Indirectos de campo:",    "pct_indirectos_campo"),
            ("Indirectos de oficina:",  "pct_indirectos_oficina"),
            ("Financiamiento:",         "pct_financiamiento"),
            ("Utilidad:",               "pct_utilidad"),
            ("Cargos adicionales:",     "pct_cargos_adicionales"),
        ]

        spinboxes = {}
        for i, (etiqueta, clave) in enumerate(campos):
            lbl_campo = QLabel(etiqueta)
            spin = QDoubleSpinBox()
            spin.setRange(0, 999.99)
            spin.setDecimals(2)
            spin.setSuffix(" %")
            spin.setValue(datos.get(clave, 0.0))
            spinboxes[clave] = spin
            grid.addWidget(lbl_campo, i, 0)
            grid.addWidget(spin, i, 1)

        layout.addWidget(grupo)

        # Factor total calculado
        factor_display = QLabel()
        factor_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(factor_display)

        def _actualizar_factor():
            f = FactoresSobrecostoRepo._calcular_factor(
                spinboxes["pct_indirectos_campo"].value(),
                spinboxes["pct_indirectos_oficina"].value(),
                spinboxes["pct_financiamiento"].value(),
                spinboxes["pct_utilidad"].value(),
                spinboxes["pct_cargos_adicionales"].value(),
            )
            factor_display.setText(
                f"Factor total: <b>{f:.6f}</b>  |  "
                f"(costo_final = costo_directo × {f:.6f})"
            )
            factor_display.setTextFormat(Qt.TextFormat.RichText)

        for spin in spinboxes.values():
            spin.valueChanged.connect(_actualizar_factor)
        _actualizar_factor()

        # Botón guardar
        btn = QPushButton("Guardar y recalcular")
        btn.clicked.connect(lambda: self._guardar_sobrecostos(repo, spinboxes, pid))
        layout.addWidget(btn)
        layout.addStretch()

        return container

    def _guardar_sobrecostos(self, repo, spinboxes, proyecto_id):
        """Guarda los factores, recalcula y refresca el presupuesto."""
        from backend.database.repos.recalculo import RecalculoRepo
        try:
            valores = {k: s.value() for k, s in spinboxes.items()}
            repo.guardar(proyecto_id, **valores)
            RecalculoRepo(repo._conn).recalcular_proyecto(proyecto_id)
            # Refrescar pestaña del presupuesto si está abierta
            self._refrescar_presupuesto()
            self._sb.showMessage("Factores guardados y presupuesto recalculado.", 5000)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Error al guardar sobrecostos:\n{e}")

    def _refrescar_presupuesto(self):
        """Busca la pestaña de presupuesto y la reconstruye."""
        for i in range(self._tabs.count()):
            title = self._tabs.tabText(i)
            if title == "📋 Presupuesto programable":
                # Reemplazar el contenido con uno nuevo
                nuevo = self._build_presupuesto()
                self._tabs.removeTab(i)
                self._tabs.insertTab(i, nuevo, title)
                self._tabs.setCurrentIndex(i)
                break

    def _add_comp_row(self, parent, comp, nivel, depth=0, depth_role=None):
        """Agrega una fila de componente APU al árbol y guarda insumo_id como ID_ROLE."""
        from frontend.ventana.widgets.arbol import ID_ROLE, COLORES_NIVEL
        from PySide6.QtGui import QBrush, QColor
        v  = comp.get("valor", 0) or 0
        op = comp.get("operador", "*")
        pu = comp.get("precio") or comp.get("costo_final", 0)
        qty = v if op == "*" else (1.0 / v if v else 0.0)
        importe = comp.get("importe", 0) or (pu * qty)
        item = QTreeWidgetItem(parent, [
            str(nivel) if nivel else "",
            "",  # columna Clave: ya no aplica, navegación usa insumo_id vía ID_ROLE
            comp.get("insumo_descripcion", comp.get("insumo_desc_corta", "")),
            comp.get("insumo_unidad", ""),
            f"{pu:.2f}" if pu else "",
            op,                        # Operador
            f"{v:.4f}" if v else "",  # Valor raw
            f"{importe:.2f}" if importe else "",
            comp.get("tipo_nombre", ""),
        ])
        item.setData(0, ID_ROLE, comp.get("insumo_id"))
        if depth_role is not None:
            item.setData(0, depth_role, depth)
        if depth > 0 and comp.get("insumo_es_compuesto"):
            color = QBrush(QColor(COLORES_NIVEL[min(depth, len(COLORES_NIVEL) - 1)]))
            f = item.font(0)
            f.setBold(True)
            for c in range(item.columnCount()):
                item.setForeground(c, color)
                item.setFont(c, f)
        return item

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