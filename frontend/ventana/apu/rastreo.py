"""
rastreo_mixins.py
==================
Mixin de rastreo de insumos: buscar uso, tabla de resultados, navegación.

Se mezcla en VentanaPrincipal via herencia múltiple.
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
        desc  = insumo.get("descripcion") or insumo.get("descripcion_corta") or f"#{insumo_id}"
        title = f"\U0001f50d Uso: {desc[:30]}"
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i) == title:
                self._tabs.setCurrentIndex(i)
                return
        filas = self._api.rastrear_insumo(insumo_id)
        idx = self._tabs.addTab(
            self._build_rastrear_tab(desc, filas), title
        )
        self._tabs.setCurrentIndex(idx)

    def _build_rastrear_tab(self, descripcion: str, filas: list):
        """Construye tabla plana con las matrices que consumen un insumo."""
        from frontend.ventana.widgets.base import TreeTableWidget
        from PySide6.QtWidgets import QHeaderView

        tabla = TreeTableWidget(
            ["Tipo", "Clave", "Descripción", "WBS", "Cantidad", "P.U.", "Importe"],
            flat=True,
        )
        tabla.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([80, 90, 250, 100, 80, 100, 110])
        })
        tabla.header().setMaximumSectionSize(400)

        for r in filas:
            es_concepto = r["tipo_origen"] == "concepto"
            tipo = "📄 Concepto" if es_concepto else "\u2699 Compuesto"
            row_item = tabla.add_row([
                tipo,
                r.get("matriz_clave", "") if es_concepto else "",
                r.get("matriz_descripcion", ""),
                r.get("matriz_wbs", ""),
                f"{r.get('cantidad', 0):,.3f}",
                f"${r.get('precio', 0):,.2f}",
                f"${r.get('importe', 0):,.2f}",
            ], editable=False)
            row_item.setData(0, Qt.ItemDataRole.UserRole, r.get("matriz_id"))

        if not filas:
            tabla.add_row([
                "", "", f"\u2716 '{descripcion}' no se usa en ninguna matriz", "", "", "", ""
            ], editable=False)
            return tabla

        tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tabla.customContextMenuRequested.connect(
            lambda pos: self._on_rastrear_context_menu(tabla, pos))

        tabla.itemDoubleClicked.connect(
            lambda item, col: self._abrir_matriz_desde_rastreo(item)
        )
        return tabla

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
        copy_act = menu.addAction(_menu_icon("📋"), "Copiar")
        copy_act.setShortcut(QKeySequence.StandardKey.Copy)
        copy_act.triggered.connect(tabla._copy)
        cut_act = menu.addAction(_menu_icon("✂"), "Cortar")
        cut_act.setShortcut(QKeySequence.StandardKey.Cut)
        cut_act.triggered.connect(tabla._cut)
        paste_act = menu.addAction(_menu_icon("📋"), "Pegar")
        paste_act.setShortcut(QKeySequence.StandardKey.Paste)
        paste_act.triggered.connect(tabla._paste)
        menu.addSeparator()
        matriz_id = item.data(0, Qt.ItemDataRole.UserRole)
        es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if es_compuesto is not None:
            insumo_id = matriz_id
            if es_compuesto:
                act = menu.addAction(_menu_icon("🔍"), "Rastrear uso")
                act.triggered.connect(lambda: self._on_rastrear_insumo(insumo_id))
                act = menu.addAction(_menu_icon("🔗"), "Desglozar")
                act.triggered.connect(lambda: self._abrir_apu_insumo(insumo_id))
        elif matriz_id and matriz_id < 0:
            insumo_id = -matriz_id
            act = menu.addAction(_menu_icon("🔍"), "Rastrear uso")
            act.triggered.connect(lambda: self._on_rastrear_insumo(insumo_id))
            act = menu.addAction(_menu_icon("🔗"), "Desglozar")
            act.triggered.connect(lambda: self._abrir_apu_insumo(insumo_id))
        elif matriz_id and matriz_id > 0:
            act = menu.addAction(_menu_icon("🔗"), "Desglozar")
            act.triggered.connect(lambda: self._abrir_apu_por_id(matriz_id))
        menu.exec(tabla.mapToGlobal(pos))
