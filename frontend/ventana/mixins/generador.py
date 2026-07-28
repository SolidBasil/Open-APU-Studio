"""
generador.py
============
Mixin de generadores de obra para VentanaPrincipal.

Cada generador vive en su propia pestaña de contenido (dentro de
self._tabs) con el visor CAD. Los renglones de medición
(Eje/Tramo/Veces/Largo/Ancho/Alto) se muestran en el panel izquierdo
(sidebar) reemplazando el explorador — ver _show_renglones_in_left_panel().
Cada pestaña tiene su propio visor CAD independiente — puede tener un
DXF distinto abierto, ligado (persistido en generadores.cad_archivo_path)
a ESE generador específico, y se recarga solo la próxima vez que se abre
esa pestaña.

Ya no existe un panel/pestaña singleton de "Generadores de obra" ni un
árbol de presupuesto en el panel izquierdo — ver mixins/paneles.py
(_build_left_panel, simplificado a solo el sidebar normal).

Puntos de entrada para abrir un generador (siempre en su propia
pestaña; reabrir uno ya abierto solo lo enfoca):
  - Menú contextual "Abrir generador" sobre un concepto, en el árbol de
    Presupuesto normal (ver widgets/arbol.py → TablaArbol.abrir_generador
    → _on_abrir_generador).
  - Doble clic en la columna Cantidad de un concepto que ya tiene
    generadores (ver mixins/apu.py → _on_item_dblclick).
  - Botón "Generadores" del ribbon INICIO → crea un generador suelto
    ("Extraordinario", sin concepto) y lo abre en pestaña nueva.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QHeaderView, QFileDialog, QStackedWidget,
)

from frontend.ventana.widgets.generador import TablaGenerador
from frontend.ventana.widgets.base import EMPTY_ROLE
from frontend.ventana.cad.visor import VisorCadWidget, CadTool


class GeneradorMixin:
    """Mixin de generadores de obra — se mezcla en VentanaPrincipal."""

    # ── Helpers de la pestaña de generador activa ──────────────────

    def _generador_tab_activo(self):
        """Contenedor de la pestaña de generador actualmente enfocada,
        o None si la pestaña activa no es de un generador."""
        tabs = getattr(self, "_tabs", None)
        if tabs is None:
            return None
        w = tabs.currentWidget()
        return w if getattr(w, "_es_generador_tab", False) else None

    def _generador_tab_por_id(self, generador_id: int):
        """Busca, entre las pestañas abiertas, la de un generador dado."""
        tabs = getattr(self, "_tabs", None)
        if tabs is None:
            return None
        for i in range(tabs.count()):
            w = tabs.widget(i)
            if getattr(w, "_es_generador_tab", False) and w._generador_id == generador_id:
                return w
        return None

    # ── Apertura de generadores ─────────────────────────────────────

    def _obtener_o_crear_generador(self, concepto_id: int | None, wbs: str = "") -> int | None:
        """Busca el primer generador del concepto; si no existe, lo crea."""
        if not self._api:
            return None
        gens = self._api.generadores_por_concepto(concepto_id)
        if gens:
            return gens[0]["id"]

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

        return self._api.generador_crear(nombre=nombre, concepto_id=concepto_id)

    def _on_abrir_generador(self, concepto_id: int):
        """Handler del menú contextual "Abrir generador" del árbol de
        Presupuesto: busca/crea el generador de ese concepto y lo abre
        en su propia pestaña."""
        from backend.database.repos.presupuesto import NodoRepo
        nodo = NodoRepo(self._api._conn).buscar(concepto_id)
        wbs = nodo.get("wbs", "") if nodo else ""
        desc = nodo.get("descripcion", "") if nodo else ""
        self._abrir_generadores_para_concepto(concepto_id, wbs, desc)

    def _abrir_generadores_para_concepto(self, concepto_id: int, wbs: str = "", desc: str = ""):
        """Busca/crea el generador de un concepto y lo abre en su pestaña."""
        if not self._api:
            return
        gen_id = self._obtener_o_crear_generador(concepto_id, wbs)
        if not gen_id:
            return
        nombre = f"{wbs} {desc}".strip()[:30] or f"Concepto #{concepto_id}"
        self._abrir_generador_tab(gen_id, nombre)

    def _on_nuevo_generador_extra(self):
        """Botón 'Generadores' del ribbon INICIO: crea un generador
        suelto (sin concepto — 'Extraordinario') y lo abre en pestaña
        nueva."""
        if not self._api:
            return
        n = 1 + len(self._api.generadores_por_concepto(None))
        gen_id = self._api.generador_crear(nombre=f"Extraordinario {n}")
        self._abrir_generador_tab(gen_id, f"⚡ Extraordinario {n} (sin concepto)")

    def _abrir_generador_tab(self, generador_id: int, nombre: str = ""):
        """Abre (o enfoca, si ya está abierta) la pestaña de este
        generador. Cada generador vive por completo en su propia
        pestaña, con su propio visor CAD — reabrir uno ya abierto solo
        lo enfoca, nunca duplica la pestaña."""
        if not self._api:
            return
        existente = self._generador_tab_por_id(generador_id)
        if existente is not None:
            idx = self._tabs.indexOf(existente)
            if idx >= 0:
                self._tabs.setCurrentIndex(idx)
            return
        gen = self._api.generador_por_id(generador_id)
        if not gen:
            return
        titulo = nombre or gen.get("nombre") or f"Generador #{generador_id}"
        contenido = self._build_generador_tab(generador_id, gen, nombre)
        idx = self._tabs.addTab(contenido, titulo)
        self._tabs.setCurrentIndex(idx)

    # ── Left-panel management: renglones en lugar del sidebar ────────

    def _show_renglones_in_left_panel(self, container):
        """Pone el panel de renglones del generador en el QStackedWidget
        izquierdo (reemplaza el sidebar). Cada panel conserva su propio
        ancho de splitter."""
        stack: QStackedWidget = getattr(self, "_left_stack", None)
        if stack is None:
            return
        splitter = getattr(self, "_main_splitter", None)
        # Guardar ancho actual del sidebar antes de reemplazar
        if splitter is not None:
            sizes = splitter.sizes()
            self._sidebar_width = sizes[0]
        # Quitar renglones viejos del stack (si los hay)
        while stack.count() > 1:
            old = stack.widget(1)
            stack.removeWidget(old)
            if getattr(old, "_generador_id", None) is not None:
                old.setParent(old._generador_container or None)
                old.hide()
        rp = container._renglones_panel
        rp.setParent(None)
        rp._generador_container = container
        stack.addWidget(rp)
        stack.setCurrentIndex(1)
        rp.show()
        # Restaurar el ancho que tenía el panel de renglones la última vez
        if splitter is not None:
            total = splitter.width()
            rw = getattr(self, "_renglones_width", max(total // 3, 420))
            splitter.setSizes([rw, total - rw])

    def _restore_sidebar(self):
        """Restaura el sidebar en el panel izquierdo con su último ancho conocido."""
        stack: QStackedWidget = getattr(self, "_left_stack", None)
        if stack is None:
            return
        splitter = getattr(self, "_main_splitter", None)
        # Guardar ancho actual del panel de renglones antes de reemplazar
        if splitter is not None:
            sizes = splitter.sizes()
            self._renglones_width = sizes[0]
        while stack.count() > 1:
            old = stack.widget(1)
            stack.removeWidget(old)
            if getattr(old, "_generador_id", None) is not None:
                old.setParent(old._generador_container or None)
                old.hide()
        stack.setCurrentIndex(0)
        # Restaurar el ancho que tenía el sidebar la última vez
        if splitter is not None:
            total = splitter.width()
            sw = getattr(self, "_sidebar_width", 220)
            splitter.setSizes([sw, total - sw])

    # ── Construcción de la pestaña: CAD (renglones van al left stack) ─

    def _build_generador_tab(self, generador_id: int, gen: dict, nombre: str) -> QWidget:
        """Contenedor de UN generador: visor CAD propio. Los renglones
        de medición se muestran en el panel izquierdo (sidebar) en lugar
        de dentro de la pestaña — ver _show_renglones_in_left_panel()."""
        from frontend.ventana.cad.undo_stack import empty_undo_state

        container = QWidget()
        container._es_generador_tab = True
        container._generador_id = generador_id
        container._nombre_base = nombre or gen.get("nombre") or f"Generador #{generador_id}"
        container._unidad_activa = gen.get("unidad") or ""
        container._cad_entities_raw = []
        container._cad_layers = []
        container._cad_undo_state = empty_undo_state()
        container._cad_dxf_path = gen.get("cad_archivo_path") or None

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_cad_panel_tab(container), 1)

        # Renglones panel: se construye pero vive en el left stack,
        # no en el layout de la pestaña.
        container._renglones_panel = self._build_renglones_panel_tab(container)
        container._renglones_panel.hide()
        container._renglones_panel.setParent(container)

        renglones = self._api.generador_renglones(generador_id)
        container._tabla_generador.poblar(renglones)
        total = sum(r.get("subtotal", 0) or 0 for r in renglones)
        self._actualizar_encabezado_generador(container, total)

        # Recuperar el DXF ligado a este generador, si existe y sigue en disco.
        if container._cad_dxf_path:
            self._cargar_dxf_en_tab(container, container._cad_dxf_path, silencioso=True)

        return container

    def _build_cad_panel_tab(self, container) -> QWidget:
        """Panel del visor CAD de la pestaña de un generador."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Ribbon GENERADORES: botones compartidos (Seleccionar/Línea/etc.)
        # que actúan sobre la pestaña de generador enfocada en cada
        # momento (ver _generador_tab_activo). Se resuelven una sola vez.
        if not hasattr(self, "_cad_tool_buttons"):
            if hasattr(self, "_build_page"):
                self._build_page("GENERADORES")
            tips = getattr(self, "_tb_buttons_by_tip", {})
            self._cad_tool_buttons = {
                CadTool.SELECT:  tips.get("Seleccionar"),
                CadTool.LINE:    tips.get("Línea"),
                CadTool.POLYGON: tips.get("Polígono"),
                CadTool.POINT:   tips.get("Punto"),
                CadTool.COUNT:   tips.get("Contar"),
            }
            btn_cuantificar = tips.get("Cuantificar")
            if btn_cuantificar is not None:
                btn_cuantificar.setEnabled(False)
                btn_cuantificar.setToolTip(
                    "Temporalmente deshabilitado: por ahora los renglones se "
                    "agregan manualmente con \"+ Renglón\" y se llenan a mano "
                    "usando el CAD como referencia."
                )
            self._cad_btn_undo = tips.get("Deshacer CAD")
            self._cad_btn_redo = tips.get("Rehacer CAD")

        status_bar = QHBoxLayout()
        status_bar.setContentsMargins(8, 4, 8, 4)
        status_bar.setSpacing(4)
        status_bar.addStretch()

        coords_lbl = QLabel("")
        coords_lbl.setFixedWidth(200)
        coords_lbl.setStyleSheet("color: #888; font-size: 10px;")
        status_bar.addWidget(coords_lbl)
        container._cad_coords_lbl = coords_lbl

        medicion_lbl = QLabel("")
        medicion_lbl.setFixedWidth(150)
        medicion_lbl.setStyleSheet("color: #FFD700; font-size: 10px;")
        status_bar.addWidget(medicion_lbl)
        container._cad_measurement_lbl = medicion_lbl

        layout.addLayout(status_bar)

        viewer = VisorCadWidget()
        viewer.point_clicked.connect(lambda x, y, c=container: self._on_cad_point(c, x, y))
        viewer.entity_clicked.connect(lambda h, c=container: self._on_cad_entity_clicked(c, h))
        viewer.measurement_ready.connect(lambda v, t, c=container: self._on_cad_measurement(c, v, t))
        layout.addWidget(viewer, 1)
        container._cad_viewer = viewer

        return w

    def _build_renglones_panel_tab(self, container) -> QWidget:
        """Panel de renglones de medición de esta pestaña."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        lbl = QLabel(container._nombre_base)
        lbl.setWordWrap(True)
        f = lbl.font()
        f.setBold(True)
        lbl.setFont(f)
        layout.addWidget(lbl)
        container._concepto_lbl = lbl

        header = QHBoxLayout()
        header.addWidget(QLabel("Renglones"))
        btn_nuevo = QPushButton("+ Renglón")
        btn_nuevo.clicked.connect(lambda: self._on_renglon_nuevo_tab(container))
        header.addWidget(btn_nuevo)
        btn_eliminar = QPushButton("Eliminar")
        btn_eliminar.clicked.connect(lambda: self._on_renglon_eliminar_tab(container))
        header.addWidget(btn_eliminar)
        layout.addLayout(header)

        tabla = TablaGenerador(generador_id=container._generador_id)
        tabla.renglon_editado.connect(
            lambda rid, campos, c=container: self._on_renglon_editado_tab(c, rid, campos))
        tabla.renglon_eliminar.connect(
            lambda ids, c=container: self._eliminar_renglones_tab(c, ids))
        tabla.total_actualizado.connect(
            lambda total, c=container: self._actualizar_encabezado_generador(c, total))
        tabla.nuevo_renglon.connect(lambda c=container: self._on_renglon_nuevo_tab(c))
        layout.addWidget(tabla, 1)
        container._tabla_generador = tabla

        return w

    # ── Encabezado (nombre + medido) ─────────────────────────────────

    def _actualizar_encabezado_generador(self, container, total: float):
        base = container._nombre_base
        unidad = container._unidad_activa or ""
        sufijo = f" {unidad}" if unidad else ""
        container._concepto_lbl.setText(f"{base}  —  Medido: {total:,.2f}{sufijo}")

    # ── Handlers de renglones (por pestaña) ──────────────────────────

    def _on_renglon_nuevo_tab(self, container) -> None:
        if not self._api:
            return
        gid = container._generador_id
        nuevo_id = self._api.generador_renglon_guardar(gid)
        renglones = self._api.generador_renglones(gid)
        container._tabla_generador.poblar(renglones, seleccionar_id=nuevo_id)

    def _on_renglon_editado_tab(self, container, renglon_id: int, campos: dict) -> None:
        """Diferido a propósito (ver TablaArbol._on_proyecto_recalculado,
        mismo motivo): un pegado de varias columnas en una sola fila
        escribe celda por celda, y cada una dispara itemChanged →
        _on_renglon_editado_tab. Si poblar() corriera aquí mismo,
        destruiría a medio pegado el QTreeWidgetItem que _pegar_cuadricula
        todavía está usando para las columnas siguientes."""
        if not self._api:
            return
        gid = container._generador_id
        self._api.generador_renglon_guardar(gid, renglon_id=renglon_id, **campos)
        QTimer.singleShot(0, lambda: self._refrescar_generador_tab_seguro(container, gid))

    def _refrescar_generador_tab_seguro(self, container, generador_id: int) -> None:
        if not self._api or container._generador_id != generador_id:
            return
        renglones = self._api.generador_renglones(generador_id)
        container._tabla_generador.poblar(renglones)

    def _eliminar_renglones_tab(self, container, ids: list[int]) -> None:
        """Elimina un bloque de renglones y refresca la tabla de esta
        pestaña. Compartido entre el botón "Eliminar" y Delete/drag&drop."""
        if not ids or not self._api:
            return
        for rid in ids:
            self._api.generador_renglon_eliminar(rid)
        renglones = self._api.generador_renglones(container._generador_id)
        container._tabla_generador.poblar(renglones)

    def _on_renglon_eliminar_tab(self, container) -> None:
        tabla = container._tabla_generador
        items = [it for it in tabla.selectedItems() if not it.data(0, EMPTY_ROLE)]
        if not items or not self._api:
            return
        ids = [it.data(0, Qt.ItemDataRole.UserRole) for it in items]
        ids = [i for i in ids if i]
        if not ids:
            return
        texto = ("¿Eliminar este renglón del generador?" if len(ids) == 1 else
                 f"¿Eliminar estos {len(ids)} renglones del generador?")
        resp = QMessageBox.question(self, "Eliminar renglón(es)", texto)
        if resp != QMessageBox.StandardButton.Yes:
            return
        self._eliminar_renglones_tab(container, ids)

    # ── Drag and drop entre pestañas de Generadores ──────────────────

    def _on_drop_generador(self, ids_arrastrados: list[int], generador_destino_id: int,
                            antes_de_id: int | None, copiar: bool) -> bool:
        """Handler del drag and drop de renglones (ver
        TablaGenerador.dropEvent): mueve/copia (Ctrl) un bloque de
        renglones a otro generador, o reordena si es el mismo. El
        trabajo real (mover, recalcular ambos lados, historial) ya lo
        hace generador_mover_renglones(); aquí solo se refrescan las
        pestañas de Generadores visibles afectadas."""
        api = getattr(self, '_api', None)
        if not api or not ids_arrastrados:
            return False
        ok = api.generador_mover_renglones(ids_arrastrados, generador_destino_id,
                                            antes_de_id, copiar)
        if not ok:
            return False
        tabs = getattr(self, '_tabs', None)
        if tabs is not None:
            for i in range(tabs.count()):
                w = tabs.widget(i)
                tabla = getattr(w, '_tabla_generador', None)
                if tabla is not None and tabla._generador_id is not None:
                    renglones = api.generador_renglones(tabla._generador_id)
                    tabla.poblar(renglones)
        return True

    # ── Handlers del visor CAD (actúan sobre la pestaña activa) ──────

    def _on_cad_abrir(self):
        """Abre un archivo DXF y lo carga en el visor de la pestaña de
        generador activa, ligando (persistiendo) la ruta a ese generador."""
        container = self._generador_tab_activo()
        if container is None:
            return
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
        self._cargar_dxf_en_tab(container, path)

    def _cargar_dxf_en_tab(self, container, path: str, silencioso: bool = False) -> None:
        """Carga un DXF en el visor de `container` y liga la ruta al
        generador (persiste en generadores.cad_archivo_path) para que se
        recupere sola la próxima vez que se abra esta pestaña.

        `silencioso=True` se usa al reabrir un generador con un DXF ya
        ligado: si el archivo se movió o se borró, no interrumpe con un
        diálogo de error, solo lo indica en la franja de estado."""
        try:
            from backend.cad.lector_dxf import parse_dxf
            result = parse_dxf(Path(path))
            if result.doc is not None:
                container._cad_viewer.set_document(result.doc)
            else:
                container._cad_viewer.set_entities(result.entities, result.layers)
            container._cad_layers = result.layers
            container._cad_entities_raw = [e.to_dict() for e in result.entities]
            container._cad_dxf_path = path
            if self._api:
                self._api.generador_actualizar_cad(container._generador_id, path)
        except Exception as e:
            if silencioso:
                container._cad_coords_lbl.setText(f"DXF no disponible: {Path(path).name}")
            else:
                QMessageBox.warning(self, "Error al abrir DXF", str(e))

    def _on_cad_tool(self, tool: str):
        container = self._generador_tab_activo()
        for t, btn in getattr(self, "_cad_tool_buttons", {}).items():
            if btn is not None:
                btn.setChecked(t == tool)
        if container is not None:
            container._cad_viewer.set_tool(tool)

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
        container = self._generador_tab_activo()
        self._on_cad_tool(CadTool.CALIBRATE)
        if container is not None:
            container._cad_coords_lbl.setText("Clic en punto A de referencia...")

    def _on_cad_fit(self):
        """Ajusta la vista para mostrar todas las entidades."""
        container = self._generador_tab_activo()
        if container is not None:
            container._cad_viewer.fit_in_view()

    def _on_cad_point(self, container, x: float, y: float):
        """Maneja clics en el visor CAD (referencia visual / medición)."""
        container._cad_coords_lbl.setText(f"X: {x:.4f}  Y: {y:.4f}")

    def _on_cad_measurement(self, container, valor: float, tipo: str):
        """Al terminar una medición en el visor, la liga a la celda que el
        usuario haya dejado seleccionada en la tabla de renglones de esta
        misma pestaña (Veces/Largo/Ancho/Alto). Punto y Contador acumulan
        (+1 por clic); Línea y Área sobrescriben con el valor recién medido."""
        tabla = container._tabla_generador
        modo = "sumar" if tipo in ("punto", "conteo") else "set"
        aplicado = tabla.aplicar_medicion(valor, modo=modo)
        if aplicado:
            container._cad_measurement_lbl.setText(f"✓ {valor:.4f} → celda")
            container._cad_measurement_lbl.setStyleSheet("color: #4CAF50; font-size: 10px;")
        else:
            container._cad_measurement_lbl.setText(
                "Selecciona Veces/Largo/Ancho/Alto para ligar"
            )
            container._cad_measurement_lbl.setStyleSheet("color: #FFA500; font-size: 10px;")

    def _on_cad_entity_clicked(self, container, handle: str):
        """Muestra qué entidad se seleccionó (herramienta Seleccionar)."""
        viewer = getattr(container, "_cad_viewer", None)
        if not viewer or not handle:
            return
        doc = getattr(viewer, "_doc", None)
        if doc is None:
            return
        entity = doc.entitydb.get(handle)
        if entity is None:
            return
        layer = entity.dxf.layer if entity.dxf.hasattr("layer") else "?"
        container._cad_coords_lbl.setText(f"{entity.dxftype()}  ·  capa: {layer}")

    # ── Handler de capas (popup) ──────────────────────────────────────

    def _on_cad_capas(self):
        """Abre diálogo de capas para encender/apagar."""
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
            QTableWidget, QTableWidgetItem, QAbstractItemView,
        )
        from PySide6.QtGui import QColor
        from backend.cad.lector_dxf import ACI_COLORS

        container = self._generador_tab_activo()
        if container is None:
            return
        viewer = container._cad_viewer

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

    # ── Cuantificacion y export ────────────────────────────────────────

    def _on_cad_cuantificar(self):
        """Auto-cuantifica entidades por capa y crea renglones en la
        pestaña de generador activa."""
        container = self._generador_tab_activo()
        if container is None or not self._api:
            return
        entities = container._cad_entities_raw
        if not entities:
            QMessageBox.information(self, "Cuantificar", "No hay entidades cargadas.")
            return

        from frontend.ventana.cad.auto_quantify import quantify_by_layer
        result = quantify_by_layer(entities, scale=1.0)
        gid = container._generador_id

        for r in result:
            self._api.generador_renglon_guardar(
                gid,
                eje=f"{r.layer} ({r.unit})",
                veces=1 if r.primary == "count" else None,
                largo=r.quantity if r.primary != "count" else None,
                ancho=None,
                alto=None,
            )

        renglones = self._api.generador_renglones(gid)
        container._tabla_generador.poblar(renglones)
        QMessageBox.information(
            self, "Cuantificar",
            f"{len(result)} capas procesadas, renglones creados.",
        )

    def _on_cad_export_pdf(self):
        """Exporta la vista actual del visor (de la pestaña activa) a PDF."""
        container = self._generador_tab_activo()
        if container is None:
            return
        from PySide6.QtCore import QByteArray, QBuffer, QIODevice
        pixmap = container._cad_viewer.viewport().grab()
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
        """Exporta cuantificacion por capa a Excel (pestaña activa)."""
        container = self._generador_tab_activo()
        if container is None:
            return
        entities = container._cad_entities_raw
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

    # ── Undo/Redo (por pestaña) ─────────────────────────────────────

    def _on_cad_undo(self):
        """Deshacer ultima anotacion en la pestaña activa."""
        container = self._generador_tab_activo()
        if container is None:
            return
        from frontend.ventana.cad.undo_stack import pop_undo, can_undo
        if can_undo(container._cad_undo_state):
            container._cad_undo_state, entry = pop_undo(container._cad_undo_state)
            self._apply_undo_entry(container, entry, undo=True)
            self._update_undo_buttons()

    def _on_cad_redo(self):
        """Rehacer anotacion deshecha en la pestaña activa."""
        container = self._generador_tab_activo()
        if container is None:
            return
        from frontend.ventana.cad.undo_stack import pop_redo, can_redo
        if can_redo(container._cad_undo_state):
            container._cad_undo_state, entry = pop_redo(container._cad_undo_state)
            self._apply_undo_entry(container, entry, undo=False)
            self._update_undo_buttons()

    def _apply_undo_entry(self, container, entry, undo: bool):
        """Aplica o revierte una entrada de undo."""
        if not entry:
            return
        if entry.kind == "create":
            item = container._cad_viewer._entity_items.get(entry.id)
            if item:
                item.setVisible(not undo)
        elif entry.kind == "delete" and not undo:
            pass  # re-creation would need snapshot data
        self._update_undo_buttons()

    def _update_undo_buttons(self):
        """Sincroniza los botones Deshacer/Rehacer CAD con el estado de
        la pestaña de generador activa (si no hay ninguna, los apaga)."""
        container = self._generador_tab_activo()
        btn_undo = getattr(self, "_cad_btn_undo", None)
        btn_redo = getattr(self, "_cad_btn_redo", None)
        from frontend.ventana.cad.undo_stack import can_undo, can_redo
        if container is None:
            if btn_undo is not None:
                btn_undo.setEnabled(False)
            if btn_redo is not None:
                btn_redo.setEnabled(False)
            return
        if btn_undo is not None:
            btn_undo.setEnabled(can_undo(container._cad_undo_state))
        if btn_redo is not None:
            btn_redo.setEnabled(can_redo(container._cad_undo_state))
