"""
diag_dialogs.py
================
Mixin de diálogos de diagnóstico: depurar catálogos, homologar hash,
info proyecto, calculadora.

Se mezcla en VentanaPrincipal via herencia múltiple.
"""


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

        self._reload_presupuesto()
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
        from frontend.ventana.widgets.insumos import TIPO_NOMBRE

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
                 "📄 Concepto", "Conceptos sin APU")

        for r in diag.descripciones_duplicadas(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Descripciones duplicadas (insumos)")

        for r in diag.costos_en_cero(pid):
            _ins(r["id"], r["clave"], r["descripcion"],
                 _tipo_str(r["tipo_id"]), "Costos en cero")

        for r in diag.descripciones_vacias(pid):
            _ins(r["id"], r["clave"], "",
                 _tipo_str(r["tipo_id"]) if r["tipo_id"] else "📄 Concepto",
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
                [f"▶ {nombre_grupo} ({len(items)})", "", "", ""],
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

        title = f"🔧 Depurar catálogos ({total})"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i).startswith("🔧 Depurar"):
                self._tabs.removeTab(i)
                break
        self._tabs.addTab(w, title)
        self._tabs.setCurrentWidget(w)

    def _on_estandarizar_unidades(self, items):
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                        QPushButton, QComboBox, QTableWidget,
                                        QTableWidgetItem, QAbstractItemView)
        from PySide6.QtCore import Qt
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
                    cambios.append((r["id"], combo.currentText()))
            if cambios:
                self._db.conn.executemany(
                    "UPDATE insumos SET unidad = ? WHERE id = ?",
                    [(u, id_) for id_, u in cambios]
                )
                self._db.conn.commit()
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
        from PySide6.QtCore import Qt

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
            self._db.conn.executemany(
                "UPDATE insumos SET unidad = ? WHERE id = ?",
                cambios
            )
            self._db.conn.commit()
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
            warn = QLabel(
                f"<b style='color:#A06A6A;'>⚠ Colisiones detectadas:</b><br>"
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
        import subprocess, sys
        if sys.platform == "win32":
            subprocess.Popen(["calc.exe"])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Calculator"])
        else:
            subprocess.Popen(["gnome-calculator"])

    def _on_info_proyecto(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PySide6.QtCore import Qt
        from pathlib import Path
        from backend.database.repos.diagnostico import DiagnosticoRepo

        if not self._db or not self._api:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Sin proyecto", "Abre un proyecto primero.")
            return

        diag = DiagnosticoRepo(self._db.conn)
        est = diag.estadisticas(self._api._pid)
        nombre = Path(self._db.db_path).stem

        dlg = QDialog(self)
        dlg.setWindowTitle("Información del proyecto")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg)

        filas = [
            ("Nombre", nombre),
            ("Nodos en presupuesto", str(est["n_nodos"])),
            ("Conceptos", str(est["n_conceptos"])),
            ("Insumos en catálogo", str(est["n_insumos"])),
            ("Matrices APU", str(est["n_matrices"])),
        ]
        for label, valor in filas:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{label}:</b>"))
            row.addWidget(QLabel(valor))
            row.addStretch()
            layout.addLayout(row)

        layout.addSpacing(12)
        btn = QPushButton("Cerrar")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        dlg.exec()
