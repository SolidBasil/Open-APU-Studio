"""
handlers/
=========
Paquete de handlers de eventos para VentanaPrincipal.

Contiene toolbar actions, navegación, búsqueda, pestañas,
adjuntos y vista (HandlersMixin). Los submódulos manejan:
    gestion_proyectos.py — lifecycle de proyectos
    informes.py          — generación de PDF
    diag_dialogs.py      — diagnóstico y utilidades
"""

from pathlib           import Path
from PySide6.QtCore    import Qt, QPoint
from PySide6.QtGui     import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QAbstractItemView,
    QInputDialog, QMessageBox, QFileDialog, QMenu,
)

from .gestion_proyectos import GestionProyectosMixin
from .informes          import InformesMixin
from .diag_dialogs      import DiagDialogsMixin


class HandlersMixin:
    """Mixin de handlers — se mezcla en VentanaPrincipal.

    Nota: `self` siempre es la instancia de VentanaPrincipal.
    Los atributos como self._db, self._api, self._tabs, self._sb
    se definen en VentanaPrincipal.__init__ o en otros mixins.
    """

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
        for i in range(self._tabs.count()):
            if "Presupuesto" in self._tabs.tabText(i):
                self._cerrar_tab_widget(i)
                break
        new_widget = self._build_presupuesto()
        self._tabs.insertTab(0, new_widget, "📋 Presupuesto programable")
        self._tabs.setCurrentIndex(0)

    def _on_copy_toolbar(self):
        """Delega copia al widget activo en la pestaña actual."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "copy_selection"):
            widget.copy_selection()

    def _on_select_all_toolbar(self):
        """Selecciona todas las filas visibles del widget activo."""
        from frontend.ventana.widgets.base import TreeTableWidget
        tab = self._tabs.currentWidget()
        if tab is None:
            return
        if isinstance(tab, TreeTableWidget):
            tab.selectAll()
            return
        tree = tab.findChild(TreeTableWidget)
        if tree is not None:
            tree.selectAll()

    def _on_modificar_toolbar(self):
        """Activa edición en la celda actual (equivalente a F2)."""
        from frontend.ventana.widgets.base import TreeTableWidget
        tab = self._tabs.currentWidget()
        if tab is None:
            return
        tree = tab if isinstance(tab, TreeTableWidget) else tab.findChild(TreeTableWidget)
        if tree is None:
            return
        idx = tree.currentIndex()
        if idx.isValid():
            tree.edit(idx)

    def _on_desglozar_toolbar(self):
        """Abre APU del ítem seleccionado (equivalente a doble clic en P.U.)."""
        from frontend.ventana.widgets.base import TreeTableWidget
        from frontend.ventana.widgets.arbol import ID_ROLE
        tab = self._tabs.currentWidget()
        if tab is None:
            return
        tree = tab if isinstance(tab, TreeTableWidget) else tab.findChild(TreeTableWidget)
        if tree is None:
            return
        item = tree.currentItem()
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

    def _on_sidebar_click(self, item, column):
        """Click simple en sidebar: abre pestaña temporal o enfoca si ya existe."""
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
        """Doble click en sidebar: abre pestaña permanente."""
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
        """Abre pestaña según título del sidebar."""
        if self._tab_temp is not None:
            idx = self._tabs.indexOf(self._tab_temp)
            if idx >= 0:
                self._cerrar_tab_widget(idx)
            self._tab_temp = None

        insumos_titles = {
            "📚 Todos", "📐 Conceptos", "🧱 Materiales", "👷 Mano de obra",
            "🔧 Herramienta", "🚜 Equipo", "⚙️ Auxiliares",
            "🧮 Matrices", "🚛 Fletes", "🏗️ Trabajos",
        }
        if title == "📋 Presupuesto programable":
            content = self._build_presupuesto()
        elif title == "🔍 Buscar partidas":
            content = self._build_buscador_partidas()
        elif title == "💰 Cálculo de indirectos":
            content = self._build_placeholder(title, "En desarrollo")
        elif title == "📊 Cálculo de sobrecostos":
            content = self._build_sobrecostos()
        elif title == "📦 Explosión de insumos":
            content = self._build_explosion()
            if content is None:
                return
        elif title == "📦 Explosión de matrices":
            content = self._build_matriz_explosion()
            if content is None:
                return
        elif title in insumos_titles:
            content = self._build_insumos(title)
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
        from frontend.ventana.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if isinstance(w, TreeTableWidget):
            w.filter_rows(text)
            return
        tree = w.findChild(TreeTableWidget) if w else None
        if tree is not None:
            tree.filter_rows(text)

    def _on_tab_changed(self, idx):
        """Re-aplica el filtro de búsqueda al cambiar de pestaña."""
        self._on_search(self._search_input.text())

    # ── Adjuntar / Ver adjuntos ───────────────────────────────────────────

    def _on_adjuntar_archivo(self):
        from PySide6.QtWidgets import QMessageBox
        from backend.database.db import Rutas
        import shutil

        if not self._db or not self._db.db_path:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
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

        if not self._db:
            QMessageBox.information(self, "Sin proyecto",
                                    "Abre un proyecto primero.")
            return

        adj_dir = Rutas.proyectos() / f"{Path(self._db.db_path).stem}_adjuntos"
        if not adj_dir.is_dir():
            QMessageBox.information(self, "Sin adjuntos",
                                    "Este proyecto no tiene archivos adjuntos.")
            return

        archivos = sorted(adj_dir.iterdir())
        if not archivos:
            QMessageBox.information(self, "Sin adjuntos",
                                    "La carpeta de adjuntos está vacía.")
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
            r = QMessageBox.question(
                dlg, "Confirmar",
                f"¿Eliminar '{Path(item.data(1)).name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
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
        """Alterna entre pantalla completa y normal."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()


__all__ = [
    "HandlersMixin",
    "GestionProyectosMixin",
    "InformesMixin",
    "DiagDialogsMixin",
]
