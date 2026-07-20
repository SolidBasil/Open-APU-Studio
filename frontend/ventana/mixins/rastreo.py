"""
rastreo_mixins.py
==================
Mixin de rastreo de insumos: buscar uso, tabla de resultados, navegación.

Se mezcla en VentanaPrincipal via herencia múltiple.

Actualizado: 2026-07-19 (hora local)
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence


class RastreoMixin:
    """Mixin de rastreo — se mezcla en VentanaPrincipal."""

    def _on_rastrear_insumo(self, insumo_id: int):
        """Busca insumo por id y abre pestaña con todas las matrices donde se usa."""
        if not insumo_id or not self._api:
            return
        insumo = self._api.insumo_por_id(insumo_id)
        if not insumo:
            self._sb.showMessage(f"Insumo #{insumo_id} no encontrado", 4000)
            return
        desc = insumo.get("descripcion") or insumo.get("descripcion_corta") or f"#{insumo_id}"
        clave = insumo.get("clave", "")
        title = f"Uso: {desc[:30]}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        filas = self._api.rastrear_insumo(insumo_id)
        idx = self._tabs.addTab(
            self._build_rastrear_tab(insumo, filas), title
        )
        self._tabs.setCurrentIndex(idx)

    def _build_rastrear_tab(self, insumo: dict, filas: list):
        """Construye pestaña de rastreo con resumen del insumo y tabla de uso."""
        from frontend.ventana.iconos import icono
        from frontend.ventana.tipos_insumo import ICONO_SVG, COLOR as _COLOR_TIPO
        from frontend.ventana.widgets.base import TreeTableWidget
        from PySide6.QtWidgets import (
            QHBoxLayout, QLabel, QHeaderView, QVBoxLayout, QWidget,
        )

        desc = insumo.get("descripcion") or insumo.get("descripcion_corta") or ""
        clave = insumo.get("clave", "")
        tipo_nombre = insumo.get("tipo_nombre", "")
        unidad = insumo.get("unidad", "")
        es_compuesto = insumo.get("es_compuesto", False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(12, 10, 12, 8)
        header.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(icono("search", 18).pixmap(18, 18))
        header.addWidget(icon_lbl)

        title_lbl = QLabel(f"<b>{desc}</b>")
        title_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header.addWidget(title_lbl)

        if clave:
            sep = QLabel(f"  ·  <span style='color:#7FAFD6'>{clave}</span>")
            sep.setTextFormat(Qt.TextFormat.RichText)
            sep.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            header.addWidget(sep)

        if tipo_nombre:
            tipo_lbl = QLabel(f"  ·  {tipo_nombre}")
            tipo_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            header.addWidget(tipo_lbl)

        if unidad:
            uni_lbl = QLabel(f"  ·  {unidad}")
            uni_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            header.addWidget(uni_lbl)

        header.addStretch()

        n_conceptos = sum(1 for r in filas if r["tipo_origen"] == "concepto")
        n_compuestos = len(filas) - n_conceptos
        count_parts = []
        if n_conceptos:
            count_parts.append(f"{n_conceptos} concepto{'s' if n_conceptos != 1 else ''}")
        if n_compuestos:
            count_parts.append(f"{n_compuestos} compuesto{'s' if n_compuestos != 1 else ''}")
        if count_parts:
            count_lbl = QLabel(f"<span style='color:#B7C0C8'>{', '.join(count_parts)}</span>")
            count_lbl.setTextFormat(Qt.TextFormat.RichText)
            header.addWidget(count_lbl)

        layout.addLayout(header)

        tabla = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "Nivel", "Cantidad", "P.U.", "Importe"],
            flat=True,
        )
        tabla.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([120, 90, 300, 140, 90, 110, 120])
        })
        tabla.header().setMaximumSectionSize(400)
        tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabla.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(tabla, pos))
        tabla.itemDoubleClicked.connect(
            lambda item, col: self._abrir_matriz_desde_rastreo(item))

        for r in filas:
            es_concepto = r["tipo_origen"] == "concepto"
            tipo_id = r.get("matriz_tipo_id")
            tipo_nombre = r.get("matriz_tipo") or ("Concepto" if es_concepto else "Compuesto")
            tipo_svg = ICONO_SVG.get(tipo_id, "file-text" if es_concepto else "component")
            row_item = tabla.add_row([
                tipo_nombre,
                r.get("matriz_clave") or "",
                r.get("matriz_descripcion", ""),
                (r.get("matriz_wbs") or "") if es_concepto else "",
                f"{r.get('valor', 0):,.3f}",
                f"${r.get('precio', 0):,.2f}",
                f"${r.get('importe', 0):,.2f}",
            ], editable=False)
            row_item.setData(0, Qt.ItemDataRole.UserRole, r.get("matriz_id"))
            row_item.setIcon(0, icono(tipo_svg, 16, _COLOR_TIPO.get(tipo_id)))

        if not filas:
            tabla.add_row([
                "", "", f"'{desc}' no se usa en ninguna matriz", "", "", "", ""
            ], editable=False)

        layout.addWidget(tabla)
        return container

    def _abrir_matriz_desde_rastreo(self, item):
        """Abre el APU de una fila de rastreo."""
        matriz_id = item.data(0, Qt.ItemDataRole.UserRole)
        if matriz_id is None:
            return
        if matriz_id > 0:
            self._abrir_apu_por_id(matriz_id)
        else:
            self._abrir_apu_insumo(-matriz_id)

    def _on_rastrear_context_menu(self, tabla, pos):
        """Menú contextual sobre tablas de APU y rastreo."""
        from PySide6.QtWidgets import QMenu
        from frontend.ventana.widgets.base import _menu_icon
        item = tabla.itemAt(pos)
        if not item:
            return
        tabla.setCurrentItem(item)
        menu = QMenu(self)
        copy_act = menu.addAction(_menu_icon("clipboard"), "Copiar")
        copy_act.setShortcut(QKeySequence.StandardKey.Copy)
        copy_act.triggered.connect(tabla._copy)
        cut_act = menu.addAction(_menu_icon("scissors"), "Cortar")
        cut_act.setShortcut(QKeySequence.StandardKey.Cut)
        cut_act.triggered.connect(tabla._cut)
        paste_act = menu.addAction(_menu_icon("file-text"), "Pegar")
        paste_act.setShortcut(QKeySequence.StandardKey.Paste)
        paste_act.triggered.connect(tabla._paste)
        menu.addSeparator()
        matriz_id = item.data(0, Qt.ItemDataRole.UserRole)
        es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if es_compuesto is not None:
            insumo_id = matriz_id
            if es_compuesto:
                act = menu.addAction(_menu_icon("search"), "Rastrear uso")
                act.triggered.connect(lambda: self._on_rastrear_insumo(insumo_id))
                act = menu.addAction(_menu_icon("link"), "Desglozar")
                act.triggered.connect(lambda: self._abrir_apu_insumo(insumo_id))
        elif matriz_id and matriz_id < 0:
            insumo_id = -matriz_id
            act = menu.addAction(_menu_icon("search"), "Rastrear uso")
            act.triggered.connect(lambda: self._on_rastrear_insumo(insumo_id))
            act = menu.addAction(_menu_icon("link"), "Desglozar")
            act.triggered.connect(lambda: self._abrir_apu_insumo(insumo_id))
        elif matriz_id and matriz_id > 0:
            act = menu.addAction(_menu_icon("link"), "Desglozar")
            act.triggered.connect(lambda: self._abrir_apu_por_id(matriz_id))
        menu.exec(tabla.mapToGlobal(pos))