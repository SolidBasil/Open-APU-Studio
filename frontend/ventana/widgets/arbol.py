"""
arbol.py
========
Tabla jerárquica del presupuesto (capítulos + conceptos).

Uso:
    from frontend.widgets.arbol import TablaArbol
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from PySide6.QtWidgets import QHeaderView

from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef, FORMULA_ROLE


# ── Icono desde tipo_id (Lucide SVG) ─────────────────────────────

from frontend.ventana.iconos import icono
from frontend.ventana.colores import ACCENT, SUCCESS, WARNING, ERROR
from frontend.ventana.tipos_insumo import ICONO_SVG as _ICONOS_TIPO_SVG, COLOR as _COLOR_TIPO


# ── Roles de datos ────────────────────────────────────────────────

WBS_ROLE       = Qt.ItemDataRole.UserRole
ID_ROLE        = Qt.ItemDataRole.UserRole + 1   # id de estructura_presupuesto
TIPO_ROLE      = Qt.ItemDataRole.UserRole + 12  # 'capitulo' | 'concepto', seteado explícitamente
                                                 # al crear la fila (NO se infiere leyendo texto)
INSUMO_ROLE    = Qt.ItemDataRole.UserRole + 13  # insumo_id ligado (solo conceptos), para
                                                 # localizar filas afectadas por InsumoActualizado
EMPTY_ROLE     = Qt.ItemDataRole.UserRole + 60  # fila visual vacía (no existe en DB)

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
EDITABLE    = frozenset()               # editable_cols_fn define edición por fila
_AGRUP_COLS = {0, 1, 4, 8}

# Catálogo para el esquema de favoritas + "Personalizar columnas…" (ver
# widgets/base.py PersonalizarColumnasDialog). idx debe coincidir con la
# posición en COLUMNAS de arriba. _VISIBLE ya no se lista a mano: se
# deriva del catálogo (visible_default) en __init__.
COLUMNAS_CATALOGO = [
    ColumnaDef(0,  "Estructura",  "Identificación", favorita_default=True,  visible_default=True,  imprimible_default=False),
    ColumnaDef(1,  "Nivel",       "Identificación", favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(2,  "Tipo",        "Identificación", favorita_default=True,  visible_default=False, imprimible_default=False),
    ColumnaDef(3,  "Clave",       "Identificación", favorita_default=False, visible_default=False, imprimible_default=False),
    ColumnaDef(4,  "Descripción", "Identificación", favorita_default=True,  visible_default=True,  imprimible_default=True),

    ColumnaDef(5,  "Unidad",      "Cálculo", favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(6,  "Cant",        "Cálculo", favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(7,  "P.U.",        "Cálculo", favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(8,  "Total",       "Cálculo", favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(13, "Orden",       "Cálculo", favorita_default=False, visible_default=False, imprimible_default=False),
    ColumnaDef(14, "Fórmula",     "Cálculo", favorita_default=False, visible_default=False, imprimible_default=False),

    ColumnaDef(9,  "Estado",      "Seguimiento", favorita_default=True,  visible_default=False, imprimible_default=False),
    ColumnaDef(10, "Notas",       "Seguimiento", favorita_default=True,  visible_default=True,  imprimible_default=False),

    ColumnaDef(11, "Creado",      "Auditoría", favorita_default=False, visible_default=False, imprimible_default=False),
    ColumnaDef(12, "Modificado",  "Auditoría", favorita_default=False, visible_default=False, imprimible_default=False),
]

# Traduce cada idx de columna del árbol al nombre de campo que entiende
# backend/exportar/informe_pdf/latex.py al armar la tabla del reporte
# (ver ReportePresupuesto y _CAMPOS ahí). Mantiene arbol.py y latex.py
# desacoplados: latex.py no conoce el layout de columnas de esta tabla.
CAMPO_REPORTE = {
    0:  "estructura",
    1:  "nivel",
    2:  "tipo",
    3:  "clave",
    4:  "descripcion",
    5:  "unidad",
    6:  "cantidad",
    7:  "precio_unitario",
    8:  "total",
    9:  "estado",
    10: "notas",
    11: "creado",
    12: "modificado",
    13: "orden",
    14: "formula",
}

# Columnas editables según el tipo de nodo (fila). Se usa vía editable_cols_fn
# — el tipo se lee de TIPO_ROLE (dato explícito seteado al crear la fila),
# nunca del texto de la columna "Tipo", que en otras tablas basadas en
# TreeTableWidget significa otra cosa (ver base.py::_Delegate).
_EDITABLE_POR_TIPO = {
    "capitulo": {4, 10},      # Descripción, Notas
    "concepto": {6, 10},      # Cant, Notas
}


def _editable_cols_arbol(item) -> set[int]:
    """Columnas editables para una fila del árbol de presupuesto, según su tipo."""
    tipo = item.data(0, TIPO_ROLE)
    return _EDITABLE_POR_TIPO.get(tipo, set())

# ── Colores por nivel jerárquico ─────────────────────────────────

COLORES_NIVEL = [
    "#8B6FB5",  # 0: púrpura  — capítulo raíz
    ACCENT,     # 1: azul
    "#5E9CA0",  # 2: teal
    WARNING,    # 3: beige cálido
    SUCCESS,    # 4: verde
    ERROR,      # 5+: vino
]

from backend.database.repos.presupuesto import ESTADO_NOMBRE
from backend.database.event_bus import (
    ConceptoActualizado, InsumoActualizado, NodoEliminado, ProyectoRecalculado,
)


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
    EVENTOS_SUSCRITOS = {
        ConceptoActualizado: '_on_concepto_actualizado',
        InsumoActualizado:   '_on_insumo_actualizado',
        NodoEliminado:       '_on_nodo_eliminado',
        ProyectoRecalculado: '_on_proyecto_recalculado',
    }
    modificar_insumo = Signal(int)
    cambiar_insumo = Signal(int)
    agregar_agrupador = Signal()
    agregar_concepto = Signal()
    eliminar_seleccion = Signal()

    # Handler por defecto de cada señal, buscado por nombre en el objeto
    # que reciba conectar_handlers(). Evita repetir este cableado en cada
    # lugar que construye un TablaArbol (panel principal, panel "extra",
    # popup — ver conectar_handlers()).
    _HANDLERS_ESTANDAR = {
        "itemChanged":         "_on_concepto_editado",
        "itemDoubleClicked":   "_on_item_dblclick",
        "rastrear_insumo":     "_on_rastrear_insumo",
        "modificar_insumo":    "_on_modificar_insumo",
        "cambiar_insumo":      "_on_cambiar_insumo",
        "desglozar_nodo":      "_abrir_apu_por_id",
        "agregar_agrupador":   "_on_agregar_agrupador",
        "agregar_concepto":    "_on_agregar_concepto",
        "eliminar_seleccion":  "_on_eliminar",
    }

    def __init__(self, parent=None, header_key: str | None = None,
                 extra: bool = False):
        """Inicializa el árbol de presupuesto.
        Si extra=True, este árbol muestra nodos es_extra=1 (fuera de presupuesto).
        """
        self._extra = extra
        if header_key:
            self._HEADER_KEY = header_key
        super().__init__(COLUMNAS, EDITABLE, parent=parent,
                          editable_cols_fn=_editable_cols_arbol)
        anchos = [160, 160, 140, 180, 500, 110, 130, 180, 180, 140, 200, 260, 260]
        anchos += [140, 320]  # Orden, Fórmula
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
        #
        # setColumnHidden dispara sectionResized al cambiar el ancho a 0,
        # y esa señal llama a _save_header_state, que sobreescribe el
        # estado guardado del usuario con valores por defecto.
        # El guard _applying_modes evita esa escritura espuria.
        self._applying_modes = True
        for col in COLUMNAS_CATALOGO:
            self.setColumnHidden(col.idx, not col.visible_default)
        self._applying_modes = False
        self._restore_header_state()
        self._search_cols = {4}  # búsqueda por Descripción
        self._api = None  # inyectado por conectar_eventos()
        self._event_bus = None  # inyectado por conectar_eventos()
        self.itemClicked.connect(self._on_item_clicked)

    def columnas_para_reporte(self) -> list[dict]:
        """Columnas imprimibles en orden visual + ancho actual, traducidas a
        los nombres de campo que espera ReportePresupuesto (ver latex.py).
        Se pasa tal cual a ReportePresupuesto(..., columnas=...) al generar
        el .tex del presupuesto.
        """
        columnas = []
        for c in self.columnas_para_imprimir():
            campo = CAMPO_REPORTE.get(c["idx"])
            if campo is None:
                continue
            columnas.append({"campo": campo, "label": c["label"], "ancho_px": c["ancho_px"]})
        return columnas

    def _on_item_clicked(self, item, column):
        """Click en la fila vacía final → crea un concepto nuevo."""
        if item.data(0, EMPTY_ROLE):
            self.agregar_concepto.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            item = self.currentItem()
            if item:
                insumo_id = item.data(0, INSUMO_ROLE)
                if insumo_id:
                    self.modificar_insumo.emit(insumo_id)
                    return
        elif event.key() == Qt.Key.Key_F5:
            item = self.currentItem()
            if item and item.data(0, TIPO_ROLE) == "concepto":
                nodo_id = item.data(0, ID_ROLE)
                if nodo_id:
                    self.cambiar_insumo.emit(nodo_id)
                    return
        elif event.key() == Qt.Key.Key_Insert:
            self.agregar_concepto.emit()
            return
        elif event.key() == Qt.Key.Key_Delete:
            self.eliminar_seleccion.emit()
            return
        super().keyPressEvent(event)

    def _context_menu_actions(self, menu):
        from frontend.ventana.widgets.base import _menu_icon
        menu.addSeparator()

        act = menu.addAction(_menu_icon("square-plus"), "Agregar agrupador")
        act.triggered.connect(self.agregar_agrupador)

        act = menu.addAction(_menu_icon("plus"), "Agregar concepto")
        act.triggered.connect(self.agregar_concepto)

        if self.selectedItems():
            act = menu.addAction(_menu_icon("x"), "Eliminar")
            act.triggered.connect(self.eliminar_seleccion)

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
        if insumo_id:
            act = menu.addAction(_menu_icon("search"), "Rastrear uso")
            act.triggered.connect(lambda: self.rastrear_insumo.emit(insumo_id))
            act = menu.addAction(_menu_icon("edit"), "Modificar insumo")
            act.triggered.connect(lambda: self.modificar_insumo.emit(insumo_id))
        if nodo_id:
            act = menu.addAction(_menu_icon("link"), "Desglozar")
            act.triggered.connect(lambda: self.desglozar_nodo.emit(nodo_id))


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
        data = self._celdas(n, wbs)
        item = self.add_row(data, parent, editable=True)
        item.setData(0, WBS_ROLE, wbs)
        item.setData(0, ID_ROLE, n.get("id"))
        item.setData(0, TIPO_ROLE, "capitulo")
        item.setIcon(0, icono("folder-open", 20))
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
        wbs = n.get("wbs", "")
        data = self._celdas(n, wbs)
        item = self.add_row(data, parent, editable=True)
        item.setData(0, WBS_ROLE, wbs)
        item.setData(0, ID_ROLE, n.get("id"))
        item.setData(0, TIPO_ROLE, "concepto")
        item.setData(0, INSUMO_ROLE, n.get("insumo_id"))
        item.setData(6, FORMULA_ROLE, n.get("formula") or "")
        tid = n.get("tipo_id")
        item.setIcon(0, icono(_ICONOS_TIPO_SVG.get(tid, "file-text"), 20, _COLOR_TIPO.get(tid)))
        return item

    # ── Poblado del árbol ─────────────────────────────────────────

    def poblar(self, nodos_raiz: list[dict]):
        """Puebla el árbol completo desde lista de nodos raíz devuelta por NodoRepo.arbol()."""
        self.clear()
        self._poblar_nodos(nodos_raiz, None)
        self._add_empty_row()

    def _add_empty_row(self):
        """Fila visual vacía al final del árbol — no existe en BD.
        Al hacer clic crea un capítulo nuevo."""
        item = self.add_row(
            ["", "", "Capítulo", "", "Nuevo capítulo...",
             "", "", "", "", "", "", "", "", "", ""],
            editable=False,
        )
        item.setData(0, EMPTY_ROLE, True)
        item.setData(0, ID_ROLE, None)
        item.setData(0, TIPO_ROLE, "")
        self._estilizar_fila_vacia(item)
        item.setToolTip(4, "Haz clic para agregar un capítulo nuevo")
        self._empty_row_item = item

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

    def conectar_handlers(self, target, **overrides):
        """Conecta las señales estándar de este árbol a los métodos de
        `target` que compartan nombre con _HANDLERS_ESTANDAR.

        `overrides` permite redirigir señales puntuales a otro nombre de
        método — por ejemplo, el panel "extra" (fuera de presupuesto) usa
        sus propios handlers de agregar_agrupador/agregar_concepto:

            tree.conectar_handlers(self,
                agregar_agrupador='_on_agregar_agrupador_extra',
                agregar_concepto='_on_agregar_concepto_extra')

        Si `target` no tiene el método (getattr devuelve None, como puede
        pasar en PresupuestoPopup si algún día se abre sin ventana padre
        completa), esa señal simplemente no se conecta — mismo
        comportamiento defensivo que tenía el cableado manual con hasattr().
        """
        mapa = {**self._HANDLERS_ESTANDAR, **overrides}
        for señal_nombre, metodo_nombre in mapa.items():
            if not metodo_nombre:
                continue
            handler = getattr(target, metodo_nombre, None)
            if handler is not None:
                getattr(self, señal_nombre).connect(handler)

    def conceptos_seleccionados(self) -> list[int]:
        """IDs de concepto (estructura_presupuesto) implicados en la
        selección actual del árbol.

        Si el ítem seleccionado es un capítulo, expande a todos los
        conceptos bajo ese nodo (requiere que el árbol ya esté conectado
        vía conectar_eventos(), de donde viene self._api). Devuelve []
        si no hay selección o si el árbol no está conectado.

        Reemplaza el patrón que antes vivía duplicado en
        ExplosionMixin._build_explosion()/_build_matriz_explosion(), que
        leía item.data(0, TIPO_ROLE)/ID_ROLE directamente desde fuera de
        esta clase (ver PLAN_REPARACION.md #7).
        """
        if self._api is None:
            return []
        concepto_ids: list[int] = []
        for item in self.selectedItems():
            tipo = item.data(0, TIPO_ROLE)
            if tipo is None:
                continue
            if tipo == "concepto":
                cid = item.data(0, ID_ROLE)
                if cid is not None:
                    concepto_ids.append(cid)
            elif tipo == "capitulo":
                cid = item.data(0, ID_ROLE)
                if cid is not None:
                    concepto_ids.extend(self._api.conceptos_bajo_nodo(cid))
        return concepto_ids

    def ids_seleccionados_arbol(self) -> set[int]:
        """IDs (estructura_presupuesto) de las filas seleccionadas en el
        árbol tal cual — a diferencia de conceptos_seleccionados(), aquí un
        capítulo seleccionado se deja como su propio id (no se expande a
        sus conceptos), porque quien arma el reporte de la selección (ver
        latex.py::filtrar_por_seleccion) ya incluye el subárbol completo de
        cualquier capítulo cuyo id esté en el set. Devuelve set vacío si no
        hay selección.
        """
        ids: set[int] = set()
        for item in self.selectedItems():
            nid = item.data(0, ID_ROLE)
            if nid is not None:
                ids.add(nid)
        return ids

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

        Bloquea señales para evitar que item.setText() (col 6) dispare
        itemChanged recursivamente y sobreescriba la fórmula con el valor
        numérico (ver _on_concepto_editado en mixins/apu.py).
        """
        try:
            item = self._buscar_item_por_id(evento.concepto_id)
            if item is None:
                return
            self.blockSignals(True)
            try:
                registro = evento.registro or {}
                if "descripcion" in evento.cambios:
                    item.setText(4, registro.get("descripcion", "") or "")
                if "cantidad" in evento.cambios:
                    item.setText(6, _num(registro.get("cantidad")))
                if "formula" in evento.cambios:
                    item.setText(14, registro.get("formula") or "")
                    item.setData(6, FORMULA_ROLE, registro.get("formula") or "")
                if "total" in registro:
                    item.setText(8, _fmt(registro.get("total")))
            finally:
                self.blockSignals(False)
        except Exception as e:
            print(f"[eventbus] _on_concepto_actualizado: {type(e).__name__}: {e}")

    def _on_insumo_actualizado(self, evento):
        """InsumoActualizado: actualiza in-place todas las filas de concepto
        ligadas a este insumo (descripción, unidad, P.U.).
        """
        try:
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
        except Exception as e:
            print(f"[eventbus] _on_insumo_actualizado: {type(e).__name__}: {e}")

    def _on_nodo_eliminado(self, evento):
        """NodoEliminado (entidad='estructura_presupuesto'): quita la fila."""
        try:
            if evento.tipo != "estructura_presupuesto":
                return
            item = self._buscar_item_por_id(evento.nodo_id)
            if item is None:
                return
            parent = item.parent()
            if parent:
                parent.removeChild(item)
            else:
                idx = self.indexOfTopLevelItem(item)
                if idx >= 0:
                    self.takeTopLevelItem(idx)
        except Exception as e:
            print(f"[eventbus] _on_nodo_eliminado: {type(e).__name__}: {e}")

    def _on_proyecto_recalculado(self, evento):
        """ProyectoRecalculado: repuebla desde la fuente de verdad.

        Se difiere con QTimer.singleShot(0) para no destruir el item
        dentro de la cadena de itemChanged que pueda estar procesando
        Qt (p. ej. al editar una fórmula). Misma lógica que el detalle
        APU (apu.py).
        """
        try:
            if self._api is None:
                return
            scroll_y = self.verticalScrollBar().value()
            current = self.currentItem()
            id_actual = current.data(0, ID_ROLE) if current else None
            col_actual = self.currentColumn()
            ids_seleccionados = {
                it.data(0, ID_ROLE) for it in self.selectedItems()
                if it.data(0, ID_ROLE) is not None
            }
            ids_expandidos = set()
            self._collect_expanded_ids(self.invisibleRootItem(), ids_expandidos)
            texto_busqueda = self.window()._search_input.text() if (
                hasattr(self.window(), '_search_input')
                and hasattr(self.window(), '_on_search')
            ) else None

            def _refrescar_seguro():
                try:
                    self.blockSignals(True)
                    try:
                        nodos = self._api.presupuesto_arbol(extra=self._extra)
                        self.poblar(nodos)
                    finally:
                        self.blockSignals(False)
                    self._restore_expansion(self.invisibleRootItem(), ids_expandidos)
                    self.verticalScrollBar().setValue(scroll_y)
                    if id_actual is not None:
                        item = self._buscar_item_por_id(id_actual)
                        if item is not None:
                            self.setCurrentItem(item, col_actual if col_actual >= 0 else 0)
                    if ids_seleccionados:
                        for nid in ids_seleccionados:
                            item = self._buscar_item_por_id(nid)
                            if item is not None:
                                item.setSelected(True)
                    if texto_busqueda is not None:
                        self.window()._on_search(texto_busqueda)
                except Exception as e:
                    print(f"[eventbus] _refrescar_seguro: {type(e).__name__}: {e}")

            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, _refrescar_seguro)
        except Exception as e:
            print(f"[eventbus] _on_proyecto_recalculado: {type(e).__name__}: {e}")

    def _collect_expanded_ids(self, parent, ids: set):
        """Recolecta IDs de nodos expandidos recursivamente."""
        for i in range(parent.childCount()):
            child = parent.child(i)
            nid = child.data(0, ID_ROLE)
            if child.isExpanded() and nid is not None:
                ids.add(nid)
            self._collect_expanded_ids(child, ids)

    def _restore_expansion(self, parent, ids_expandidos: set):
        """Restaura expansión: expande los que estaban abiertos, colapsa los demás."""
        for i in range(parent.childCount()):
            child = parent.child(i)
            nid = child.data(0, ID_ROLE)
            if nid is not None:
                child.setExpanded(nid in ids_expandidos)
            self._restore_expansion(child, ids_expandidos)
