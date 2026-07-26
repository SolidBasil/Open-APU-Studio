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
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHeaderView
from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef, EMPTY_ROLE
from backend.database.event_bus import (
    InsumoActualizado, NodoInsertado, NodoEliminado, ProyectoRecalculado,
)
from frontend.ventana.iconos import icono
from frontend.ventana.tipos_insumo import NOMBRE as _TIPO_NOMBRE, ICONO_SVG as _TIPO_ICONO_SVG, COLOR as _COLOR_TIPO

# Índice de la columna "Tipo" en COLUMNAS — usado para pintar el icono
# real (QIcon) del tipo de insumo en cada fila, en vez de un emoji de texto.
_COL_TIPO = 4


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
    "Usar Hoja FASAR", "Factor FSR",
    "Tipo de Trabajo",
    "Peso (kg)", "Comentarios",
    "Creado", "Creado Por", "Modificado", "Modificado Por",
]
EDITABLE = frozenset({1, 2, 3, 4, 5})  # Descripción, Unidad, Precio, Tipo, Familia

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

    ColumnaDef(15, "Usar Hoja FASAR",   "Mano de obra",   favorita_default=False, visible_default=False),
    ColumnaDef(16, "Factor FSR",        "Mano de obra",   favorita_default=False, visible_default=False),

    ColumnaDef(17, "Tipo de Trabajo",   "Trabajo",        favorita_default=False, visible_default=False),

    ColumnaDef(18, "Peso (kg)",         "Datos adicionales", favorita_default=False, visible_default=False),
    ColumnaDef(19, "Comentarios",       "Datos adicionales", favorita_default=False, visible_default=False),

    ColumnaDef(11, "Hash",              "Auditoría",      favorita_default=True,  visible_default=False),
    ColumnaDef(20, "Creado",            "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(21, "Creado Por",        "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(22, "Modificado",        "Auditoría",      favorita_default=False, visible_default=False),
    ColumnaDef(23, "Modificado Por",    "Auditoría",      favorita_default=False, visible_default=False),
]

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
    nuevo_insumo = Signal()
    EVENTOS_SUSCRITOS = {
        InsumoActualizado:   '_on_insumo_actualizado',
        NodoInsertado:       '_on_nodo_insertado',
        NodoEliminado:       '_on_nodo_eliminado',
        ProyectoRecalculado: '_on_proyecto_recalculado',
    }

    def __init__(self, parent=None):

        def _combo_unidad(parent):
            from PySide6.QtWidgets import QComboBox
            from frontend.ventana.widgets.base import UNIDADES
            combo = QComboBox(parent)
            combo.setEditable(False)
            combo.addItems(UNIDADES)
            return combo

        def _combo_tipo(parent):
            from PySide6.QtWidgets import QComboBox
            from frontend.ventana.tipos_insumo import NOMBRE as _NOMBRE
            combo = QComboBox(parent)
            combo.setEditable(False)
            for tid in (32, 1, 2, 4, 8, 16, 64, 128):
                nombre = _NOMBRE.get(tid, f"Tipo {tid}")
                combo.addItem(nombre, tid)
            return combo

        def _combo_familia(parent):
            from PySide6.QtWidgets import QComboBox
            combo = QComboBox(parent)
            combo.setEditable(False)
            combo.addItem("(Sin familia)", None)
            api = getattr(self, '_api', None)
            if api:
                for f in api.familias():
                    combo.addItem(f.get("nombre", "?"), f.get("id"))
            return combo

        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent,
                         column_editors={2: _combo_unidad, 4: _combo_tipo,
                                         5: _combo_familia},
                         paste_col_fn={4: self._resolver_tipo_pegado,
                                       5: self._resolver_familia_pegado})
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

    # ── Cortar / pegar: resolvers y creación de filas ─────────────────

    def _resolver_tipo_pegado(self, valor: str):
        """paste_col_fn de la columna Tipo (4): el texto pegado debe
        coincidir (sin importar mayúsculas) con el nombre de un tipo de
        insumo conocido (Material, Mano de obra, Herramienta...). Si no
        coincide con ninguno, no se toca la celda — pegar "asdf" en Tipo
        no debe dejar la fila con un tipo corrompido o vacío."""
        v = (valor or "").strip().lower()
        if not v:
            return None
        for tid, nombre in _TIPO_NOMBRE.items():
            if nombre.lower() == v:
                return (nombre, tid)
        return None

    def _resolver_familia_pegado(self, valor: str):
        """paste_col_fn de la columna Familia (5): busca por nombre entre
        las familias existentes del proyecto. Una celda pegada vacía sí
        limpia la familia (equivale a elegir "(Sin familia)" en el combo);
        un texto que no coincide con ninguna familia existente NO se
        escribe — evita que pegar algo mal escrito borre una familia ya
        asignada por accidente."""
        api = getattr(self, '_api', None)
        v = (valor or "").strip()
        if not v:
            return ("", None)
        if not api:
            return None
        for f in api.familias():
            nombre = (f.get("nombre") or "").strip()
            if nombre.lower() == v.lower():
                return (nombre, f.get("id"))
        return None

    def crear_fila_pegado(self, item_referencia, datos_fila: dict[int, str]):
        """Crea un insumo nuevo cuando el pegado trae más filas de las que
        hay en la tabla (ver TreeTableWidget.crear_fila_pegado). Requiere
        Descripción (col 1) y un Tipo reconocible (col 4); el resto de
        columnas pegadas (Unidad, Precio, Familia) son opcionales. Usa el
        mismo método que el diálogo "Nuevo insumo" (Api.insumo_insertar),
        así que dispara el mismo evento NodoInsertado que ya agrega la fila
        a esta tabla — solo hace falta ubicarla y devolverla."""
        api = getattr(self, '_api', None)
        if api is None:
            return None

        descripcion = (datos_fila.get(1) or "").strip()
        if not descripcion:
            return None

        tipo_resuelto = self._resolver_tipo_pegado(datos_fila.get(4, ""))
        if tipo_resuelto is None:
            return None
        _, tipo_id = tipo_resuelto

        unidad = (datos_fila.get(2) or "").strip() or None

        costo = 0.0
        precio_txt = (datos_fila.get(3) or "").strip()
        if precio_txt:
            try:
                costo = float(precio_txt.replace("$", "").replace(",", ""))
            except ValueError:
                costo = 0.0

        familia_id = None
        if datos_fila.get(5):
            familia_resuelta = self._resolver_familia_pegado(datos_fila[5])
            if familia_resuelta is not None:
                _, familia_id = familia_resuelta

        try:
            nuevo_id = api.insumo_insertar(
                tipo_id=tipo_id, descripcion=descripcion,
                unidad=unidad, costo=costo, familia_id=familia_id,
            )
        except Exception as e:
            print(f"Error insertando insumo pegado: {e}")
            return None

        return self._item_por_insumo(nuevo_id)

    def _context_menu_actions(self, menu):
        from frontend.ventana.widgets.base import _menu_icon
        items = self.selectedItems()
        act_nuevo = menu.addAction(_menu_icon("plus"), "Nuevo insumo")
        act_nuevo.triggered.connect(self._emit_nuevo)
        if len(items) == 1:
            item = items[0]
            insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
            act_rastrear = menu.addAction(_menu_icon("search"), "Rastrear uso")
            act_rastrear.setEnabled(bool(insumo_id))
            act_rastrear.triggered.connect(lambda: self._emit_rastrear(item))
            es_compuesto = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if es_compuesto:
                act = menu.addAction(_menu_icon("link"), "Desglozar")
                act.triggered.connect(lambda: self._emit_desglozar(insumo_id))

    def _emit_rastrear(self, item):
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if insumo_id:
            self.rastrear_insumo.emit(insumo_id)

    def _emit_desglozar(self, insumo_id):
        if insumo_id:
            self.desglozar_insumo.emit(insumo_id)

    def _emit_nuevo(self):
        self.nuevo_insumo.emit()

    @staticmethod
    def _valores_fila(ins: dict, tiene_sub_apu: bool) -> list[str]:
        """Construye los valores de columna para un insumo. Compartido por
        poblar() y por las actualizaciones in-place vía eventos, para que
        ambos caminos formateen exactamente igual."""
        clave_opus = ins.get("clave_opus") or ""
        tipo_id    = ins.get("tipo_id") or ins.get("tipo", 0)
        tipo_txt   = _TIPO_NOMBRE.get(tipo_id) or ins.get("tipo_nombre") or f"Tipo {tipo_id}"
        precio     = ins.get("costo_directo", 0) or 0
        desc       = ins.get("descripcion") or ins.get("descripcion_corta") or ""
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
            _si_no(ins.get("usar_hoja_fasar")),
            _num_opcional(ins.get("factor_fsr"), decimales=4),
            TIPO_TRABAJO_NOMBRE.get(tipo_trabajo, tipo_trabajo),
            _num_opcional(ins.get("peso_kg"), decimales=3),
            ins.get("comentarios") or "",
            ins.get("creado_en") or "",
            ins.get("creado_por_nombre") or "",
            ins.get("modificado_en") or "",
            ins.get("modificado_por_nombre") or "",
        ]

    @staticmethod
    def _set_tipo_icon(item, ins: dict):
        """Pinta el icono SVG real (Lucide) de la columna Tipo — reemplaza
        el viejo prefijo de emoji embebido en el texto."""
        tipo_id = ins.get("tipo_id") or ins.get("tipo", 0)
        svg_name = _TIPO_ICONO_SVG.get(tipo_id, "file-text")
        item.setIcon(_COL_TIPO, icono(svg_name, 16, _COLOR_TIPO.get(tipo_id)))

    def poblar(self, insumos: list[dict], ids_con_apu: set[int] | None = None):
        """Puebla la tabla. Marca con icono de capas los insumos compuestos."""
        self.clear()
        for ins in insumos:
            insumo_id = ins.get("id")
            tiene_sub_apu = bool(ids_con_apu and insumo_id in ids_con_apu)
            row_item = self.add_row(self._valores_fila(ins, tiene_sub_apu), editable=True)
            if row_item is not None:
                row_item.setData(0, Qt.ItemDataRole.UserRole, insumo_id)
                row_item.setData(0, Qt.ItemDataRole.UserRole + 1, tiene_sub_apu)
                self._set_tipo_icon(row_item, ins)
                if tiene_sub_apu:
                    row_item.setIcon(1, icono("combine", 16))
        self._add_empty_row()

    def _add_empty_row(self):
        """Fila visual vacía al final — al hacer clic crea un insumo nuevo."""
        item = self.add_row(
            ["", "Nuevo insumo...", "", "", "", "", "", "", "", "",
             "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
            editable=False,
        )
        item.setData(0, EMPTY_ROLE, True)
        self._estilizar_fila_vacia(item)

    def _al_click_fila_vacia(self):
        """Click en fila vacía → abre diálogo de nuevo insumo."""
        self.nuevo_insumo.emit()

    # ── Fase 3: suscripción a eventos semánticos ───────────────────
    #
    # Mismo esquema que TablaArbol.conectar_eventos(): reemplaza a la vieja
    # _refrescar_tabla_insumos()/_refrescar_tab_activa() centralizadas.

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
        """InsumoActualizado: actualiza in-place la fila, o muestre entre pestañas si cambia de tipo."""
        try:
            registro = evento.registro or {}
            item = self._item_por_insumo(evento.insumo_id)
            if item is not None:
                if not self._coincide_filtro(registro):
                    idx = self.indexOfTopLevelItem(item)
                    if idx >= 0:
                        self.takeTopLevelItem(idx)
                    return
                tiene_sub_apu = bool(registro.get("es_compuesto"))
                self.blockSignals(True)
                try:
                    for c, val in enumerate(self._valores_fila(registro, tiene_sub_apu)):
                        item.setText(c, val)
                    self._set_tipo_icon(item, registro)
                    item.setIcon(1, icono("combine", 16) if tiene_sub_apu else QIcon())
                finally:
                    self.blockSignals(False)
            elif self._coincide_filtro(registro):
                tiene_sub_apu = bool(registro.get("es_compuesto"))
                row_item = self.add_row(self._valores_fila(registro, tiene_sub_apu), editable=True)
                if row_item is not None:
                    row_item.setData(0, Qt.ItemDataRole.UserRole, evento.insumo_id)
                    row_item.setData(0, Qt.ItemDataRole.UserRole + 1, tiene_sub_apu)
                    self._set_tipo_icon(row_item, registro)
                    if tiene_sub_apu:
                        row_item.setIcon(1, icono("combine", 16))
        except Exception as e:
            print(f"[eventbus] _on_insumo_actualizado: {type(e).__name__}: {e}")

    def _on_nodo_insertado(self, evento):
        """NodoInsertado (entidad='insumos'): agrega la fila si coincide
        con el filtro de esta tabla."""
        try:
            if evento.tipo != "insumos" or self._api is None:
                return
            insumo = self._api.insumo_por_id(evento.nodo_id)
            if not insumo or not self._coincide_filtro(insumo):
                return
            tiene_sub_apu = bool(insumo.get("es_compuesto"))
            row_item = self.add_row(self._valores_fila(insumo, tiene_sub_apu=tiene_sub_apu), editable=True)
            if row_item is not None:
                row_item.setData(0, Qt.ItemDataRole.UserRole, evento.nodo_id)
                self._set_tipo_icon(row_item, insumo)
        except Exception as e:
            print(f"[eventbus] _on_nodo_insertado: {type(e).__name__}: {e}")

    def _on_nodo_eliminado(self, evento):
        """NodoEliminado (entidad='insumos'): quita la fila si está presente."""
        try:
            if evento.tipo != "insumos":
                return
            item = self._item_por_insumo(evento.nodo_id)
            if item is None:
                return
            idx = self.indexOfTopLevelItem(item)
            if idx >= 0:
                self.takeTopLevelItem(idx)
        except Exception as e:
            print(f"[eventbus] _on_nodo_eliminado: {type(e).__name__}: {e}")

    def _on_proyecto_recalculado(self, evento):
        """ProyectoRecalculado: repuebla desde la fuente de verdad,
        preservando scroll y selección."""
        try:
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
                    # ponytail: setCurrentItem → scrollTo async, restaurar después
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, lambda: self.verticalScrollBar().setValue(scroll_y))

            win = self.window()
            if hasattr(win, '_search_input') and hasattr(win, '_on_search'):
                win._on_search(win._search_input.text())
        except Exception as e:
            print(f"[eventbus] _on_proyecto_recalculado: {type(e).__name__}: {e}")
