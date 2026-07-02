"""
handlers.py
===========
Mixin de handlers de eventos para VentanaPrincipal.

Contiene todos los manejadores de acciones del usuario:
gestión de proyectos, importación OPUS, acciones de toolbar,
navegación de pestañas, búsqueda y barra de estado.
"""

from pathlib           import Path
from PySide6.QtCore    import Qt
from PySide6.QtGui     import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QAbstractItemView,
    QInputDialog, QMessageBox, QFileDialog, QMenu,
)


class HandlersMixin:
    """Mixin de handlers — se mezcla en VentanaPrincipal.

    Nota: `self` siempre es la instancia de VentanaPrincipal.
    Los atributos como self._db, self._api, self._tabs, self._sb
    se definen en VentanaPrincipal.__init__ o en otros mixins.
    """

    # ── Gestión de proyectos (Abrir / Cerrar / Duplicar / Eliminar) ─────

    def eventFilter(self, obj, event):
        """Captura clics en el placeholder 'Sin proyecto' para abrir el ProjectDialog."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            self._on_abrir_proyecto()
            return True
        return super().eventFilter(obj, event)

    def _on_abrir_proyecto(self):
        """Selecciona y abre un proyecto .db existente.
        Cierra el proyecto actual si hay uno abierto, recarga el presupuesto
        y cambia a la pestaña PRINCIPAL con la toolbar completa.
        """
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.database.db import Database, Rutas
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Abrir proyecto",
                                    "No hay proyectos guardados.")
            return
        dlg = ProjectDialog(proyectos, "Abrir proyecto", "Abrir", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre = dlg.proyecto_seleccionado
        if not nombre:
            return
        db_path = Rutas.db_proyecto(nombre)
        if not db_path.exists():
            return
        try:
            if self._db:
                Database.cerrar()
            self._db = Database.abrir(db_path)
            from frontend.ventana.api import Api
            self._api = Api(self._db.conn, self._db.db_path)
            self._reload_presupuesto()
            self._update_statusbar()
            self._switch_tab("PRINCIPAL")
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error al abrir proyecto", str(e))

    def _on_cerrar_proyecto(self):
        """Cierra el proyecto actual con confirmación."""
        if not self._db:
            return
        from PySide6.QtWidgets import QMessageBox
        from backend.database.db import Database

        msg = QMessageBox(self)
        msg.setWindowTitle("Cerrar proyecto")
        msg.setText("¿Cerrar el proyecto actual?")
        msg.setInformativeText("Los datos no guardados se perderán.")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        btn_ok = msg.addButton("Cerrar", QMessageBox.ButtonRole.AcceptRole)
        msg.setDefaultButton(btn_ok)
        msg.exec()
        if msg.clickedButton() != btn_ok:
            return

        Database.cerrar()
        self._db = None
        self._api = None
        for i in range(self._tabs.count() - 1, -1, -1):
            self._tabs.removeTab(i)
        self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")
        self._sb.showMessage("Proyecto cerrado", 3000)

    def _on_copiar_proyecto(self):
        """Duplica un proyecto existente: selecciona origen, asigna nombre, copia .db."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox
        from backend.database.db import Rutas
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Duplicar proyecto",
                                    "No hay proyectos guardados.")
            return
        actual = Path(self._db.db_path).stem if self._db and self._db.db_path else None
        dlg = ProjectDialog(proyectos, "Duplicar proyecto", "Duplicar",
                            accion_color="#5B8A72", seleccionado=actual,
                            parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        source_name = dlg.proyecto_seleccionado
        if not source_name:
            return
        original = Rutas.db_proyecto(source_name)
        name, ok = QInputDialog.getText(
            self, "Duplicar proyecto",
            "Nombre para la copia:",
            text=source_name + "_copia",
        )
        if not ok or not name.strip():
            return
        dest = Rutas.db_proyecto(name.strip())
        if dest.exists():
            QMessageBox.warning(self, "Ya existe",
                                f"'{dest.name}' ya existe.")
            return
        import shutil
        shutil.copy2(original, dest)
        self._sb.showMessage(f"Duplicado como '{dest.name}'", 4000)

    def _on_renombrar_proyecto(self):
        """Renombra un proyecto .db: selecciona, escribe nuevo nombre, renombra archivo."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox
        from backend.database.db import Rutas, Database
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Renombrar proyecto",
                                    "No hay proyectos guardados.")
            return
        dlg = ProjectDialog(proyectos, "Renombrar proyecto", "Renombrar",
                            accion_color="#D5B39B", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        source_name = dlg.proyecto_seleccionado
        if not source_name:
            return

        name, ok = QInputDialog.getText(
            self, "Renombrar proyecto",
            "Nuevo nombre:",
            text=source_name,
        )
        if not ok or not name.strip() or name.strip() == source_name:
            return
        name = name.strip()
        dest = Rutas.db_proyecto(name)
        if dest.exists():
            QMessageBox.warning(self, "Ya existe",
                                f"'{name}' ya existe.")
            return

        original = Rutas.db_proyecto(source_name)
        if self._db and self._db.db_path and Path(self._db.db_path).resolve() == original.resolve():
            Database.cerrar()
            self._db = Database.abrir(dest)
            from frontend.ventana.api import Api
            self._api = Api(self._db.conn, self._db.db_path)
            self._update_statusbar()

        original.rename(dest)
        self._sb.showMessage(f"Renombrado a '{name}'", 4000)

    def _on_eliminar_proyecto(self):
        """Elimina permanentemente un proyecto .db con doble confirmación."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.database.db import Rutas, Database
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            QMessageBox.information(self, "Eliminar proyecto",
                                    "No hay proyectos guardados.")
            return
        dlg = ProjectDialog(proyectos, "Eliminar proyecto", "Eliminar",
                            accion_color="#A06A6A", parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        nombre = dlg.proyecto_seleccionado
        if not nombre:
            return
        ruta = Rutas.db_proyecto(nombre)

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirmar eliminación")
        msg.setText(f"¿Eliminar permanentemente '{nombre}'?")
        msg.setInformativeText("Esta acción no se puede deshacer.")
        msg.setIcon(QMessageBox.Icon.Warning)
        btn_ok = msg.addButton("Eliminar", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg.exec()
        if msg.clickedButton() != btn_ok:
            return

        if self._db and self._db.db_path and Path(self._db.db_path).resolve() == ruta.resolve():
            Database.cerrar()
            self._db = None
            self._api = None
            for i in range(self._tabs.count() - 1, -1, -1):
                self._tabs.removeTab(i)
            self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")
        ruta.unlink()
        self._sb.showMessage(f"'{nombre}' eliminado", 4000)

    # ── Importación OPUS ──────────────────────────────────────────────────
    # Importa proyectos completos desde formato OPUS 2010 (archivos .DBF).
    # Convierte jerarquía, insumos, APU y auxiliares a SQLite.

    def _on_importar_opus(self):
        """Flujo completo de importación OPUS:
        1. Seleccionar carpeta con archivos .DBF
        2. Si ya existe .db, pregunta: renombrar anterior o sobrescribir
        3. Ejecuta importar() que lee DBF y escribe el SQLite
        4. Abre el proyecto recién importado y recarga el presupuesto
        """
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.database.db import Config, Database, Rutas
        from backend.importar.importar import importar

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
            from frontend.ventana.api import Api
            self._api = Api(self._db.conn, self._db.db_path)
            print(f"[import] {nombre}: nodos={result['nodos']}, insumos={result['insumos']}, "
                  f"apu_matrices={result['apu_matrices']}, apu_resumen_totales={result['apu_resumen_totales']}, "
                  f"insumos_compuestos={result['insumos_compuestos']}")
            QMessageBox.information(self, "Importación exitosa",
                                    f"'{nombre}' importado correctamente.")
            self._reload_presupuesto()
            self._switch_tab("PRINCIPAL")
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

    def _on_select_all_toolbar(self):
        """Selecciona todas las filas visibles del widget activo.
        Busca el TreeTableWidget dentro del widget de la pestaña actual,
        ya que currentWidget() puede ser un contenedor (QWidget wrapper).
        """
        from frontend.ventana.widgets.base import TreeTableWidget
        tab = self._tabs.currentWidget()
        if tab is None:
            return
        # Si la pestaña ES directamente el TreeTableWidget
        if isinstance(tab, TreeTableWidget):
            tab.selectAll()
            return
        # Si la pestaña CONTIENE un TreeTableWidget (wrapper como PestañaExplosion)
        tree = tab.findChild(TreeTableWidget)
        if tree is not None:
            tree.selectAll()

    # ── Desplegar (Primer nivel / Resumen / Todo / Nivel) ────────────────
    # Controla la expansión y colapso del árbol del presupuesto activo.
    # Primer nivel: solo raíces. Resumen: solo agrupadores. Todo: expande completo. Nivel: hasta N.

    def _on_desplegar_primer_nivel(self):
        """Colapsa el árbol del widget activo mostrando solo las raíces."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_primer_nivel"):
            widget.show_primer_nivel()

    def _on_desplegar_resumen(self):
        """Colapsa el árbol mostrando solo los agrupadores (partidas), ocultando hojas."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_solo_agrupadores"):
            widget.show_solo_agrupadores()

    def _on_desplegar_todo(self):
        """Expande completamente el árbol del widget activo."""
        widget = self._tabs.currentWidget()
        if widget and hasattr(widget, "show_todo"):
            widget.show_todo()

    def _on_desplegar_nivel(self):
        """Menú contextual para elegir profundidad de expansión.
        Nivel 1 = solo raíces (collapseAll), Nivel 2 = raíces expandidas, etc.
        Convención 1-based para que sea intuitivo para el usuario.
        """
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
        # Mostrar el menú justo debajo del botón que lo invocó
        btn = self.sender()
        if btn:
            menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        else:
            menu.exec(QPoint(
                self._tb.mapToGlobal(self._tb.rect().topLeft()).x(),
                self._tb.mapToGlobal(self._tb.rect().bottomLeft()).y(),
            ))

    # ── Placeholder ───────────────────────────────────────────────────────
    # Widget genérico para secciones no implementadas aún (MVP).
    # Muestra icono, título y mensaje "no implementado" de forma visual.

    def _build_placeholder(self, title, msg="Esta sección aún no ha sido implementada."):
        """Widget placeholder con icono 🚧 + título + mensaje para secciones no implementadas."""
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
    # Gestiona la interacción con el sidebar: click simple (pestaña temporal),
    # doble click (permanente). También atajos de teclado Ctrl+Tab.

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
        """Doble click en sidebar: abre pestaña permanente y elimina el estado temporal si existía."""
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
        """Abre pestaña según título del sidebar (presupuesto, conceptos, explosión, insumos). Reemplaza temporal anterior si existe."""
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
            content = self._build_placeholder(title, "En desarrollo")
        elif title == "📊 Cálculo de sobrecostos":
            content = self._build_sobrecostos()
        elif title == "📦 Explosión de insumos":
            content = self._build_explosion()
            if content is None:
                return   # usuario canceló el diálogo
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
        if temporary:
            self._tab_temp = content

    def _next_tab(self):
        """Avanza a la siguiente pestaña cíclicamente."""
        self._tabs.setCurrentIndex((self._tabs.currentIndex() + 1) % self._tabs.count())

    def _prev_tab(self):
        """Retrocede a la pestaña anterior cíclicamente."""
        self._tabs.setCurrentIndex((self._tabs.currentIndex() - 1) % self._tabs.count())

    def _on_tab_close(self, idx):
        """Cierra la pestaña en el índice dado; limpia referencia temporal si corresponde."""
        widget = self._tabs.widget(idx)
        if widget is self._tab_temp:
            self._tab_temp = None
        self._tabs.removeTab(idx)

    # ── Búsqueda ──────────────────────────────────────────────────────────
    # Filtro en tiempo real sobre el TreeTableWidget activo.
    # Se re-ejecuta al escribir o al cambiar de pestaña.

    def _on_search(self, text):
        """Filtra filas del TreeTableWidget activo aplicando el texto de búsqueda."""
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

    # ── Adjuntar archivo ───────────────────────────────────────────────────

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

    # ── Ver adjuntos ───────────────────────────────────────────────────────

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
            item.setData(1, str(f))  # ponytail: store path as user role
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

    # ── Depurar catálogos ──────────────────────────────────────────────────

    def _on_recalcular(self):
        """Recalcula en cascada todo el presupuesto: costo de insumos
        compuestos → totales de conceptos → totales de capítulos.
        """
        from PySide6.QtWidgets import QMessageBox

        if not self._db or not self._api:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        try:
            resultado = self._api.recalcular_proyecto()
        except Exception as e:
            QMessageBox.critical(self, "Error al recalcular", str(e))
            return

        self._reload_presupuesto()
        n_iter = resultado.get("iteraciones_compuestos", 0)
        self._sb.showMessage(f"Presupuesto recalculado ({n_iter} iteración(es))", 4000)

    def _on_depurar_catalogos(self):
        from PySide6.QtWidgets import QMessageBox, QWidget, QVBoxLayout, QLabel, QAbstractItemView, QHeaderView
        from frontend.ventana.widgets.base import TreeTableWidget

        if not self._db:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        conn = self._db.conn
        from frontend.ventana.widgets.insumos import TIPO_NOMBRE

        def _tipo_str(tipo_id):
            return TIPO_NOMBRE.get(tipo_id, "")

        grupos = {}

        def _ins(item_id, clave, desc, tipo, origen):
            """Agrega un item a su grupo."""
            grupos.setdefault(origen, []).append({
                "id": item_id, "clave": clave, "desc": desc,
                "tipo": tipo, "origen": origen,
            })

        def _id_tipo(origen, item_id):
            """Resuelve el tipo display para un item según su origen."""
            if origen == "concepto":
                return "📄 Concepto"
            if item_id is None:
                return ""
            return _tipo_str(item_id)

        # Insumos sin uso
        filas = conn.execute("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id
            FROM insumos i
            WHERE i.proyecto_id = 1 AND i.activo = 1
              AND NOT EXISTS (SELECT 1 FROM apu_matrices am WHERE am.insumo_id = i.id)
            ORDER BY i.id
        """).fetchall()
        for r in filas:
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Insumos sin uso")

        # Conceptos sin APU
        filas = conn.execute("""
            SELECT ep.id, CAST(ep.id AS TEXT) AS clave, ep.descripcion
            FROM estructura_presupuesto ep
            WHERE ep.proyecto_id = 1 AND ep.tipo = 'concepto' AND ep.activo = 1
              AND NOT EXISTS (SELECT 1 FROM apu_matrices am WHERE am.matriz_id = ep.id)
            ORDER BY ep.wbs
        """).fetchall()
        for r in filas:
            _ins(r["id"], r["clave"], r["descripcion"],
                 "📄 Concepto", "Conceptos sin APU")

        # Descripciones duplicadas — detectadas por hash, no por clave_opus.
        # clave_opus ya no es UNIQUE (es solo referencial), así que la
        # verdadera fuente de duplicados es el hash de descripción normalizada.
        filas = conn.execute("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id
            FROM insumos i
            WHERE i.proyecto_id = 1 AND i.activo = 1
              AND i.hash IN (
                  SELECT hash FROM insumos
                  WHERE proyecto_id = 1 AND activo = 1 AND hash IS NOT NULL
                  GROUP BY hash HAVING COUNT(*) > 1
              )
            ORDER BY i.hash, i.id
        """).fetchall()
        for r in filas:
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Descripciones duplicadas (insumos)")

        # Costos en cero
        filas = conn.execute("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, i.tipo_id
            FROM insumos i
            WHERE i.proyecto_id = 1 AND i.activo = 1
              AND (i.costo_final IS NULL OR i.costo_final = 0)
            ORDER BY i.id
        """).fetchall()
        for r in filas:
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Costos en cero")

        # Descripción vacía
        filas = conn.execute("""
            SELECT i.id, i.clave_opus AS clave, i.tipo_id, 'insumo' AS src
            FROM insumos i
            WHERE i.proyecto_id = 1 AND i.activo = 1
              AND (i.descripcion IS NULL OR i.descripcion = '')
            UNION ALL
            SELECT ep.id, CAST(ep.id AS TEXT), NULL, 'concepto'
            FROM estructura_presupuesto ep
            WHERE ep.proyecto_id = 1 AND ep.activo = 1 AND ep.tipo = 'concepto'
              AND (ep.descripcion IS NULL OR ep.descripcion = '')
            ORDER BY 2
        """).fetchall()
        for r in filas:
            _ins(r["id"], r["clave"], "",
                 _tipo_str(r["tipo_id"]) if r["tipo_id"] else "📄 Concepto",
                 "Descripción vacía")

        # Auto-referencia
        filas = conn.execute("""
            SELECT i.id, i.clave_opus AS clave, i.descripcion, t.id AS tipo_id
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE i.es_compuesto = 1
              AND i.proyecto_id = 1 AND i.activo = 1
              AND EXISTS (
                SELECT 1 FROM apu_matrices ac
                WHERE ac.matriz_id = i.id
                  AND ac.insumo_id = i.id
                  AND NOT EXISTS (
                    SELECT 1 FROM estructura_presupuesto ep
                    WHERE ep.id = ac.matriz_id AND ep.activo = 1
                  )
              )
            ORDER BY i.id
        """).fetchall()
        for r in filas:
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Auto-referencia (circular)")

        total = sum(len(v) for v in grupos.values())
        if not total:
            QMessageBox.information(self, "Catálogo limpio",
                                    "No se encontraron inconsistencias.")
            return

        # ── Construir árbol ────────────────────────────────────────────

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        lbl = QLabel(f"<b>Diagnóstico del catálogo</b> — {total} incidencias")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)

        tree = TreeTableWidget(["Problema", "Clave", "Descripción", "Tipo"])
        tree.setAlternatingRowColors(True)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        for nombre_grupo, items in grupos.items():
            padre = tree.add_row(
                [f"▶ {nombre_grupo} ({len(items)})", "", "", ""],
                editable=False)
            for item in items:
                tree.add_row(
                    ["", item["clave"], item["desc"], item["tipo"]],
                    parent=padre, editable=False)
            padre.setExpanded(True)

        tree.set_column_modes({
            0: (QHeaderView.ResizeMode.ResizeToContents, None),
            1: (QHeaderView.ResizeMode.ResizeToContents, None),
            2: (QHeaderView.ResizeMode.Stretch, 300),
            3: (QHeaderView.ResizeMode.ResizeToContents, None),
        })
        layout.addWidget(tree)

        title = f"🔧 Depurar catálogos ({total})"
        self._tabs.addTab(w, title)
        self._tabs.setCurrentWidget(w)

    # ── Homologar hash ───────────────────────────────────────────────────

    def _on_homologar_hash(self):
        from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
        from backend.database.core import generar_hash

        if not self._db:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        conn = self._db.conn
        cambios = []

        # Insumos con hash faltante o desactualizado
        filas = conn.execute("""
            SELECT id, descripcion, hash FROM insumos
            WHERE proyecto_id = 1 AND activo = 1
              AND descripcion IS NOT NULL AND descripcion != ''
            ORDER BY id
        """).fetchall()
        for r in filas:
            try:
                h = generar_hash(r["descripcion"])
            except ValueError:
                continue
            if not r["hash"] or r["hash"] != h:
                cambios.append((r["id"], r["descripcion"], r["hash"] or "", h))

        if not cambios:
            QMessageBox.information(self, "Hash normalizados",
                                    "Todos los insumos tienen su hash correcto.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Homologar hash ({len(cambios)} cambios)")
        dlg.setMinimumSize(700, 400)
        layout = QVBoxLayout(dlg)

        lbl = QLabel(
            f"Se encontraron <b>{len(cambios)}</b> insumos con hash faltante o desactualizado. "
            "Revisa los cambios propuestos antes de aplicar."
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        cols = ["ID", "Descripción", "Hash actual", "Hash nuevo"]
        tabla = QTableWidget(len(cambios), 4)
        tabla.setHorizontalHeaderLabels(cols)
        tabla.horizontalHeader().setStretchLastSection(True)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.verticalHeader().setVisible(False)
        for i, (id_, desc, old, new) in enumerate(cambios):
            tabla.setItem(i, 0, QTableWidgetItem(str(id_)))
            tabla.setItem(i, 1, QTableWidgetItem(desc))
            tabla.setItem(i, 2, QTableWidgetItem(old or "—"))
            tabla.setItem(i, 3, QTableWidgetItem(new))
        tabla.resizeColumnsToContents()
        layout.addWidget(tabla)

        # Verificar colisiones entre los nuevos hashes
        colisiones = {}
        for id_, _, _, h in cambios:
            colisiones.setdefault(h, []).append(id_)
        colisiones = {h: ids for h, ids in colisiones.items() if len(ids) > 1}
        if colisiones:
            msgs = []
            for h, ids in colisiones.items():
                msgs.append(f"<b>{h}</b> → IDs {ids}")
            warn = QLabel(
                f"<b style='color:#A06A6A;'>⚠ Colisiones detectadas:</b><br>"
                + "<br>".join(msgs)
            )
            warn.setTextFormat(Qt.TextFormat.RichText)
            warn.setWordWrap(True)
            layout.addWidget(warn)

        row = QHBoxLayout()
        btn_aplicar = QPushButton("Aplicar cambios")
        btn_cancel  = QPushButton("Cancelar")
        row.addStretch()
        row.addWidget(btn_aplicar)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        def aplicar():
            cur = conn.cursor()
            for id_, _, _, h in cambios:
                cur.execute("UPDATE insumos SET hash = ? WHERE id = ?", (h, id_))
            conn.commit()
            self._sb.showMessage(f"Homologados {len(cambios)} hashes", 4000)
            dlg.accept()

        btn_aplicar.clicked.connect(aplicar)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    # ── Calculadora ────────────────────────────────────────────────────────

    def _on_calculadora(self):
        import subprocess, sys
        if sys.platform == "win32":
            subprocess.Popen(["calc.exe"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Calculator"])
        else:
            subprocess.Popen(["gnome-calculator"])

    # ── VISTA handlers ─────────────────────────────────────────────────────
    # Ajustar columnas, mostrar/ocultar, formato, restablecer,
    # pantalla completa y filtro avanzado — todos operan sobre el
    # TreeTableWidget activo en la pestaña actual.

    def _get_active_table(self):
        """Retorna el TreeTableWidget activo o None."""
        from frontend.ventana.widgets.base import TreeTableWidget
        w = self._tabs.currentWidget()
        if isinstance(w, TreeTableWidget):
            return w
        return w.findChild(TreeTableWidget) if w else None

    def _on_ajustar_columnas(self):
        """Auto-ajusta ancho de columnas al contenido."""
        from PySide6.QtWidgets import QHeaderView
        t = self._get_active_table()
        if not t:
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

    # ── INICIO handlers ────────────────────────────────────────────────────

    def _on_info_proyecto(self):
        """Muestra información general del proyecto actual."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from pathlib import Path

        if not self._db:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        conn = self._db.conn
        nombre = Path(self._db.db_path).stem
        n_nodos = conn.execute(
            "SELECT COUNT(*) FROM estructura_presupuesto WHERE activo = 1"
        ).fetchone()[0]
        n_conceptos = conn.execute(
            "SELECT COUNT(*) FROM estructura_presupuesto WHERE tipo = 'concepto' AND activo = 1"
        ).fetchone()[0]
        n_insumos = conn.execute(
            "SELECT COUNT(*) FROM insumos WHERE activo = 1"
        ).fetchone()[0]
        n_matrices = conn.execute(
            "SELECT COUNT(*) FROM apu_matrices"
        ).fetchone()[0]

        dlg = QDialog(self)
        dlg.setWindowTitle("Información del proyecto")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg)

        filas = [
            ("Nombre", nombre),
            ("Nodos en presupuesto", str(n_nodos)),
            ("Conceptos", str(n_conceptos)),
            ("Insumos en catálogo", str(n_insumos)),
            ("Matrices APU", str(n_matrices)),
        ]
        for label, valor in filas:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{label}:</b>"))
            row.addWidget(QLabel(valor))
            row.addStretch()
            layout.addLayout(row)

        layout.addSpacing(12)
        btn = QPushButton("Cerrar")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        dlg.exec()

    # ── INFORMES handlers ───────────────────────────────────────────────────

    def _on_generar_presupuesto(self):
        """Genera .tex y .pdf del presupuesto en la carpeta de reportes del usuario."""
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from backend.exportar.informe_pdf.latex import ReportePresupuesto, compilar_pdf
        from backend.database.db import Rutas
        from pathlib import Path

        if not self._api:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        nombre = Path(self._db.db_path).stem
        nodos = self._api.presupuesto_arbol()
        if not nodos:
            QMessageBox.information(self, "Sin datos", "El presupuesto está vacío.")
            return

        tex_path = Rutas.reportes() / f"{nombre}_presupuesto.tex"
        ReportePresupuesto(nombre, nodos).generar(tex_path)

        pdf = compilar_pdf(tex_path)
        if pdf:
            self._sb.showMessage(f"PDF generado: {pdf}", 5000)
            QDesktopServices.openUrl(QUrl.fromLocalFile(pdf))
        else:
            self._sb.showMessage(f"Reporte .tex generado: {tex_path}", 5000)

    def _on_compilar_pdf(self):
        """Compila el .tex seleccionado a PDF con pdflatex."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.exportar.informe_pdf.latex import compilar_pdf

        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo .tex",
            "", "LaTeX (*.tex)",
        )
        if not path:
            return

        pdf = compilar_pdf(path)
        if pdf:
            QMessageBox.information(self, "Compilación exitosa",
                                    f"PDF generado:\n{pdf}")
        else:
            QMessageBox.warning(self, "Error de compilación",
                                "No se pudo compilar el PDF.\n"
                                "Verifica que pdflatex esté instalado y en el PATH.")

    def _on_vista_previa(self):
        """Abre el PDF generado con el visor del sistema."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        from pathlib import Path

        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo PDF",
            "", "PDF (*.pdf)",
        )
        if not path:
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ── StatusBar ─────────────────────────────────────────────────────────
    # Barra de estado inferior que muestra información del tema activo
    # y la versión de la aplicación.

