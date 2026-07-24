"""
generador.py
============
Mixin de generadores de obra para VentanaPrincipal.

Panel izquierdo: árbol del presupuesto + nodo Extraordinarios.
Contenido: visor CAD + renglones inline (sección inferior).
Doble clic en concepto → carga generadores asociados.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QHeaderView, QFileDialog, QFrame,
)

from frontend.ventana.widgets.generador import TablaGenerador
from frontend.ventana.cad.visor import VisorCadWidget, CadTool

# Constante para el ítem "Extraordinarios" en el árbol
_EXTRA_ROLE = Qt.ItemDataRole.UserRole + 50


def _toolbar_sep():
    """Separador vertical para toolbars (QHBoxLayout no tiene addSeparator)."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep


class GeneradorMixin:
    """Mixin de generadores de obra — se mezcla en VentanaPrincipal."""

    # ── Panel izquierdo: árbol + renglones (stacked) ───────────────

    def _build_generadores_lateral(self) -> QWidget:
        """Panel lateral para la sección Generadores:
        QStackedWidget con idx 0 = árbol del presupuesto,
        idx 1 = renglones del concepto seleccionado.

        El árbol se pobla lazy en poblar_generadores() (llamado al entrar
        a la pestaña), no aquí, porque al construirse la ventana aún no
        hay proyecto abierto.
        """
        from PySide6.QtWidgets import QStackedWidget
        from frontend.ventana.widgets.arbol import TablaArbol

        self._gen_seleccionado: int | None = None
        self._gen_concepto_activo: int | None = None

        # ponytail: limpiar una sola vez el estado stale del header principal
        # que el árbol de generadores sobreescribía antes del fix de header_key
        from backend.database.db import Config
        if not Config.get("_arbol_header_stale_cleared"):
            Config.set("arbol_header_state", None)
            Config.set("_arbol_header_stale_cleared", True)

        stacked = QStackedWidget()

        # ── idx 0: Árbol del presupuesto (vacío, se pobla lazy) ──
        tree = TablaArbol(header_key="gen_arbol_header_state")
        tree.setHeaderLabel("Presupuesto")
        self._configurar_arbol_gen(tree)
        tree.itemDoubleClicked.connect(self._on_concepto_dblclick)
        tree.setMinimumWidth(180)
        stacked.addWidget(tree)
        self._arbol_gen = tree

        # ── idx 1: Renglones del concepto ──────────────────────
        stacked.addWidget(self._build_renglones_panel())

        self._gen_stacked = stacked
        return stacked

    def _configurar_arbol_gen(self, tree):
        """Aplica formato compacto al árbol: ocultar columnas, anchos, word wrap."""
        for col in [0, 1, 2, 3, 7, 8, 9, 10, 11, 12, 13, 14]:
            tree.setColumnHidden(col, True)
        tree.set_column_modes({
            4: (QHeaderView.ResizeMode.Interactive, 340),
            5: (QHeaderView.ResizeMode.Interactive, 60),
            6: (QHeaderView.ResizeMode.Interactive, 60),
        })
        tree.setWordWrap(True)
        tree.setStyleSheet(
            "QTreeWidget::item { min-height: 100px; padding: 2px 4px; }"
        )

    # ── Contenido: solo visor CAD ──────────────────────────────────

    def _build_generadores(self) -> QWidget:
        """Construye el contenido de la pestaña Generadores: solo el visor CAD."""
        cad_widget = self._build_cad_panel()
        self._gen_parts = (cad_widget,)
        return cad_widget

    def _abrir_generadores_para_concepto(self, concepto_id: int, wbs: str = "", desc: str = ""):
        """Abre la pestaña de generadores y carga el concepto dado."""
        self._on_abrir_generadores()
        self._gen_concepto_activo = concepto_id
        label = f"{wbs} {desc}".strip() or f"Concepto #{concepto_id}"
        self._gen_nombre_base = label
        self._gen_concepto_lbl.setText(label)
        gen_id = self._obtener_o_crear_generador(concepto_id)
        if not gen_id:
            self._gen_stacked.setCurrentIndex(0)
            return
        self._gen_seleccionado = gen_id
        gen_info = self._api.generador_por_id(gen_id) or {}
        self._gen_unidad_activa = gen_info.get("unidad") or ""
        renglones = self._api.generador_renglones(gen_id)
        self._gen_tabla.poblar(renglones)
        self._gen_stacked.setCurrentIndex(1)
        self._gen_tabla.setFocus()

    def _build_renglones_panel(self) -> QWidget:
        """Panel de renglones directos (sin capa de generadores)."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Botón volver al árbol
        btn_volver = QPushButton("← Volver al presupuesto")
        btn_volver.clicked.connect(self._on_volver_arbol)
        layout.addWidget(btn_volver)

        # Concepto seleccionado
        self._gen_concepto_lbl = QLabel("Selecciona un concepto del presupuesto")
        self._gen_concepto_lbl.setWordWrap(True)
        f = self._gen_concepto_lbl.font()
        f.setBold(True)
        self._gen_concepto_lbl.setFont(f)
        layout.addWidget(self._gen_concepto_lbl)

        # Renglones header
        renglones_header = QHBoxLayout()
        renglones_header.addWidget(QLabel("Renglones"))
        btn_renglon_nuevo = QPushButton("+ Renglón")
        btn_renglon_nuevo.clicked.connect(self._on_renglon_nuevo)
        renglones_header.addWidget(btn_renglon_nuevo)
        btn_renglon_eliminar = QPushButton("Eliminar")
        btn_renglon_eliminar.clicked.connect(self._on_renglon_eliminar)
        renglones_header.addWidget(btn_renglon_eliminar)
        layout.addLayout(renglones_header)

        self._gen_tabla = TablaGenerador()
        self._gen_tabla.renglon_editado.connect(self._on_renglon_editado)
        self._gen_tabla.total_actualizado.connect(self._on_gen_total_actualizado)
        self._gen_tabla.nuevo_renglon.connect(self._on_renglon_nuevo)
        layout.addWidget(self._gen_tabla, 1)

        return w

    # ── Handlers: doble clic en concepto ─────────────────────────

    def _on_concepto_dblclick(self, item, _col):
        """Doble clic en concepto: crea/busca generador y muestra renglones."""
        from frontend.ventana.widgets.arbol import TIPO_ROLE
        tipo = item.data(0, TIPO_ROLE)
        es_extra = item.data(0, _EXTRA_ROLE)

        if es_extra or tipo == "extraordinarios":
            concepto_id = None
            self._gen_nombre_base = "⚡ Extraordinarios (sin concepto)"
        elif tipo == "concepto":
            from frontend.ventana.widgets.arbol import ID_ROLE
            concepto_id = item.data(0, ID_ROLE)
            wbs = item.text(1)
            desc = item.text(4)
            self._gen_nombre_base = f"{wbs} {desc}"
        else:
            return

        self._gen_concepto_lbl.setText(self._gen_nombre_base)
        self._gen_concepto_activo = concepto_id

        # Buscar o crear generador para este concepto
        gen_id = self._obtener_o_crear_generador(concepto_id)
        if not gen_id:
            return
        self._gen_seleccionado = gen_id
        gen_info = self._api.generador_por_id(gen_id) or {}
        self._gen_unidad_activa = gen_info.get("unidad") or ""
        renglones = self._api.generador_renglones(gen_id)
        self._gen_tabla.poblar(renglones)
        self._gen_stacked.setCurrentIndex(1)
        self._gen_tabla.setFocus()

    def _obtener_o_crear_generador(self, concepto_id: int | None) -> int | None:
        """Busca el primer generador del concepto; si no existe, lo crea."""
        if not self._api:
            return None
        gens = self._api.generadores_por_concepto(concepto_id)
        if gens:
            return gens[0]["id"]
        # Auto-crear
        wbs = ""
        if concepto_id and hasattr(self, "_gen_concepto_lbl"):
            texto = self._gen_concepto_lbl.text()
            wbs = texto.split(" ", 1)[0] if texto else ""
        nombre = wbs if wbs else "General"

        if concepto_id is not None:
            cant = self._api.concepto_cantidad(concepto_id)
            if cant > 0:
                resp = QMessageBox.question(
                    self, "Vincular generador",
                    f"El concepto ya tiene una cantidad de {cant}.\n"
                    "¿Deseas borrarla y vincular la cantidad al generador?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return None
                self._api.concepto_actualizar(concepto_id, cantidad=0.0)

        return self._api.generador_crear(
            nombre=nombre, concepto_id=concepto_id,
        )

    def _on_gen_total_actualizado(self, total: float):
        """Actualiza el encabezado del concepto con el total ya medido,
        igual que en APU (nombre — Total). Se dispara cada vez que la
        tabla de renglones se repuebla (alta, edición, borrado o
        medición ligada desde el CAD)."""
        base = getattr(self, "_gen_nombre_base", "") or self._gen_concepto_lbl.text()
        unidad = getattr(self, "_gen_unidad_activa", "") or ""
        sufijo = f" {unidad}" if unidad else ""
        self._gen_concepto_lbl.setText(f"{base}  —  Medido: {total:,.2f}{sufijo}")

    def _on_volver_arbol(self):
        """Vuelve a mostrar el árbol del presupuesto."""
        self._gen_stacked.setCurrentIndex(0)

    # ── Handlers de renglones ──────────────────────────────────────

    def _on_renglon_nuevo(self):
        if not self._gen_seleccionado or not self._api:
            return
        nuevo_id = self._api.generador_renglon_guardar(
            self._gen_seleccionado
        )
        renglones = self._api.generador_renglones(self._gen_seleccionado)
        self._gen_tabla.poblar(renglones, seleccionar_id=nuevo_id)

    def _on_renglon_editado(self, renglon_id: int, campos: dict):
        if not self._gen_seleccionado or not self._api:
            return
        self._api.generador_renglon_guardar(
            self._gen_seleccionado, renglon_id=renglon_id, **campos
        )
        renglones = self._api.generador_renglones(self._gen_seleccionado)
        self._gen_tabla.poblar(renglones)

    def _on_renglon_eliminar(self):
        items = self._gen_tabla.selectedItems()
        if not items or not self._api:
            return
        item = items[0]
        renglon_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not renglon_id:
            return
        self._api.generador_renglon_eliminar(renglon_id)
        renglones = self._api.generador_renglones(self._gen_seleccionado)
        self._gen_tabla.poblar(renglones)

    # ── Refresco externo (llamado desde handlers/__init__.py) ────

    def poblar_generadores(self):
        """Repobla el árbol del presupuesto."""
        if not self._api or not hasattr(self, "_arbol_gen"):
            return

        from frontend.ventana.widgets.arbol import ID_ROLE, TIPO_ROLE
        tree = self._arbol_gen
        tree.blockSignals(True)
        try:
            nodos = self._api.presupuesto_arbol()
            tree.poblar(nodos)
        except Exception as e:
            print(f"Error cargando presupuesto en generadores: {e}")
        finally:
            tree.blockSignals(False)

        # Re-aplicar columnas compactas tras poblar()
        self._configurar_arbol_gen(tree)

        # Conectar/reactivar al bus de eventos para que refleje cambios en tiempo real.
        # conectar_eventos ya verifica si está conectado a un bus distinto y
        # llama a desconectar_eventos antes de re-suscribir.
        if self._event_bus:
            tree.conectar_eventos(self._event_bus, self._api)

        extra_item = tree.add_row(
            ["", "", "Extraordinarios", "", "Generadores sueltos",
             "", "", "", "", "", "", "", "", "", ""],
            editable=False,
        )
        tree.addTopLevelItem(extra_item)
        from frontend.ventana.iconos import icono
        extra_item.setIcon(0, icono("zap", 16))
        extra_item.setData(0, _EXTRA_ROLE, True)
        extra_item.setData(0, ID_ROLE, None)
        extra_item.setData(0, TIPO_ROLE, "extraordinarios")
        font = extra_item.font(0)
        font.setBold(True)
        extra_item.setFont(0, font)

    # ── Handlers del visor CAD ─────────────────────────────────────

    def _build_cad_panel(self) -> QWidget:
        """Construye el panel del visor CAD (sin side panel derecho)."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Forzar construcción del ribbon GENERADORES (idempotente)
        self._build_page("GENERADORES")
        self._cad_tool_buttons = {
            CadTool.SELECT: self._tb_buttons_by_tip.get("Seleccionar"),
            CadTool.LINE: self._tb_buttons_by_tip.get("Línea"),
            CadTool.POLYGON: self._tb_buttons_by_tip.get("Polígono"),
            CadTool.POINT: self._tb_buttons_by_tip.get("Punto"),
            CadTool.COUNT: self._tb_buttons_by_tip.get("Contar"),
        }
        btn_cuantificar = self._tb_buttons_by_tip.get("Cuantificar")
        if btn_cuantificar is not None:
            btn_cuantificar.setEnabled(False)
            btn_cuantificar.setToolTip(
                "Temporalmente deshabilitado: por ahora los renglones se "
                "agregan manualmente con \"+ Renglón\" y se llenan a mano "
                "usando el CAD como referencia."
            )

        # ── Franja de estado (arriba del canvas) ──────────────────
        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(8, 4, 8, 4)
        status_bar.setSpacing(4)
        status_bar.addStretch()

        self._cad_coords_lbl = QLabel("")
        self._cad_coords_lbl.setFixedWidth(200)
        self._cad_coords_lbl.setStyleSheet("color: #888; font-size: 10px;")
        status_bar.addWidget(self._cad_coords_lbl)

        self._cad_measurement_lbl = QLabel("")
        self._cad_measurement_lbl.setFixedWidth(150)
        self._cad_measurement_lbl.setStyleSheet("color: #FFD700; font-size: 10px;")
        status_bar.addWidget(self._cad_measurement_lbl)

        layout.addLayout(status_bar)

        # ── Visor CAD (ocupa todo el espacio) ────────────────────
        self._cad_viewer = VisorCadWidget()
        self._cad_viewer.point_clicked.connect(self._on_cad_point)
        self._cad_viewer.entity_clicked.connect(self._on_cad_entity_clicked)
        self._cad_viewer.measurement_ready.connect(self._on_cad_measurement)
        layout.addWidget(self._cad_viewer, 1)

        self._cad_btn_undo = self._tb_buttons_by_tip.get("Deshacer CAD")
        self._cad_btn_redo = self._tb_buttons_by_tip.get("Rehacer CAD")

        return w

    def _on_cad_abrir(self):
        """Abre un archivo DXF y lo carga en el visor."""
        start_dir = ""
        if self._db and self._db.db_path:
            from backend.database.db import Rutas
            adj_dir = Rutas.proyectos() / f"{Path(self._db.db_path).stem}_adjuntos"
            adj_dir.mkdir(parents=True, exist_ok=True)
            start_dir = str(adj_dir)
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir archivo DXF", start_dir,
            "Archivos DXF (*.dxf);;Todos los archivos (*)",
        )
        if not path:
            return
        try:
            from backend.cad.lector_dxf import parse_dxf
            result = parse_dxf(Path(path))
            if result.doc is not None:
                self._cad_viewer.set_document(result.doc)
            else:
                self._cad_viewer.set_entities(result.entities, result.layers)
            self._cad_layers = result.layers
            self._cad_entities_raw = [e.to_dict() for e in result.entities]
        except Exception as e:
            QMessageBox.warning(self, "Error al abrir DXF", str(e))

    def _on_cad_tool(self, tool: str):
        """Cambia la herramienta activa del visor CAD."""
        for t, btn in self._cad_tool_buttons.items():
            if btn is not None:
                btn.setChecked(t == tool)
        self._cad_viewer.set_tool(tool)

    def _on_cad_tool_select(self):
        self._on_cad_tool(CadTool.SELECT)

    def _on_cad_tool_line(self):
        self._on_cad_tool(CadTool.LINE)

    def _on_cad_tool_polygon(self):
        self._on_cad_tool(CadTool.POLYGON)

    def _on_cad_tool_point(self):
        self._on_cad_tool(CadTool.POINT)

    def _on_cad_tool_count(self):
        self._on_cad_tool(CadTool.COUNT)

    def _on_cad_calibrar(self):
        """Inicia el flujo de calibración de dos clics."""
        self._on_cad_tool(CadTool.CALIBRATE)
        self._cad_coords_lbl.setText("Clic en punto A de referencia...")

    def _on_cad_fit(self):
        """Ajusta la vista para mostrar todas las entidades."""
        self._cad_viewer.fit_in_view()

    def _on_cad_point(self, x: float, y: float):
        """Maneja clics en el visor CAD (referencia visual / medición)."""
        self._cad_coords_lbl.setText(f"X: {x:.4f}  Y: {y:.4f}")

    def _on_cad_measurement(self, valor: float, tipo: str):
        """Al terminar una medición en el visor, la liga a la celda que el
        usuario haya dejado seleccionada en la tabla de renglones
        (Veces/Largo/Ancho/Alto). Punto y Contador acumulan (+1 por clic);
        Línea y Área sobrescriben con el valor recién medido.
        """
        tabla = getattr(self, "_gen_tabla", None)
        if tabla is None:
            return
        modo = "sumar" if tipo in ("punto", "conteo") else "set"
        aplicado = tabla.aplicar_medicion(valor, modo=modo)
        if aplicado:
            self._cad_measurement_lbl.setText(f"✓ {valor:.4f} → celda")
            self._cad_measurement_lbl.setStyleSheet(
                "color: #4CAF50; font-size: 10px;"
            )
        else:
            self._cad_measurement_lbl.setText(
                "Selecciona Veces/Largo/Ancho/Alto para ligar"
            )
            self._cad_measurement_lbl.setStyleSheet(
                "color: #FFA500; font-size: 10px;"
            )

    def _on_cad_entity_clicked(self, handle: str):
        """Muestra qué entidad se seleccionó (herramienta Seleccionar)."""
        doc = getattr(self, "_cad_viewer", None)
        if not doc or not handle:
            return
        entity = doc.entitydb.get(handle)
        if entity is None:
            return
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else "?"
        self._cad_coords_lbl.setText(f"{entity.dxftype()}  ·  capa: {layer}")

    # ── Handler de capas (popup) ──────────────────────────────────

    def _on_cad_capas(self):
        """Abre diálogo de capas para encender/apagar."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
            QTableWidget, QTableWidgetItem, QAbstractItemView,
        )
        from PySide6.QtGui import QColor
        from backend.cad.lector_dxf import ACI_COLORS

        viewer = getattr(self, "_cad_viewer", None)
        if viewer is None:
            return

        layers = viewer.get_layers()
        if not layers:
            QMessageBox.information(self, "Capas", "No hay capas disponibles.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Capas")
        dlg.setMinimumSize(400, 420)
        dlg.setModal(True)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        # Filtro
        search = QLineEdit()
        search.setPlaceholderText("Filtrar capas...")
        search.setClearButtonEnabled(True)
        lay.addWidget(search)

        # Tabla
        table = QTableWidget(len(layers), 3)
        table.setHorizontalHeaderLabels(["", "Capa", "Entidades"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for i, layer in enumerate(layers):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(
                Qt.CheckState.Checked if layer["visible"] else Qt.CheckState.Unchecked
            )
            table.setItem(i, 0, chk)

            name_item = QTableWidgetItem(layer["name"])
            color = layer.get("color", "#CCCCCC")
            if isinstance(color, int):
                color = ACI_COLORS.get(color, "#CCCCCC")
            name_item.setForeground(QColor(color))
            table.setItem(i, 1, name_item)

            count_item = QTableWidgetItem(str(layer.get("entity_count", 0)))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(i, 2, count_item)

        lay.addWidget(table, 1)

        # Filtro de texto
        def filter_rows(text):
            q = text.strip().lower()
            for i in range(table.rowCount()):
                name = table.item(i, 1).text().lower()
                table.setRowHidden(i, q and q not in name)
        search.textChanged.connect(filter_rows)

        # Botones
        btn_row = QHBoxLayout()
        btn_all = QPushButton("Mostrar todas")
        btn_none = QPushButton("Ocultar todas")
        btn_close = QPushButton("Cerrar")
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)

        def apply_changes():
            for i in range(table.rowCount()):
                name = table.item(i, 1).text()
                visible = table.item(i, 0).checkState() == Qt.CheckState.Checked
                viewer.set_layer_visibility(name, visible)

        def show_all():
            for i in range(table.rowCount()):
                table.item(i, 0).setCheckState(Qt.CheckState.Checked)
            apply_changes()

        def hide_all():
            for i in range(table.rowCount()):
                table.item(i, 0).setCheckState(Qt.CheckState.Unchecked)
            apply_changes()

        table.cellChanged.connect(lambda row, col: apply_changes() if col == 0 else None)
        btn_all.clicked.connect(show_all)
        btn_none.clicked.connect(hide_all)
        btn_close.clicked.connect(dlg.accept)

        dlg.exec()

    # ── Cuantificacion y export ────────────────────────────────────

    def _on_cad_cuantificar(self):
        """Auto-cuantifica entidades por capa y crea renglones."""
        if not self._gen_seleccionado or not self._api:
            return
        entities = getattr(self, "_cad_entities_raw", [])
        if not entities:
            QMessageBox.information(self, "Cuantificar", "No hay entidades cargadas.")
            return

        from frontend.ventana.cad.auto_quantify import quantify_by_layer
        result = quantify_by_layer(entities, scale=1.0)

        for r in result:
            self._api.generador_renglon_guardar(
                self._gen_seleccionado,
                eje=f"{r.layer} ({r.unit})",
                veces=1 if r.primary == "count" else None,
                largo=r.quantity if r.primary != "count" else None,
                ancho=None,
                alto=None,
            )

        renglones = self._api.generador_renglones(self._gen_seleccionado)
        self._gen_tabla.poblar(renglones)
        QMessageBox.information(
            self, "Cuantificar",
            f"{len(result)} capas procesadas, renglones creados.",
        )

    def _on_cad_export_pdf(self):
        """Exporta la vista actual del visor a PDF."""
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        pixmap = self._cad_viewer.viewport().grab()
        img_data = QByteArray()
        buf = QBuffer(img_data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        buf.close()

        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar PDF", "", "PDF (*.pdf)",
        )
        if not path:
            return

        try:
            from frontend.ventana.cad.exportar_pdf import export_canvas_to_pdf
            result_path = export_canvas_to_pdf(
                bytes(img_data),
                filename=path,
                output_path=path,
            )
            QMessageBox.information(self, "PDF Exportado", result_path)
        except Exception as e:
            QMessageBox.warning(self, "Error al exportar PDF", str(e))

    def _on_cad_export_excel(self):
        """Exporta cuantificacion por capa a Excel."""
        entities = getattr(self, "_cad_entities_raw", [])
        if not entities:
            QMessageBox.information(self, "Exportar Excel", "No hay entidades cargadas.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Excel", "", "Excel (*.xlsx)",
        )
        if not path:
            return

        try:
            from frontend.ventana.cad.auto_quantify import quantify_by_layer
            from frontend.ventana.cad.exportar_excel import export_quantify_to_excel
            result = quantify_by_layer(entities, scale=1.0)
            result_path = export_quantify_to_excel(
                result,
                drawing_name="generadores",
                output_path=path,
            )
            QMessageBox.information(self, "Excel Exportado", result_path)
        except Exception as e:
            QMessageBox.warning(self, "Error al exportar Excel", str(e))

    # ── Undo/Redo ──────────────────────────────────────────────────

    def _on_cad_undo(self):
        """Deshacer ultima anotacion."""
        if hasattr(self, "_cad_undo_state"):
            from frontend.ventana.cad.undo_stack import pop_undo, can_undo
            if can_undo(self._cad_undo_state):
                self._cad_undo_state, entry = pop_undo(self._cad_undo_state)
                self._apply_undo_entry(entry, undo=True)
                self._update_undo_buttons()

    def _on_cad_redo(self):
        """Rehacer anotacion deshecha."""
        if hasattr(self, "_cad_undo_state"):
            from frontend.ventana.cad.undo_stack import pop_redo, can_redo
            if can_redo(self._cad_undo_state):
                self._cad_undo_state, entry = pop_redo(self._cad_undo_state)
                self._apply_undo_entry(entry, undo=False)
                self._update_undo_buttons()

    def _apply_undo_entry(self, entry, undo: bool):
        """Aplica o revierte una entrada de undo."""
        if not entry:
            return
        if entry.kind == "create":
            item = self._cad_viewer._entity_items.get(entry.id)
            if item:
                item.setVisible(not undo)
        elif entry.kind == "delete" and not undo:
            pass  # re-creation would need snapshot data
        self._update_undo_buttons()

    def _update_undo_buttons(self):
        if not hasattr(self, "_cad_undo_state"):
            from frontend.ventana.cad.undo_stack import empty_undo_state
            self._cad_undo_state = empty_undo_state()
        from frontend.ventana.cad.undo_stack import can_undo, can_redo
        if self._cad_btn_undo is not None:
            self._cad_btn_undo.setEnabled(can_undo(self._cad_undo_state))
        if self._cad_btn_redo is not None:
            self._cad_btn_redo.setEnabled(can_redo(self._cad_undo_state))
