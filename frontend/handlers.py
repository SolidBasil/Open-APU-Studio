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
        from backend.db import Database, Rutas
        from frontend.widgets.dialogs import ProjectDialog

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
            from frontend.api import Api
            self._api = Api(self._db.conn, self._db.db_path)
            from frontend.api import Api
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
        from backend.db import Database

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
        from backend.db import Rutas
        from frontend.widgets.dialogs import ProjectDialog

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
        from backend.db import Rutas, Database
        from frontend.widgets.dialogs import ProjectDialog

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
            from frontend.api import Api
            self._api = Api(self._db.conn, self._db.db_path)
            self._update_statusbar()

        original.rename(dest)
        self._sb.showMessage(f"Renombrado a '{name}'", 4000)

    def _on_eliminar_proyecto(self):
        """Elimina permanentemente un proyecto .db con doble confirmación."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.db import Rutas, Database
        from frontend.widgets.dialogs import ProjectDialog

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
            from frontend.api import Api
            self._api = Api(self._db.conn, self._db.db_path)
            from frontend.api import Api
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
        from frontend.widgets.base import TreeTableWidget
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
        elif title == "📦 Explosión de insumos":
            content = self._build_explosion()
            if content is None:
                return   # usuario canceló el diálogo
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
        from frontend.widgets.base import TreeTableWidget
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

    # ── StatusBar ─────────────────────────────────────────────────────────
    # Barra de estado inferior que muestra información del tema activo
    # y la versión de la aplicación.

