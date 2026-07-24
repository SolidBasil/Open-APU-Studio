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
    QMessageBox, QFileDialog, QMenu,
)

from frontend.ventana.mixins.paneles import INSUMOS_TITLES
from frontend.ventana.iconos import icono


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
        if item.childCount() > 0:
            return
        if not self._db:
            return
        self._focus_or_open_tab(item.text(0), temporary=True)

    def _on_sidebar_double_click(self, item, column):
        """Doble click en sidebar: abre pestaña permanente."""
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
        """Handler del botón 'Generadores' en la toolbar (pestaña INICIO)."""
        self._focus_or_open_tab("Generadores de obra", temporary=False)

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
        elif title == "Generadores de obra":
            content = self._build_generadores()
            self.poblar_generadores()
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

    def _on_tab_changed(self, idx):
        """Re-aplica el filtro de búsqueda al cambiar de pestaña."""
        self._on_search(self._search_input.text())

        title = self._tabs.tabText(idx) if idx >= 0 else ""
        es_generadores = title == "Generadores de obra"

        # Panel izquierdo contextual
        if hasattr(self, "_left_stack"):
            splitter = self._left_stack.parent()
            prev = self._left_stack.currentIndex()
            if es_generadores:
                if prev == 0 and splitter is not None:
                    self._sidebar_splitter_size = splitter.sizes()
                self._left_stack.setCurrentIndex(1)
                if splitter is not None and hasattr(self, '_gen_splitter_size'):
                    splitter.setSizes(self._gen_splitter_size)
                elif splitter is not None:
                    s = splitter.sizes()
                    gen_left = int(s[0] * 1.2)  # 20% más que sidebar actual
                    splitter.setSizes([gen_left, s[1] - (gen_left - s[0])])
                self.poblar_generadores()
                if self._gen_seleccionado and self._api and hasattr(self, "_gen_tabla"):
                    renglones = self._api.generador_renglones(self._gen_seleccionado)
                    self._gen_tabla.poblar(renglones)
            else:
                if prev == 1 and splitter is not None:
                    self._gen_splitter_size = splitter.sizes()
                self._left_stack.setCurrentIndex(0)
                if splitter is not None and hasattr(self, '_sidebar_splitter_size'):
                    splitter.setSizes(self._sidebar_splitter_size)

        # ponytail: auto-switch ribbon según pestaña de contenido activa
        ribbon_objetivo = None
        if es_generadores:
            ribbon_objetivo = "GENERADORES"
        elif title == "Fuera de presupuesto":
            ribbon_objetivo = "PRINCIPAL"
        elif title == "Presupuesto programable":
            ribbon_objetivo = "PRINCIPAL"
        if ribbon_objetivo and getattr(self, "_tab_activa", None) != ribbon_objetivo:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda r=ribbon_objetivo: self._switch_tab(r))

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
                    orden_nuevo = repo.proximo_orden(proyecto_id, padre_id)
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
            resp = QMessageBox.question(
                self, "Eliminar insumos",
                f"¿Eliminar {len(ids)} insumo(s) del catálogo?\n"
                "Los insumos se desactivarán y no aparecerán en el presupuesto.",
            )
            if resp != QMessageBox.StandardButton.Yes:
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
            resp = QMessageBox.question(
                self, "Eliminar elementos",
                f"¿Eliminar {len(nodos)} elemento(s) del presupuesto?\n"
                "Se desactivarán y los totales se recalcularán.",
            )
            if resp != QMessageBox.StandardButton.Yes:
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

    def _agregar_nodo(self, tipo: str):
        """Inserta un nodo del tipo dado en el presupuesto.

        - Capítulo: se inserta directo.
        - Concepto: abre selector de insumo; si se cancela (Esc), no inserta nada.

        Contexto del árbol al momento de insertar:
          - Capítulo seleccionado → hijo, arriba del primero
          - Concepto seleccionado → hermano, arriba de él
          - Nada seleccionado → nodo raíz, al final

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

        # Concepto: pedir insumo antes de insertar
        insumo_id = None
        if tipo == "concepto":
            from PySide6.QtWidgets import QDialog
            from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
            dlg = DialogoSeleccionarInsumo(api, parent=self)
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
        duracion_actual = float(self._api._conn.execute(
            "SELECT COALESCE(duracion_obra_dias, 0) FROM proyectos WHERE id = ?",
            (self._api._pid,)
        ).fetchone()[0])
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
        btn_guardar = QPushButton("Guardar y recalcular")
        btn_guardar.setObjectName("btnPrimario")
        btn_cancelar = QPushButton("Cancelar")
        btn_row.addWidget(btn_plant)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_del)
        btn_row.addStretch()
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
            self._api._conn.execute(
                "UPDATE proyectos SET duracion_obra_dias = ? WHERE id = ?",
                (nueva_duracion, self._api._pid)
            )
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
            self._api.indirectos_calcular_totales()
            self._conn.commit()
            tabla.blockSignals(False)
            dlg.accept()
            self._sb.showMessage(f"{titulo} guardados", 3000)

        btn_plant.clicked.connect(cargar_plantilla)
        btn_add.clicked.connect(agregar_fila)
        btn_del.clicked.connect(quitar_fila)
        btn_guardar.clicked.connect(guardar)
        btn_cancelar.clicked.connect(dlg.reject)

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
