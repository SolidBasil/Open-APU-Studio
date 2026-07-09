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

        A diferencia de TablaArbol/TablaInsumos (Fase 3), esta pestaña no es
        una clase propia — es un QWidget armado aquí mismo. Para poder
        suscribirla al EventBus igual que las otras, la función interna
        _refrescar() hace las veces de "poblar()": puede llamarse tanto al
        construir como cada vez que llega un evento relevante, y siempre
        vuelve a consultar la fuente de verdad (api.apu()) en vez de
        confiar en aritmética local — así el total del encabezado y el
        importe de cada fila quedan consistentes con lo que de verdad
        recalculó RecalculoRepo (incluyendo casos como herramienta, cuyo
        importe NO es valor×precio sino un % del subtotal de mano de obra).
        """
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QHeaderView
        from PySide6.QtCore import QTimer
        from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef

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

        def _editable_cols_detalle(item):
            # ponytail: descripción y unidad se editan vía popup (doble clic),
            # no inline — misma filosofía que el árbol de presupuesto.
            if item.data(0, Qt.ItemDataRole.UserRole + 1):
                return {5, 6}
            return {4, 5, 6}

        def _combo_operador(parent):
            from PySide6.QtWidgets import QComboBox
            combo = QComboBox(parent)
            combo.setEditable(False)
            combo.addItems(["*", "/"])
            return combo

        def _combo_unidad(parent):
            from PySide6.QtWidgets import QComboBox
            from frontend.ventana.widgets.base import UNIDADES
            combo = QComboBox(parent)
            combo.setEditable(False)
            combo.addItems(UNIDADES)
            return combo

        detail = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "Unidad", "P.U.", "Op", "Valor", "Importe",
             "Fórmula", "Creado", "Modificado"],
            flat=True,
            editable_cols=frozenset({5}),
            editable_cols_fn=_editable_cols_detalle,
            column_editors={3: _combo_unidad, 5: _combo_operador},
        )
        # Catálogo de favoritas + "Personalizar columnas…" (ver base.py).
        # Esta tabla no es una subclase propia de TreeTableWidget — se arma
        # inline aquí — así que el catálogo se inyecta como atributo de
        # instancia en vez de heredarlo como class var, mismo patrón que ya
        # usa este archivo para desconectar_eventos() más abajo.
        detail._CATALOGO_KEY = "apu_columnas_favoritas"
        detail._HEADER_KEY = "apu_header_state"
        detail.COLUMNAS_CATALOGO = [
            ColumnaDef(0, "Tipo",        "Identificación", favorita_default=True,  visible_default=True),
            ColumnaDef(1, "Clave",       "Identificación", favorita_default=True,  visible_default=True),
            ColumnaDef(2, "Descripción", "Identificación", favorita_default=True,  visible_default=True),
            ColumnaDef(3, "Unidad",      "Identificación", favorita_default=True,  visible_default=True),
            ColumnaDef(4, "P.U.",        "Costos",         favorita_default=True,  visible_default=True),
            ColumnaDef(5, "Op",          "Cálculo",        favorita_default=True,  visible_default=True),
            ColumnaDef(6, "Valor",       "Cálculo",        favorita_default=True,  visible_default=True),
            ColumnaDef(7, "Importe",     "Cálculo",        favorita_default=True,  visible_default=True),
            ColumnaDef(8, "Fórmula",     "Cálculo",        favorita_default=False, visible_default=False),
            ColumnaDef(9, "Creado",      "Auditoría",      favorita_default=False, visible_default=False),
            ColumnaDef(10, "Modificado", "Auditoría",      favorita_default=False, visible_default=False),
        ]
        detail.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([110, 90, 250, 50, 100, 40, 80, 110, 160, 130, 130])
        })
        detail.header().setMaximumSectionSize(400)
        detail._applying_modes = True
        for col in detail.COLUMNAS_CATALOGO:
            detail.setColumnHidden(col.idx, not col.visible_default)
        detail._applying_modes = False

        def _consultar():
            if not self._api:
                return None
            return self._api.apu(nodo_id=matriz_id) if matriz_id > 0 else self._api.apu(insumo_id=-matriz_id)

        def _refrescar():
            """Vuelve a consultar la API y repuebla filas + total, preservando
            selección/scroll. Se llama al construir y ante cada evento suscrito."""
            resultado = _consultar()

            total = 0.0
            if resultado:
                totales = resultado.get("totales")
                if totales and totales.get("costo_directo") is not None:
                    total = totales["costo_directo"]
                else:
                    total = sum(r.get("importe", 0) or 0 for r in resultado.get("detalle", []))
            lbl.setText(f"<b>{descripcion or f'Matriz #{matriz_id}'}</b> — Total: ${total:,.2f}")

            scroll_y = detail.verticalScrollBar().value()
            comp_actual = detail.currentItem().data(5, Qt.ItemDataRole.UserRole) \
                if detail.currentItem() else None
            col_actual = detail.currentColumn() if detail.currentItem() else 0

            detail.blockSignals(True)
            try:
                detail.clear()
                if resultado:
                    for r in resultado["detalle"]:
                        tid = r["tipo_id"]
                        tn  = r["tipo_nombre"]
                        es_compuesto = bool(r.get("tiene_sub_apu"))
                        row_item = detail.add_row([
                            f"{r['tipo_emoji']} {tn}".strip() if r["tipo_emoji"] else tn,
                            "",
                            r["descripcion"],
                            r["insumo_unidad"],
                            f"${r['precio']:,.2f}",
                            r["operador"],
                            f"{r['valor']:,.8f}".rstrip("0").rstrip("."),
                            f"${r['importe']:,.2f}",
                            r.get("formula") or "",
                            r.get("creado_en") or "",
                            r.get("modificado_en") or "",
                        ], editable=True)
                        row_item.setData(0, Qt.ItemDataRole.UserRole, r.get("insumo_id"))
                        row_item.setData(0, Qt.ItemDataRole.UserRole + 1, es_compuesto)
                        row_item.setData(5, Qt.ItemDataRole.UserRole, r.get("id"))
            finally:
                detail.blockSignals(False)

            detail.verticalScrollBar().setValue(scroll_y)
            if comp_actual is not None:
                for i in range(detail.topLevelItemCount()):
                    it = detail.topLevelItem(i)
                    if it.data(5, Qt.ItemDataRole.UserRole) == comp_actual:
                        detail.setCurrentItem(it, col_actual)
                        break

        _refrescar()
        detail.itemChanged.connect(self._on_apu_detalle_editado)

        detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        detail.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(detail, pos))

        detail.itemDoubleClicked.connect(self._on_apu_detail_dblclick)
        layout.addWidget(detail)
        container.setProperty("apu_matriz_id", matriz_id)

        # ── Suscripción al EventBus (mismo patrón que TablaArbol/TablaInsumos) ──
        # Un cambio de precio hecho desde OTRA pestaña (Insumos, u otro APU que
        # comparte el mismo insumo compuesto) debe reflejarse aquí también, y
        # el recálculo en cascada (ProyectoRecalculado) es la única fuente
        # confiable para el total del encabezado.
        #
        # Cuando la edición ocurre EN ESTA MISMA tabla, api.apu_actualizar_*()
        # emite el evento de forma síncrona, todavía dentro del itemChanged
        # que la originó. Repoblar (detail.clear()) en ese momento borraría
        # el item que Qt sigue procesando en esa misma señal — por eso el
        # refresco se difiere con QTimer.singleShot(0, ...) al siguiente
        # ciclo del event loop, nunca inline.
        if self._event_bus:
            from PySide6.QtCore import QTimer
            from backend.database.event_bus import (
                ApuComponenteActualizado, InsumoActualizado, ProyectoRecalculado,
            )
            def _on_evento(evento):
                def _refrescar_seguro():
                    try:
                        _refrescar()
                    except RuntimeError:
                        pass  # la pestaña se cerró antes de que corriera el timer
                QTimer.singleShot(0, _refrescar_seguro)
            handlers = {
                ApuComponenteActualizado: _on_evento,
                InsumoActualizado:        _on_evento,
                ProyectoRecalculado:      _on_evento,
            }
            for tipo, cb in handlers.items():
                self._event_bus.suscribir(tipo, cb)

            def _desconectar():
                for tipo, cb in handlers.items():
                    self._event_bus.desuscribir(tipo, cb)
            detail.desconectar_eventos = _desconectar

        return container

    def _on_apu_detail_dblclick(self, item, column):
        """Doble clic: Descripción → selector de insumo (como en presupuesto); P.U. → sub-APU."""
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not insumo_id:
            return

        if column == 2:  # Descripción → reasignar insumo (mismo diálogo que el árbol)
            from PySide6.QtWidgets import QDialog
            from frontend.ventana.widgets.dialogs import DialogoSeleccionarInsumo
            dlg = DialogoSeleccionarInsumo(self._api, self, default_tipos={1, 2})
            if dlg.exec() == QDialog.DialogCode.Accepted:
                nuevo_id = dlg.insumo_seleccionado
                comp_id = item.data(5, Qt.ItemDataRole.UserRole)
                if nuevo_id is not None and comp_id:
                    self._api.apu_reasignar_componente(comp_id, nuevo_id)
            return

        if column == 4:  # P.U.
            es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if es_compuesto:
                self._abrir_apu_insumo(insumo_id)

    def _on_apu_detalle_editado(self, item, column):
        """Persiste edición de Precio (col 4), Operador (col 5) o Valor (col 6).

        No hace falta recalcular nada a mano aquí: api.apu_actualizar_*()
        emite ApuComponenteActualizado/InsumoActualizado de forma SÍNCRONA
        (antes de que este método siquiera retorne), y _build_apu_tab()
        suscribió _refrescar() a esos eventos — repuebla filas y total
        desde la fuente de verdad. Por eso NO se debe tocar `item` después
        de llamar a self._api.apu_actualizar_*(): _refrescar() ya lo borró
        y recreó (detail.clear()), y seguir usándolo revienta con
        RuntimeError: libshiboken...already deleted.
        """
        if column not in (4, 5, 6) or not self._api:
            return
        comp_id = item.data(5, Qt.ItemDataRole.UserRole)

        if column == 5:
            op = item.text(column).strip()
            if op not in ('*', '/'):
                item.setText(column, '*')
                return
            if comp_id:
                self._api.apu_actualizar_operador(comp_id, op)
            return

        from PySide6.QtWidgets import QMessageBox

        if column == 6:
            try:
                texto = item.text(column).replace(",", "").strip()
                valor = float(texto)
            except ValueError:
                return
            if not comp_id:
                return
            try:
                self._api.apu_actualizar_valor(comp_id, valor)
            except ValueError as e:
                QMessageBox.warning(self, "Cantidad inválida", str(e))
                self._revertir_item(item, column, "apu_matrices", comp_id, "valor", ":,.8f")
            return

        if column == 4:
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            if not insumo_id:
                return
            try:
                texto = item.text(column).replace("$", "").replace(",", "").strip()
                precio = float(texto)
            except ValueError:
                return
            try:
                self._api.apu_actualizar_precio_componente(insumo_id, precio)
            except ValueError as e:
                QMessageBox.warning(self, "Precio inválido", str(e))
                self._revertir_item(item, column, "insumos", insumo_id, "costo_mn", "$:,.2f")

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

    def _revertir_item(self, item, column: int, tabla: str, reg_id: int, campo: str, fmt: str):
        """Revierte el texto de un item al valor real de la DB tras error de validación."""
        tw = item.treeWidget()
        if not tw:
            return
        tw.blockSignals(True)
        row = self._api._conn.execute(
            f"SELECT {campo} FROM {tabla} WHERE id=?", (reg_id,)
        ).fetchone()
        if row:
            val = row[0] or 0
            txt = f"${val:,.2f}" if "$" in fmt else f"{val:,.8f}".rstrip("0").rstrip(".")
            item.setText(column, txt)
        tw.blockSignals(False)

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