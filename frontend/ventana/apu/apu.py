"""
apu_mixins.py
=============
Mixin de pestañas APU: desglose, edición inline, navegación a sub-APU.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""

from PySide6.QtCore import Qt


class ApuMixin:
    """Mixin de APU — se mezcla en VentanaPrincipal."""

    def _build_apu_tab(self, matriz_id: int, descripcion: str = ""):
        """Pestaña de desglose APU: componentes de un concepto o insumo compuesto.

        Arma el contenedor (encabezado con título/total + botón "abrir
        presupuesto en popup") y le mete una TablaApuDetalle (ver
        frontend/ventana/widgets/apu.py) — la parte con estado (filas,
        suscripción a eventos, edición) vive ahí como clase propia, ya no
        aquí como closures (ver docs/PLAN_REPARACION.md #21).
        """
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from frontend.ventana.widgets.apu import TablaApuDetalle

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

        btn_presupuesto = QPushButton("📋")
        btn_presupuesto.setFixedSize(28, 28)
        btn_presupuesto.setToolTip("Abrir presupuesto en ventana emergente")
        btn_presupuesto.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_presupuesto.clicked.connect(self._abrir_popup_presupuesto)
        hdr.addWidget(btn_presupuesto)

        layout.addLayout(hdr)
        layout.addSpacing(2)

        detail = TablaApuDetalle(matriz_id, descripcion, on_apu_click=self._abrir_apu_insumo)
        detail.resumen_actualizado.connect(lbl.setText)
        detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        detail.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(detail, pos))
        layout.addWidget(detail)
        container.setProperty("apu_matriz_id", matriz_id)

        # Ciclo de vida estándar (ver GUIA_INTERFAZ.md §7.6): poblar()
        # antes que conectar_eventos(). desconectar_eventos() no necesita
        # wiring aquí — _cerrar_tab_widget() ya recorre findChildren(QWidget)
        # y lo llama solo en cualquier hijo que lo tenga (ver handlers/__init__.py).
        detail.poblar(
            self._api.apu(nodo_id=matriz_id) if matriz_id > 0
            else self._api.apu(insumo_id=-matriz_id)
        )
        detail.conectar_eventos(self._event_bus, self._api)

        return container

    def _on_item_dblclick(self, item, column):
        """Doble clic en el árbol de presupuesto.

        Col 7 (P.U.) → abre APU del concepto.
        Col 4 (Descripción) en Concepto → abre selector de insumo.
        """
        from frontend.ventana.widgets.arbol import ID_ROLE
        if self._es_pu(item, column):
            nodo_id = item.data(0, ID_ROLE)
            if nodo_id:
                self._abrir_apu_por_id(nodo_id)
            return

        if column == 4 and item.text(2) == "Concepto":
            nodo_id = item.data(0, ID_ROLE)
            if not nodo_id or not self._api:
                return
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
            try:
                texto = item.text(column).strip().replace("$", "")
                if texto.count(",") == 1 and texto.count(".") == 0:
                    texto = texto.replace(",", ".")
                else:
                    texto = texto.replace(",", "")
                cantidad = float(texto)
            except ValueError:
                return
            self._api.concepto_actualizar_cantidad(nodo_id, cantidad)

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
                idx = self._tabs.insertTab(i, self._build_apu_tab(matriz_id, descripcion), title)
                self._tabs.setCurrentIndex(idx)
                return
        idx = self._tabs.addTab(self._build_apu_tab(matriz_id, descripcion), title)
        self._tabs.setCurrentIndex(idx)