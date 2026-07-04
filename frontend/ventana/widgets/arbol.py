"""
arbol.py
========
Tabla jerárquica del presupuesto (capítulos + conceptos).

Uso:
    from frontend.widgets.arbol import TablaArbol
"""

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QColor, QBrush, QFont, QIcon, QPixmap, QPainter
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QHeaderView

from frontend.ventana.widgets.base import TreeTableWidget
from backend.database.db import Config


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
INSUMO_ID_ROLE = Qt.ItemDataRole.UserRole + 11  # insumo_id del insumo vinculado
TIPO_ROLE      = Qt.ItemDataRole.UserRole + 12  # 'capitulo' | 'concepto', seteado explícitamente
                                                 # al crear la fila (NO se infiere leyendo texto)

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
COLUMNAS = [
    "Estructura", "Nivel", "Tipo", "Clave", "Descripción",
    "Unidad", "Cant", "P.U.", "Total",
    "Estado", "Notas", "Creado", "Modificado",
]
_VISIBLE    = {0, 1, 4, 5, 6, 7, 8}   # Clave y Tipo ocultas por defecto
EDITABLE    = frozenset({4, 6})        # fallback genérico (usado hoy solo por copiar/pegar)
_AGRUP_COLS = {0, 1, 4, 8}

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

    def __init__(self, parent=None):
        """Inicializa el árbol de presupuesto con columnas fijas, modo de columnas, búsqueda y restauración del header."""
        super().__init__(COLUMNAS, EDITABLE, parent=parent,
                          editable_cols_fn=_editable_cols_arbol)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([80, 80, 70, 90, 250, 55, 65, 90, 90,
                                   70, 100, 130, 130])
        })
        self.header().setMaximumSectionSize(400)
        self._restore_header_state()
        for c in range(len(COLUMNAS)):
            if c not in _VISIBLE:
                self.setColumnHidden(c, True)
        self._search_cols = {4}  # búsqueda por Descripción



    def _header_context_menu(self, pos):
        """Extiende menú contextual de cabecera del padre y persiste estado tras cambios."""
        super()._header_context_menu(pos)
        self._save_header_state()

    def _save_header_state(self):
        """Guarda estado del header (anchos, visibilidad) en config.json como base64."""
        raw = self.header().saveState()
        Config.set(self._HEADER_KEY, raw.toBase64().data().decode("ascii"))

    def _restore_header_state(self):
        """Restaura estado guardado del header desde config.json si existe."""
        saved = Config.get(self._HEADER_KEY)
        if saved:
            self.header().restoreState(QByteArray.fromBase64(saved.encode("ascii")))

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
            n.get("estado_nombre", ""),                    # 9  Estado
            n.get("notas_rapidas", ""),                    # 10 Notas
            str(n.get("creado_en", "") or ""),             # 11 Creado
            str(n.get("modificado_en", "") or ""),         # 12 Modificado
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
        item.setData(0, INSUMO_ID_ROLE, n.get("insumo_id"))
        item.setData(0, TIPO_ROLE, "concepto")
        item.setIcon(0, _emoji_icon("\U0001F4C4", 20))  # 📄 leaf
        return item

    # ── Poblado del árbol ─────────────────────────────────────────

    def poblar(self, nodos_raiz: list[dict]):
        """Puebla el árbol completo desde lista de nodos raíz devuelta por core.build_budget_tree()."""
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
