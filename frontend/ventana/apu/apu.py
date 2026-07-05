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
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHeaderView
        from frontend.ventana.widgets.base import TreeTableWidget

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        lbl = QLabel()
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(lbl)
        layout.addSpacing(2)

        def _editable_cols_detalle(item):
            if item.data(0, Qt.ItemDataRole.UserRole + 1):
                return {5, 6}
            return {4, 5, 6}

        detail = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "Unidad", "P.U.", "Op", "Valor", "Importe"],
            flat=True,
            editable_cols=frozenset({5}),
            editable_cols_fn=_editable_cols_detalle,
        )
        detail.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([110, 90, 250, 50, 100, 40, 80, 110])
        })
        detail.header().setMaximumSectionSize(400)

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
                        detail.setCurrentItem(it)
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
        """Doble clic en columna P.U. → abre sub-APU si el insumo es compuesto."""
        if column != 4:
            return
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if insumo_id and es_compuesto:
            self._abrir_apu_insumo(insumo_id)

    def _on_apu_detalle_editado(self, item, column):
        """Persiste edición de Precio (col 4), Operador (col 5) o Cantidad (col 6).

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

        if column == 6:
            try:
                texto = item.text(column).replace(",", "").strip()
                valor = float(texto)
            except ValueError:
                return
            if not comp_id:
                return
            from PySide6.QtWidgets import QMessageBox
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
        """Doble clic en presupuesto/insumos → abre APU del concepto."""
        from frontend.ventana.widgets.arbol import ID_ROLE
        if self._es_pu(item, column):
            nodo_id = item.data(0, ID_ROLE)
            if nodo_id:
                self._abrir_apu_por_id(nodo_id)

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