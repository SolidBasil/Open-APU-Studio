"""
insumos.py
==========
Tabla plana del catálogo de insumos.

Nota sobre identificadores:
    La navegación interna (rastrear, editar, abrir APU) siempre usa el `id`
    (INTEGER PRIMARY KEY) del insumo, guardado en UserRole de la columna 0.
    La columna "Clave" muestra clave_opus — el código original de OPUS — y
    es puramente referencial: queda oculta por defecto y solo es útil para
    quien importó datos de OPUS y quiere seguir reconociendo sus códigos.

Uso:
    from frontend.widgets.insumos import TablaInsumos
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QMenu
from frontend.ventana.widgets.base import TreeTableWidget


# ── Configuración de columnas ─────────────────────────────────────

COLUMNAS = [
    "Clave", "Descripción", "Unidad", "Precio", "Tipo",
    "Familia", "Proveedor", "F. Precio", "Desc. Corta", "Costo MN", "Costo ME", "Hash",
]
EDITABLE = frozenset({1, 2, 3})  # Descripción, Unidad, Precio

TIPO_NOMBRE = {
    1:  "🧱 Material",
    2:  "👷 Mano de obra",
    4:  "🔧 Herramienta",
    8:  "🚜 Equipo",
    16: "⚙️ Auxiliar",
    32: "📄 Concepto",
    64: "🚛 Flete",
    128:"🏗️ Trabajo",
}


class TablaInsumos(TreeTableWidget):
    """Tabla plana del catálogo de insumos (sin jerarquía)."""
    _HEADER_KEY = "insumos_header_state"
    rastrear_insumo = Signal(int)
    desglozar_insumo = Signal(int)

    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 60, 100, 120, 120, 140, 85, 140, 95, 95, 90])
        })
        self.header().setMaximumSectionSize(400)
        for c in (0, 7, 8, 9, 10, 11):
            self.setColumnHidden(c, True)
        self._search_cols = {1, 5}
        self._restore_header_state()
        self._api = None  # inyectado por conectar_eventos()
        self._event_bus = None  # inyectado por conectar_eventos()

    def _context_menu_actions(self, menu):
        from frontend.ventana.widgets.base import _menu_icon
        items = self.selectedItems()
        if len(items) == 1:
            item = items[0]
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            act_rastrear = menu.addAction(_menu_icon("🔍"), "Rastrear uso")
            act_rastrear.setEnabled(bool(insumo_id))
            act_rastrear.triggered.connect(lambda: self._emit_rastrear(item))
            desc = item.text(1) or ""
            if desc.startswith("▶"):
                act = menu.addAction(_menu_icon("🔗"), "Desglozar")
                act.triggered.connect(lambda: self._emit_desglozar(insumo_id))

    def _emit_rastrear(self, item):
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if insumo_id:
            self.rastrear_insumo.emit(insumo_id)

    def _emit_desglozar(self, insumo_id):
        if insumo_id:
            self.desglozar_insumo.emit(insumo_id)

    @staticmethod
    def _valores_fila(ins: dict, tiene_sub_apu: bool) -> list[str]:
        """Construye los valores de columna para un insumo. Compartido por
        poblar() y por las actualizaciones in-place vía eventos, para que
        ambos caminos formateen exactamente igual."""
        clave_opus = ins.get("clave_opus") or ""
        tipo_id    = ins.get("tipo_id") or ins.get("tipo", 0)
        tipo_txt   = TIPO_NOMBRE.get(tipo_id) or ins.get("tipo_nombre") or f"Tipo {tipo_id}"
        precio     = ins.get("costo_final", 0) or 0
        desc       = ins.get("descripcion") or ins.get("descripcion_corta") or ""
        if tiene_sub_apu:
            desc = f"\u25b6 {desc}"
        return [
            clave_opus,
            desc,
            ins.get("unidad", "") or "",
            f"${precio:,.2f}",
            tipo_txt,
            (lambda f, s: f"{f} › {s}" if s else f)(
                ins.get("familia_nombre") or "",
                ins.get("subfamilia_nombre") or "",
            ),
            ins.get("proveedor_nombre") or "",
            ins.get("fecha_precio") or "",
            ins.get("descripcion_corta") or "",
            f"${ins.get('costo_mn', 0) or 0:,.2f}",
            f"${ins.get('costo_me', 0) or 0:,.2f}",
            ins.get("hash") or "",
        ]

    def poblar(self, insumos: list[dict], ids_con_apu: set[int] | None = None):
        """Puebla la tabla. ids_con_apu antepone ▶ a insumos compuestos."""
        self.clear()
        for ins in insumos:
            insumo_id = ins.get("id")
            tiene_sub_apu = bool(ids_con_apu and insumo_id in ids_con_apu)
            row_item = self.add_row(self._valores_fila(ins, tiene_sub_apu), editable=True)
            if row_item is not None:
                row_item.setData(0, Qt.ItemDataRole.UserRole, insumo_id)

    # ── Fase 3: suscripción a eventos semánticos ───────────────────
    #
    # Mismo esquema que TablaArbol.conectar_eventos(): reemplaza a la vieja
    # _refrescar_tabla_insumos()/_refrescar_tab_activa() centralizadas.

    def conectar_eventos(self, event_bus, api):
        """Suscribe esta tabla al EventBus del proyecto abierto.

        Llamar una sola vez tras poblar() (ver _build_insumos() en
        paneles.py), con el EventBus/Api vigentes al momento de construir
        la tabla.

        IMPORTANTE: quien remueva esta tabla de una pestaña DEBE llamar a
        desconectar_eventos() antes — ver la misma nota en
        widgets/arbol.py TablaArbol.conectar_eventos().
        """
        from backend.database.event_bus import (
            InsumoActualizado, NodoInsertado, NodoEliminado, ProyectoRecalculado,
        )
        self._api = api
        self._event_bus = event_bus
        event_bus.suscribir(InsumoActualizado, self._on_insumo_actualizado)
        event_bus.suscribir(NodoInsertado, self._on_nodo_insertado)
        event_bus.suscribir(NodoEliminado, self._on_nodo_eliminado)
        event_bus.suscribir(ProyectoRecalculado, self._on_proyecto_recalculado)

    def desconectar_eventos(self):
        """Retira las suscripciones hechas por conectar_eventos().
        Idempotente: no falla si nunca se conectó o ya se desconectó."""
        bus = getattr(self, '_event_bus', None)
        if bus is None:
            return
        from backend.database.event_bus import (
            InsumoActualizado, NodoInsertado, NodoEliminado, ProyectoRecalculado,
        )
        bus.desuscribir(InsumoActualizado, self._on_insumo_actualizado)
        bus.desuscribir(NodoInsertado, self._on_nodo_insertado)
        bus.desuscribir(NodoEliminado, self._on_nodo_eliminado)
        bus.desuscribir(ProyectoRecalculado, self._on_proyecto_recalculado)
        self._event_bus = None

    def _item_por_insumo(self, insumo_id: int):
        """Tabla plana: basta recorrer topLevelItems."""
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == insumo_id:
                return item
        return None

    def _coincide_filtro(self, registro: dict) -> bool:
        """True si un insumo pertenece al filtro de esta tabla (tipo / matrices)."""
        tipo = getattr(self, '_insumos_tipo', None)
        if tipo and registro.get("tipo_clave") != tipo:
            return False
        return True

    def _on_insumo_actualizado(self, evento):
        """InsumoActualizado: actualiza in-place la fila de este insumo, si
        está presente en esta tabla. No recalcula Total (esta tabla no lo
        muestra); ProyectoRecalculado se encarga de insumos compuestos cuyo
        costo_final cambia en cascada por este mismo edit."""
        item = self._item_por_insumo(evento.insumo_id)
        if item is None:
            return
        registro = evento.registro or {}
        prefijo = "\u25b6 " if item.text(1).startswith("\u25b6 ") else ""
        tiene_sub_apu = bool(prefijo)
        self.blockSignals(True)
        try:
            for c, val in enumerate(self._valores_fila(registro, tiene_sub_apu)):
                item.setText(c, val)
        finally:
            self.blockSignals(False)

    def _on_nodo_insertado(self, evento):
        """NodoInsertado (entidad='insumos'): agrega la fila si coincide
        con el filtro de esta tabla."""
        if evento.tipo != "insumos" or self._api is None:
            return
        insumo = self._api.insumo_por_id(evento.nodo_id)
        if not insumo or not self._coincide_filtro(insumo):
            return
        row_item = self.add_row(self._valores_fila(insumo, tiene_sub_apu=False), editable=True)
        if row_item is not None:
            row_item.setData(0, Qt.ItemDataRole.UserRole, evento.nodo_id)

    def _on_nodo_eliminado(self, evento):
        """NodoEliminado (entidad='insumos'): quita la fila si está presente."""
        if evento.tipo != "insumos":
            return
        item = self._item_por_insumo(evento.nodo_id)
        if item is None:
            return
        idx = self.indexOfTopLevelItem(item)
        if idx >= 0:
            self.takeTopLevelItem(idx)

    def _on_proyecto_recalculado(self, evento):
        """ProyectoRecalculado: repuebla desde la fuente de verdad,
        preservando scroll y selección.

        Necesario porque una cascada de recálculo puede cambiar el
        costo_final de insumos compuestos que no recibieron su propio
        InsumoActualizado (RecalculoRepo escribe directo, sin pasar por
        DataService) — no hay forma barata de saber cuáles sin repetir el
        cálculo del backend."""
        if self._api is None:
            return
        scroll_y = self.verticalScrollBar().value()
        current = self.currentItem()
        id_actual = current.data(0, Qt.ItemDataRole.UserRole) if current else None

        self.blockSignals(True)
        try:
            tipo = getattr(self, '_insumos_tipo', None)
            ids = self._api.insumo_ids_con_apu()
            if getattr(self, '_insumos_matrices', False):
                insumos = self._api.insumos_con_matrices(tipo)
            else:
                insumos = self._api.insumos(tipo)
            self.poblar(insumos, ids)
        finally:
            self.blockSignals(False)

        self.verticalScrollBar().setValue(scroll_y)
        if id_actual is not None:
            item = self._item_por_insumo(id_actual)
            if item is not None:
                self.setCurrentItem(item)

        win = self.window()
        if hasattr(win, '_search_input') and hasattr(win, '_on_search'):
            win._on_search(win._search_input.text())
