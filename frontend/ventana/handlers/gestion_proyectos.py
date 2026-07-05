"""
gestion_proyectos.py
====================
Mixin de gestión de proyectos: abrir, cerrar, duplicar, renombrar,
eliminar e importar desde OPUS.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""


class GestionProyectosMixin:
    """Mixin de lifecycle de proyectos — se mezcla en VentanaPrincipal."""

    def _wire_servicios(self, db):
        """Ensambla EventBus → RepositoryRegistry → DataService → Api para
        el proyecto recién abierto y los deja instalados en self.

        Único punto de wiring: abrir, importar (y cualquier flujo futuro
        que abra un .db) deben llamar aquí en lugar de repetir el bloque.
        """
        from backend.database.event_bus import EventBus
        from backend.database.services.repository_registry import RepositoryRegistry
        from backend.database.services.data_service import DataService
        from backend.database.repos import (
            InsumoRepo, NodoRepo, ApuMatricesRepo, ProyectoRepo,
            FactoresSobrecostoRepo, FamiliaRepo, SubfamiliaRepo, NotaRepo,
        )
        from frontend.ventana.api import Api

        self._event_bus = EventBus()
        registry = RepositoryRegistry(db)
        registry.registrar("insumos", InsumoRepo)
        registry.registrar("estructura_presupuesto", NodoRepo)
        registry.registrar("apu_matrices", ApuMatricesRepo)
        registry.registrar("proyectos", ProyectoRepo)
        registry.registrar("factores_sobrecosto", FactoresSobrecostoRepo)
        registry.registrar("familias", FamiliaRepo)
        registry.registrar("subfamilias", SubfamiliaRepo)
        registry.registrar("notas", NotaRepo)
        self._registry = registry

        self._data_service = DataService(db, registry, self._event_bus)
        self._api = Api(db.conn, db.db_path, data_service=self._data_service)

    def eventFilter(self, obj, event):
        """Captura clics en el placeholder 'Sin proyecto' para abrir el ProjectDialog."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            self._on_abrir_proyecto()
            return True
        return super().eventFilter(obj, event)

    def _on_abrir_proyecto(self):
        """Selecciona y abre un proyecto .db existente."""
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
            self._wire_servicios(self._db)
            self._api.unificar_matrices_apu()
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
        self._data_service = None
        self._registry = None
        self._event_bus = None
        for i in range(self._tabs.count() - 1, -1, -1):
            self._cerrar_tab_widget(i)
        self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")
        self._sb.showMessage("Proyecto cerrado", 3000)

    def _on_copiar_proyecto(self):
        """Duplica un proyecto existente."""
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
        """Renombra un proyecto .db."""
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
            # Database.cerrar()+abrir() crea una conexión SQLite nueva.
            # Los repos del registry quedaron apuntando a la conexión vieja
            # (ya cerrada), así que hay que re-wirear todo, no solo Api.
            self._wire_servicios(self._db)
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
            self._data_service = None
            self._registry = None
            self._event_bus = None
            for i in range(self._tabs.count() - 1, -1, -1):
                self._cerrar_tab_widget(i)
            self._tabs.addTab(self._build_presupuesto(), "📋 Presupuesto programable")
        ruta.unlink()
        self._sb.showMessage(f"'{nombre}' eliminado", 4000)

    def _on_importar_opus(self):
        """Flujo completo de importación OPUS."""
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
            else:
                Path(db_path).unlink(missing_ok=True)

        try:
            result = importar(dir_path, db_path, nombre)
            if self._db:
                Database.cerrar()
            self._db = Database.abrir(db_path)
            self._wire_servicios(self._db)
            self._api.unificar_matrices_apu()
            print(f"[import] {nombre}: nodos={result['nodos']}, insumos={result['insumos']}, "
                  f"apu_matrices={result['apu_matrices']}, apu_resumen_totales={result['apu_resumen_totales']}, "
                  f"insumos_compuestos={result['insumos_compuestos']}")
            QMessageBox.information(self, "Importación exitosa",
                                    f"'{nombre}' importado correctamente.")
            self._reload_presupuesto()
            self._switch_tab("PRINCIPAL")
        except Exception as e:
            QMessageBox.critical(self, "Error de importación", str(e))
