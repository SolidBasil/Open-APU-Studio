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
from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef


# ── Configuración de columnas ─────────────────────────────────────
#
# Las primeras 12 son las de siempre (mismo orden e índice, para no romper
# el header state ya guardado de quien actualice). El resto — hasta ahora
# datos que existían en la BD pero ninguna columna mostraba — se agregan
# al final, ocultas y sin marcar como favoritas por defecto: no aparecen
# en el menú rápido de clic derecho hasta que el usuario las active desde
# "Personalizar columnas…", así el menú de hoy no cambia de tamaño solo.

COLUMNAS = [
    "Clave", "Descripción", "Unidad", "Precio", "Tipo",
    "Familia", "Proveedor", "F. Precio", "Desc. Corta", "Costo MN", "Costo ME", "Hash",
    "Costo Directo", "Clave Usuario", "Compuesto",
    "Salario Nominal", "Salario Real", "Usar Hoja FASAR", "CatFSR", "Factor FSR", "FSR Mínimo",
    "Tipo de Trabajo",
    "Peso (kg)", "Comentarios", "Índice INEGI",
    "Creado", "Creado Por", "Modificado", "Modificado Por",
]
EDITABLE = frozenset({1, 2, 3})  # Descripción, Unidad, Precio

# Catálogo para el esquema de favoritas + "Personalizar columnas…" (ver
# widgets/base.py PersonalizarColumnasDialog). idx debe coincidir con la
# posición en COLUMNAS de arriba.
COLUMNAS_CATALOGO = [
    ColumnaDef(0,  "Clave",             "Identificación", favorita_default=True,  visible_default=False),
    ColumnaDef(1,  "Descripción",       "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(2,  "Unidad",            "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(4,  "Tipo",              "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(5,  "Familia",           "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(6,  "Proveedor",         "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(13, "Clave Usuario",     "Identificación", favorita_default=False, visible_default=False),
    ColumnaDef(14, "Compuesto",         "Identificación", favorita_default=False, visible_default=False),

    ColumnaDef(8,  "Desc. Corta",       "Descripción",    favorita_default=True,  visible_default=False),

    ColumnaDef(3,  "Precio",            "Costos",         favorita_default=True,  visible_default=True),
    ColumnaDef(7,  "F. Precio",         "Costos",         favorita_default=True,  visible_default=False),
    ColumnaDef(9,  "Costo MN",          "Costos",         favorita_default=True,  visible_default=False),
    ColumnaDef(10, "Costo ME",          "Costos",         favorita_default=True,  visible_default=False),
    ColumnaDef(12, "Costo Directo",     "Costos",         favorita_default=False, visible_default=False),

    ColumnaDef(15, "Salario Nominal",   "Mano de obra",   favorita_default=False, visible_default=False),
    ColumnaDef(16, "Salario Real",      "Mano de obra",   favorita_default=False, visible_default=False),
    ColumnaDef(17, "Usar Hoja FASAR",   "Mano de obra",   favorita_default=False, visible_default=False),
    ColumnaDef(18, "CatFSR",            "Mano de obra",   favorita_default=False, visible_default=False),
    ColumnaDef(19, "Factor FSR",        "Mano de obra",   favorita_default=False, visible_default=False),
    ColumnaDef(20, "FSR Mínimo",        "Mano de obra",   favorita_default=False, visible_default=False),

    ColumnaDef(21, "Tipo de Trabajo",   "Trabajo",        favorita_default=False, visible_default=False),

    ColumnaDef(22, "Peso (kg)",         "Datos adicionales", favorita_default=False, visible_default=False),
    ColumnaDef(23, "Comentarios",       "Datos adicionales", favorita_default=False, visible_default=False),
    ColumnaDef(24, "Índice INEGI",      "Datos adicionales", favorita_default=False, visible_default=False),

    ColumnaDef(11, "Hash",              "Auditoría",      favorita_default=True,  visible_default=False),
    ColumnaDef(25, "Creado",            "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(26, "Creado Por",        "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(27, "Modificado",        "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(28, "Modificado Por",    "Auditoría",      favorita_default=False, visible_default=False),
]

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

TIPO_TRABAJO_NOMBRE = {
    "subcontrato": "Subcontrato",
    "acarreo":     "Acarreo",
    "destajo":     "Destajo",
}


def _si_no(val) -> str:
    """Formatea un entero 0/1 de SQLite como Sí/No."""
    return "Sí" if val else "No"


def _num_opcional(val, decimales: int = 2) -> str:
    """Formatea un número que puede ser NULL. NULL -> '' (no '0.00', que
    daría a entender un valor real de cero donde en realidad no hay dato)."""
    if val is None:
        return ""
    return f"{val:,.{decimales}f}"


class TablaInsumos(TreeTableWidget):
    """Tabla plana del catálogo de insumos (sin jerarquía)."""
    _HEADER_KEY = "insumos_header_state"
    _CATALOGO_KEY = "insumos_columnas_favoritas"
    COLUMNAS_CATALOGO = COLUMNAS_CATALOGO
    rastrear_insumo = Signal(int)
    desglozar_insumo = Signal(int)

    def __init__(self, parent=None):
        def _combo_unidad(parent):
            from PySide6.QtWidgets import QComboBox
            from frontend.ventana.widgets.base import UNIDADES
            combo = QComboBox(parent)
            combo.setEditable(False)
            combo.addItems(UNIDADES)
            return combo

        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent,
                         column_editors={2: _combo_unidad})
        anchos = [90, 250, 60, 100, 120, 120, 140, 85, 140, 95, 95, 90]
        anchos += [100] * (len(COLUMNAS) - len(anchos))  # columnas nuevas: ancho por defecto
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate(anchos)
        })
        self.header().setMaximumSectionSize(400)
        # Visibilidad inicial: la define el catálogo (visible_default), no
        # una lista de índices a mano — así agregar una columna al catálogo
        # no obliga a acordarse de tocar esta lista también.
        #
        # setColumnHidden dispara sectionResized (N→0); _applying_modes
        # evita que _save_header_state sobreescriba el estado del usuario.
        self._applying_modes = True
        for col in COLUMNAS_CATALOGO:
            self.setColumnHidden(col.idx, not col.visible_default)
        self._applying_modes = False
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
        tipo_trabajo = ins.get("tipo_trabajo") or ""
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
            f"${ins.get('costo_directo', 0) or 0:,.2f}",
            ins.get("clave_usuario") or "",
            _si_no(ins.get("es_compuesto")),
            _num_opcional(ins.get("salario_nominal")),
            _num_opcional(ins.get("salario_real")),
            _si_no(ins.get("usar_hoja_fasar")),
            ins.get("catfsr") or "",
            _num_opcional(ins.get("factor_fsr"), decimales=4),
            _si_no(ins.get("fsr_minimo")),
            TIPO_TRABAJO_NOMBRE.get(tipo_trabajo, tipo_trabajo),
            _num_opcional(ins.get("peso_kg"), decimales=3),
            ins.get("comentarios") or "",
            ins.get("indice_inegi") or "",
            ins.get("creado_en") or "",
            ins.get("creado_por_nombre") or "",
            ins.get("modificado_en") or "",
            ins.get("modificado_por_nombre") or "",
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
