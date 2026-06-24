"""
arbol.py
========
Tabla jerárquica del presupuesto (capítulos + conceptos).

Uso:
    from frontend.widgets.arbol import TablaArbol
"""

from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import QHeaderView

from frontend.widgets.base import TreeTableWidget
from backend.db import Config


# ── Roles de datos ────────────────────────────────────────────────

WBS_ROLE     = Qt.ItemDataRole.UserRole

# ── Configuración de columnas ─────────────────────────────────────

# Subtotal se fusionó en Total (col 6): conceptos → importe, capítulos → subtotal.
# El índice que ocupaba Subtotal (7) se eliminó; columnas posteriores corrieron -1.
COLUMNAS     = [
    "Nivel", "Clave", "Descripción", "Unid", "Cant", "P.U.", "Total",
    "Desc. Corta", "Tipo", "Estado", "Notas", "Creado", "Modificado",
]
_VISIBLE    = {0, 1, 2, 3, 4, 5, 6}
EDITABLE    = frozenset({1, 2, 3, 4, 5})
_AGRUP_COLS = {0, 1, 2, 6}

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
    if v is None:
        return ""
    return f"${v:,.{decimals}f}" if isinstance(v, (int, float)) else str(v)


def _num(v, decimals=2):
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
        super().__init__(COLUMNAS, EDITABLE, parent=parent)
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([50, 80, 250, 45, 60, 80, 90,
                                   120, 60, 70, 100, 130, 130])
        })
        self.header().setMaximumSectionSize(400)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for c in range(len(COLUMNAS)):
            if c not in _VISIBLE:
                self.setColumnHidden(c, True)
        # búsqueda por defecto: Nivel, Clave, Descripción, Tipo
        # (Tipo es columna 8 desde que se eliminó Subtotal)
        self._search_cols = {0, 1, 2, 8}
        self._restore_header_state()



    def _header_context_menu(self, pos):
        super()._header_context_menu(pos)
        self._save_header_state()

    def _save_header_state(self):
        raw = self.header().saveState()
        Config.set(self._HEADER_KEY, raw.toBase64().data().decode("ascii"))

    def _restore_header_state(self):
        saved = Config.get(self._HEADER_KEY)
        if saved:
            self.header().restoreState(QByteArray.fromBase64(saved.encode("ascii")))

    # ── Helpers de WBS ────────────────────────────────────────────

    @staticmethod
    def _calc_wbs(wbs: str, parent):
        if not wbs:
            return ""
        pwbs = ""
        if parent is not None:
            try:
                pwbs = parent.data(0, WBS_ROLE)
            except AttributeError:
                pass
        if not pwbs:
            return str(int(wbs))
        suffix = wbs[len(pwbs):]
        return f"{parent.text(0)}.{str(int(suffix))}"

    # ── Construcción de celdas desde dict ─────────────────────────

    @staticmethod
    def _celdas(n, wbs):
        """Construye la lista de valores para todas las columnas desde el dict del nodo."""
        return [
            wbs,                                           # 0 Nivel
            n.get("clave", ""),                            # 1 Clave
            n.get("descripcion", ""),                      # 2 Descripción
            n.get("unidad", ""),                           # 3 Unid
            _num(n.get("cantidad")),                       # 4 Cant
            _fmt(n.get("precio_unitario")),                # 5 P.U.
            # Total: conceptos muestran importe directo, capítulos muestran subtotal acumulado
            _fmt(n.get("importe") if n.get("tipo") == "concepto" else n.get("subtotal")),  # 6 Total
            n.get("descripcion_corta", ""),                # 7 Desc. Corta
            n.get("tipo", ""),                             # 8 Tipo
            n.get("estado_nombre", ""),                    # 9 Estado
            n.get("notas_rapidas", ""),                    # 10 Notas
            str(n.get("creado_en", "") or ""),             # 11 Creado
            str(n.get("modificado_en", "") or ""),         # 12 Modificado
        ]

    # ── Inserción de agrupadores ──────────────────────────────────

    def add_agrupador(self, n, parent=None, expanded=True):
        parent = parent or self
        nivel = 0
        p = parent
        while p is not None and p is not self:
            nivel += 1
            p = p.parent()
        wbs  = n.get("wbs", "")
        fmt  = self._calc_wbs(wbs, parent)
        data = self._celdas(n, fmt)
        item = self.add_row(data, parent, editable=False)
        item.setData(0, WBS_ROLE, wbs)
        color = COLORES_NIVEL[min(nivel, len(COLORES_NIVEL) - 1)]
        brush = QBrush(QColor(color))
        f     = item.font(0)
        f.setBold(True)
        for c in range(item.columnCount()):
            item.setForeground(c, brush)
            item.setFont(c, f)
        item.setExpanded(expanded)
        return item

    # ── Inserción de registros hoja ───────────────────────────────

    def add_registro(self, n, parent=None):
        data = self._celdas(n, "")
        return self.add_row(data, parent, editable=True)

    # ── Poblado del árbol ─────────────────────────────────────────

    def poblar(self, nodos_raiz: list[dict]):
        self.clear()
        self._poblar_nodos(nodos_raiz, None)

    def _poblar_nodos(self, nodos, parent):
        for n in nodos:
            if n["tipo"] == "capitulo":
                if not n.get("wbs"):
                    self._poblar_nodos(n.get("hijos", []), parent)
                    continue
                item = self.add_agrupador(n, parent=parent)
                self._poblar_nodos(n.get("hijos", []), item)
            else:
                self.add_registro(n, parent=parent)
