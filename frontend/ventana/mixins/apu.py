"""
apu_mixins.py
=============
Mixin de pestañas APU: desglose, edición inline, navegación a sub-APU.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""

from PySide6.QtCore import Qt, QTimer


class ApuMixin:
    """Mixin de APU — se mezcla en VentanaPrincipal."""

    def _build_apu_tab(self, matriz_id: int, descripcion: str = "", *,
                       resultado: dict | None = None):
        """Pestaña de desglose APU: componentes de un concepto o insumo compuesto.

        resultado opcional evita una segunda consulta a la API cuando quien
        llama ya lo obtuvo (ver _abrir_apu_resultado).
        Incluye una barra de filtros por tipo de insumo entre el encabezado
        y la tabla.
        """
        from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                                       QLabel, QPushButton, QFrame)
        from frontend.ventana.widgets.apu import TablaApuDetalle
        from frontend.ventana.widgets.apu import _TIPO_ID_TO_TOTALES_CLAVE
        from frontend.ventana.tipos_insumo import ICONO as _INS_ICONO
        from frontend.ventana.tipos_insumo import NOMBRES as _INS_NOMBRES

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(8, 4, 0, 4)
        lbl = QLabel()
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        hdr.addWidget(lbl, 1)
        layout.addLayout(hdr)
        layout.addSpacing(2)

        # ── Filter bar ─────────────────────────────────────────────
        filter_frame = QFrame()
        filter_frame.setObjectName("apuFilterBar")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(8, 2, 8, 2)
        filter_layout.setSpacing(6)
        layout.addWidget(filter_frame)
        layout.addSpacing(2)

        def _construir_filtros(subtotales: dict):
            if not subtotales:
                return
            while filter_layout.count():
                item = filter_layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

            def _set_filtro(tipo_id, clicked_btn):
                for i in range(filter_layout.count()):
                    w = filter_layout.itemAt(i).widget()
                    if isinstance(w, QPushButton):
                        w.setChecked(w is clicked_btn)
                detail.filtrar_por_tipo(tipo_id)

            # "Todos" button
            btn_todos = QPushButton("Todos")
            btn_todos.setCheckable(True)
            btn_todos.setChecked(True)
            STYLE = (
                "QPushButton{background:#005A9E;color:#fff;border:none;"
                "border-radius:4px;padding:3px 10px;font-size:12px}"
                "QPushButton:!checked{background:#2d2d2d;color:#E8EDF2;"
                "border:1px solid #3d3d3d}"
                "QPushButton:hover{border-color:#005A9E}"
            )
            btn_todos.setStyleSheet(STYLE)
            btn_todos.clicked.connect(
                lambda checked, b=btn_todos: _set_filtro(None, b))
            filter_layout.addWidget(btn_todos)

            # One button per tipo
            STYLE_INACTIVE = (
                "QPushButton{background:#2d2d2d;color:#E8EDF2;"
                "border:1px solid #3d3d3d;border-radius:4px;"
                "padding:3px 10px;font-size:12px}"
                "QPushButton:checked{background:#005A9E;color:#fff;"
                "border-color:#005A9E}"
                "QPushButton:hover{border-color:#005A9E}"
            )
            for tid in sorted(subtotales.keys()):
                subtotal = subtotales[tid]
                emoji = _INS_ICONO.get(tid, "")
                nombre = _INS_NOMBRES.get(tid, "")
                btn = QPushButton(f"{emoji} {nombre}  ${subtotal:,.2f}")
                btn.setCheckable(True)
                btn.setStyleSheet(STYLE_INACTIVE)
                btn.clicked.connect(
                    lambda checked, t=tid, b=btn: _set_filtro(t, b))
                filter_layout.addWidget(btn)

            filter_layout.addStretch(1)

        # ── Obtain resultado ───────────────────────────────────────
        if resultado is None:
            resultado = (self._api.apu(nodo_id=matriz_id) if matriz_id > 0
                         else self._api.apu(insumo_id=-matriz_id))

        # Initial filter bar
        tipos_ids = {r.get("tipo_id") for r in (resultado.get("detalle") or [])}
        totales_data = resultado.get("totales") or {}
        subtotales = {}
        for tid in tipos_ids:
            clave = _TIPO_ID_TO_TOTALES_CLAVE.get(tid)
            if clave:
                subtotales[tid] = totales_data.get(clave, 0)
        _construir_filtros(subtotales)

        # ── Table ──────────────────────────────────────────────────
        detail = TablaApuDetalle(matriz_id, descripcion,
                                 on_apu_click=self._abrir_apu_insumo)
        detail.resumen_actualizado.connect(lbl.setText)
        detail.tipos_actualizados.connect(_construir_filtros)
        detail.agregar_componente.connect(self._on_agregar_componente_apu)
        detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        detail.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(detail, pos))
        layout.addWidget(detail)
        container.setProperty("apu_matriz_id", matriz_id)

        # Ciclo de vida estándar (ver GUIA_INTERFAZ.md §7.6): poblar()
        # antes que conectar_eventos(). desconectar_eventos() no necesita
        # wiring aquí — _cerrar_tab_widget() ya recorre findChildren(QWidget)
        # y lo llama solo en cualquier hijo que lo tenga (ver handlers/__init__.py).
        detail.poblar(resultado)
        detail.conectar_eventos(self._event_bus, self._api)

        return container

    def _on_item_dblclick(self, item, column):
        """Doble clic en el árbol de presupuesto.

        Col 7 (P.U.) → abre APU del concepto.
        Col 4 (Descripción) en Concepto → abre selector de insumo.
        Col 6 (Cant) en Concepto con generadores → abre generadores.
        """
        from frontend.ventana.widgets.arbol import ID_ROLE
        nodo_id = item.data(0, ID_ROLE)
        if not nodo_id or not self._api:
            return

        if column == 6:
            if item.text(2) == "Concepto":
                gens = self._api.generadores_por_concepto(nodo_id)
                if gens:
                    wbs = item.text(1)
                    desc = item.text(4)
                    self._abrir_generadores_para_concepto(nodo_id, wbs, desc)
                return

        if self._es_pu(item, column):
            if nodo_id:
                self._abrir_apu_por_id(nodo_id)
            return

        if column == 4 and item.text(2) == "Concepto":
            from PySide6.QtWidgets import QDialog
            from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
            dlg = DialogoSeleccionarInsumo(self._api, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                nuevo_id = dlg.insumo_seleccionado
                if nuevo_id is not None:
                    self._api.concepto_reasignar_insumo(nodo_id, nuevo_id)

    def _abrir_apu_por_id(self, nodo_id: int):
        """Abre el APU de un concepto del árbol de presupuesto."""
        if not nodo_id or not self._api:
            return
        resultado = self._api.apu(nodo_id=nodo_id)
        self._abrir_apu_resultado(resultado, referencia=f"Concepto #{nodo_id}",
                                   id_fallback=f"#{nodo_id}")

    def _on_concepto_editado(self, item, column):
        """Persiste edición inline del árbol del presupuesto.

        No hace falta refrescar nada aquí a mano: DataService.actualizar()
        emite ConceptoActualizado/InsumoActualizado, y las mutaciones que
        cambian totales emiten además ProyectoRecalculado tras la cascada
        — el propio TablaArbol se suscribió a esos eventos al construirse
        y se actualiza in-place o se repuebla solo (ver arbol.py).
        """
        from frontend.ventana.widgets.arbol import ID_ROLE
        nodo_id = item.data(0, ID_ROLE)
        if nodo_id is None:
            return
        tipo = item.text(2)

        if column == 6:
            from PySide6.QtWidgets import QMessageBox
            from frontend.ventana.widgets.arbol import _num
            from frontend.ventana.widgets.base import FORMULA_ROLE
            texto = item.text(column).strip().replace(",", "")
            try:
                self._api.concepto_actualizar_cantidad(nodo_id, cantidad=0, formula=texto or None)
            except ValueError as e:
                QMessageBox.warning(self, "Fórmula inválida", str(e))
                tree = item.treeWidget()
                if tree:
                    tree.blockSignals(True)
                    nodo = self._api.campo_valor("estructura_presupuesto", "cantidad", nodo_id)
                    item.setText(6, _num((nodo or {}).get("cantidad")))
                    item.setData(6, FORMULA_ROLE, texto)
                    tree.blockSignals(False)
                    QTimer.singleShot(0, lambda t=tree, i=item, c=column: t.editItem(i, c))

        elif column == 4:
            if tipo == "Capítulo":
                self._api.agrupador_actualizar_descripcion(nodo_id, item.text(column))
            else:
                from PySide6.QtWidgets import QMessageBox
                try:
                    self._api.concepto_actualizar_descripcion(nodo_id, item.text(column))
                except ValueError as e:
                    QMessageBox.warning(self, "Descripción duplicada", str(e))
                    tree = item.treeWidget()
                    tree.blockSignals(True)
                    item.setText(column, self._api.nodo_descripcion_actual(nodo_id))
                    tree.blockSignals(False)

        elif column == 5:
            if tipo == "Concepto":
                self._api.concepto_actualizar_unidad(nodo_id, item.text(column))

        elif column == 10:
            self._api.concepto_actualizar(nodo_id, notas_rapidas=item.text(column).strip() or None)

    @staticmethod
    def _es_pu(item, column) -> bool:
        """Detecta si la columna contiene 'PU' o 'PRECIO'."""
        tw = item.treeWidget()
        if not tw:
            return False
        h = tw.headerItem().text(column).replace(".", "").upper()
        return "PU" in h or "PRECIO" in h

    def _abrir_apu_insumo(self, insumo_id: int):
        """Abre el APU de un insumo compuesto del catálogo."""
        if not insumo_id or not self._api:
            return
        resultado = self._api.apu(insumo_id=insumo_id)
        self._abrir_apu_resultado(resultado, referencia=f"Insumo #{insumo_id}",
                                   id_fallback=f"#{insumo_id}")

    def _abrir_popup_presupuesto(self):
        """Abre el presupuesto en una ventana emergente no modal."""
        from frontend.ventana.widgets.presupuesto_popup import PresupuestoPopup
        existing = getattr(self, '_popup_presupuesto', None)
        if existing:
            try:
                if existing.isVisible():
                    existing.raise_()
                    existing.activateWindow()
                    return
            except RuntimeError:
                pass  # C++ object was deleted (WA_DeleteOnClose)
        self._popup_presupuesto = PresupuestoPopup(self._api, self._event_bus, self)
        self._popup_presupuesto.show()

    def _abrir_apu_resultado(self, resultado, *, referencia: str, id_fallback: str):
        """Punto único que arma o enfoca la pestaña de un APU ya resuelto.

        Si ya hay una pestaña abierta para esta misma matriz, se
        RECONSTRUYE (no solo se enfoca): antes solo hacía setCurrentIndex
        sobre el widget existente, que había quedado poblado con los datos
        de cuando se abrió por primera vez y nunca se refrescaba — daba la
        sensación de que una edición "revertía" al reabrir el APU, cuando
        en realidad la base de datos sí tenía el valor nuevo, solo que esta
        pestaña nunca volvía a consultarla.
        """
        if not resultado:
            self._sb.showMessage(f"{referencia} no tiene matriz relacionada", 4000)
            return
        matriz_id   = resultado["matriz_id"]
        descripcion = resultado.get("descripcion", "") or ""
        title = f"APU: {descripcion[:30]}" if descripcion else f"APU: {id_fallback}"

        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._cerrar_tab_widget(i)
                idx = self._tabs.insertTab(i, self._build_apu_tab(matriz_id, descripcion, resultado=resultado), title)
                self._tabs.setCurrentIndex(idx)
                return
        idx = self._tabs.addTab(self._build_apu_tab(matriz_id, descripcion, resultado=resultado), title)
        self._tabs.setCurrentIndex(idx)

    def _on_agregar_componente_apu(self, matriz_id: int):
        """Selecciona insumo y lo agrega como componente al APU."""
        from PySide6.QtWidgets import QDialog
        from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
        api = getattr(self, '_api', None)
        if not api:
            return
        dlg = DialogoSeleccionarInsumo(api, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        insumo_id = dlg.insumo_seleccionado
        if insumo_id is None:
            return
        api.apu_agregar_componente(matriz_id, insumo_id)
