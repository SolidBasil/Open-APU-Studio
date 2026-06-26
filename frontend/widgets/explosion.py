"""
explosion.py
============
Explosión de insumos — Open APU Studio v2.

Componentes:
    DialogoExplosion   — ventana de opciones (nivel de composición + tipos)
    TablaExplosion     — tabla con agrupación por tipo e subtotales
    PestañaExplosion   — widget completo de la pestaña

Herramienta: su total viene de am.importe (ya calculado como % de MO),
no de cantidad × costo_final. Por eso sus columnas Cantidad y P.U. muestran —.
"""

from PySide6.QtCore    import Qt
from PySide6.QtGui     import QFont, QColor, QBrush
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QRadioButton, QCheckBox, QDialogButtonBox,
    QLabel, QWidget, QHeaderView,
)

from frontend.widgets.base import TreeTableWidget


# =============================================================================
# CONSTANTES
# =============================================================================

TIPOS_INSUMO = [
    (1,   "Materiales",    "material"),
    (2,   "Mano de obra",  "mano_obra"),
    (4,   "Herramienta",   "herramienta"),
    (8,   "Equipo",        "equipo"),
    (16,  "Auxiliares",    "auxiliar"),
    (32,  "Conceptos",     "concepto"),
    (64,  "Fletes",        "flete"),
    (128, "Trabajos",      "trabajo"),
]

COLUMNAS_EXP = ["Tipo", "Clave", "Descripción", "Unidad", "Cantidad", "P.U.", "Total", "%"]
EDITABLE_EXP = frozenset()

# Color de texto del encabezado de cada tipo (fila de agrupador)
COLOR_GRUPO = {
    1:   "#5A9FD4",   # material   → azul
    2:   "#4A9A72",   # mano obra  → verde
    4:   "#C4956B",   # herramienta → sienna
    8:   "#8B6FB5",   # equipo     → púrpura
    16:  "#4E9298",   # auxiliar   → teal
    32:  "#9A5A5A",   # concepto   → vino
    64:  "#BF9B30",   # flete      → ámbar
    128: "#5A9A7A",   # trabajo    → sage
}

NIVEL_BASICO       = "basico"
NIVEL_COMPUESTO    = "compuesto"
NIVEL_PRIMER_NIVEL = "primer_nivel"


# =============================================================================
# DIÁLOGO DE OPCIONES
# =============================================================================

class DialogoExplosion(QDialog):
    """Ventana de configuración de la explosión de insumos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Explosión de Insumos")
        self.setModal(True)
        self.setFixedWidth(420)

        self.nivel     = NIVEL_PRIMER_NIVEL
        self.tipos_ids = [t[0] for t in TIPOS_INSUMO]

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "Esta operación puede tardar varios segundos\n"
            "dependiendo de la cantidad de información procesada."
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        # Nivel de composición
        grp_nivel = QGroupBox("Calcular:")
        vbox = QVBoxLayout(grp_nivel)
        self._rb_basico       = QRadioButton("Insumos básicos")
        self._rb_compuesto    = QRadioButton("Insumos compuestos")
        self._rb_primer_nivel = QRadioButton("Primer nivel de composición")
        self._rb_primer_nivel.setChecked(True)
        vbox.addWidget(self._rb_basico)
        vbox.addWidget(self._rb_compuesto)
        vbox.addWidget(self._rb_primer_nivel)
        layout.addWidget(grp_nivel)

        # Tipos de insumo — 3 columnas
        grp_tipos = QGroupBox("Explosión de:")
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout(grp_tipos)
        grid.setHorizontalSpacing(20)

        self._checks_tipo: dict[int, QCheckBox] = {}
        for idx, (tipo_id, nombre, _) in enumerate(TIPOS_INSUMO):
            cb = QCheckBox(nombre)
            cb.setChecked(True)
            self._checks_tipo[tipo_id] = cb
            grid.addWidget(cb, idx // 3, idx % 3)

        layout.addWidget(grp_tipos)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        if self._rb_basico.isChecked():
            self.nivel = NIVEL_BASICO
        elif self._rb_compuesto.isChecked():
            self.nivel = NIVEL_COMPUESTO
        else:
            self.nivel = NIVEL_PRIMER_NIVEL

        self.tipos_ids = [
            tid for tid, cb in self._checks_tipo.items() if cb.isChecked()
        ]

        if not self.tipos_ids:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Sin tipos",
                "Selecciona al menos un tipo de insumo para la explosión."
            )
            return

        self.accept()


# =============================================================================
# TABLA DE RESULTADOS
# =============================================================================

class TablaExplosion(TreeTableWidget):
    """Tabla de resultados con agrupación por tipo de insumo.

    Estructura visual:
        ▼ Materiales                              $xxx,xxx.xx   xx.xx%
            material_1   desc   und   cant   PU   $xxx.xx       x.xx%
            material_2   ...
          [Subtotal Materiales]                   $xxx,xxx.xx   xx.xx%
        ▼ Mano de obra
            ...
        TOTAL GENERAL                             $xxx,xxx.xx  100.00%

    Herramienta: columnas Cantidad y P.U. muestran "—" porque su costo
    es un porcentaje de la MO calculado en el APU, no cantidad × precio.
    """

    TIPO_ID_HERRAMIENTA = 4

    def __init__(self, parent=None):
        super().__init__(COLUMNAS_EXP, EDITABLE_EXP, flat=False, parent=parent)
        self.set_column_modes({
            0: (QHeaderView.ResizeMode.Interactive, 130),
            1: (QHeaderView.ResizeMode.Interactive, 90),
            2: (QHeaderView.ResizeMode.Stretch,     240),
            3: (QHeaderView.ResizeMode.Interactive, 55),
            4: (QHeaderView.ResizeMode.Interactive, 85),
            5: (QHeaderView.ResizeMode.Interactive, 90),
            6: (QHeaderView.ResizeMode.Interactive, 105),
            7: (QHeaderView.ResizeMode.Interactive, 65),
        })
        self._search_cols = {0, 1, 2}

    # ── Poblado ───────────────────────────────────────────────────

    def poblar(self, filas: list[dict], total_global: float):
        """
        filas ordenadas por tipo_orden asc, total desc.
        total_global — suma de todos los totales (ya calculado en repo).
        """
        self.clear()
        if not filas:
            return

        # Agrupar por tipo
        grupos: dict[int, list[dict]] = {}
        orden_tipos: list[int] = []
        for f in filas:
            tid = f.get("tipo_id", 0)
            if tid not in grupos:
                grupos[tid] = []
                orden_tipos.append(tid)
            grupos[tid].append(f)

        for tid in orden_tipos:
            grupo = grupos[tid]
            tipo_nombre  = grupo[0].get("tipo_nombre", "")
            subtotal     = sum(f.get("total") or 0 for f in grupo)
            pct_subtotal = (subtotal / total_global * 100) if total_global else 0

            # ── Fila de encabezado de tipo (agrupador)
            grupo_item = self.add_row([
                tipo_nombre, "", "", "", "", "",
                f"${subtotal:,.2f}",
                f"{pct_subtotal:.2f}%",
            ], editable=False)
            self._estilizar_grupo(grupo_item, tid)

            # ── Filas de insumos dentro del grupo
            es_herramienta = (tid == self.TIPO_ID_HERRAMIENTA)
            for f in grupo:
                cantidad = f.get("cantidad_total")
                pu       = f.get("pu")
                pct_mo   = f.get("pct_mo")   # % ponderado vs MO (solo herramienta)
                total    = f.get("total") or 0
                pct      = f.get("pct") or 0

                cant_txt = "—" if es_herramienta or cantidad is None else f"{cantidad:,.4f}"
                if es_herramienta:
                    pu_txt = f"{pct_mo*100:.2f}% MO" if pct_mo is not None else "—"
                else:
                    pu_txt = "—" if pu is None else f"${pu:,.2f}"

                child = self.add_row([
                    "",
                    f.get("clave", ""),
                    f.get("descripcion", ""),
                    f.get("unidad", "") or "",
                    cant_txt,
                    pu_txt,
                    f"${total:,.2f}",
                    f"{pct:.2f}%",
                ], parent=grupo_item, editable=False)

            # Expandir por defecto
            grupo_item.setExpanded(True)

        # ── Fila de total general
        self._add_total_general(total_global)

    # ── Estilos ───────────────────────────────────────────────────

    def _estilizar_grupo(self, item, tipo_id: int):
        """Aplica negrita y color al encabezado de tipo."""
        f = QFont()
        f.setBold(True)
        color = QColor(COLOR_GRUPO.get(tipo_id, "#888888"))
        for c in range(item.columnCount()):
            item.setFont(c, f)
            item.setForeground(c, QBrush(color))

    def _add_total_general(self, total_global: float):
        item = self.add_row([
            "TOTAL GENERAL", "", "", "", "", "",
            f"${total_global:,.2f}",
            "100.00%",
        ], editable=False)
        f = QFont()
        f.setBold(True)
        for c in range(item.columnCount()):
            item.setFont(c, f)


# =============================================================================
# WIDGET CONTENEDOR (pestaña completa)
# =============================================================================

class PestañaExplosion(QWidget):
    """Pestaña completa: encabezado informativo + TablaExplosion."""

    def __init__(self, filas: list[dict], total_global: float, resumen: dict, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._build_header(resumen))

        self._tabla = TablaExplosion()
        self._tabla.poblar(filas, total_global)
        layout.addWidget(self._tabla)

    def _build_header(self, resumen: dict) -> QWidget:
        w    = QWidget()
        hbox = QHBoxLayout(w)
        hbox.setContentsMargins(8, 2, 8, 2)

        nivel_txt = {
            NIVEL_BASICO:       "Insumos básicos",
            NIVEL_COMPUESTO:    "Insumos compuestos",
            NIVEL_PRIMER_NIVEL: "Primer nivel de composición",
        }.get(resumen.get("nivel", ""), "—")

        lbl = QLabel(
            f"Nivel: <b>{nivel_txt}</b> · "
            f"Conceptos: <b>{resumen.get('n_conceptos', 0)}</b> · "
            f"Tipos: <b>{resumen.get('tipos_nombres', '')}</b>"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        hbox.addWidget(lbl)
        hbox.addStretch()
        return w

    def copy_selection(self):
        return self._tabla.copy_selection()
