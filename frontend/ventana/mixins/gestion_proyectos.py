"""
gestion_proyectos.py
====================
Mixin de gestión de proyectos: abrir, cerrar, duplicar, renombrar,
eliminar e importar desde OPUS.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""

from frontend.ventana.colores import SUCCESS, WARNING, ERROR


class GestionProyectosMixin:
    """Mixin de lifecycle de proyectos — se mezcla en VentanaPrincipal."""

    # ── Servidor embebido (SRV-11) ─────────────────────────────────

    def _ensure_server(self) -> str | None:
        """Devuelve la URL del servidor, arrancándolo bajo demanda (lazy)."""
        proc = getattr(self, "_server_proc", None)
        if proc is not None and proc.poll() is None:
            return self._servidor_url
        url = self._start_server()
        if url:
            self._start_ws_client(url)
        return url

    def _start_ws_client(self, server_url: str):
        """Arranca el cliente WebSocket para recibir eventos en vivo (SRV-05)."""
        self._stop_ws_client()
        from pathlib import Path
        from frontend.ventana.ws_client import WebSocketClient
        nombre = Path(self._db.db_path).stem if self._db else None
        if not nombre:
            return
        self._ws_client = WebSocketClient(server_url, nombre, parent=self)
        self._ws_client.evento_recibido.connect(self._on_ws_evento)
        self._ws_client.start()

    def _stop_ws_client(self):
        client = getattr(self, "_ws_client", None)
        if client is not None:
            client.detener()
            client.wait(3000)
            self._ws_client = None

    def _on_ws_evento(self, nombre_evento: str, data: dict):
        """Handler de eventos WS — re-emite en el EventBus local (SRV-05)."""
        from backend.database.event_bus import (
            InsumoActualizado, ConceptoActualizado, ApuComponenteActualizado,
            FactoresSobrecostoActualizados, NodoInsertado, NodoEliminado,
            ProyectoRecalculado, GeneradorActualizado,
            VariableFormulaActualizada, IndirectoActualizado,
        )
        _map = {
            "InsumoActualizado": lambda d: InsumoActualizado(
                d.get("insumo_id", 0), d.get("cambios", {}),
                d.get("registro", {})),
            "ConceptoActualizado": lambda d: ConceptoActualizado(
                d.get("concepto_id", 0), d.get("cambios", {}),
                d.get("registro", {})),
            "ApuComponenteActualizado": lambda d: ApuComponenteActualizado(
                d.get("componente_id", 0), d.get("cambios", {}),
                d.get("registro", {})),
            "FactoresSobrecostoActualizados": lambda d: FactoresSobrecostoActualizados(
                d.get("proyecto_id", 0), d.get("registro", {})),
            "NodoInsertado": lambda d: NodoInsertado(
                d.get("nodo_id", 0), d.get("tipo", ""), d.get("padre_id")),
            "NodoEliminado": lambda d: NodoEliminado(
                d.get("nodo_id", 0), d.get("tipo", "")),
            "ProyectoRecalculado": lambda d: ProyectoRecalculado(
                d.get("proyecto_id", 0), d.get("usuario_id", 1)),
            # Fase C: el servidor ya broadcastea estos 3 vía suscriptor
            # genérico (antes morían en silencio en el bus del servidor).
            "GeneradorActualizado": lambda d: GeneradorActualizado(
                d.get("generador_id", 0), d.get("conceptos_ids", [])),
            "VariableFormulaActualizada": lambda d: VariableFormulaActualizada(
                d.get("variable_id", 0), d.get("cambios", {}),
                d.get("registro", {})),
            "IndirectoActualizado": lambda d: IndirectoActualizado(
                d.get("proyecto_id", 0)),
        }
        ctor = _map.get(nombre_evento)
        if ctor and self._event_bus:
            try:
                self._event_bus.emit(ctor(data))
            except Exception as e:
                print(f"[eventbus] error reemitiendo '{nombre_evento}': {e}")

    def _start_server(self) -> str | None:
        """Arranca el servidor embebido como subprocess (SRV-11).
        Devuelve la URL base o None si falla."""
        import sys
        import subprocess
        import time
        cmd = [sys.executable, "-u", "-m", "server.servidor", "--embedded", "--port", "0"]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, bufsize=1)
        except Exception as e:
            print(f"No se pudo arrancar el servidor embebido: {e}")
            return None
        self._server_proc = proc
        deadline = time.time() + 10
        while time.time() < deadline:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    self._server_proc = None
                    return None
                continue
            if line.strip().startswith("PUERTO:"):
                port = int(line.strip().split(":", 1)[1])
                self._servidor_url = f"http://127.0.0.1:{port}"
                return self._servidor_url
        self._server_proc = None
        return None

    def _stop_server(self):
        """Detiene el servidor embebido y el cliente WS (SRV-13)."""
        import subprocess
        self._stop_ws_client()
        proc = getattr(self, "_server_proc", None)
        if proc is None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        self._server_proc = None
        self._servidor_url = None

    def _wire_servicios(self, db, servidor_url=None):
        """Ensambla EventBus → RepositoryRegistry → DataService → Api para
        el proyecto recién abierto y los deja instalados en self.

        Único punto de wiring: abrir, importar (y cualquier flujo futuro
        que abra un .db) deben llamar aquí en lugar de repetir el bloque.
        """
        from backend.database.event_bus import EventBus
        from backend.database.services.repository_registry import crear_registry
        from backend.database.services.data_service import DataService
        from frontend.ventana.api import Api

        self._event_bus = EventBus()
        registry = crear_registry(db)
        self._registry = registry

        self._data_service = DataService(db, registry, self._event_bus)
        self._api = Api(db.conn, db.db_path, data_service=self._data_service,
                        servidor_url=None,
                        ensure_server=getattr(self, "_ensure_server", None))

        from backend.database.event_bus import ProyectoAbierto
        self._event_bus.emit(ProyectoAbierto(self._api.proyecto_actual_id(), str(db.db_path)))

        from pathlib import Path
        self.setWindowTitle(f"{Path(db.db_path).stem} — {self._TITULO_BASE}")

    def eventFilter(self, obj, event):
        """Captura clics en el placeholder 'Sin proyecto' para abrir el ProjectDialog.

        Solo reacciona si el evento viene del placeholder (o sus hijos);
        los demás widgets filtrados (botones de la cinta, etc.) pasan de largo.
        """
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonPress:
            placeholder = getattr(self, '_placeholder_sin_proyecto', None)
            if placeholder is not None:
                cur = obj
                while cur is not None:
                    if cur is placeholder:
                        self._on_abrir_proyecto()
                        return True
                    cur = cur.parent()
        return super().eventFilter(obj, event)

    def _on_abrir_proyecto(self):
        """Selecciona y abre un proyecto .db existente."""
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.database.db import Database, Rutas
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            self._sb.showMessage("No hay proyectos guardados.", 3000)
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
                self._db.close()
                self._stop_server()
            self._db = Database.abrir(db_path)
            self._wire_servicios(self._db)
            self._api.unificar_matrices_apu()
            self._reload_presupuesto()
            self._update_statusbar()
            self._switch_tab("PRINCIPAL")
        except Exception as e:
            from frontend.ventana.ui_utils import mostrar_error
            mostrar_error(self, "Error al abrir proyecto", e)

    def _on_nuevo_proyecto(self):
        """Abre formulario vacío; al guardar se crea el .db con el nombre indicado."""
        self._on_info_proyecto(nuevo=True)

    def _on_cerrar_proyecto(self):
        """Cierra el proyecto actual con confirmación."""
        if not self._db:
            return
        from PySide6.QtWidgets import QMessageBox

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

        from backend.database.event_bus import ProyectoCerrado
        self._event_bus.emit(ProyectoCerrado(self._api.proyecto_actual_id()))

        self._db.close()
        self._stop_server()
        self._db = None
        self._api = None
        self._data_service = None
        self._registry = None
        self._event_bus = None
        self.setWindowTitle(self._TITULO_BASE)
        for i in range(self._tabs.count() - 1, -1, -1):
            self._cerrar_tab_widget(i)
        self._tabs.addTab(self._build_presupuesto(), "Presupuesto programable")
        self._sb.showMessage("Proyecto cerrado", 3000)

    def _on_copiar_proyecto(self):
        """Duplica un proyecto existente."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox
        from backend.database.db import Rutas
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            self._sb.showMessage("No hay proyectos guardados.", 3000)
            return
        actual = Path(self._db.db_path).stem if self._db and self._db.db_path else None
        dlg = ProjectDialog(proyectos, "Duplicar proyecto", "Duplicar",
                            accion_color=SUCCESS, seleccionado=actual,
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
        from backend.database.db import Rutas
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            self._sb.showMessage("No hay proyectos guardados.", 3000)
            return
        dlg = ProjectDialog(proyectos, "Renombrar proyecto", "Renombrar",
                            accion_color=WARNING, parent=self)
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
            QMessageBox.warning(self, "Obra ya abierta",
                                f"'{source_name}' ya está abierta. Ciérrala antes de renombrar.")
            return

        original.rename(dest)
        self._sb.showMessage(f"Renombrado a '{name}'", 4000)

    def _on_eliminar_proyecto(self):
        """Elimina permanentemente un proyecto .db con doble confirmación."""
        from pathlib import Path
        from PySide6.QtWidgets import QDialog, QMessageBox
        from backend.database.db import Rutas
        from frontend.ventana.widgets.dialogs import ProjectDialog

        proyectos = Rutas.listar_proyectos()
        if not proyectos:
            self._sb.showMessage("No hay proyectos guardados.", 3000)
            return
        dlg = ProjectDialog(proyectos, "Eliminar proyecto", "Eliminar",
                            accion_color=ERROR, parent=self)
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
            QMessageBox.warning(self, "Obra ya abierta",
                                f"'{nombre}' ya está abierta. Ciérrala antes de eliminar.")
            return
        ruta.unlink()
        self._sb.showMessage(f"'{nombre}' eliminado", 4000)

    def _on_importar_opus(self):
        """Flujo completo de importación OPUS."""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from backend.database.db import Database, Rutas
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

        if self._db and Path(self._db.db_path).resolve() == Path(db_path).resolve():
            QMessageBox.warning(self, "Obra ya abierta",
                                f"'{nombre}' ya está abierta. Ciérrala antes de importar.")
            return

        if Path(db_path).exists():
            from datetime import datetime
            msg = QMessageBox(self)
            msg.setWindowTitle("Base de datos existente")
            msg.setText(f"Ya existe una base de datos para '{nombre}'.")
            msg.setInformativeText("¿Cómo quieres proceder?")
            btn_rename = msg.addButton("Renombrar anterior", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Sobrescribir", QMessageBox.ButtonRole.DestructiveRole)
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

        from frontend.ventana.ui_utils import progreso_indeterminado

        try:
            with progreso_indeterminado(self, f"Importando '{nombre}'…"):
                result = importar(dir_path, db_path, nombre)
                if self._db:
                    self._db.close()
                    self._stop_server()
                self._db = Database.abrir(db_path)
                self._wire_servicios(self._db)
                self._api.unificar_matrices_apu()
            print(f"[import] {nombre}: nodos={result['nodos']}, insumos={result['insumos']}, "
                  f"apu_matrices={result['apu_matrices']}, "
                  f"insumos_compuestos={result['insumos_compuestos']}")
            sin_resolver = result.get("wbs_sin_resolver", 0)
            ambiguo = result.get("wbs_ambiguo", 0)
            if sin_resolver or ambiguo:
                # Hallazgo 9 de la auditoría: antes esta información solo
                # se imprimía en consola (invisible para el usuario de la
                # app de escritorio) y se perdía apenas terminaba la
                # importación. "wbs_ambiguo" > 0 no significa que algo
                # esté mal necesariamente — el truncado de WBS puede saltar
                # niveles legítimamente — pero es una señal real de que la
                # jerarquía importada vale la pena revisarse a mano.
                detalle = []
                if sin_resolver:
                    detalle.append(f"• {sin_resolver} nodo(s) sin padre resuelto (quedaron en la raíz)")
                if ambiguo:
                    detalle.append(f"• {ambiguo} nodo(s) con jerarquía ambigua (revisar el árbol)")
                QMessageBox.warning(
                    self, "Importación completada con avisos",
                    f"'{nombre}' se importó, pero hay puntos que conviene revisar "
                    "en el árbol de presupuesto:\n\n" + "\n".join(detalle),
                )
            else:
                self._sb.showMessage(f"'{nombre}' importado correctamente.", 4000)
            self._reload_presupuesto()
            self._switch_tab("PRINCIPAL")
        except Exception as e:
            from frontend.ventana.ui_utils import mostrar_error
            mostrar_error(self, "Error de importación", e)
