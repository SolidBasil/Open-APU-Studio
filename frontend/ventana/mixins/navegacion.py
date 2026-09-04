"""
navegacion.py
=============
Mixin de navegación para VentanaPrincipal: toolbar actions, navegación,
búsqueda, pestañas, adjuntos y vista (HandlersMixin).

Mixins hermanos relacionados (ver mixins/): gestion_proyectos.py,
informes.py, diag_dialogs.py.
"""

from pathlib           import Path
from PySide6.QtCore    import Qt, QPoint
from PySide6.QtGui     import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QAbstractItemView,
    QMessageBox, QFileDialog, QMenu, QDialog, QLineEdit,
    QListWidget, QListWidgetItem,
)

from frontend.ventana.mixins.paneles import INSUMOS_TITLES
from frontend.ventana.iconos import icono
from frontend.ventana.ui_utils import confirmar


class _PaletaInput(QLineEdit):
    """QLineEdit de la paleta de comandos: ↑/↓ mueven la selección de la
    lista sin perder el foco de escritura y Enter ejecuta la acción."""

    def __init__(self, lst, run):
        super().__init__()
        self._lst = lst
        self._run = run

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            row = self._lst.currentRow() + (1 if key == Qt.Key.Key_Down else -1)
            self._lst.setCurrentRow(max(0, min(self._lst.count() - 1, row)))
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._run()
            return
        super().keyPressEvent(event)


class _PaletaComandos(QDialog):
    """Paleta Ctrl+P: filtra acciones/pestañas con el teclado y ejecuta."""

    def __init__(self, parent, entradas, ejecutar):
        super().__init__(parent)
        self._entradas = entradas          # [(label, accion)]
        self._ejecutar = ejecutar
        self.setWindowTitle("Comandos")
        self.resize(540, 420)
        lay = QVBoxLayout(self)

        self._lst = QListWidget()
        self._lst.itemActivated.connect(self._run_actual_item)
        lay.addWidget(self._lst)

        self._inp = _PaletaInput(self._lst, self._run_actual)
        self._inp.setPlaceholderText("Filtra acciones, pestañas…")
        lay.addWidget(self._inp)

        self._inp.textChanged.connect(self._reconstruir)
        self._reconstruir()
        self._inp.setFocus()

    @staticmethod
    def _norm(s):
        import unicodedata
        return unicodedata.normalize("NFD", s.lower())

    def _reconstruir(self, *_):
        q = self._norm(self._inp.text())
        self._lst.clear()
        for label, accion in self._entradas:
            if q and q not in self._norm(label):
                continue
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, accion)
            self._lst.addItem(it)
        if self._lst.count():
            self._lst.setCurrentRow(0)

    def _run_actual(self):
        it = self._lst.currentItem()
        if it:
            self._run_actual_item(it)

    def _run_actual_item(self, item):
        self.accept()
        self._ejecutar(item.data(Qt.ItemDataRole.UserRole))


class HandlersMixin:
    """Mixin de handlers — se mezcla en VentanaPrincipal.

    Nota: `self` siempre es la instancia de VentanaPrincipal.
    Los atributos como self._db, self._api, self._tabs, self._sb
    se definen en VentanaPrincipal.__init__ o en otros mixins.
    """

    def _requiere_proyecto(self, *, ruta: bool = False, api: bool = False) -> bool:
        """Guard clause centralizado para handlers que necesitan un proyecto
        abierto. Muestra "Sin proyecto — abre un proyecto primero" y
        devuelve True si la condición pedida no se cumple.

        - Sin argumentos: exige self._db (equivalente al chequeo más laxo
          usado antes en _on_ver_adjuntos).
        - ruta=True: además exige self._db.db_path (equivalente al chequeo
          usado antes en _on_adjuntar_archivo).
        - api=True: además exige self._api (equivalente al chequeo usado
          antes en diag_dialogs.py e informes.py).

        Reemplaza el mismo QMessageBox.information(self, "Sin proyecto",
        "Abre un proyecto primero.") + return que estaba duplicado a mano
        en 7 lugares distintos (navegacion.py, diag_dialogs.py,
        informes.py) — un cambio de texto ahora se hace en un solo sitio.

        Uso: `if self._requiere_proyecto(): return` al inicio del handler.
        """
        sin_proyecto = not self._db
        if not sin_proyecto and ruta:
            sin_proyecto = not getattr(self._db, "db_path", None)
        if not sin_proyecto and api:
            sin_proyecto = not self._api
        if sin_proyecto:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
        return sin_proyecto

    def _on_mostrar_ayuda(self):
        """Abre el diálogo de ayuda con todos los atajos de teclado
        (F1, o VISTA > Ayuda > Atajos de teclado)."""
        from frontend.ventana.widgets.ayuda import DialogoAyuda
        DialogoAyuda(self).exec()

    def _cerrar_tab_widget(self, idx: int):
        """Quita la pestaña en `idx`, guardando estado de columnas y
        desconectando primero del EventBus cualquier widget que se haya
        suscrito (TablaArbol/TablaInsumos, directamente o anidado dentro
        de una pestaña compuesta).

        Usar SIEMPRE esta función en vez de self._tabs.removeTab(idx)
        directo. removeTab() por sí solo no elimina el widget ni lo
        desuscribe — si el widget escuchaba eventos, queda "zombi": vivo
        en Python (referenciado por el EventBus) pero con su objeto Qt ya
        destruido, y la próxima emisión de evento revienta con
        RuntimeError: libshiboken...already deleted (ver event_bus.py).
        """
        widget = self._tabs.widget(idx)
        if widget is not None:
            if hasattr(widget, '_save_header_state'):
                widget._save_header_state()
            for hijo in widget.findChildren(QWidget):
                if hasattr(hijo, '_save_header_state'):
                    hijo._save_header_state()
            for hijo in widget.findChildren(QWidget):
                if hasattr(hijo, 'desconectar_eventos'):
                    hijo.desconectar_eventos()
            if hasattr(widget, 'desconectar_eventos'):
                widget.desconectar_eventos()
        self._tabs.removeTab(idx)

    def _reload_presupuesto(self):
        """Recarga la pestaña de presupuesto con los datos nuevos."""
        idx_actual = self._tabs.currentIndex()
        for i in range(self._tabs.count()):
            if "Presupuesto" in self._tabs.tabText(i):
                self._cerrar_tab_widget(i)
                break
        new_widget = self._build_presupuesto()
        self._tabs.insertTab(0, new_widget, "Presupuesto programable")
        self._tabs.setCurrentIndex(min(idx_actual, self._tabs.count() - 1))

    def _on_copy_toolbar(self):
        """Delega copia al widget activo en la pestaña actual."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "copy_selection"):
            widget.copy_selection()

    def _on_select_all_toolbar(self):
        """Selecciona todas las filas visibles del widget activo."""
        t = self._get_active_table()
        if t:
            t.selectAll()

    def _on_modificar_toolbar(self):
        """Activa edición en la celda actual (equivalente a F2)."""
        t = self._get_active_table()
        if t:
            idx = t.currentIndex()
            if idx.isValid():
                if t.state() == QAbstractItemView.State.EditingState:
                    t.closeEditor(t.indexWidget(idx), QAbstractItemView.NoHint)
                t.edit(idx)

    def _on_desglozar_toolbar(self):
        """Abre APU del ítem seleccionado (equivalente a doble clic en P.U.)."""
        from frontend.ventana.widgets.arbol import ID_ROLE
        t = self._get_active_table()
        if not t:
            return
        item = t.currentItem()
        if not item:
            return
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(insumo_id, int) and insumo_id and hasattr(self, '_abrir_apu_insumo'):
            self._abrir_apu_insumo(insumo_id)
            return
        nodo_id = item.data(0, ID_ROLE)
        if isinstance(nodo_id, int) and nodo_id and hasattr(self, '_abrir_apu_por_id'):
            self._abrir_apu_por_id(nodo_id)

    # ── Desplegar (Primer nivel / Resumen / Todo / Nivel) ────────────────

    def _on_desplegar_primer_nivel(self):
        """Colapsa el árbol del widget activo mostrando solo las raíces."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_primer_nivel"):
            widget.show_primer_nivel()

    def _on_desplegar_resumen(self):
        """Colapsa el árbol mostrando solo los agrupadores."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_solo_agrupadores"):
            widget.show_solo_agrupadores()

    def _on_desplegar_todo(self):
        """Expande completamente el árbol del widget activo."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_todo"):
            widget.show_todo()

    def _on_desplegar_nivel(self):
        """Menú contextual para elegir profundidad de expansión."""
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
        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        else:
            menu.exec(QPoint(
                self._tb.mapToGlobal(self._tb.rect().topLeft()).x(),
                self._tb.mapToGlobal(self._tb.rect().bottomLeft()).y(),
            ))

    # ── Placeholder ───────────────────────────────────────────────────────

    def _build_placeholder(self, title, msg="Esta sección aún no ha sido implementada."):
        """Widget placeholder con icono + título + mensaje."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.Alignment.AlignCenter)
        icon = QLabel()
        icon.setPixmap(icono("construction", 48).pixmap(48, 48))
        icon.setAlignment(Qt.Alignment.AlignCenter)
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

    def _on_sidebar_click(self, item, column):
        """Click simple en sidebar: abre pestaña temporal o enfoca si ya existe."""
        if item is None:
            return  # clic en zona vacía: Qt pasa item=None
        if item.childCount() > 0:
            return
        if not self._db:
            return
        self._focus_or_open_tab(item.text(0), temporary=True)

    def _on_sidebar_double_click(self, item, column):
        """Doble click en sidebar: abre pestaña permanente."""
        if item is None:
            return  # doble clic en zona vacía: Qt pasa item=None
        if item.childCount() > 0:
            return
        if not self._db:
            return
        self._focus_or_open_tab(item.text(0), temporary=False)

    def _focus_or_open_tab(self, title, temporary):
        """Si ya existe una pestaña con ese título, la enfoca; si no, la abre.

        Punto de entrada único para cualquier acción que deba abrir una de
        estas pestañas (sidebar, doble click, botones de toolbar, etc.) —
        centralizar esto evita que un nuevo punto de entrada olvide el
        chequeo de duplicados y termine abriendo una pestaña repetida.
        """
        if not self._db:
            return
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                widget = self._tabs.widget(i)
                if not temporary and widget is self._tab_temp:
                    self._tab_temp = None
                self._tabs.setCurrentIndex(i)
                return
        self._open_sidebar_tab(title, temporary=temporary)

    def _on_abrir_generadores(self):
        """Handler del botón 'Generadores' en la toolbar (pestaña INICIO):
        crea un generador suelto ('Extraordinario', sin concepto) y lo
        abre en su propia pestaña — ver GeneradorMixin._on_nuevo_generador_extra.
        Los generadores ligados a un concepto se abren desde el menú
        contextual "Abrir generador" del árbol de Presupuesto."""
        self._on_nuevo_generador_extra()

    def _on_abrir_extra(self):
        """Handler del botón 'Fuera de presupuesto' en la toolbar."""
        self._focus_or_open_tab("Fuera de presupuesto", temporary=False)

    def _open_sidebar_tab(self, title, temporary):
        """Abre pestaña según título del sidebar."""
        if self._tab_temp is not None:
            idx = self._tabs.indexOf(self._tab_temp)
            if idx >= 0:
                self._cerrar_tab_widget(idx)
            self._tab_temp = None

        if title == "Presupuesto programable":
            content = self._build_presupuesto()
        elif title == "Buscar partidas":
            content = self._build_buscador_partidas()
        elif title == "Explosión de insumos":
            content = self._build_explosion()
            if content is None:
                return
        elif title == "Explosión de matrices":
            content = self._build_matriz_explosion()
            if content is None:
                return
        elif title in INSUMOS_TITLES:
            content = self._build_insumos(title)
        elif title == "Fuera de presupuesto":
            content = self._build_extra_panel()
        else:
            content = self._build_placeholder(title)

        idx = self._tabs.addTab(content, title)
        self._tabs.setCurrentIndex(idx)
        self._on_ajustar_columnas()
        if temporary:
            self._tab_temp = content

    def _next_tab(self):
        """Avanza a la siguiente pestaña cíclicamente."""
        self._tabs.setCurrentIndex((self._tabs.currentIndex() + 1) % self._tabs.count())

    def _prev_tab(self):
        """Retrocede a la pestaña anterior cíclicamente."""
        self._tabs.setCurrentIndex((self._tabs.currentIndex() - 1) % self._tabs.count())

    def _on_tab_close(self, idx):
        """Cierra la pestaña en el índice dado."""
        widget = self._tabs.widget(idx)
        if widget is self._tab_temp:
            self._tab_temp = None
        self._cerrar_tab_widget(idx)

    # ── Búsqueda ──────────────────────────────────────────────────────────

    def _on_search(self, text):
        """Filtra filas del TreeTableWidget activo."""
        t = self._get_active_table()
        if t:
            t.filter_rows(text)

    # ── Atajos teclado-first ─────────────────────────────────────────────

    def _on_foco_busqueda(self):
        """Ctrl+F (o /): enfoca la barra de búsqueda con el texto seleccionado."""
        if not getattr(self, '_search_input', None):
            return
        self._search_input.setFocus()
        self._search_input.selectAll()

    def _on_foco_sidebar(self):
        """Ctrl+Shift+L: enfoca el explorador lateral (navegar con flechas y Enter)."""
        if getattr(self, '_sidebar_tree', None):
            self._sidebar_tree.setFocus()

    def _on_cerrar_pestana(self):
        """Ctrl+W: cierra la pestaña de contenido activa (no la última)."""
        if self._tabs.count() > 1:
            idx = self._tabs.currentIndex()
            if idx >= 0:
                self._on_tab_close(idx)

    def _on_paleta_comandos(self):
        """Ctrl+P: paleta de comandos — escribe para filtrar, Enter para ejecutar."""
        from frontend.ventana.mixins.toolbar import _HANDLERS, _TOOLBAR_CFG

        entradas = [("Cambiar a " + t, ("tab", t)) for t in _TOOLBAR_CFG]
        entradas += [(tip, ("accion", nombre)) for tip, nombre in _HANDLERS.items()
                     if getattr(self, nombre, None)]

        def ejecutar(accion):
            if accion[0] == "tab":
                self._switch_tab(accion[1])
            else:
                getattr(self, accion[1])()

        _PaletaComandos(self, entradas, ejecutar).exec()

    def _on_tab_changed(self, idx):
        """Re-aplica el filtro de búsqueda al cambiar de pestaña.

        Ya no maneja el intercambio de panel izquierdo para generadores
        — los generadores viven en su propio espacio de trabajo
        (self._tabs_generadores, separado de self._tabs — ver
        mixins/generador.py), así que esta pestaña nunca es una pestaña
        de generador, y el auto-switch de ribbon hacia GENERADORES ya lo
        hace _abrir_generador_tab directamente."""
        self._on_search(self._search_input.text())

        title = self._tabs.tabText(idx) if idx >= 0 else ""
        widget = self._tabs.widget(idx) if idx >= 0 else None

        # ponytail: auto-switch ribbon según pestaña de contenido activa
        ribbon_objetivo = None
        if title == "Fuera de presupuesto":
            ribbon_objetivo = "PRINCIPAL"
        elif title == "Presupuesto programable":
            ribbon_objetivo = "PRINCIPAL"
        if ribbon_objetivo and getattr(self, "_tab_activa", None) != ribbon_objetivo:
            from PySide6.QtCore import QTimer

            def _aplicar_ribbon_diferido(r=ribbon_objetivo, t=title, i=idx):
                # Re-verificar AL DISPARAR, no solo al programar: si algo
                # más cambió mientras este timer esperaba su turno no
                # debe pisar ese cambio más reciente con uno más viejo y
                # ya obsoleto. Bug real encontrado así: abrir un
                # generador inmediatamente después de que arranca la app
                # (antes de que el event loop alcance a vaciar este
                # timer, programado desde el arranque al agregarse la
                # primera pestaña normal) hacía que este timer disparara
                # DESPUÉS de _abrir_generador_tab y regresara el ribbon a
                # PRINCIPAL — pisando el cambio a GENERADORES.
                #
                # No basta con revisar que la pestaña normal siga siendo
                # la misma (self._tabs.currentIndex()/tabText): abrir un
                # generador no le mueve el índice a self._tabs para
                # nada, así que esa condición sigue cumpliéndose aunque
                # ya se haya entrado al espacio de Generadores. Hay que
                # revisar además que el espacio ACTIVO siga siendo el
                # normal (self._central_stack, índice 0) — si ya se
                # cambió al espacio de Generadores (índice 1), este
                # ribbon-sync viejo de la pestaña normal ya no aplica.
                central = getattr(self, "_central_stack", None)
                if central is not None and central.currentIndex() != 0:
                    return
                if (self._tabs.currentIndex() == i
                        and self._tabs.tabText(i) == t):
                    self._switch_tab(r)

            QTimer.singleShot(0, _aplicar_ribbon_diferido)

        # Los botones Deshacer/Rehacer CAD siguen al generador de la
        # pestaña activa (cada uno tiene su propio undo stack).
        if hasattr(self, "_update_undo_buttons"):
            self._update_undo_buttons()

        # Teclado-first: al cambiar de pestaña, enfocar su tabla para que
        # las flechas/atajos funcionen de inmediato sin clic previo.
        from frontend.ventana.widgets.base import TreeTableWidget
        from PySide6.QtCore import QTimer as _QT
        if widget is not None:
            target = widget if isinstance(widget, TreeTableWidget) \
                else widget.findChild(TreeTableWidget)
            if target is not None:
                _QT.singleShot(0, target.setFocus)

    # ── Adjuntar / Ver adjuntos ───────────────────────────────────────────

    def _on_adjuntar_archivo(self):
        from PySide6.QtWidgets import QMessageBox
        from backend.database.db import Rutas
        import shutil

        if self._requiere_proyecto(ruta=True):
            return

        path, _ = QFileDialog.getOpenFileName(self, "Adjuntar archivo al proyecto")
        if not path:
            return

        nombre = Path(self._db.db_path).stem
        dst_dir = Rutas.proyectos() / f"{nombre}_adjuntos"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / Path(path).name
        shutil.copy2(path, dst)

        self._sb.showMessage(f"Archivo adjuntado: {dst.name}", 4000)

    def _on_ver_adjuntos(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, \
            QPushButton, QListWidget, QListWidgetItem, QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from backend.database.db import Rutas

        if self._requiere_proyecto():
            return

        adj_dir = Rutas.proyectos() / f"{Path(self._db.db_path).stem}_adjuntos"
        if not adj_dir.is_dir():
            self._sb.showMessage("Este proyecto no tiene archivos adjuntos.", 3000)
            return

        archivos = sorted(adj_dir.iterdir())
        if not archivos:
            self._sb.showMessage("La carpeta de adjuntos está vacía.", 3000)
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Adjuntos — {Path(self._db.db_path).stem}")
        dlg.setMinimumSize(500, 360)
        layout = QVBoxLayout(dlg)

        lst = QListWidget()
        for f in archivos:
            st = f.stat()
            size = st.st_size
            if size < 1024:
                label = f"{size} B"
            elif size < 1024**2:
                label = f"{size/1024:.1f} KB"
            else:
                label = f"{size/1024**2:.1f} MB"
            item = QListWidgetItem(f"{f.name}  ({label})")
            item.setData(1, str(f))
            lst.addItem(item)
        layout.addWidget(lst)

        row = QHBoxLayout()
        btn_open = QPushButton("Abrir")
        btn_del  = QPushButton("Eliminar")
        btn_close = QPushButton("Cerrar")
        row.addWidget(btn_open)
        row.addWidget(btn_del)
        row.addStretch()
        row.addWidget(btn_close)
        layout.addLayout(row)

        def abrir():
            item = lst.currentItem()
            if item:
                QDesktopServices.openUrl(QUrl.fromLocalFile(item.data(1)))

        def eliminar():
            item = lst.currentItem()
            if not item:
                return
            if confirmar(dlg, "Confirmar", f"¿Eliminar '{Path(item.data(1)).name}'?",
                         "Eliminar", destructivo=True):
                Path(item.data(1)).unlink()
                lst.takeItem(lst.row(item))
                if lst.count() == 0:
                    dlg.accept()

        btn_open.clicked.connect(abrir)
        btn_del.clicked.connect(eliminar)
        btn_close.clicked.connect(dlg.close)
        dlg.exec()

    # ── VISTA handlers ─────────────────────────────────────────────────────

    def _get_active_table(self):
        """Retorna el TreeTableWidget activo o None."""
        from frontend.ventana.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if isinstance(w, TreeTableWidget):
            return w
        return w.findChild(TreeTableWidget) if w else None

    def _get_move_context(self):
        """Contexto común para operaciones de mover/indent/outdent.
        Devuelve (t, ds, conn, proyecto_id, repo, seleccionados) o
        (None, …) si no hay tabla activa, proyecto o selección."""
        from backend.database.repos import NodoRepo
        t = self._get_active_table()
        ds = getattr(self, '_data_service', None)
        api = getattr(self, '_api', None)
        conn = getattr(self, '_conn', None)
        if not t or not conn or not ds or not api:
            return None, None, None, None, None, None
        seleccionados = t.selectedItems()
        if not seleccionados:
            return t, ds, conn, None, None, None
        return t, ds, conn, api.proyecto_actual_id(), NodoRepo(conn), seleccionados

    def _on_ajustar_columnas(self):
        """Auto-ajusta ancho de columnas al contenido (solo si no hay estado guardado)."""
        from PySide6.QtWidgets import QHeaderView
        t = self._get_active_table()
        if not t:
            return
        if hasattr(t, '_restore_header_state') and t._restore_header_state():
            return
        h = t.header()
        h.resizeSections(QHeaderView.ResizeMode.ResizeToContents)
        for c in range(t.columnCount()):
            if not t.isColumnHidden(c):
                h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)

    def _on_mostrar_ocultar(self):
        """Menú contextual con checkboxes de columnas visibles."""
        t = self._get_active_table()
        if not t:
            return
        btn = self.sender()
        menu = QMenu(self)
        for c in range(t.columnCount()):
            name = t.headerItem().text(c)
            if not name:
                continue
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(not t.isColumnHidden(c))
            act.toggled.connect(lambda checked, col=c: t.setColumnHidden(col, not checked))
        pos = btn.mapToGlobal(btn.rect().bottomLeft()) if btn else self._tb.mapToGlobal(self._tb.rect().topLeft())
        menu.exec(pos)
        if hasattr(t, '_save_header_state'):
            t._save_header_state()

    def _on_restablecer_formato(self):
        """Restaura anchos y visibilidad de columnas a sus valores por defecto."""
        from frontend.ventana.widgets.arbol import TablaArbol
        t = self._get_active_table()
        if not t:
            return
        if isinstance(t, TablaArbol):
            t._restore_header_state()
            for c in range(t.columnCount()):
                t.setColumnHidden(c, c not in TablaArbol._VISIBLE)
        elif hasattr(t, '_pending_modes'):
            t._apply_column_modes()

    def _on_pantalla_completa(self):
        """Alterna entre pantalla completa y el modo anterior.

        showNormal() por sí solo siempre cae a una geometría "normal"
        genérica, sin importar si la ventana venía maximizada o con un
        tamaño/posición específico — por eso al salir de pantalla
        completa se veía "rara". Ahora se guarda el estado previo
        (maximizada o no, y su geometría) al entrar, y se restaura
        exactamente ese estado al salir.
        """
        if self.isFullScreen():
            if getattr(self, "_pre_fullscreen_maximizada", False):
                self.showMaximized()
            else:
                self.showNormal()
                geom = getattr(self, "_pre_fullscreen_geometria", None)
                if geom is not None:
                    self.setGeometry(geom)
        else:
            self._pre_fullscreen_maximizada = self.isMaximized()
            self._pre_fullscreen_geometria = self.geometry()
            self.showFullScreen()

    # ── Reordenar nodos ────────────────────────────────────────────
    #
    # Las 4 operaciones (Subir/Bajar/Izquierda/Derecha) tocan ÚNICAMENTE
    # padre_id y/o orden del nodo movido — nunca wbs/nivel a mano, y nunca
    # a sus descendientes. padre_id + orden (con alcance local a cada
    # padre_id) son la única fuente de verdad de la jerarquía; wbs/nivel
    # son etiquetas derivadas que reindexar() recalcula desde cero al
    # final de cada operación, por lo que nunca pueden desincronizarse
    # (ver NodoRepo.reindexar() en backend/database/repos/presupuesto.py).

    def _on_subir(self):
        self._mover_nodo(-1)

    def _on_bajar(self):
        self._mover_nodo(1)

    @property
    def _conn(self):
        return self._db._conn if self._db else None

    @staticmethod
    def _grupos_por_padre(t, seleccionados, ID_ROLE):
        """Agrupa los QTreeWidgetItem seleccionados por el id de su padre
        real (None = nivel raíz). Selecciones que abarcan varios grupos
        de hermanos distintos (ej. conceptos de dos capítulos diferentes,
        seleccionados juntos con Ctrl+click) se procesan cada una por
        separado, cada quien dentro de su propia lista de hermanos."""
        grupos: dict[int | None, set[int]] = {}
        for item in seleccionados:
            node_id = item.data(0, ID_ROLE)
            if node_id is None:
                continue
            padre_item = item.parent()
            padre_id = padre_item.data(0, ID_ROLE) if padre_item is not None else None
            grupos.setdefault(padre_id, set()).add(node_id)
        return grupos

    @staticmethod
    def _runs_contiguos(hermanos: list[int], seleccionados: set[int]) -> list[list[int]]:
        """Tramos contiguos de ids seleccionados dentro de la lista de
        hermanos (en su orden actual). Un Shift+click típico produce un
        solo tramo; un Ctrl+click salteado puede producir varios, cada
        uno tratado como su propio bloque."""
        runs: list[list[int]] = []
        actual: list[int] = []
        for nid in hermanos:
            if nid in seleccionados:
                actual.append(nid)
            elif actual:
                runs.append(actual)
                actual = []
        if actual:
            runs.append(actual)
        return runs

    def _mover_nodo(self, direccion: int):
        """Sube (-1) o baja (+1) los nodos seleccionados un lugar entre
        sus hermanos. Soporta selección múltiple (Shift/Ctrl+click): cada
        tramo contiguo de seleccionados se mueve como bloque, y cada
        grupo de hermanos afectado (si la selección abarca más de un
        padre) se procesa por separado — ver NodoRepo.reordenar_grupo()."""
        from frontend.ventana.widgets.arbol import ID_ROLE
        from backend.database.event_bus import ProyectoRecalculado

        t, ds, conn, proyecto_id, repo, seleccionados = self._get_move_context()
        if not repo or not seleccionados:
            return
        grupos = self._grupos_por_padre(t, seleccionados, ID_ROLE)

        hubo_cambio = False
        for padre_id, ids_sel in grupos.items():
            hermanos = repo.hermanos_de(padre_id, proyecto_id)
            nuevo = repo.reordenar_grupo(hermanos, ids_sel, direccion)
            if nuevo != hermanos:
                # SRV-10: capturar orden ANTES de escribir para undo
                from backend.database.repos.historial import HistorialRepo
                h_repo = HistorialRepo(conn)
                h_repo.limpiar_deshachadas(1)
                import uuid as _uuid
                sesion = str(_uuid.uuid4())
                viejos_map = repo.orden_antes_de(nuevo)
                for pos, nid in enumerate(nuevo, start=1):
                    viejo = viejos_map.get(nid)
                    if viejo is not None and viejo != pos:
                        h_repo.capturar(
                            tabla="estructura_presupuesto", registro_id=nid,
                            campo="orden", valor_anterior=viejo,
                            valor_nuevo=pos, usuario_id=1, sesion=sesion,
                        )
                repo.escribir_orden(nuevo)
                hubo_cambio = True

        if not hubo_cambio:
            return
        repo.reindexar(proyecto_id)
        conn.commit()
        ds.emitir(ProyectoRecalculado(proyecto_id))

    def _on_izquierda(self):
        """Saca los nodos seleccionados de su padre (outdent): pasan a
        ser hijos de su abuelo (o del nivel raíz, si el padre ya estaba
        en la raíz), colocándose como bloque justo DESPUÉS de su antiguo
        padre — para conservar su ubicación relativa en vez de saltar al
        final de todo el grupo (que, si el abuelo es la raíz, sería el
        final de TODOS los capítulos del proyecto).

        Con selección múltiple: los seleccionados que comparten el mismo
        padre salen juntos, preservando su orden relativo original entre
        sí, aunque no hayan estado contiguos dentro de ese padre."""
        from frontend.ventana.widgets.arbol import ID_ROLE
        from backend.database.event_bus import ProyectoRecalculado

        t, ds, conn, proyecto_id, repo, seleccionados = self._get_move_context()
        if not repo or not seleccionados:
            return

        # Solo agrupa seleccionados que SÍ tienen padre (los que ya están
        # en la raíz no tienen adónde "salir" y se ignoran en silencio).
        grupos: dict[int, set[int]] = {}
        for item in seleccionados:
            node_id = item.data(0, ID_ROLE)
            if node_id is None:
                continue
            padre_item = item.parent()
            if padre_item is None:
                continue
            padre_id = padre_item.data(0, ID_ROLE)
            if padre_id is None:
                continue
            grupos.setdefault(padre_id, set()).add(node_id)

        hubo_cambio = False
        for padre_id, ids_sel in grupos.items():
            fila_padre = repo.info_nodo(padre_id)
            if not fila_padre:
                continue
            abuelo_id = fila_padre["padre_id"]

            # Orden relativo original dentro de padre_id, para preservarlo
            # al reinsertar el bloque tras su antiguo padre.
            hermanos = repo.hermanos_de(padre_id, proyecto_id)
            ids_en_orden = [nid for nid in hermanos if nid in ids_sel]
            if not ids_en_orden:
                continue

            base = repo.orden_tras(proyecto_id, abuelo_id, fila_padre["orden"],
                                    hueco=len(ids_en_orden))
            for offset, nid in enumerate(ids_en_orden):
                ds.actualizar("estructura_presupuesto", nid,
                               padre_id=abuelo_id, orden=base + offset)
            hubo_cambio = True

        if not hubo_cambio:
            return
        repo.reindexar(proyecto_id)
        conn.commit()
        ds.emitir(ProyectoRecalculado(proyecto_id))

    def _on_derecha(self):
        """Mete los nodos seleccionados como hijos del hermano inmediato
        anterior (indent), al final de los hijos de ese hermano.

        Si el hermano anterior es un concepto (no agrupador), se crea un
        nuevo agrupador como hermano de ese concepto y los nodos entran
        como hijos del nuevo agrupador.

        Con selección múltiple: cada tramo CONTIGUO de seleccionados (ver
        _runs_contiguos) se mueve como un solo bloque hacia el hermano
        que estaba justo antes del tramo — así el bloque entra completo
        a un mismo nuevo padre, en vez de que cada nodo busque su propio
        "hermano anterior" (que tras mover el primero ya habría cambiado)."""
        from frontend.ventana.widgets.arbol import ID_ROLE
        from backend.database.event_bus import ProyectoRecalculado

        t, ds, conn, proyecto_id, repo, seleccionados = self._get_move_context()
        if not repo or not seleccionados:
            return
        grupos = self._grupos_por_padre(t, seleccionados, ID_ROLE)

        hubo_cambio = False
        for padre_id, ids_sel in grupos.items():
            hermanos = repo.hermanos_de(padre_id, proyecto_id)
            for run in self._runs_contiguos(hermanos, ids_sel):
                idx0 = hermanos.index(run[0])
                if idx0 == 0:
                    continue
                objetivo_id = hermanos[idx0 - 1]
                objetivo = repo.buscar(objetivo_id)
                if objetivo and objetivo["tipo"] != "capitulo":
                    # El nuevo agrupador debe quedar EN EL LUGAR de objetivo
                    # (justo después de él, entre sus hermanos bajo padre_id),
                    # no al final de todo el grupo — por eso orden_tras() en
                    # vez de proximo_orden() (bug: mandaba el agrupador hasta
                    # el fondo del presupuesto).
                    orden_nuevo = repo.orden_tras(proyecto_id, padre_id, objetivo["orden"])
                    nuevo_ag_id = repo.insert({
                        "proyecto_id": proyecto_id,
                        "padre_id":    padre_id,
                        "wbs":         "",
                        "nivel":       0,
                        "tipo":        "capitulo",
                        "descripcion": "Agrupador",
                        "orden":       orden_nuevo,
                        "total":       0.0,
                        "estado":      0,
                        "activo":      1,
                        "creado_por":  1,
                    })
                    objetivo_id = nuevo_ag_id
                base = repo.proximo_orden(proyecto_id, objetivo_id)
                for offset, nid in enumerate(run):
                    ds.actualizar("estructura_presupuesto", nid,
                                   padre_id=objetivo_id, orden=base + offset)
                hubo_cambio = True

        if not hubo_cambio:
            return
        repo.reindexar(proyecto_id)
        conn.commit()
        ds.emitir(ProyectoRecalculado(proyecto_id))

    def _on_drop_arbol(self, ids_arrastrados: list[int], nuevo_padre_id: int | None,
                        antes_de_id: int | None, copiar: bool) -> bool:
        """Handler del drag and drop del árbol de Presupuesto (ver
        TablaArbol.dropEvent): mueve o copia (Ctrl) el bloque de nodos
        arrastrados para que queden hijos de nuevo_padre_id, insertados
        justo antes de antes_de_id (o al final de sus hijos si es None).

        Devuelve True si se aplicó el cambio, False si se rechazó (ej.
        soltar un capítulo dentro de su propio subárbol al mover) — el
        caller decide qué hacer visualmente con ese resultado (TablaArbol
        simplemente ignora el evento de drop).

        Tanto mover como copiar quedan en el historial de deshacer: mover
        invierte padre_id/orden; copiar borra (soft-delete) todas las
        filas nuevas creadas — ver HistorialRepo.capturar_creado."""
        from backend.database.repos import NodoRepo, RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        conn = getattr(self, '_conn', None)
        ds = getattr(self, '_data_service', None)
        api = getattr(self, '_api', None)
        if not conn or not ds or not api or not ids_arrastrados:
            return False
        proyecto_id = api.proyecto_actual_id()
        repo = NodoRepo(conn)

        if not copiar:
            # Mover: rechazar si el destino cae dentro del propio bloque
            # arrastrado (crearía un padre_id cíclico — ver es_ancestro_o_mismo).
            for nid in ids_arrastrados:
                if nuevo_padre_id is not None and repo.es_ancestro_o_mismo(nid, nuevo_padre_id):
                    return False
                if antes_de_id in ids_arrastrados:
                    return False

            from backend.database.repos.historial import HistorialRepo
            h_repo = HistorialRepo(conn)
            h_repo.limpiar_deshachadas(1)
            import uuid as _uuid
            sesion = str(_uuid.uuid4())
            viejos = {nid: repo.info_nodo(nid) for nid in ids_arrastrados}
            repo.mover_bloque(ids_arrastrados, proyecto_id, nuevo_padre_id, antes_de_id)
            nuevos = {nid: repo.info_nodo(nid) for nid in ids_arrastrados}
            for nid in ids_arrastrados:
                viejo, nuevo = viejos[nid], nuevos[nid]
                if not viejo or not nuevo:
                    continue
                if viejo["padre_id"] != nuevo["padre_id"]:
                    h_repo.capturar(
                        tabla="estructura_presupuesto", registro_id=nid,
                        campo="padre_id", valor_anterior=viejo["padre_id"],
                        valor_nuevo=nuevo["padre_id"], usuario_id=1, sesion=sesion,
                    )
                if viejo["orden"] != nuevo["orden"]:
                    h_repo.capturar(
                        tabla="estructura_presupuesto", registro_id=nid,
                        campo="orden", valor_anterior=viejo["orden"],
                        valor_nuevo=nuevo["orden"], usuario_id=1, sesion=sesion,
                    )
        else:
            from backend.database.repos.historial import HistorialRepo
            h_repo = HistorialRepo(conn)
            h_repo.limpiar_deshachadas(1)
            import uuid as _uuid
            sesion = str(_uuid.uuid4())
            nuevas_raices = repo.duplicar_bloque(ids_arrastrados, proyecto_id,
                                                  nuevo_padre_id, antes_de_id)
            # Capturar TODAS las filas nuevas (cada raíz duplicada más sus
            # descendientes, si era un capítulo con contenido) — de otro
            # modo Ctrl+Z solo borraría las raíces y dejaría huérfanos
            # duplicados sueltos en el árbol.
            for raiz_id in nuevas_raices:
                for fila in repo.descendientes(raiz_id):
                    h_repo.capturar_creado("estructura_presupuesto", fila["id"],
                                            usuario_id=1, sesion=sesion)

        repo.reindexar(proyecto_id)
        RecalculoRepo(conn).recalcular_proyecto(proyecto_id)
        conn.commit()
        ds.emitir(ProyectoRecalculado(proyecto_id))
        return True

    def _on_eliminar(self):
        """Elimina los elementos seleccionados (nodos del árbol o filas de insumos).

        Detecta qué pestaña está activa y qué tipo de widget contiene la selección.
        Muestra confirmación antes de proceder.
        """
        from frontend.ventana.widgets.arbol import TablaArbol, ID_ROLE, TIPO_ROLE
        from frontend.ventana.widgets.insumos import TablaInsumos

        t = self._get_active_table()
        api = getattr(self, '_api', None)
        if not t or not api:
            return
        seleccionados = t.selectedItems()
        if not seleccionados:
            return

        if isinstance(t, TablaInsumos):
            ids = [it.data(0, Qt.ItemDataRole.UserRole) for it in seleccionados
                   if it.data(0, Qt.ItemDataRole.UserRole) is not None]
            if not ids:
                return
            resp = confirmar(
                self, "Eliminar insumos",
                f"¿Eliminar {len(ids)} insumo(s) del catálogo?\n"
                "Los insumos se desactivarán y no aparecerán en el presupuesto.",
                "Eliminar", destructivo=True,
            )
            if not resp:
                return
            for iid in ids:
                api.eliminar_insumo(iid)

        elif isinstance(t, TablaArbol):
            nodos = []
            for it in seleccionados:
                nid = it.data(0, ID_ROLE)
                tipo = it.data(0, TIPO_ROLE)
                if nid is not None:
                    nodos.append((nid, tipo))
            if not nodos:
                return
            resp = confirmar(
                self, "Eliminar elementos",
                f"¿Eliminar {len(nodos)} elemento(s) del presupuesto?\n"
                "Se desactivarán y los totales se recalcularán.",
                "Eliminar", destructivo=True,
            )
            if not resp:
                return
            for nid, tipo in nodos:
                api.eliminar_nodo(nid)

    def _on_deshacer(self):
        """Ctrl+Z: deshace la última operación (SRV-10)."""
        api = getattr(self, '_api', None)
        if not api:
            return
        try:
            ok = api.deshacer()
            if ok:
                # ponytail: ProyectoRecalculado ya refresca el árbol in-place
                # preservando selección y scroll (ver arbol.py:_on_proyecto_recalculado)
                self._sb.showMessage("Operación deshecha", 2000)
            else:
                self._sb.showMessage("Nada que deshacer", 2000)
        except Exception as e:
            self._sb.showMessage(f"Error al deshacer: {e}", 4000)

    def _on_rehacer(self):
        """Ctrl+Y: rehace la última operación deshecha (SRV-10)."""
        api = getattr(self, '_api', None)
        if not api:
            return
        try:
            ok = api.rehacer()
            if ok:
                self._sb.showMessage("Operación rehecha", 2000)
            else:
                self._sb.showMessage("Nada que rehacer", 2000)
        except Exception as e:
            self._sb.showMessage(f"Error al rehacer: {e}", 4000)

    def _on_agregar_agrupador(self):
        """Agrega un capítulo/agrupador nuevo al presupuesto (solo si la pestaña activa es presupuesto)."""
        from frontend.ventana.mixins.paneles import INSUMOS_TITLES
        idx = self._tabs.currentIndex()
        title = self._tabs.tabText(idx) if idx >= 0 else ""
        if title in INSUMOS_TITLES:
            return
        self._agregar_nodo("capitulo")

    def _on_agregar_concepto(self):
        """Agrega un concepto nuevo al presupuesto, o un insumo si estamos en la pestaña de insumos."""
        from frontend.ventana.mixins.paneles import INSUMOS_ITEMS, INSUMOS_TITLES
        idx = self._tabs.currentIndex()
        title = self._tabs.tabText(idx) if idx >= 0 else ""
        if title in INSUMOS_TITLES:
            from frontend.ventana.widgets.dialogs import InsumoDialog
            from frontend.ventana.tipos_insumo import CLAVE as _CLAVE
            if not self._api:
                return
            tipo_map = {t: k for t, k in INSUMOS_ITEMS}
            tipo_clave = tipo_map.get(title)
            default_tipo = next((tid for tid, c in _CLAVE.items() if c == tipo_clave), None) if tipo_clave else None
            dlg = InsumoDialog(self._api, parent=self, default_tipo=default_tipo)
            if dlg.exec() == 1:
                self._on_tab_changed(idx)
            return
        self._agregar_nodo("concepto")

    def _agregar_nodo(self, tipo: str, *, insumo_id: int | None = None,
                       busqueda_inicial: str = ""):
        """Inserta un nodo del tipo dado en el presupuesto.

        - Capítulo: se inserta directo.
        - Concepto: si no se pasa `insumo_id` ya resuelto, abre selector de
          insumo (con `busqueda_inicial` precargada en el buscador si se
          da); si se cancela (Esc), no inserta nada. `insumo_id` ya
          resuelto salta el diálogo por completo — lo usa
          _on_fila_vacia_editada (mixins/apu.py) cuando escribir en la
          fila vacía final ya matcheó una descripción del catálogo.

        Contexto del árbol al momento de insertar:
          - Capítulo seleccionado → hijo, arriba del primero
          - Concepto seleccionado → hermano, arriba de él
          - Nada seleccionado (o la fila vacía final) → nodo raíz, al final

        Tras insertar, selecciona el nodo nuevo y abre edición inline.
        """
        from frontend.ventana.widgets.arbol import TablaArbol, ID_ROLE, TIPO_ROLE
        from PySide6.QtCore import QTimer

        api = getattr(self, '_api', None)
        t = getattr(self, '_arbol_presupuesto', None)
        if not t or not api or not isinstance(t, TablaArbol):
            return

        # Calcular padre y posición
        sel = t.selectedItems()
        padre_id = None
        antes_de = None

        if sel:
            item = sel[0]
            id_actual = item.data(0, ID_ROLE)
            tipo_actual = item.data(0, TIPO_ROLE)
            if tipo_actual == "capitulo":
                padre_id = id_actual
                if item.childCount() > 0:
                    antes_de = item.child(0).data(0, ID_ROLE)
            elif tipo_actual == "concepto":
                padre_id = item.parent().data(0, ID_ROLE) if item.parent() else None
                antes_de = id_actual
            # tipo_actual == "" (fila vacía final, ver _on_fila_vacia_editada):
            # ni capitulo ni concepto → cae al default (raíz, al final).

        # Concepto sin insumo_id ya resuelto: pedir uno antes de insertar
        if tipo == "concepto" and insumo_id is None:
            from PySide6.QtWidgets import QDialog
            from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
            dlg = DialogoSeleccionarInsumo(api, parent=self, busqueda_inicial=busqueda_inicial)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            insumo_id = dlg.insumo_seleccionado
            if insumo_id is None:
                return

        nuevo_id = api.agregar_nodo(
            tipo, padre_id=padre_id, antes_de=antes_de, insumo_id=insumo_id,
        )

        edit_col = 6 if tipo == "concepto" else 4

        def _seleccionar_nuevo():
            item = t._buscar_item_por_id(nuevo_id)
            if item:
                t.setCurrentItem(item)
                if t.isColumnHidden(edit_col):
                    t.setColumnHidden(edit_col, False)
                t.editItem(item, edit_col)
        QTimer.singleShot(0, _seleccionar_nuevo)

    # ── Sobrecostos / Indirectos (popup) ──────────────────────────────

    def _on_indirectos(self):
        """Abre popup de indirectos de campo."""
        self._abrir_indirectos_dlg("campo")

    def _on_personal_indirectos(self):
        """Abre popup de indirectos de oficina."""
        self._abrir_indirectos_dlg("oficina")

    def _abrir_indirectos_dlg(self, tipo: str):
        """Construye y muestra el diálogo de indirectos para un tipo ('campo' | 'oficina')."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QTableWidget, QTableWidgetItem, QDoubleSpinBox,
            QAbstractItemView, QHeaderView,
        )
        titulo = "Indirectos de campo" if tipo == "campo" else "Personal en indirectos"
        dlg = QDialog(self)
        dlg.setWindowTitle(titulo)
        dlg.setMinimumSize(750, 480)
        dlg.setModal(True)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # ── Cabecera + duración de obra ──────────────────────────
        hdr_row = QHBoxLayout()
        hdr = QLabel(f"<b>{titulo}</b>")
        hdr.setTextFormat(Qt.TextFormat.RichText)
        hdr_row.addWidget(hdr, 1)
        hdr_row.addSpacing(16)
        lbl_dias = QLabel("Duración obra (días):")
        spin_dias = QDoubleSpinBox()
        spin_dias.setRange(0, 9999)
        spin_dias.setDecimals(0)
        spin_dias.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        duracion_actual = float(self._api.proyecto_leer().get("duracion_obra_dias") or 0)
        spin_dias.setValue(duracion_actual)
        hdr_row.addWidget(lbl_dias)
        hdr_row.addWidget(spin_dias)
        lay.addLayout(hdr_row)

        # ── Tabla ────────────────────────────────────────────────
        COLUMNAS = ["Categoría", "Concepto", "Periodo (días)", "Importe", "% Part.", "Total"]
        datos = self._api.indirectos_lista(tipo)

        tabla = QTableWidget(len(datos), len(COLUMNAS))
        tabla.setHorizontalHeaderLabels(COLUMNAS)
        tabla.verticalHeader().setVisible(False)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setAlternatingRowColors(True)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        def _recalcular_fila(fila):
            """Recalcula el total de una fila según la fórmula de indirectos."""
            periodo = tabla.item(fila, 2)
            importe = tabla.item(fila, 3)
            pct = tabla.item(fila, 4)
            if not (periodo and importe and pct):
                return
            duracion = spin_dias.value()
            p = float(periodo.text() or 0)
            imp = float(importe.text() or 0)
            pc = float(pct.text() or 100)
            total = imp * (duracion / p) * (pc / 100) if p > 0 else imp * (pc / 100)
            tabla.setItem(fila, 5, QTableWidgetItem(f"{total:.2f}"))

        def _recalcular_todas():
            for fila in range(tabla.rowCount()):
                _recalcular_fila(fila)

        def _on_cell_changed(fila, col):
            if col in {1, 2, 3, 4}:
                _recalcular_fila(fila)

        spin_dias.valueChanged.connect(lambda: _recalcular_todas())
        tabla.cellChanged.connect(_on_cell_changed)

        tabla.setColumnCount(len(COLUMNAS) + 1)  # columna oculta para id
        tabla.setColumnHidden(len(COLUMNAS), True)
        for i, reg in enumerate(datos):
            tabla.setItem(i, 0, QTableWidgetItem(reg.get("categoria") or ""))
            tabla.setItem(i, 1, QTableWidgetItem(reg.get("concepto") or ""))
            tabla.setItem(i, 2, QTableWidgetItem(str(reg.get("periodo_dias") or 0)))
            tabla.setItem(i, 3, QTableWidgetItem(str(reg.get("importe") or 0)))
            tabla.setItem(i, 4, QTableWidgetItem(str(reg.get("pct_participacion") or 100)))
            tabla.setItem(i, 5, QTableWidgetItem(f"{reg.get('total') or 0:.2f}"))
            id_item = QTableWidgetItem()
            id_item.setData(Qt.ItemDataRole.UserRole, reg["id"])
            tabla.setItem(i, len(COLUMNAS), id_item)

        tabla.resizeColumnsToContents()
        lay.addWidget(tabla, 1)

        # ── Botones inferiores ───────────────────────────────────
        btn_row = QHBoxLayout()
        btn_plant = QPushButton("Cargar plantilla")
        btn_add = QPushButton("+ Agregar")
        btn_del = QPushButton("− Quitar")
        btn_aplicar = QPushButton("Aplicar a Sobrecostos →")
        btn_aplicar.setToolTip(
            "Calcula el %CI (indirectos ÷ costo directo del proyecto × 100) "
            "y lo traslada a los factores de sobrecosto del presupuesto."
        )
        btn_guardar = QPushButton("Guardar y recalcular")
        btn_guardar.setObjectName("btnPrimario")
        btn_cancelar = QPushButton("Cancelar")
        btn_row.addWidget(btn_plant)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        btn_row.addWidget(btn_aplicar)
        btn_row.addWidget(btn_guardar)
        btn_row.addWidget(btn_cancelar)
        lay.addLayout(btn_row)

        # ── Acciones ─────────────────────────────────────────────
        def cargar_plantilla():
            n = self._api.indirectos_cargar_plantilla(tipo)
            if n:
                self._sb.showMessage(f"Plantilla cargada: {n} ítems nuevos", 4000)
            else:
                self._sb.showMessage("Todos los ítems de la plantilla ya existen", 4000)
            _recargar_tabla()

        def agregar_fila():
            fila = tabla.rowCount()
            tabla.insertRow(fila)
            tabla.setItem(fila, 0, QTableWidgetItem(""))
            tabla.setItem(fila, 1, QTableWidgetItem("Nuevo ítem"))
            tabla.setItem(fila, 2, QTableWidgetItem("0"))
            tabla.setItem(fila, 3, QTableWidgetItem("0"))
            tabla.setItem(fila, 4, QTableWidgetItem("100"))
            tabla.setItem(fila, 5, QTableWidgetItem("0.00"))
            id_item = QTableWidgetItem()
            id_item.setData(Qt.ItemDataRole.UserRole, None)
            tabla.setItem(fila, len(COLUMNAS), id_item)

        def quitar_fila():
            fila = tabla.currentRow()
            if fila < 0:
                return
            id_item = tabla.item(fila, len(COLUMNAS))
            reg_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
            concepto_item = tabla.item(fila, 0)
            concepto = concepto_item.text() if concepto_item else ""
            resp = confirmar(
                dlg, "Eliminar indirecto",
                f"¿Eliminar \"{concepto}\"?" if concepto else "¿Eliminar este indirecto?",
                "Eliminar", destructivo=True,
            )
            if not resp:
                return
            if reg_id is not None:
                self._api.indirectos_eliminar(reg_id)
            tabla.removeRow(fila)

        def _recargar_tabla():
            nonlocal datos
            tabla.blockSignals(True)
            datos = self._api.indirectos_lista(tipo)
            tabla.setRowCount(len(datos))
            for i, reg in enumerate(datos):
                tabla.setItem(i, 0, QTableWidgetItem(reg.get("categoria") or ""))
                tabla.setItem(i, 1, QTableWidgetItem(reg.get("concepto") or ""))
                tabla.setItem(i, 2, QTableWidgetItem(str(reg.get("periodo_dias") or 0)))
                tabla.setItem(i, 3, QTableWidgetItem(str(reg.get("importe") or 0)))
                tabla.setItem(i, 4, QTableWidgetItem(str(reg.get("pct_participacion") or 100)))
                tabla.setItem(i, 5, QTableWidgetItem(f"{reg.get('total') or 0:.2f}"))
                id_item = QTableWidgetItem()
                id_item.setData(Qt.ItemDataRole.UserRole, reg["id"])
                tabla.setItem(i, len(COLUMNAS), id_item)
            tabla.blockSignals(False)

        def guardar():
            tabla.blockSignals(True)
            # Guardar duración de obra al proyecto
            nueva_duracion = int(spin_dias.value())
            self._api.proyecto_guardar({"duracion_obra_dias": nueva_duracion})
            for fila in range(tabla.rowCount()):
                id_item = tabla.item(fila, len(COLUMNAS))
                reg_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
                campos = {
                    "categoria": (tabla.item(fila, 0).text() if tabla.item(fila, 0) else ""),
                    "concepto": (tabla.item(fila, 1).text() if tabla.item(fila, 1) else ""),
                    "periodo_dias": float(tabla.item(fila, 2).text() or 0) if tabla.item(fila, 2) else 0,
                    "importe": float(tabla.item(fila, 3).text() or 0) if tabla.item(fila, 3) else 0,
                    "pct_participacion": float(tabla.item(fila, 4).text() or 100) if tabla.item(fila, 4) else 100,
                }
                if reg_id is not None:
                    self._api.indirectos_guardar(reg_id, campos)
                else:
                    campos["tipo"] = tipo
                    campos["orden"] = fila
                    campos["total"] = 0.0
                    campos["activo"] = 1
                    self._api.indirectos_insertar(campos)
            resultado_totales = self._api.indirectos_calcular_totales()
            # Ya no hace falta un commit manual aquí: tanto
            # proyecto_guardar() (duración de obra) como los métodos de
            # indirectos pasan por DataService, que comitea su propia
            # transacción en cada llamada (ver N1 del seguimiento —
            # proyecto_guardar() se corrigió para dejar de escribir
            # directo vía ProyectoRepo sin pasar por DataService).
            tabla.blockSignals(False)
            dlg.accept()
            afectados = resultado_totales.get("afectados_por_duracion_faltante") or []
            if afectados:
                # Hallazgo 7: antes esto daba total=0 en silencio. Ahora se
                # avisa explícitamente — no se bloquea el guardado (la
                # duración se puede capturar después), solo se informa.
                QMessageBox.warning(
                    self, "Falta la duración de obra",
                    f"{len(afectados)} indirecto(s) tienen un periodo (días) "
                    "definido pero la 'Duración de obra (días)' del proyecto "
                    "está en 0 — su total se calculó como 0.\n\n"
                    "Captura la duración de obra (arriba, en este mismo "
                    "diálogo) y vuelve a guardar para que se calculen bien.",
                )
            else:
                self._sb.showMessage(f"{titulo} guardados", 3000)

        def aplicar_a_sobrecosto():
            """Guarda las filas visibles y traslada el %CI resultante a
            factores_sobrecosto (ver Api.indirectos_aplicar_a_sobrecosto).
            Antes de esto, capturar indirectos aquí no tenía ningún efecto
            sobre el presupuesto final."""
            guardar()  # persiste filas + duración de obra antes de calcular %CI
            try:
                resultado = self._api.indirectos_aplicar_a_sobrecosto()
            except ValueError as e:
                QMessageBox.warning(dlg_parent, "No se pudo aplicar", str(e))
                return
            except Exception as e:
                from frontend.ventana.ui_utils import mostrar_error
                mostrar_error(dlg_parent, "Error al aplicar a sobrecostos", e)
                return
            aviso_duracion = ""
            if resultado.get("afectados_por_duracion_faltante"):
                n = len(resultado["afectados_por_duracion_faltante"])
                aviso_duracion = (
                    f" {n} indirecto(s) dieron total=0 por falta de "
                    "duración de obra — el %CI no los incluye."
                )
            self._sb.showMessage(
                "Indirectos aplicados a sobrecostos: "
                f"campo {resultado['pct_indirectos_campo']:.2f}%, "
                f"oficina {resultado['pct_indirectos_oficina']:.2f}% "
                f"(sobre costo directo de {resultado['costo_directo_total']:.2f})"
                f"{aviso_duracion}",
                8000,
            )


        # dlg_parent: guardar() ya cierra el diálogo (dlg.accept()), así que
        # los QMessageBox posteriores deben colgar de la ventana principal.
        dlg_parent = self

        btn_plant.clicked.connect(cargar_plantilla)
        btn_add.clicked.connect(agregar_fila)
        btn_aplicar.clicked.connect(aplicar_a_sobrecosto)
        btn_del.clicked.connect(quitar_fila)
        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dlg.reject)

        dlg.exec()

    def _on_variables_formula(self):
        """Abre el diálogo de variables de fórmula (N3 del seguimiento).

        Hasta este fix, Api.variables_crear/listar/actualizar/eliminar
        existían y estaban probadas (incluida la corrección del
        Hallazgo 5: borrar una variable reescribe las fórmulas que la
        referencian), pero no había ningún panel conectado a ellas — la
        feature era solo-backend.
        """
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        from backend.formulas import resolver_variables, ErrorFormula

        dlg = QDialog(self)
        dlg.setWindowTitle("Variables de fórmula")
        dlg.setMinimumSize(720, 460)
        dlg.setModal(True)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        hdr = QLabel("<b>Variables de fórmula</b>")
        hdr.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(hdr)
        sub = QLabel(
            "Úsalas por nombre en las fórmulas de cantidad de conceptos y "
            "de componentes APU (ej. \"ancho_muro * altura\")."
        )
        sub.setWordWrap(True)
        lay.addWidget(sub)

        lbl_error = QLabel("")
        lbl_error.setWordWrap(True)
        lbl_error.setStyleSheet("color: #b91c1c;")
        lbl_error.setVisible(False)
        lay.addWidget(lbl_error)

        COLUMNAS = ["Nombre", "Expresión", "Valor", "Descripción"]
        datos = self._api.variables_listar()

        tabla = QTableWidget(len(datos), len(COLUMNAS) + 1)  # +1: columna oculta de id
        tabla.setHorizontalHeaderLabels(COLUMNAS + ["_id"])
        tabla.setColumnHidden(len(COLUMNAS), True)
        tabla.verticalHeader().setVisible(False)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setAlternatingRowColors(True)
        tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        def _fila_valores(fila: int) -> tuple[str, str, str]:
            nombre_item = tabla.item(fila, 0)
            expr_item = tabla.item(fila, 1)
            desc_item = tabla.item(fila, 3)
            nombre = (nombre_item.text() if nombre_item else "").strip()
            expr = (expr_item.text() if expr_item else "").strip()
            desc = (desc_item.text() if desc_item else "").strip()
            return nombre, expr, desc

        def _recalcular_valores():
            """Previsualiza el valor resuelto de cada variable con el
            contenido ACTUAL de la tabla (aún sin guardar) — permite ver
            de inmediato si hay un ciclo o una variable indefinida antes
            de guardar, en vez de enterarse recién al guardar."""
            expresiones = {}
            for fila in range(tabla.rowCount()):
                nombre, expr, _ = _fila_valores(fila)
                if nombre:
                    expresiones[nombre] = expr
            try:
                resueltas = resolver_variables(expresiones)
                error_txt = None
            except ErrorFormula as e:
                resueltas = {}
                error_txt = str(e)

            tabla.blockSignals(True)
            for fila in range(tabla.rowCount()):
                nombre, _, _ = _fila_valores(fila)
                if error_txt:
                    texto = "—"
                elif nombre in resueltas:
                    texto = f"{resueltas[nombre]:g}"
                else:
                    texto = "?"
                item = QTableWidgetItem(texto)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                tabla.setItem(fila, 2, item)
            tabla.blockSignals(False)

            if error_txt:
                lbl_error.setText(error_txt)
                lbl_error.setVisible(True)
            else:
                lbl_error.setVisible(False)

        def _cargar_fila(fila: int, reg: dict):
            tabla.setItem(fila, 0, QTableWidgetItem(reg.get("nombre") or ""))
            tabla.setItem(fila, 1, QTableWidgetItem(reg.get("expresion") or ""))
            valor_item = QTableWidgetItem("")
            valor_item.setFlags(valor_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tabla.setItem(fila, 2, valor_item)
            tabla.setItem(fila, 3, QTableWidgetItem(reg.get("descripcion") or ""))
            id_item = QTableWidgetItem()
            id_item.setData(Qt.ItemDataRole.UserRole, reg.get("id"))
            tabla.setItem(fila, len(COLUMNAS), id_item)

        for i, reg in enumerate(datos):
            _cargar_fila(i, reg)
        tabla.resizeColumnsToContents()
        lay.addWidget(tabla, 1)
        _recalcular_valores()

        def _on_cell_changed(_fila, col):
            if col in (0, 1):  # nombre o expresión cambiaron
                _recalcular_valores()

        tabla.cellChanged.connect(_on_cell_changed)

        # ── Botones ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Agregar")
        btn_del = QPushButton("− Quitar")
        btn_guardar = QPushButton("Guardar")
        btn_guardar.setObjectName("btnPrimario")
        btn_cerrar = QPushButton("Cerrar")
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
        btn_row.addWidget(btn_guardar)
        btn_row.addWidget(btn_cerrar)
        lay.addLayout(btn_row)

        def agregar_fila():
            fila = tabla.rowCount()
            tabla.insertRow(fila)
            tabla.blockSignals(True)
            tabla.setItem(fila, 0, QTableWidgetItem(""))
            tabla.setItem(fila, 1, QTableWidgetItem(""))
            valor_item = QTableWidgetItem("")
            valor_item.setFlags(valor_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tabla.setItem(fila, 2, valor_item)
            tabla.setItem(fila, 3, QTableWidgetItem(""))
            id_item = QTableWidgetItem()
            id_item.setData(Qt.ItemDataRole.UserRole, None)
            tabla.setItem(fila, len(COLUMNAS), id_item)
            tabla.blockSignals(False)
            tabla.setCurrentCell(fila, 0)
            tabla.editItem(tabla.item(fila, 0))

        def quitar_fila():
            fila = tabla.currentRow()
            if fila < 0:
                return
            id_item = tabla.item(fila, len(COLUMNAS))
            reg_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
            nombre, _, _ = _fila_valores(fila)

            if reg_id is None:
                # Fila nueva sin guardar todavía: solo se quita de la tabla.
                tabla.removeRow(fila)
                _recalcular_valores()
                return

            resp = confirmar(
                dlg, "Eliminar variable",
                f"¿Eliminar la variable \"{nombre}\"?\n\n"
                "Si otras fórmulas la usan, se reemplazará por su último "
                "valor conocido antes de eliminarla (no quedarán rotas).",
                "Eliminar", destructivo=True,
            )
            if not resp:
                return
            try:
                resultado = self._api.variables_eliminar(reg_id)
            except Exception as e:
                from frontend.ventana.ui_utils import mostrar_error
                mostrar_error(dlg, "No se pudo eliminar", e)
                return
            tabla.removeRow(fila)
            _recalcular_valores()

            afectados = (
                len(resultado.get("variables", []))
                + len(resultado.get("conceptos", []))
                + len(resultado.get("componentes_apu", []))
            )
            if afectados:
                self._sb.showMessage(
                    f"'{nombre}' eliminada — se actualizaron {afectados} "
                    "fórmula(s) que la usaban.", 6000,
                )
            else:
                self._sb.showMessage(f"'{nombre}' eliminada", 3000)

        def guardar():
            errores = []
            for fila in range(tabla.rowCount()):
                nombre, expr, desc = _fila_valores(fila)
                if not nombre:
                    continue  # fila en blanco, se ignora silenciosamente
                id_item = tabla.item(fila, len(COLUMNAS))
                reg_id = id_item.data(Qt.ItemDataRole.UserRole) if id_item else None
                try:
                    if reg_id is None:
                        nuevo_id = self._api.variables_crear(
                            nombre, expresion=expr, descripcion=desc)
                        id_item.setData(Qt.ItemDataRole.UserRole, nuevo_id)
                    else:
                        self._api.variables_actualizar(
                            reg_id, nombre=nombre, expresion=expr, descripcion=desc)
                except ValueError as e:
                    errores.append(f"• \"{nombre}\": {e}")
                except Exception as e:
                    errores.append(f"• \"{nombre}\": error inesperado — {e}")

            if errores:
                QMessageBox.warning(
                    dlg, "No se pudieron guardar algunas variables",
                    "Se guardó lo demás, pero estas filas tienen problemas "
                    "que hay que corregir:\n\n" + "\n".join(errores),
                )
                _recalcular_valores()
                return  # deja el diálogo abierto para corregir

            self._sb.showMessage("Variables guardadas", 3000)
            dlg.accept()

        btn_add.clicked.connect(agregar_fila)
        btn_del.clicked.connect(quitar_fila)
        btn_guardar.clicked.connect(guardar)
        btn_cerrar.clicked.connect(dlg.reject)

        dlg.exec()

    def _on_sobrecostos(self):
        """Abre popup de cálculo de sobrecostos."""
        if not self._db:
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Cálculo de sobrecostos")
        dlg.setMinimumSize(420, 380)
        dlg.setModal(False)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._build_sobrecostos())
        dlg.exec()


__all__ = [
    "HandlersMixin",
]
