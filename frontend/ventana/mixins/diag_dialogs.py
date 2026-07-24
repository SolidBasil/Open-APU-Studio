"""
diag_dialogs.py
================
Mixin de diálogos de diagnóstico: depurar catálogos, homologar hash,
info proyecto, calculadora.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""

import os

from frontend.ventana.iconos import icono
class DiagDialogsMixin:
    """Mixin de diagnóstico — se mezcla en VentanaPrincipal."""

    def _on_recalcular(self):
        """Recalcula en cascada todo el presupuesto."""
        from PySide6.QtWidgets import QMessageBox

        if not self._db or not self._api:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        try:
            resultado = self._api.recalcular_proyecto()
        except Exception as e:
            QMessageBox.critical(self, "Error al recalcular", str(e))
            return

        n_iter = resultado.get("iteraciones_compuestos", 0)
        self._sb.showMessage(f"Presupuesto recalculado ({n_iter} iteración(es))", 4000)

    def _on_depurar_catalogos(self):
        from PySide6.QtWidgets import QMessageBox, QWidget, QVBoxLayout, QLabel, QAbstractItemView, QHeaderView
        from PySide6.QtCore import Qt
        from frontend.ventana.widgets.base import TreeTableWidget
        from backend.database.repos.diagnostico import DiagnosticoRepo

        if not self._db or not self._api:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        diag = DiagnosticoRepo(self._db.conn)
        pid = self._api._pid
        from frontend.ventana.tipos_insumo import NOMBRE as TIPO_NOMBRE

        def _tipo_str(tipo_id):
            return TIPO_NOMBRE.get(tipo_id, "")

        grupos = {}

        def _ins(item_id, clave, desc, tipo, origen):
            grupos.setdefault(origen, []).append({
                "id": item_id, "clave": clave, "desc": desc,
                "tipo": tipo, "origen": origen,
            })

        for r in diag.insumos_sin_uso(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Insumos sin uso")

        for r in diag.conceptos_sin_apu(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 "Concepto", "Conceptos sin APU")

        for r in diag.descripciones_duplicadas(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Descripciones duplicadas (insumos)")

        for r in diag.costos_en_cero(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Costos en cero")

        for r in diag.descripciones_vacias(pid):
            _ins(r["id"], r["clave"], "",
                 _tipo_str(r["tipo_id"]) if r["tipo_id"] else "Concepto",
                 "Descripción vacía")

        for r in diag.auto_referencia(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Auto-referencia (circular)")

        for r in diag.unidades_no_estandar(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 f'{_tipo_str(r["tipo_id"])} [{r["unidad"]}]',
                 "Unidad no estándar")

        for r in diag.componentes_cantidad_cero(pid):
            _ins(r["id"], r["clave"],
                 f"{r['descripcion']} (matriz {r['matriz_id']})",
                 _tipo_str(r["tipo_id"]), "Componentes APU con cantidad cero")

        for r in diag.insumos_duplicados_en_matriz(pid):
            _ins(r["id"], r["clave"],
                 f"{r['descripcion']} (matriz {r['matriz_id']}, ×{r['cnt']})",
                 _tipo_str(r["tipo_id"]), "Insumos duplicados en misma matriz")

        total = sum(len(v) for v in grupos.values())
        if not total:
            QMessageBox.information(self, "Catálogo limpio",
                                    "No se encontraron inconsistencias.")
            return

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        lbl = QLabel(f"<b>Diagnóstico del catálogo</b> — {total} incidencias")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)

        tree = TreeTableWidget(["Problema", "Clave", "Descripción", "Tipo"])
        tree.setAlternatingRowColors(True)
        tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        for nombre_grupo, items in grupos.items():
            padre = tree.add_row(
                [f"{nombre_grupo} ({len(items)})", "", "", ""],
                editable=False)
            for item in items:
                tree.add_row(
                    ["", item["clave"], item["desc"], item["tipo"]],
                    parent=padre, editable=False)
            padre.setExpanded(True)

        tree.set_column_modes({
            0: (QHeaderView.ResizeMode.ResizeToContents, None),
            1: (QHeaderView.ResizeMode.ResizeToContents, None),
            2: (QHeaderView.ResizeMode.Stretch, 300),
            3: (QHeaderView.ResizeMode.ResizeToContents, None),
        })
        layout.addWidget(tree)

        unidadesgrupo = diag.unidades_no_estandar(pid)
        if unidadesgrupo:
            from PySide6.QtWidgets import QPushButton
            btn = QPushButton(f"Estandarizar unidades ({len(unidadesgrupo)})")
            btn.clicked.connect(lambda: self._on_estandarizar_unidades(unidadesgrupo))
            layout.addWidget(btn)

        casegrupo = diag.unidades_case(pid)
        if casegrupo:
            from PySide6.QtWidgets import QPushButton
            btn = QPushButton(f"Corregir mayúsculas/minúsculas ({len(casegrupo)})")
            btn.clicked.connect(lambda: self._on_corregir_case_unidades(casegrupo))
            layout.addWidget(btn)

        title = f"Depurar catálogos ({total})"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i).startswith("Depurar"):
                self._cerrar_tab_widget(i)
                break
        self._tabs.addTab(w, title)
        self._tabs.setCurrentWidget(w)

    def _on_estandarizar_unidades(self, items):
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                        QPushButton, QComboBox, QTableWidget,
                                        QTableWidgetItem, QAbstractItemView)
        from frontend.ventana.widgets.base import UNIDADES

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Estandarizar unidades ({len(items)} insumos)")
        dlg.setMinimumSize(600, 400)
        layout = QVBoxLayout(dlg)

        lbl = QLabel("Selecciona la unidad estándar para cada unidad no estándar encontrada:")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        unidades_unicas = sorted(set(r["unidad"] for r in items))
        combos = {}
        tabla = QTableWidget(len(unidades_unicas), 2)
        tabla.setHorizontalHeaderLabels(["Unidad actual", "Reemplazar por"])
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, uni in enumerate(unidades_unicas):
            tabla.setItem(i, 0, QTableWidgetItem(uni))
            combo = QComboBox()
            combo.addItems(["(mantener)"] + UNIDADES)
            combo.setCurrentText("(mantener)")
            tabla.setCellWidget(i, 1, combo)
            combos[uni] = combo
        tabla.resizeColumnsToContents()
        layout.addWidget(tabla)

        row = QHBoxLayout()
        btn_aplicar = QPushButton("Aplicar")
        btn_cancel = QPushButton("Cancelar")
        row.addStretch()
        row.addWidget(btn_aplicar)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        def aplicar():
            cambios = []
            for r in items:
                combo = combos.get(r["unidad"])
                if combo and combo.currentText() != "(mantener)":
                    cambios.append((combo.currentText(), r["id"]))
            if cambios:
                from backend.database.repos import InsumoRepo
                InsumoRepo(self._db.conn).actualizar_unidades_batch(cambios)
                self._db.conn.commit()
                from backend.database.event_bus import InsumoActualizado
                for u, id_ in cambios:
                    registro = self._api.insumo_por_id(id_)
                    self._event_bus.emit(InsumoActualizado(id_, {"unidad": u}, registro))
                self._sb.showMessage(f"Unidades estandarizadas: {len(cambios)} insumos", 4000)
            dlg.accept()
            self._on_depurar_catalogos()

        btn_aplicar.clicked.connect(aplicar)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def _on_corregir_case_unidades(self, items):
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                        QPushButton, QTableWidget, QTableWidgetItem,
                                        QAbstractItemView)

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Corregir mayúsculas/minúsculas ({len(items)} insumos)")
        dlg.setMinimumSize(600, 400)
        layout = QVBoxLayout(dlg)

        lbl = QLabel("Se corregirán las unidades para que coincidan con el estándar:")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        tabla = QTableWidget(len(items), 3)
        tabla.setHorizontalHeaderLabels(["Clave", "Unidad actual", "Corregir a"])
        tabla.verticalHeader().setVisible(False)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i, r in enumerate(items):
            tabla.setItem(i, 0, QTableWidgetItem(r["clave"]))
            tabla.setItem(i, 1, QTableWidgetItem(r["unidad"]))
            tabla.setItem(i, 2, QTableWidgetItem(r["canonical"]))
        tabla.resizeColumnsToContents()
        layout.addWidget(tabla)

        row = QHBoxLayout()
        btn_aplicar = QPushButton("Aplicar")
        btn_cancel = QPushButton("Cancelar")
        row.addStretch()
        row.addWidget(btn_aplicar)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        def aplicar():
            cambios = [(r["canonical"], r["id"]) for r in items]
            if not cambios:
                return
            from backend.database.repos import InsumoRepo
            InsumoRepo(self._db.conn).actualizar_unidades_batch(cambios)
            self._db.conn.commit()
            from backend.database.event_bus import InsumoActualizado
            for u, id_ in cambios:
                registro = self._api.insumo_por_id(id_)
                self._event_bus.emit(InsumoActualizado(id_, {"unidad": u}, registro))
            self._sb.showMessage(f"Unidades corregidas: {len(cambios)} insumos", 4000)
            dlg.accept()
            self._on_depurar_catalogos()

        btn_aplicar.clicked.connect(aplicar)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def _on_homologar_hash(self):
        from PySide6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QAbstractItemView
        from PySide6.QtCore import Qt
        from backend.database.repos.diagnostico import DiagnosticoRepo

        if not self._db or not self._api:
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        diag = DiagnosticoRepo(self._db.conn)
        pid = self._api._pid
        cambios = diag.insumos_hash_desactualizado(pid)

        if not cambios:
            QMessageBox.information(self, "Hash normalizados",
                                    "Todos los insumos tienen su hash correcto.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Homologar hash ({len(cambios)} cambios)")
        dlg.setMinimumSize(700, 400)
        layout = QVBoxLayout(dlg)

        lbl = QLabel(
            f"Se encontraron <b>{len(cambios)}</b> insumos con hash faltante o desactualizado. "
            "Revisa los cambios propuestos antes de aplicar."
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        cols = ["ID", "Descripción", "Hash actual", "Hash nuevo"]
        tabla = QTableWidget(len(cambios), 4)
        tabla.setHorizontalHeaderLabels(cols)
        tabla.horizontalHeader().setStretchLastSection(True)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.verticalHeader().setVisible(False)
        for i, (id_, desc, old, new) in enumerate(cambios):
            tabla.setItem(i, 0, QTableWidgetItem(str(id_)))
            tabla.setItem(i, 1, QTableWidgetItem(desc))
            tabla.setItem(i, 2, QTableWidgetItem(old or "—"))
            tabla.setItem(i, 3, QTableWidgetItem(new))
        tabla.resizeColumnsToContents()
        layout.addWidget(tabla)

        colisiones = {}
        for id_, _, _, h in cambios:
            colisiones.setdefault(h, []).append(id_)
        colisiones = {h: ids for h, ids in colisiones.items() if len(ids) > 1}
        if colisiones:
            msgs = []
            for h, ids in colisiones.items():
                msgs.append(f"<b>{h}</b> → IDs {ids}")
            from frontend.ventana.colores import ERROR
            warn = QLabel(
                f"<b style='color:{ERROR};'>⚠ Colisiones detectadas:</b><br>"
                + "<br>".join(msgs)
            )
            warn.setTextFormat(Qt.TextFormat.RichText)
            warn.setWordWrap(True)
            layout.addWidget(warn)

        row = QHBoxLayout()
        btn_aplicar = QPushButton("Aplicar cambios")
        btn_cancel  = QPushButton("Cancelar")
        row.addStretch()
        row.addWidget(btn_aplicar)
        row.addWidget(btn_cancel)
        layout.addLayout(row)

        def aplicar():
            diag.aplicar_hash(cambios)
            self._sb.showMessage(f"Homologados {len(cambios)} hashes", 4000)
            dlg.accept()

        btn_aplicar.clicked.connect(aplicar)
        btn_cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def _on_calculadora(self):
        import subprocess
        import sys
        if sys.platform == "win32":
            subprocess.Popen(["calc.exe"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Calculator"])
        else:
            subprocess.Popen(["gnome-calculator"])

    def _on_info_proyecto(self, nuevo=False):
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QWidget, QFrame, QListWidget, QListWidgetItem, QStackedWidget,
            QLineEdit, QDoubleSpinBox, QComboBox, QFormLayout, QScrollArea,
            QMessageBox, QCheckBox,
        )
        from PySide6.QtCore import Qt
        from datetime import datetime

        if nuevo:
            datos = {}
        else:
            if not self._db or not self._api:
                QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
                return
            datos = self._api.proyecto_leer()
            if not datos:
                QMessageBox.warning(self, "Error", "No se pudo leer el proyecto.")
                return

        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo proyecto" if nuevo else "Información del proyecto")
        dlg.setMinimumSize(700, 520)
        dlg.setModal(True)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ───────────────────────────────────────────────
        hdr = QFrame()
        hdr.setObjectName("dlgAjustesHeader")
        hdr.setFixedHeight(48)
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(16, 0, 16, 0)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(icono("clipboard", 24).pixmap(24, 24))
        icon_lbl.setObjectName("dlgIcon")
        hdr_row.addWidget(icon_lbl)
        title_lbl = QLabel("Información del proyecto")
        title_lbl.setObjectName("dlgHeader")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()
        layout.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("dlgSep")
        layout.addWidget(sep)

        # ── Body: sidebar + stacked ──────────────────────────────
        body = QWidget()
        body_row = QHBoxLayout(body)
        body_row.setSpacing(0)
        body_row.setContentsMargins(0, 0, 0, 0)

        self._info_nav = QListWidget()
        self._info_nav.setObjectName("dlgAjustesNav")
        self._info_nav.setFixedWidth(150)
        self._info_nav.setSpacing(0)

        CATEGORIAS = [
            ("clipboard", "General"),
            ("users", "Cliente"),
            ("building", "Obra"),
            ("banknote", "Financiero"),
            ("factory", "Constructora"),
            ("phone", "Contacto"),
            ("file-text", "Reportes"),
        ]

        for svg, nombre in CATEGORIAS:
            pix = icono(svg, 16).pixmap(16, 16)
            item = QListWidgetItem(pix, f"  {nombre}")
            item.setSizeHint(item.sizeHint())
            self._info_nav.addItem(item)

        body_row.addWidget(self._info_nav)

        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setObjectName("dlgVSep")
        body_row.addWidget(vsep)

        stack = QStackedWidget()
        stack.setObjectName("dlgAjustesStack")

        # ── Widgets de campos (referencias para leer/escribir) ───
        self._info_fields: dict[str, QWidget] = {}

        def _add_field(form: QFormLayout, key: str, label: str,
                       value=None, widget_type="line"):
            if widget_type == "line":
                w = QLineEdit()
                w.setText(str(value) if value is not None else "")
            elif widget_type == "spin_int":
                w = QDoubleSpinBox()
                w.setDecimals(0)
                w.setRange(0, 999999)
                w.setValue(float(value) if value else 0)
                w.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            elif widget_type == "spin_float":
                w = QDoubleSpinBox()
                w.setDecimals(2)
                w.setRange(0, 999999)
                w.setValue(float(value) if value else 0)
                w.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            elif widget_type == "spin_pct":
                w = QDoubleSpinBox()
                w.setDecimals(2)
                w.setRange(0, 100)
                w.setValue(float(value) if value else 0)
                w.setSuffix(" %")
                w.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            elif widget_type == "combo_moneda":
                w = QComboBox()
                w.setEditable(True)
                w.addItems(["Peso mexicano", "Dólar USD", "Euro", "Otra"])
                w.setCurrentText(str(value) if value else "Peso mexicano")
            elif widget_type == "combo_iva":
                w = QComboBox()
                w.setEditable(True)
                w.addItems(["IVA", "ISR", "Ninguno"])
                w.setCurrentText(str(value) if value else "IVA")
            elif widget_type == "check":
                w = QCheckBox()
                w.setChecked(bool(value))
            else:
                w = QLineEdit()
                w.setText(str(value) if value is not None else "")
            self._info_fields[key] = w
            form.addRow(label, w)
            return w

        def _make_page(titulo: str) -> QWidget:
            page = QWidget()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            inner = QWidget()
            form = QFormLayout(inner)
            form.setSpacing(10)
            form.setContentsMargins(16, 16, 16, 16)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
            scroll.setWidget(inner)
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.addWidget(scroll)
            return page, form

        # ── Tab: General ─────────────────────────────────────────
        page, form = _make_page("General")
        _add_field(form, "nombre", "Nombre:", datos.get("nombre"))
        _add_field(form, "descripcion", "Descripción:", datos.get("descripcion"))
        _add_field(form, "duracion_obra_dias", "Duración obra (días):",
                   datos.get("duracion_obra_dias"), "spin_int")
        lbl_total = QLabel(f"<b>${float(datos.get('total_obra') or 0):,.2f}</b>")
        lbl_total.setTextFormat(Qt.TextFormat.RichText)
        form.addRow("Total obra:", lbl_total)
        stack.addWidget(page)

        # ── Tab: Cliente ─────────────────────────────────────────
        page, form = _make_page("Cliente")
        _add_field(form, "cliente_nombre", "Nombre:", datos.get("cliente_nombre"))
        _add_field(form, "cliente_domicilio", "Domicilio:", datos.get("cliente_domicilio"))
        _add_field(form, "cliente_ciudad", "Ciudad:", datos.get("cliente_ciudad"))
        _add_field(form, "cliente_cp", "C.P.:", datos.get("cliente_cp"))
        _add_field(form, "cliente_pais", "País:", datos.get("cliente_pais"))
        _add_field(form, "cliente_email", "Email:", datos.get("cliente_email"))
        _add_field(form, "cliente_tel", "Teléfono:", datos.get("cliente_tel"))
        stack.addWidget(page)

        # ── Tab: Obra ───────────────────────────────────────────
        page, form = _make_page("Obra")
        _add_field(form, "obra_domicilio", "Domicilio:", datos.get("obra_domicilio"))
        _add_field(form, "obra_ciudad", "Ciudad:", datos.get("obra_ciudad"))
        _add_field(form, "obra_estado", "Estado:", datos.get("obra_estado"))
        _add_field(form, "obra_cp", "C.P.:", datos.get("obra_cp"))
        _add_field(form, "obra_pais", "País:", datos.get("obra_pais"))
        _add_field(form, "obra_latitud", "Latitud:", datos.get("obra_latitud"), "spin_float")
        _add_field(form, "obra_longitud", "Longitud:", datos.get("obra_longitud"), "spin_float")
        _add_field(form, "obra_descripcion", "Descripción:", datos.get("obra_descripcion"))
        stack.addWidget(page)

        # ── Tab: Financiero ──────────────────────────────────────
        page, form = _make_page("Financiero")
        _add_field(form, "moneda_nombre", "Moneda nacional:", datos.get("moneda_nombre"), "combo_moneda")
        _add_field(form, "moneda_simbolo", "Símbolo:", datos.get("moneda_simbolo"))
        _add_field(form, "moneda_abrev", "Abreviatura:", datos.get("moneda_abrev"))
        _add_field(form, "moneda_ext_nombre", "Moneda extranjera:", datos.get("moneda_ext_nombre"))
        _add_field(form, "moneda_ext_simbolo", "Símbolo ext.:", datos.get("moneda_ext_simbolo"))
        _add_field(form, "moneda_ext_abrev", "Abrev. ext.:", datos.get("moneda_ext_abrev"))
        _add_field(form, "tipo_cambio", "Tipo de cambio:", datos.get("tipo_cambio"), "spin_float")
        _add_field(form, "iva_nombre", "Impuesto:", datos.get("iva_nombre"), "combo_iva")
        _add_field(form, "iva_porcentaje", "% Impuesto:", datos.get("iva_porcentaje"), "spin_pct")
        _add_field(form, "horas_dia", "Horas/día:", datos.get("horas_dia"), "spin_float")
        stack.addWidget(page)

        # ── Tab: Constructora ────────────────────────────────────
        page, form = _make_page("Constructora")
        _add_field(form, "constructora_nombre", "Nombre:", datos.get("constructora_nombre"))
        _add_field(form, "constructora_rfc", "RFC:", datos.get("constructora_rfc"))
        _add_field(form, "constructora_domicilio", "Domicilio:", datos.get("constructora_domicilio"))
        _add_field(form, "constructora_ciudad", "Ciudad:", datos.get("constructora_ciudad"))
        _add_field(form, "constructora_estado", "Estado:", datos.get("constructora_estado"))
        _add_field(form, "constructora_cp", "C.P.:", datos.get("constructora_cp"))
        _add_field(form, "constructora_pais", "País:", datos.get("constructora_pais"))
        _add_field(form, "constructora_tel", "Teléfono:", datos.get("constructora_tel"))
        _add_field(form, "constructora_email", "Email:", datos.get("constructora_email"))
        _add_field(form, "constructora_sitio_web", "Sitio web:", datos.get("constructora_sitio_web"))
        _add_field(form, "constructora_logo_path", "Logo:", datos.get("constructora_logo_path"))
        stack.addWidget(page)

        # ── Tab: Contacto ────────────────────────────────────────
        page, form = _make_page("Contacto")
        _add_field(form, "contacto_nombre", "Nombre:", datos.get("contacto_nombre"))
        _add_field(form, "contacto_cargo", "Cargo:", datos.get("contacto_cargo"))
        _add_field(form, "contacto_email", "Email:", datos.get("contacto_email"))
        _add_field(form, "contacto_tel", "Teléfono:", datos.get("contacto_tel"))
        stack.addWidget(page)

        # ── Tab: Reportes ────────────────────────────────────────
        page, form = _make_page("Reportes")
        _add_field(form, "reporte_responsable", "Responsable:", datos.get("reporte_responsable"))
        lbl_ver = QLabel(f"<b>{datos.get('reporte_version') or '1.0'}</b>")
        lbl_ver.setTextFormat(Qt.TextFormat.RichText)
        form.addRow("Versión:", lbl_ver)
        _add_field(form, "reporte_observaciones", "Observaciones:", datos.get("reporte_observaciones"))
        lbl_fecha = QLabel(f"<b>{datetime.now().strftime('%Y-%m-%d %H:%M')}</b>")
        lbl_fecha.setTextFormat(Qt.TextFormat.RichText)
        form.addRow("Fecha:", lbl_fecha)
        stack.addWidget(page)

        body_row.addWidget(stack, 1)
        layout.addWidget(body, 1)

        # ── Sidebar nav → stack ──────────────────────────────────
        self._info_nav.currentRowChanged.connect(stack.setCurrentIndex)
        self._info_nav.setCurrentRow(0)

        # ── Sep + Footer ─────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("dlgSep")
        layout.addWidget(sep2)

        footer = QFrame()
        footer.setObjectName("dlgAjustesFooter")
        foot_row = QHBoxLayout(footer)
        foot_row.setContentsMargins(16, 10, 16, 10)
        foot_row.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(dlg.reject)
        foot_row.addWidget(btn_cancel)
        btn_save = QPushButton("Guardar")
        btn_save.setObjectName("btnPrimario")
        foot_row.addWidget(btn_save)
        layout.addWidget(footer)

        # ── Guardar ──────────────────────────────────────────────
        CAMPOS = [
            "nombre", "descripcion", "duracion_obra_dias",
            "cliente_nombre", "cliente_domicilio", "cliente_ciudad",
            "cliente_cp", "cliente_pais", "cliente_email", "cliente_tel",
            "obra_domicilio", "obra_ciudad", "obra_estado", "obra_cp",
            "obra_pais", "obra_latitud", "obra_longitud", "obra_descripcion",
            "moneda_nombre", "moneda_simbolo", "moneda_abrev",
            "moneda_ext_nombre", "moneda_ext_simbolo", "moneda_ext_abrev",
            "tipo_cambio",
            "iva_nombre", "iva_porcentaje", "horas_dia",
            "constructora_nombre", "constructora_rfc", "constructora_domicilio",
            "constructora_ciudad", "constructora_estado", "constructora_cp",
            "constructora_pais", "constructora_tel", "constructora_email",
            "constructora_sitio_web", "constructora_logo_path",
            "contacto_nombre", "contacto_cargo", "contacto_email", "contacto_tel",
            "reporte_responsable", "reporte_observaciones",
        ]

        def guardar():
            campos = {}
            for key in CAMPOS:
                w = self._info_fields.get(key)
                if w is None:
                    continue
                if isinstance(w, QDoubleSpinBox):
                    campos[key] = w.value()
                elif isinstance(w, QCheckBox):
                    campos[key] = 1 if w.isChecked() else 0
                elif isinstance(w, QComboBox):
                    campos[key] = w.currentText()
                else:
                    campos[key] = w.text()
            nombre = campos.get("nombre", "").strip()
            if nuevo and not nombre:
                QMessageBox.warning(dlg, "Nombre requerido",
                                    "Escribe un nombre para el proyecto.")
                return
            now = datetime.now()
            campos["reporte_fecha"] = now.strftime("%Y-%m-%d")
            if nuevo:
                campos.setdefault("reporte_version", "1.0")
            else:
                campos["reporte_version"] = datos.get("reporte_version") or "1.0"
            try:
                if nuevo:
                    from backend.database.db import Database, Rutas
                    base_dir = Rutas.proyectos()
                    db_path = str(base_dir / f"{nombre}.db")
                    n = 1
                    while os.path.exists(db_path):
                        db_path = str(base_dir / f"{nombre} ({n}).db")
                        n += 1
                    self._db = Database.abrir(db_path)
                    self._db.conn.execute(
                        "INSERT INTO proyectos (id, nombre) VALUES (1, ?)",
                        (nombre,))
                    self._db.conn.commit()
                    self._proyecto_abierto = db_path
                    self._wire_servicios(self._db)
                    self._api.proyecto_guardar(campos)
                    self._db.conn.commit()
                    self._reload_presupuesto()
                    self._update_statusbar()
                    self._switch_tab("PRINCIPAL")
                    dlg.accept()
                    self._sb.showMessage(f"Proyecto \"{nombre}\" creado", 3000)
                    return
                self._api.proyecto_guardar(campos)
                self._db.conn.commit()
                dlg.accept()
                self._sb.showMessage("Información del proyecto guardada", 3000)
            except Exception as e:
                QMessageBox.critical(dlg, "Error", f"Error al guardar:\n{e}")

        btn_save.clicked.connect(guardar)

        dlg.exec()
