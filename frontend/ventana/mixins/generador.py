"""
generador.py
============
Mixin de generadores de obra para VentanaPrincipal.

Los generadores viven en su PROPIO espacio de trabajo (self._tabs_generadores
+ self._renglones_stack, dentro de self._central_stack indice 1 -- ver
_build_espacio_generadores() y _build_central() en ventana.py), separado
de las pestanas normales de contenido (Presupuesto, Insumos...). Entrar a
la cinta GENERADORES cambia a ese espacio; "Volver al presupuesto" (o
clicar cualquier otra pestana de la cinta) regresa al espacio normal --
ver _switch_tab en toolbar.py.

Cada generador tiene su propia pestana de generador (con su visor CAD) y
su propio panel de renglones (Eje/Tramo/Veces/Largo/Ancho/Alto), que se
muestra en self._renglones_stack sincronizado con la pestana activa en
self._tabs_generadores (ver _on_tab_generador_changed). Cada pestana
tiene su propio visor CAD independiente -- puede tener un DXF distinto
abierto, ligado (persistido en generadores.cad_archivo_path) a ESE
generador especifico, y se recarga solo la proxima vez que se abre esa
pestana.

Puntos de entrada para abrir un generador (siempre en su propia
pestana; reabrir uno ya abierto solo lo enfoca):
  - Menu contextual "Abrir generador" sobre un concepto, en el arbol de
    Presupuesto normal (ver widgets/arbol.py -> TablaArbol.abrir_generador
    -> _on_abrir_generador).
  - Doble clic en la columna Cantidad de un concepto que ya tiene
    generadores (ver mixins/apu.py -> _on_item_dblclick).
  - Boton "Generadores" del ribbon INICIO -> crea un generador suelto
    ("Extraordinario", sin concepto) y lo abre en pestana nueva.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QHeaderView, QFileDialog, QStackedWidget,
    QSplitter, QComboBox,
)

from frontend.ventana.widgets.generador import TablaGenerador, medidas_efectivas
from frontend.ventana.widgets.base import EMPTY_ROLE, TabWidgetCerrable
from frontend.ventana.cad.visor import VisorCadWidget, CadTool


class GeneradorMixin:
    """Mixin de generadores de obra — se mezcla en VentanaPrincipal."""

    # ── Helpers de la pestaña de generador activa ──────────────────

    def _build_espacio_generadores(self) -> QWidget:
        """Construye la pagina 1 de self._central_stack (ver
        _build_central en ventana.py): panel de renglones del generador
        activo a la izquierda, pestanas de generadores abiertos a la
        derecha -- el mismo layout sidebar|contenido de siempre, pero
        dedicado por completo a generadores, sin mezclarse con
        Presupuesto/Insumos/APU.
        """
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._renglones_stack = QStackedWidget()
        placeholder = QWidget()
        pl = QVBoxLayout(placeholder)
        lbl = QLabel("Abre un generador para ver sus renglones aqui.")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pl.addWidget(lbl)
        self._renglones_stack.addWidget(placeholder)  # indice 0 = nada abierto todavia
        splitter.addWidget(self._renglones_stack)

        self._tabs_generadores = TabWidgetCerrable()
        self._tabs_generadores.tabCloseRequested.connect(self._on_tab_close_generador)
        self._tabs_generadores.currentChanged.connect(self._on_tab_generador_changed)
        splitter.addWidget(self._tabs_generadores)

        splitter.setCollapsible(0, False)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        splitter.setSizes([380, 1020])
        self._espacio_generadores_splitter = splitter
        return splitter

    def _on_tab_generador_changed(self, idx: int):
        """Al cambiar de pestana dentro del espacio de Generadores,
        muestra en self._renglones_stack el panel de renglones del
        generador que quedo activo, y sincroniza Deshacer/Rehacer CAD
        (cada generador tiene su propio undo stack — ver
        _update_undo_buttons)."""
        stack = getattr(self, "_renglones_stack", None)
        tabs = getattr(self, "_tabs_generadores", None)
        if stack is None or tabs is None:
            return
        if idx < 0:
            stack.setCurrentIndex(0)  # placeholder "abre un generador..."
        else:
            widget = tabs.widget(idx)
            rp = getattr(widget, "_renglones_panel", None)
            if rp is not None and stack.indexOf(rp) >= 0:
                stack.setCurrentWidget(rp)
        if hasattr(self, "_update_undo_buttons"):
            self._update_undo_buttons()

    def _on_tab_close_generador(self, idx: int):
        """Cierra una pestana de generador -- misma proteccion contra
        widgets "zombis" que _cerrar_tab_widget usa para self._tabs (ver
        navegacion.py), aplicada aca a self._tabs_generadores."""
        tabs = getattr(self, "_tabs_generadores", None)
        stack = getattr(self, "_renglones_stack", None)
        if tabs is None:
            return
        widget = tabs.widget(idx)
        if widget is not None:
            for hijo in widget.findChildren(QWidget):
                if hasattr(hijo, "desconectar_eventos"):
                    hijo.desconectar_eventos()
            rp = getattr(widget, "_renglones_panel", None)
            if rp is not None and stack is not None and stack.indexOf(rp) >= 0:
                stack.removeWidget(rp)
        tabs.removeTab(idx)

    def _on_volver_presupuesto(self):
        """Boton "Volver al presupuesto" (cinta GENERADORES) -- regresa
        a la cinta/pestana que estaba activa antes de entrar a
        Generadores (ver _switch_tab en toolbar.py, que guarda
        self._tab_antes_generadores al entrar)."""
        destino = getattr(self, "_tab_antes_generadores", None) or "PRINCIPAL"
        self._switch_tab(destino)

    def _generador_tab_activo(self):
        """Contenedor de la pestaña de generador actualmente enfocada
        dentro del espacio de Generadores (self._tabs_generadores — ver
        _build_espacio_generadores), o None si no hay ninguna abierta."""
        tabs = getattr(self, "_tabs_generadores", None)
        if tabs is None:
            return None
        w = tabs.currentWidget()
        return w if getattr(w, "_es_generador_tab", False) else None

    def _generador_tab_por_id(self, generador_id: int):
        """Busca, entre las pestañas de generador abiertas
        (self._tabs_generadores), la de un generador dado."""
        tabs = getattr(self, "_tabs_generadores", None)
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
                from frontend.ventana.ui_utils import confirmar
                resp = confirmar(
                    self, "Vincular generador",
                    f"El concepto ya tiene una cantidad de {cant}.\n"
                    "¿Deseas borrarla y vincular la cantidad al generador?",
                    "Vincular", destructivo=False,
                )
                if not resp:
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
        self._abrir_generador_tab(gen_id, f"Extraordinario {n} (sin concepto)")

    def _abrir_generador_tab(self, generador_id: int, nombre: str = ""):
        """Abre (o enfoca, si ya está abierta) la pestaña de este
        generador dentro de su propio espacio de trabajo
        (self._tabs_generadores — ver _build_espacio_generadores), y
        cambia la cinta a GENERADORES para que ese espacio quede a la
        vista de inmediato (antes había que además hacer clic manual en
        la pestaña GENERADORES del ribbon después de abrir uno). Cada
        generador vive por completo en su propia pestaña, con su propio
        visor CAD — reabrir uno ya abierto solo lo enfoca, nunca
        duplica la pestaña."""
        if not self._api:
            return
        existente = self._generador_tab_por_id(generador_id)
        if existente is not None:
            idx = self._tabs_generadores.indexOf(existente)
            if idx >= 0:
                self._tabs_generadores.setCurrentIndex(idx)
            self._switch_tab("GENERADORES")
            return
        gen = self._api.generador_por_id(generador_id)
        if not gen:
            return
        titulo = nombre or gen.get("nombre") or f"Generador #{generador_id}"
        contenido = self._build_generador_tab(generador_id, gen, nombre)
        # El panel de renglones se agrega a self._renglones_stack ANTES
        # de addTab(): en un QTabWidget vacío, addTab() de la primera
        # pestaña ya dispara currentChanged(0) por su cuenta (Qt la deja
        # seleccionada sola) — si el panel todavía no estuviera en el
        # stack en ese momento, _on_tab_generador_changed no encontraría
        # nada que mostrar para esa primera pestaña.
        rp = getattr(contenido, "_renglones_panel", None)
        if rp is not None:
            rp.setParent(None)
            self._renglones_stack.addWidget(rp)
        idx = self._tabs_generadores.addTab(contenido, titulo)
        self._tabs_generadores.setCurrentIndex(idx)
        self._on_tab_generador_changed(idx)  # por si setCurrentIndex no re-disparó currentChanged
        self._switch_tab("GENERADORES")

    # ── Construcción de la pestaña: CAD (renglones van a su propio stack) ─

    def _build_generador_tab(self, generador_id: int, gen: dict, nombre: str) -> QWidget:
        """Contenedor de UN generador: visor CAD propio. Los renglones
        de medición se muestran en self._renglones_stack (dentro del
        espacio de Generadores, no de la pestaña misma) — ver
        _abrir_generador_tab / _on_tab_generador_changed."""
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

        # Traza tabla↔plano: seleccionar una fila resalta TODAS sus
        # mediciones en el visor (una fila puede tener Largo, Ancho y
        # Alto medidos cada uno con su propia línea); clickear un trazo
        # específico en el visor selecciona su fila.
        viewer = container._cad_viewer
        tabla = container._tabla_generador
        tabla.renglon_seleccionado.connect(viewer.resaltar_renglon)
        viewer.medicion_click.connect(lambda rid, campo, t=tabla: t.seleccionar_renglon_por_id(rid))
        viewer.medicion_editada.connect(
            lambda rid, campo, valor, pts, c=container: self._on_medicion_editada(c, rid, campo, valor, pts))

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
                CadTool.SELECT:   tips.get("Seleccionar"),
                CadTool.LINE:     tips.get("Línea"),
                CadTool.POLYLINE: tips.get("Polilínea"),
                CadTool.POLYGON:  tips.get("Área"),
                CadTool.COUNT:    tips.get("Contar"),
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

        # Selector explícito de a qué celda va la próxima medición
        # (Veces/Largo/Ancho/Alto). ANTES se usaba silenciosamente la
        # celda que tuviera el foco en la tabla (currentColumn()) — pero
        # el foco se pierde en cuanto se clickea el visor CAD para
        # dibujar, así que terminaba dependiendo de detalles de Qt poco
        # confiables (qué celda quedó "actual" antes de perder el foco).
        # Con un selector explícito, la celda destino no depende de eso:
        # se elige aquí y se queda así hasta que se cambie a mano.
        status_bar.addWidget(QLabel("Medir hacia:"))
        combo_campo = QComboBox()
        combo_campo.addItem("Veces", 2)
        combo_campo.addItem("Largo", 3)
        combo_campo.addItem("Ancho", 4)
        combo_campo.addItem("Alto", 5)
        combo_campo.setCurrentIndex(1)  # Largo, el más común, como default
        combo_campo.setFixedWidth(90)
        status_bar.addWidget(combo_campo)
        container._cad_campo_combo = combo_campo

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
        viewer.measurement_ready.connect(
            lambda v, t, tc, pts, c=container: self._on_cad_measurement(c, v, t, tc, pts))
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
        header.addStretch()
        layout.addLayout(header)

        tabla = TablaGenerador(generador_id=container._generador_id)
        tabla.renglon_editado.connect(
            lambda rid, campos, c=container: self._on_renglon_editado_tab(c, rid, campos))
        tabla.renglon_eliminar.connect(
            lambda ids, c=container: self._eliminar_renglones_tab(c, ids))
        tabla.delete_solicitado.connect(
            lambda ids, c=container: self._on_delete_solicitado_tab(c, ids))
        tabla.total_actualizado.connect(
            lambda total, c=container: self._actualizar_encabezado_generador(c, total))
        tabla.nuevo_renglon.connect(lambda c=container: self._on_renglon_nuevo_tab(c))
        tabla.renglon_nuevo.connect(
            lambda campos, c=container: self._on_renglon_nuevo_tab(c, campos))
        layout.addWidget(tabla, 1)
        container._tabla_generador = tabla
        # Fase C: refresco remoto vía EventBus (GeneradorActualizado /
        # ProyectoRecalculado). La desconexión al cerrar la pestaña ya
        # existe (_cerrar_generador_tab via duck-typing hasattr).
        _bus = getattr(self, "_event_bus", None)
        _api = getattr(self, "_api", None)
        if _bus is not None and _api is not None:
            tabla.conectar_eventos(_bus, _api)

        return w

    # ── Encabezado (nombre + medido) ─────────────────────────────────

    def _actualizar_encabezado_generador(self, container, total: float):
        base = container._nombre_base
        unidad = container._unidad_activa or ""
        sufijo = f" {unidad}" if unidad else ""
        container._concepto_lbl.setText(f"{base}  —  Medido: {total:,.2f}{sufijo}")

    # ── Handlers de renglones (por pestaña) ──────────────────────────

    def _on_renglon_nuevo_tab(self, container, campos: dict | None = None) -> None:
        """Agrega un renglón nuevo. `campos` (de renglon_nuevo, al escribir
        en la fila vacía — ver TablaGenerador._on_fila_vacia_editada) ya
        trae los valores tecleados; sin `campos` (Insert, o el signal
        viejo sin argumentos nuevo_renglon) crea un renglón en blanco,
        igual que antes.

        Diferido a propósito (mismo motivo que _on_renglon_editado_tab más
        abajo): esto se dispara DENTRO de la cadena de itemChanged de la
        fila vacía — si poblar() corriera aquí mismo, destruiría ese mismo
        QTreeWidgetItem que Qt todavía está procesando, y cualquier
        Tab/Enter que el usuario ya haya iniciado para pasar a la
        siguiente celda operaría sobre un item eliminado.
        """
        if not self._api:
            return
        gid = container._generador_id
        nuevo_id = self._api.generador_renglon_guardar(gid, **(campos or {}))
        QTimer.singleShot(0, lambda: self._refrescar_generador_tab_seguro_sel(container, gid, nuevo_id))

    def _refrescar_generador_tab_seguro_sel(self, container, generador_id: int, seleccionar_id: int) -> None:
        if not self._api or container._generador_id != generador_id:
            return
        renglones = self._api.generador_renglones(generador_id)
        container._tabla_generador.poblar(renglones, seleccionar_id=seleccionar_id)
        self._refrescar_overlay_cad(container, renglones)

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
        self._refrescar_overlay_cad(container, renglones)

    def _refrescar_overlay_cad(self, container, renglones: list[dict]) -> None:
        """Vuelve a dibujar en el visor de esta pestaña el trazo
        persistente de cada renglón con origen="cad" (ver
        VisorCadWidget.set_medicion_overlays). Se llama en cada refresco
        de la tabla para que el plano nunca quede desincronizado: un
        renglón borrado hace desaparecer su trazo, uno medido o editado
        aparece o se corrige de inmediato."""
        viewer = getattr(container, "_cad_viewer", None)
        if viewer is None:
            return
        archivo = Path(container._cad_dxf_path).name if getattr(container, "_cad_dxf_path", None) else None
        viewer.set_medicion_overlays(renglones, archivo_actual=archivo)

    def _eliminar_renglones_tab(self, container, ids: list[int]) -> None:
        """Elimina un bloque de renglones (ya confirmado por
        _on_delete_solicitado_tab) y refresca la tabla de esta pestaña."""
        if not ids or not self._api:
            return
        for rid in ids:
            self._api.generador_renglon_eliminar(rid)
        renglones = self._api.generador_renglones(container._generador_id)
        container._tabla_generador.poblar(renglones)
        self._refrescar_overlay_cad(container, renglones)

    def _on_delete_solicitado_tab(self, container, ids: list[int]) -> None:
        """Confirma antes de eliminar (Delete, o el ítem "Eliminar" del
        menú contextual — ver conectar_mixins/_HANDLERS_ESTANDAR en
        arbol.py para el patrón equivalente en Presupuesto)."""
        texto = ("¿Eliminar este renglón del generador?" if len(ids) == 1 else
                 f"¿Eliminar estos {len(ids)} renglones del generador?")
        from frontend.ventana.ui_utils import confirmar
        if not confirmar(self, "Eliminar renglón(es)", texto, "Eliminar", destructivo=True):
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
                    self._refrescar_overlay_cad(w, renglones)
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
            if result.doc is None:
                # parse_dxf() de hoy siempre devuelve un ezdxf.Drawing
                # válido en doc — esta rama no debería ejecutarse nunca en
                # la práctica. Pero `DxfParseResult.doc` está tipado como
                # `object | None`, así que si algún parser futuro (o un
                # test) construye un resultado sin `doc`, antes esto caía
                # en set_entities(), que es un compat shim que NO dibuja
                # nada (ver visor.py) — el DXF se "cargaba" sin ningún
                # aviso y el visor quedaba vacío. Lo convertimos en un
                # error explícito que cae en el except de abajo, en vez de
                # fallar en silencio (Hallazgo 13 de la auditoría).
                raise ValueError(
                    "El parser no generó un documento DXF renderizable "
                    "(result.doc es None). No se puede mostrar este archivo "
                    "en el visor."
                )
            container._cad_viewer.set_document(result.doc)
            container._cad_layers = result.layers
            container._cad_entities_raw = [e.to_dict() for e in result.entities]
            container._cad_dxf_path = path
            # Redibuja sobre el plano, de forma persistente, el trazo de
            # cada renglón ya medido en este generador (ver
            # set_medicion_overlays en visor.py) — set_document() acaba de
            # limpiar toda la escena, así que hay que reponerlos.
            renglones = self._api.generador_renglones(container._generador_id)
            container._cad_viewer.set_medicion_overlays(
                renglones, archivo_actual=Path(path).name)
            if self._api:
                self._api.generador_actualizar_cad(container._generador_id, path)
        except Exception as e:
            if silencioso:
                container._cad_coords_lbl.setText(f"DXF no disponible: {Path(path).name}")
            else:
                from frontend.ventana.ui_utils import mostrar_error
                mostrar_error(self, "Error al abrir DXF", e, critico=False)

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

    def _on_cad_tool_polyline(self):
        self._on_cad_tool(CadTool.POLYLINE)

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

    def _on_cad_measurement(self, container, valor: float, tipo: str,
                             tipo_cad: str, puntos: list):
        """Al terminar una medición en el visor, la liga a la celda que el
        usuario haya elegido en el selector "Medir hacia" del panel CAD
        (Veces/Largo/Ancho/Alto) — ya NO depende de cuál celda de la
        tabla haya quedado "actual" antes de perder el foco al clickear
        el visor, que es lo que hacía que todo terminara en una sola
        columna sin importar la intención. Punto y Contador acumulan
        (+1 por clic); Línea, Polilínea y Área sobrescriben con el valor
        recién medido.

        tipo_cad + puntos: de dónde salió la medición en el dibujo (ver
        aplicar_medicion en widgets/generador.py) — se guardan junto con
        el valor para poder auditar el renglón después.
        """
        tabla = container._tabla_generador
        modo = "sumar" if tipo in ("punto", "conteo") else "set"
        archivo = Path(container._cad_dxf_path).name if getattr(container, "_cad_dxf_path", None) else None
        col = container._cad_campo_combo.currentData()
        renglon_id = tabla.aplicar_medicion(valor, modo=modo, tipo_cad=tipo_cad,
                                             puntos=puntos, archivo=archivo, col=col)
        if renglon_id is not None:
            container._cad_measurement_lbl.setText(f"{valor:.4f} → celda")
            container._cad_measurement_lbl.setStyleSheet("color: #4CAF50; font-size: 10px;")
            # Línea/Polilínea/Área quedan trazadas de una sola vez (no como
            # Punto/Contador, que se van acumulando clic a clic) — apenas se
            # suelta el trazo, lo más útil es poder corregir sus nodos, no
            # seguir dibujando encima. Se cambia sola a Seleccionar y se
            # muestran sus grips, para no obligar a cambiar de herramienta
            # a mano cada vez que se quiere ajustar lo recién medido.
            if tipo_cad in ("linea", "polilinea", "area"):
                # Diferido: aplicar_medicion() ya disparó renglon_editado,
                # que a su vez difirió (QTimer.singleShot) el refresco de
                # la tabla Y del overlay del plano (_refrescar_overlay_cad)
                # — si se seleccionara aquí mismo, el renglón recién
                # medido todavía no existiría en self._overlays_data del
                # visor y no se verían los grips. Se encola con el mismo
                # delay 0 para correr justo después.
                campo = {2: "veces", 3: "largo", 4: "ancho", 5: "alto"}.get(col)
                QTimer.singleShot(
                    0, lambda c=container, rid=renglon_id, cp=campo:
                        self._activar_edicion_medicion(c, rid, cp))
        else:
            container._cad_measurement_lbl.setText(
                "Selecciona un renglón en la tabla para ligar"
            )
            container._cad_measurement_lbl.setStyleSheet("color: #FFA500; font-size: 10px;")

    def _activar_edicion_medicion(self, container, renglon_id: int, campo: str) -> None:
        """Cambia a la herramienta Seleccionar y muestra los grips de la
        medición recién hecha (renglon_id, campo) — ver el llamado
        diferido en _on_cad_measurement."""
        self._on_cad_tool(CadTool.SELECT)
        container._cad_viewer.seleccionar_medicion((renglon_id, campo))

    def _on_medicion_editada(self, container, renglon_id: int, campo: str, valor: float, puntos: list) -> None:
        """Al soltar un grip en el visor (mover, agregar o borrar un nodo
        de una medición ya guardada): persiste el valor recalculado en
        la entrada de cad_medidas para ESE campo exacto — sin tocar las
        mediciones de las otras celdas del mismo renglón (ver
        medidas_efectivas), y sin cambiar nunca a qué celda apunta."""
        if not self._api:
            return
        gid = container._generador_id
        renglones = self._api.generador_renglones(gid)
        rn = next((r for r in renglones if r.get("id") == renglon_id), None)
        if rn is None:
            return
        medidas = medidas_efectivas(rn)
        info = dict(medidas.get(campo) or {})
        info["puntos"] = puntos
        medidas[campo] = info
        import json
        self._api.generador_renglon_guardar(
            gid, renglon_id=renglon_id,
            **{campo: valor, "cad_medidas": json.dumps(medidas)},
        )
        self._refrescar_generador_tab_seguro(container, gid)

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
            self._sb.showMessage("No hay capas disponibles.", 3000)
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
            self._sb.showMessage("No hay entidades cargadas.", 3000)
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
        self._sb.showMessage(f"{len(result)} capas procesadas, renglones creados.", 4000)

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
            self._sb.showMessage(f"PDF exportado: {result_path}", 5000)
        except Exception as e:
            from frontend.ventana.ui_utils import mostrar_error
            mostrar_error(self, "Error al exportar PDF", e, critico=False)

    def _on_cad_export_excel(self):
        """Exporta cuantificacion por capa a Excel (pestaña activa)."""
        container = self._generador_tab_activo()
        if container is None:
            return
        entities = container._cad_entities_raw
        if not entities:
            self._sb.showMessage("No hay entidades cargadas.", 3000)
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
            self._sb.showMessage(f"Excel exportado: {result_path}", 5000)
        except Exception as e:
            from frontend.ventana.ui_utils import mostrar_error
            mostrar_error(self, "Error al exportar Excel", e, critico=False)

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
