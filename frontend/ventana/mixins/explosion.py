"""
explosion_mixins.py
====================
Mixin de explosión de insumos, explosión de matrices y sobrecostos.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""

from PySide6.QtCore import Qt


class ExplosionMixin:
    """Mixin de explosión — se mezcla en VentanaPrincipal."""

    def _build_explosion(self):
        """Construye y muestra la pestaña de explosión de insumos."""
        from frontend.ventana.widgets.explosion import (
            DialogoExplosion, PestañaExplosion,
        )

        if not self._db:
            return self._build_placeholder("Explosión de insumos")

        arbol = self._arbol_presupuesto
        concepto_ids = arbol.conceptos_seleccionados() if arbol is not None else []

        if not concepto_ids:
            concepto_ids = self._api.todos_concepto_ids()

        if not concepto_ids:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Sin conceptos",
                "No hay conceptos en el presupuesto para explotar."
            )
            return None

        dlg = DialogoExplosion(self)
        if dlg.exec() != DialogoExplosion.DialogCode.Accepted:
            return None

        nivel     = dlg.nivel
        tipos_ids = dlg.tipos_ids

        filas, total_g = self._api.explotar(
            concepto_ids = concepto_ids,
            nivel        = nivel,
            tipos_ids    = tipos_ids,
        )

        if not filas:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "Sin resultados",
                "No se encontraron insumos con los filtros seleccionados."
            )
            return None

        tipos_nombres = self._api.resumen_tipos_explosion(tipos_ids)

        resumen = {
            "nivel":        nivel,
            "n_conceptos":  len(concepto_ids),
            "tipos_nombres": tipos_nombres,
        }

        pestaña = PestañaExplosion(
            filas, total_g, resumen,
            on_apu_click=self._abrir_apu_insumo,
            on_rastrear=self._on_rastrear_insumo,
        )
        pestaña.conectar_eventos(self._event_bus, self._api)
        return pestaña

    def _build_matriz_explosion(self):
        """Construye árbol expandible con APU de cada concepto.

        Sin conectores jerárquicos. Cada concepto tiene una línea
        superior del color del nivel + fondo coloreado. Componentes
        se cargan bajo demanda al expandir.
        """
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QLabel, QAbstractItemView,
            QHeaderView, QMessageBox, QTreeWidgetItem, QTreeWidget,
            QStyledItemDelegate,
        )
        from PySide6.QtGui import QBrush, QColor, QFont, QPen
        from PySide6.QtCore import Qt
        from frontend.ventana.widgets.base import TreeTableWidget
        from frontend.ventana.widgets.arbol import COLORES_NIVEL, ID_ROLE

        _DEPTH_ROLE = ID_ROLE + 1
        _BORDER_ROLE = Qt.ItemDataRole.UserRole + 50
        _LOADED_ROLE = Qt.ItemDataRole.UserRole + 51
        _SECTION_BG = QColor("#1E2A3A")

        if not self._db:
            return self._build_placeholder("📦 Explosión de matrices")

        arbol = self._arbol_presupuesto
        concepto_ids = arbol.conceptos_seleccionados() if arbol is not None else []
        if not concepto_ids:
            concepto_ids = self._api.todos_concepto_ids()
        if not concepto_ids:
            QMessageBox.information(self, "Sin conceptos",
                                    "No hay conceptos en el presupuesto.")
            return None

        cols = ["Nivel", "Clave", "Descripción", "Unidad", "P.U.", "Op", "Valor", "Importe", "Tipo"]

        # ponytail: subclass — sin conectores jerárquicos
        class _TablaMatriz(TreeTableWidget):
            def drawBranches(self, painter, rect, index):
                QTreeWidget.drawBranches(self, painter, rect, index)

        # ponytail: delegado que hereda _Delegate y agrega línea superior coloreada
        from frontend.ventana.widgets.base import _Delegate
        class _BorderDelegate(_Delegate):
            def paint(self, painter, option, index):
                super().paint(painter, option, index)
                if index.column() != 0:
                    return
                color = index.data(_BORDER_ROLE)
                if color is not None:
                    painter.save()
                    painter.setPen(QPen(QColor(color), 2))
                    y = option.rect.top() + 1
                    last = tree.columnCount() - 1
                    right = tree.columnViewportPosition(last) + tree.columnWidth(last) - option.rect.left()
                    painter.drawLine(option.rect.left(), y, right, y)
                    painter.restore()

        tree = _TablaMatriz(cols)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tree.setItemDelegate(_BorderDelegate(tree, frozenset(), None))

        tree.set_column_modes({
            0: (QHeaderView.ResizeMode.Interactive, 60),
            1: (QHeaderView.ResizeMode.Interactive, 90),
            2: (QHeaderView.ResizeMode.Stretch, 250),
            3: (QHeaderView.ResizeMode.Interactive, 55),
            4: (QHeaderView.ResizeMode.Interactive, 80),
            5: (QHeaderView.ResizeMode.Interactive, 40),
            6: (QHeaderView.ResizeMode.Interactive, 80),
            7: (QHeaderView.ResizeMode.Interactive, 95),
            8: (QHeaderView.ResizeMode.Interactive, 110),
        })
        tree.header().setMaximumSectionSize(400)

        total_conceptos = 0
        nivel_color = COLORES_NIVEL[0]
        for idx_c, cid in enumerate(concepto_ids, 1):
            total = self._api.nodo_total(cid)
            nodo = self._api.resolver_matriz(nodo_id=cid)
            descripcion = nodo[1] if nodo[1] else ""

            raiz = QTreeWidgetItem(tree, [
                f"  {idx_c}", "", f"  {descripcion}",
                "", "", "", "",
                f"  {total:,.2f}",
                "",
            ])
            for c in range(tree.columnCount()):
                raiz.setBackground(c, _SECTION_BG)
                raiz.setForeground(c, QBrush(QColor(nivel_color)))
                f = QFont()
                f.setBold(True)
                raiz.setFont(c, f)
                raiz.setData(c, _BORDER_ROLE, nivel_color)

            apu = self._api.apu(nodo_id=cid)
            if apu:
                for comp in apu["detalle"]:
                    item = self._add_comp_row(raiz, comp, "", 1, _DEPTH_ROLE)
                    total_conceptos += 1
            raiz.setExpanded(True)

        if total_conceptos == 0:
            QMessageBox.information(self, "Sin APU",
                                    "Los conceptos seleccionados no tienen APU.")
            return None

        def _on_expanded(item):
            if item.data(0, _LOADED_ROLE):
                return
            item.setData(0, _LOADED_ROLE, True)
            insumo_id = item.data(0, ID_ROLE)
            if insumo_id is None:
                return
            depth = item.data(0, _DEPTH_ROLE) or 0
            apu = self._api.apu(insumo_id=insumo_id)
            if apu:
                for comp in apu["detalle"]:
                    self._add_comp_row(item, comp, "", depth + 1, _DEPTH_ROLE)

        tree.itemExpanded.connect(_on_expanded)

        # ponytail: contenedor con proxy de show_* para que toolbar funcione
        class _MatrizContainer(QWidget):
            def show_primer_nivel(self):
                tree.show_primer_nivel()
            def show_solo_agrupadores(self):
                tree.show_solo_agrupadores()
            def show_todo(self):
                tree.show_todo()
            def show_nivel(self, depth):
                tree.show_nivel(depth)

        w = _MatrizContainer()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        lbl = QLabel(f"<b>Explosión de matrices</b> — {len(concepto_ids)} conceptos")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)
        layout.addWidget(tree)

        return w

    def _add_comp_row(self, parent, comp, nivel, depth=0, depth_role=None):
        """Agrega una fila de componente APU al árbol."""
        from frontend.ventana.widgets.arbol import ID_ROLE, COLORES_NIVEL
        from PySide6.QtGui import QBrush, QColor
        from PySide6.QtWidgets import QTreeWidgetItem
        v  = comp.get("valor", 0) or 0
        op = comp.get("operador", "*")
        pu = comp.get("precio", 0)
        qty = v if op == "*" else (1.0 / v if v else 0.0)
        importe = comp.get("importe", 0) or (pu * qty)
        item = QTreeWidgetItem(parent, [
            str(nivel) if nivel else "",
            "",
            comp.get("descripcion", ""),
            comp.get("insumo_unidad", ""),
            f"{pu:.2f}" if pu else "",
            op,
            f"{v:.4f}" if v else "",
            f"{importe:.2f}" if importe else "",
            comp.get("tipo_nombre", ""),
        ])
        item.setData(0, ID_ROLE, comp.get("insumo_id"))
        if depth_role is not None:
            item.setData(0, depth_role, depth)
        if depth > 0 and comp.get("tiene_sub_apu"):
            color = QBrush(QColor(COLORES_NIVEL[min(depth, len(COLORES_NIVEL) - 1)]))
            f = item.font(0)
            f.setBold(True)
            for c in range(item.columnCount()):
                item.setForeground(c, color)
                item.setFont(c, f)
        return item

    def _build_sobrecostos(self):
        """Pestaña de factores de sobrecosto del proyecto."""
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
            QDoubleSpinBox, QPushButton, QGroupBox
        )

        datos = self._api.factores_sobrecosto_obtener()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl = QLabel("<b>Factores de sobrecosto</b>")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)

        grupo = QGroupBox("Porcentajes")
        grid = QGridLayout(grupo)
        grid.setSpacing(8)

        campos = [
            ("Indirectos de campo:",    "pct_indirectos_campo"),
            ("Indirectos de oficina:",  "pct_indirectos_oficina"),
            ("Financiamiento:",         "pct_financiamiento"),
            ("Utilidad:",               "pct_utilidad"),
            ("Cargos adicionales:",     "pct_cargos_adicionales"),
        ]

        spinboxes = {}
        for i, (etiqueta, clave) in enumerate(campos):
            if clave == "pct_indirectos_campo":
                lbl_campo = QLabel(etiqueta + ' <a href="indirectos" style="color:#7FAFD6;">→</a>')
                lbl_campo.setTextFormat(Qt.TextFormat.RichText)
                lbl_campo.linkActivated.connect(lambda: self._on_indirectos())
            elif clave == "pct_indirectos_oficina":
                lbl_campo = QLabel(etiqueta + ' <a href="personal" style="color:#7FAFD6;">→</a>')
                lbl_campo.setTextFormat(Qt.TextFormat.RichText)
                lbl_campo.linkActivated.connect(lambda: self._on_personal_indirectos())
            else:
                lbl_campo = QLabel(etiqueta)
            spin = QDoubleSpinBox()
            spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            spin.setRange(0, 999.99)
            spin.setDecimals(2)
            spin.setSuffix(" %")
            spin.setValue(datos.get(clave, 0.0))
            spinboxes[clave] = spin
            grid.addWidget(lbl_campo, i, 0)
            grid.addWidget(spin, i, 1)

        layout.addWidget(grupo)

        factor_display = QLabel()
        factor_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(factor_display)

        def _actualizar_factor():
            f = self._api.factores_sobrecosto_calcular(
                spinboxes["pct_indirectos_campo"].value(),
                spinboxes["pct_indirectos_oficina"].value(),
                spinboxes["pct_financiamiento"].value(),
                spinboxes["pct_utilidad"].value(),
                spinboxes["pct_cargos_adicionales"].value(),
            )
            factor_display.setText(f"Factor total: <b>{f:.6f}</b>")
            factor_display.setTextFormat(Qt.TextFormat.RichText)

        for spin in spinboxes.values():
            spin.valueChanged.connect(_actualizar_factor)
        _actualizar_factor()

        btn_row = QWidget()
        btn_lay = QHBoxLayout(btn_row)
        btn_lay.setContentsMargins(0, 0, 0, 0)
        btn_lay.setSpacing(8)
        btn_guardar = QPushButton("Guardar y recalcular")
        btn_guardar.setObjectName("btnPrimario")
        btn_guardar.clicked.connect(lambda: self._guardar_sobrecostos(spinboxes))
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(lambda: container.window().close())
        btn_lay.addStretch()
        btn_lay.addWidget(btn_guardar)
        btn_lay.addWidget(btn_cancelar)
        layout.addWidget(btn_row)

        layout.addStretch()

        return container

    def _guardar_sobrecostos(self, spinboxes):
        """Guarda los factores, recalcula y refresca el presupuesto."""
        try:
            valores = {k: s.value() for k, s in spinboxes.items()}
            self._api.factores_sobrecosto_guardar(valores)
            self._sb.showMessage("Factores guardados y presupuesto recalculado.", 5000)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Error al guardar sobrecostos:\n{e}")
