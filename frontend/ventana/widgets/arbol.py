"""
arbol.py
========
Tabla jerárquica del presupuesto (capítulos + conceptos).

Uso:
    from frontend.widgets.arbol import TablaArbol
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QIcon, QPixmap, QPainter
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QHeaderView

from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef


# ── Icono desde emoji ───────────────────────────────────────────

def _emoji_icon(char, size=20):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setPen(QColor("#E8EDF2"))
    p.setFont(QFont("Segoe UI Symbol", size - 6))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, char)
    p.end()
    return QIcon(pix)


# ── Roles de datos ────────────────────────────────────────────────

WBS_ROLE       = Qt.ItemDataRole.UserRole
ID_ROLE        = Qt.ItemDataRole.UserRole + 1   # id de estructura_presupuesto
TIPO_ROLE      = Qt.ItemDataRole.UserRole + 12  # 'capitulo' | 'concepto', seteado explícitamente
                                                 # al crear la fila (NO se infiere leyendo texto)
INSUMO_ROLE    = Qt.ItemDataRole.UserRole + 13  # insumo_id ligado (solo conceptos), para
                                                 # localizar filas afectadas por InsumoActualizado

# ── Configuración de columnas ─────────────────────────────────────

# Col  0: Estructura  (ícono)
# Col  1: Nivel       (wbs display)
# Col  2: Tipo
# Col  3: Clave       (clave_opus — referencial, oculta por defecto)
# Col  4: Descripción
# Col  5: Unidad      (desde insumos)
# Col  6: Cant
# Col  7: P.U.        (precio_unitario desde insumos.costo_final)
# Col  8: Total
# Col  9: Estado
# Col 10: Notas
# Col 11: Creado
# Col 12: Modificado
# Col 13: Orden       (orden manual dentro del padre — nuevo)
# Col 14: Fórmula     (expresión de cálculo de cantidad, cuando existe — nuevo)
COLUMNAS = [
    "Estructura", "Nivel", "Tipo", "Clave", "Descripción",
    "Unidad", "Cant", "P.U.", "Total",
    "Estado", "Notas", "Creado", "Modificado",
    "Orden", "Fórmula",
]
EDITABLE    = frozenset({4, 6})        # fallback genérico (usado hoy solo por copiar/pegar)
_AGRUP_COLS = {0, 1, 4, 8}

# Catálogo para el esquema de favoritas + "Personalizar columnas…" (ver
# widgets/base.py PersonalizarColumnasDialog). idx debe coincidir con la
# posición en COLUMNAS de arriba. _VISIBLE ya no se lista a mano: se
# deriva del catálogo (visible_default) en __init__.
COLUMNAS_CATALOGO = [
    ColumnaDef(0,  "Estructura",  "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(1,  "Nivel",       "Identificación", favorita_default=True,  visible_default=True),
    ColumnaDef(2,  "Tipo",        "Identificación", favorita_default=True,  visible_default=False),
    ColumnaDef(3,  "Clave",       "Identificación", favorita_default=True,  visible_default=False),
    ColumnaDef(4,  "Descripción", "Identificación", favorita_default=True,  visible_default=True),

    ColumnaDef(5,  "Unidad",      "Cálculo", favorita_default=True,  visible_default=True),
    ColumnaDef(6,  "Cant",        "Cálculo", favorita_default=True,  visible_default=True),
    ColumnaDef(7,  "P.U.",        "Cálculo", favorita_default=True,  visible_default=True),
    ColumnaDef(8,  "Total",       "Cálculo", favorita_default=True,  visible_default=True),
    ColumnaDef(13, "Orden",       "Cálculo", favorita_default=False, visible_default=False),
    ColumnaDef(14, "Fórmula",     "Cálculo", favorita_default=False, visible_default=False),

    ColumnaDef(9,  "Estado",      "Seguimiento", favorita_default=True,  visible_default=False),
    ColumnaDef(10, "Notas",       "Seguimiento", favorita_default=True,  visible_default=False),

    ColumnaDef(11, "Creado",      "Auditoría", favorita_default=False, visible_default=False),
    ColumnaDef(12, "Modificado",  "Auditoría", favorita_default=False, visible_default=False),
]

# Columnas editables según el tipo de nodo (fila). Se usa vía editable_cols_fn
# — el tipo se lee de TIPO_ROLE (dato explícito seteado al crear la fila),
# nunca del texto de la columna "Tipo", que en otras tablas basadas en
# TreeTableWidget significa otra cosa (ver base.py::_Delegate).
_EDITABLE_POR_TIPO = {
    "capitulo": {4},          # Descripción
    "concepto": {4, 5, 6},    # Desc, Unidad, Cant (vía insumo ligado)
    # P.U. (col 7) NO es editable aquí a propósito: el árbol solo tiene el
    # insumo_id, no si es compuesto, así que no podía distinguir "básico sin
    # APU" de "compuesto" para bloquear solo este último caso (por eso sí
    # funcionaba el bloqueo dentro del APU pero no aquí). Precio se edita
    # desde Insumos o desde dentro del APU — nunca desde el árbol.
}


def _editable_cols_arbol(item) -> set[int]:
    """Columnas editables para una fila del árbol de presupuesto, según su tipo."""
    tipo = item.data(0, TIPO_ROLE)
    return _EDITABLE_POR_TIPO.get(tipo, set())

# ── Colores por nivel jerárquico ─────────────────────────────────

COLORES_NIVEL = [
    "#8B6FB5",  # 0: púrpura  — capítulo raíz
    "#7FAFD6",  # 1: azul
    "#5E9CA0",  # 2: teal
    "#D5B39B",  # 3: beige cálido
    "#5B8A72",  # 4: verde
    "#A06A6A",  # 5+: vino
]

# Estado de revisión de un concepto (0-3, ver NodoRepo.arbol()).
ESTADO_NOMBRE = {
    0: "Sin revisar",
    1: "En revisión",
    2: "Verificado",
    3: "Cuestionado",
}


# ── Formateo de valores ───────────────────────────────────────────

def _fmt(v, decimals=2):
    """Formatea número como moneda ($1,234.56) o devuelve string vacío si es None."""
    if v is None:
        return ""
    return f"${v:,.{decimals}f}" if isinstance(v, (int, float)) else str(v)


def _num(v, decimals=2):
    """Formatea número con separadores de miles y decimales, o string vacío si es falsy."""
    if not v:
        return ""
    return f"{v:,.{decimals}f}" if isinstance(v, (int, float)) else str(v)


# ── Tabla jerárquica del presupuesto ──────────────────────────────

class TablaArbol(TreeTableWidget):
    """Árbol jerárquico del presupuesto.
    Capítulos se muestran con color según nivel y texto en negritas.
    Conceptos son hojas editables (cantidad, precio, clave, descripción).
    El estado del header (anchos, visibilidad) persiste entre sesiones.
    """
    _HEADER_KEY = "arbol_header_state"
    _CATALOGO_KEY = "arbol_columnas_favoritas"
    COLUMNAS_CATALOGO = COLUMNAS_CATALOGO
    rastrear_insumo = Signal(int)
    desglozar_nodo = Signal(int)

    def __init__(self, parent=None):
        """Inicializa el árbol de presupuesto con columnas fijas, modo de columnas, búsqueda y restauración del header."""
        super().__init__(COLUMNAS, EDITABLE, parent=parent,
                          editable_cols_fn=_editable_cols_arbol)
        anchos = [80, 80, 70, 90, 250, 55, 65, 90, 90, 70, 100, 130, 130]
        anchos += [70, 160]  # Orden, Fórmula
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate(anchos)
        })
        self.header().setMaximumSectionSize(400)
        # Visibilidad inicial: la define el catálogo (visible_default), no
        # una lista de índices a mano — agregar una columna al catálogo ya
        # no obliga a acordarse de tocar esta lista también.
        #
        # IMPORTANTE: esto va ANTES de _restore_header_state(). Si el orden
        # se invierte, un usuario que hubiera mostrado manualmente una
        # columna oculta por defecto (ej. "Clave") vería su elección
        # revertida en cada arranque, porque este bucle la volvería a
        # ocultar después de que restoreState() ya la había recuperado.
        for col in COLUMNAS_CATALOGO:
            self.setColumnHidden(col.idx, not col.visible_default)
        self._restore_header_state()
        self._search_cols = {4}  # búsqueda por Descripción
        self._api = None  # inyectado por conectar_eventos()
        self._event_bus = None  # inyectado por conectar_eventos()

    def _context_menu_actions(self, menu):
        from frontend.ventana.widgets.base import _menu_icon
        if len(self.selectedItems()) != 1:
            return
        item = self.currentItem()
        if not item:
            return
        tipo = item.data(0, TIPO_ROLE)
        if tipo != "concepto":
            return
        insumo_id = item.data(0, INSUMO_ROLE)
        nodo_id = item.data(0, ID_ROLE)
        menu.addSeparator()
        if insumo_id:
            act = menu.addAction(_menu_icon("🔍"), "Rastrear uso")
            act.triggered.connect(lambda: self.rastrear_insumo.emit(insumo_id))
        if nodo_id:
            act = menu.addAction(_menu_icon("🔗"), "Desglozar")
            act.triggered.connect(lambda: self.desglozar_nodo.emit(nodo_id))


    # ── Helpers de WBS ────────────────────────────────────────────

    @staticmethod
    def _calc_wbs(wbs: str, parent):
        """Concatena el display WBS del padre con el sufijo del nodo."""
        if not wbs:
            return ""
        pwbs_raw = ""
        pwbs_display = ""
        if parent is not None:
            try:
                pwbs_raw = parent.data(0, WBS_ROLE)
                pwbs_display = parent.text(1)  # columna Nivel = display WBS
            except AttributeError:
                pass
        if not pwbs_raw:
            return str(int(wbs))
        suffix = wbs[len(pwbs_raw):]
        return f"{pwbs_display}.{str(int(suffix))}"

    # ── Construcción de celdas desde dict ─────────────────────────

    @staticmethod
    def _celdas(n, wbs):
        """Construye la lista de valores para todas las columnas desde el dict del nodo."""
        return [
            "",                                            # 0  Estructura (icon via setIcon)
            wbs,                                           # 1  Nivel (wbs display)
            {"capitulo": "Capítulo", "concepto": "Concepto"}.get(n.get("tipo"), n.get("tipo", "")),  # 2  Tipo
            n.get("clave_opus") or "",                     # 3  Clave (referencial, oculta)
            n.get("descripcion", ""),                      # 4  Descripción
            n.get("unidad") or "",                         # 5  Unidad (desde insumos)
            _num(n.get("cantidad")),                       # 6  Cant
            _fmt(n.get("precio_unitario")),                # 7  P.U.
            _fmt(n.get("total")),                          # 8  Total
            ESTADO_NOMBRE.get(n.get("estado"), ""),        # 9  Estado (bug previo: leía "estado_nombre",
                                                            #    clave que el repo nunca devuelve — siempre
                                                            #    salía vacío; ahora resuelve desde "estado")
            n.get("notas_rapidas", ""),                    # 10 Notas
            str(n.get("creado_en", "") or ""),             # 11 Creado
            str(n.get("modificado_en", "") or ""),         # 12 Modificado
            _num(n.get("orden"), decimals=0),              # 13 Orden
            n.get("formula") or "",                        # 14 Fórmula
        ]

    # ── Inserción de agrupadores ──────────────────────────────────

    def add_agrupador(self, n, parent=None, expanded=True):
        """Agrega nodo agrupador (capítulo).
        El delegado inteligente permite editar col 4 (Descripción) para capítulos.
        """
        parent = parent or self
        nivel = 0
        p = parent
        while p is not None and p is not self:
            nivel += 1
            p = p.parent()
        wbs  = n.get("wbs", "")
        fmt  = self._calc_wbs(wbs, parent)
        data = self._celdas(n, fmt)
        item = self.add_row(data, parent, editable=True)
        item.setData(0, WBS_ROLE, wbs)
        item.setData(0, ID_ROLE, n.get("id"))
        item.setData(0, TIPO_ROLE, "capitulo")
        item.setIcon(0, _emoji_icon("\U0001F4C2", 20))  # 📂 folder
        color = COLORES_NIVEL[min(nivel, len(COLORES_NIVEL) - 1)]
        brush = QBrush(QColor(color))
        f     = item.font(0)
        f.setBold(True)
        for c in range(item.columnCount()):
            item.setForeground(c, brush)
            item.setFont(c, f)
        item.setExpanded(expanded)
        return item

    def add_registro(self, n, parent=None):
        """Agrega nodo hoja (concepto).
        El delegado inteligente permite editar col 6 (Cant) para conceptos.
        Descripción (col 4) no es editable — refleja insumos.descripcion via JOIN.
        """
        data = self._celdas(n, "")
        item = self.add_row(data, parent, editable=True)
        item.setData(0, ID_ROLE, n.get("id"))
        item.setData(0, TIPO_ROLE, "concepto")
        item.setData(0, INSUMO_ROLE, n.get("insumo_id"))
        item.setIcon(0, _emoji_icon("\U0001F4C4", 20))  # 📄 leaf
        return item

    # ── Poblado del árbol ─────────────────────────────────────────

    def poblar(self, nodos_raiz: list[dict]):
        """Puebla el árbol completo desde lista de nodos raíz devuelta por NodoRepo.arbol()."""
        self.clear()
        self._poblar_nodos(nodos_raiz, None)

    def _poblar_nodos(self, nodos, parent):
        """Recorre recursivamente los nodos insertando agrupadores y registros en el widget."""
        for n in nodos:
            if n["tipo"] == "capitulo":
                if not n.get("wbs"):
                    self._poblar_nodos(n.get("hijos", []), parent)
                    continue
                item = self.add_agrupador(n, parent=parent)
                self._poblar_nodos(n.get("hijos", []), item)
            else:
                self.add_registro(n, parent=parent)

    # ── Fase 3: suscripción a eventos semánticos ───────────────────
    #
    # Reemplaza a la vieja _refrescar_tab_activa() centralizada: el propio
    # widget se suscribe al EventBus del proyecto abierto y decide cómo
    # reaccionar a cada evento. Ediciones que no cambian totales (descripción,
    # unidad) se resuelven fila por fila, in-place. Ediciones que sí cambian
    # totales (cantidad, precio, factores) disparan una cascada que puede
    # tocar un número arbitrario de nodos ancestro — para esas, ProyectoRecalculado
    # es la señal de "repuebla desde la fuente de verdad", que aquí se
    # implementa preservando scroll y selección.

    def conectar_eventos(self, event_bus, api):
        """Suscribe este árbol al EventBus del proyecto abierto.

        Debe llamarse una sola vez, justo después de poblar(), con el
        EventBus y el Api vigentes en ese momento (ver _build_presupuesto()
        en paneles.py). Como cada apertura de proyecto crea un EventBus
        nuevo, este árbol se reconstruye desde cero en cada apertura y por
        lo tanto siempre queda enganchado al bus correcto.

        IMPORTANTE: quien remueva este widget de una pestaña (removeTab,
        reemplazo por pestaña temporal del sidebar, etc.) DEBE llamar a
        desconectar_eventos() antes — si no, el widget queda "zombi":
        sigue registrado en el bus con su objeto Qt ya destruido, y la
        próxima emisión de evento revienta con
        RuntimeError: libshiboken...already deleted.
        """
        from backend.database.event_bus import (
            ConceptoActualizado, InsumoActualizado, ProyectoRecalculado,
        )
        self._api = api
        self._event_bus = event_bus
        event_bus.suscribir(ConceptoActualizado, self._on_concepto_actualizado)
        event_bus.suscribir(InsumoActualizado, self._on_insumo_actualizado)
        event_bus.suscribir(ProyectoRecalculado, self._on_proyecto_recalculado)

    def desconectar_eventos(self):
        """Retira las suscripciones hechas por conectar_eventos().

        Llamar SIEMPRE antes de quitar este widget de su pestaña (ver
        HandlersMixin._cerrar_tab_widget() en handlers/__init__.py).
        Idempotente: no falla si nunca se conectó o ya se desconectó.
        """
        bus = getattr(self, '_event_bus', None)
        if bus is None:
            return
        from backend.database.event_bus import (
            ConceptoActualizado, InsumoActualizado, ProyectoRecalculado,
        )
        bus.desuscribir(ConceptoActualizado, self._on_concepto_actualizado)
        bus.desuscribir(InsumoActualizado, self._on_insumo_actualizado)
        bus.desuscribir(ProyectoRecalculado, self._on_proyecto_recalculado)
        self._event_bus = None

    def _buscar_item_por_id(self, nodo_id: int):
        """Búsqueda recursiva de la fila cuyo ID_ROLE == nodo_id."""
        def _rec(item):
            for i in range(item.childCount()):
                hijo = item.child(i)
                if hijo.data(0, ID_ROLE) == nodo_id:
                    return hijo
                encontrado = _rec(hijo)
                if encontrado is not None:
                    return encontrado
            return None
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            if top.data(0, ID_ROLE) == nodo_id:
                return top
            encontrado = _rec(top)
            if encontrado is not None:
                return encontrado
        return None

    def _buscar_items_por_insumo(self, insumo_id: int) -> list:
        """Búsqueda recursiva de todas las filas cuyo INSUMO_ROLE == insumo_id
        (un mismo insumo puede aparecer en varios conceptos del árbol)."""
        encontrados = []
        def _rec(item):
            for i in range(item.childCount()):
                hijo = item.child(i)
                if hijo.data(0, INSUMO_ROLE) == insumo_id:
                    encontrados.append(hijo)
                _rec(hijo)
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            if top.data(0, INSUMO_ROLE) == insumo_id:
                encontrados.append(top)
            _rec(top)
        return encontrados

    def _on_concepto_actualizado(self, evento):
        """ConceptoActualizado: actualiza in-place la fila propia del nodo.

        Cubre descripción de agrupadores (el único campo de
        estructura_presupuesto editable directamente desde la UI que no
        depende del insumo ligado). El total mostrado aquí puede quedar
        momentáneamente desactualizado si el cambio también dispara una
        cascada — el ProyectoRecalculado que le sigue lo deja consistente.
        """
        item = self._buscar_item_por_id(evento.concepto_id)
        if item is None:
            return
        registro = evento.registro or {}
        if "descripcion" in evento.cambios:
            item.setText(4, registro.get("descripcion", "") or "")
        if "cantidad" in evento.cambios:
            item.setText(6, _num(registro.get("cantidad")))
        if "total" in registro:
            item.setText(8, _fmt(registro.get("total")))

    def _on_insumo_actualizado(self, evento):
        """InsumoActualizado: actualiza in-place todas las filas de concepto
        ligadas a este insumo (descripción, unidad, P.U.).

        El Total no se recalcula aquí: cambiar el precio de un insumo
        siempre dispara RecalculoRepo.recalcular_proyecto() en api.py, que
        emite ProyectoRecalculado a continuación con los totales correctos.
        """
        items = self._buscar_items_por_insumo(evento.insumo_id)
        if not items:
            return
        registro = evento.registro or {}
        for item in items:
            if "descripcion" in evento.cambios:
                item.setText(4, registro.get("descripcion", "") or "")
            if "unidad" in evento.cambios:
                item.setText(5, registro.get("unidad", "") or "")
            if any(c in evento.cambios for c in ("costo_final", "costo_mn", "costo_directo")):
                item.setText(7, _fmt(registro.get("costo_final")))

    def _on_proyecto_recalculado(self, evento):
        """ProyectoRecalculado: repuebla desde la fuente de verdad.

        Una cascada de recálculo puede alterar el total de un número
        arbitrario de conceptos y capítulos ancestro — no hay forma barata
        de saber cuáles sin repetir el propio cálculo del backend. Repoblar
        preservando scroll y selección es el equivalente in-place razonable
        para este caso (igual a lo que hacía _refrescar_tab_activa(), pero
        ahora decidido por el propio widget, no por un router central).
        """
        if self._api is None:
            return
        scroll_y = self.verticalScrollBar().value()
        current = self.currentItem()
        id_actual = current.data(0, ID_ROLE) if current else None

        self.blockSignals(True)
        try:
            nodos = self._api.presupuesto_arbol()
            self.poblar(nodos)
        finally:
            self.blockSignals(False)

        self.verticalScrollBar().setValue(scroll_y)
        if id_actual is not None:
            item = self._buscar_item_por_id(id_actual)
            if item is not None:
                self.setCurrentItem(item)

        win = self.window()
        if hasattr(win, '_search_input') and hasattr(win, '_on_search'):
            win._on_search(win._search_input.text())
