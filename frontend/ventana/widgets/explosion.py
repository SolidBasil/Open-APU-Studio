"""
explosion.py
============
Explosión de insumos — Open APU Studio v2.

Componentes:
    DialogoExplosion   — ventana de opciones (nivel de composición + tipos)
    TablaExplosion     — tabla con agrupación por tipo e subtotales
    PestañaExplosion   — widget completo de la pestaña

Herramienta: su total viene de am.importe (ya calculado como % de MO),
no de cantidad x costo_final. Por eso sus columnas Cantidad y P.U. muestran —.
"""

from PySide6.QtCore    import Qt, QSize
from PySide6.QtGui     import QFont, QColor, QBrush, QPalette
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QCheckBox, QPushButton, QMenu,
    QLabel, QWidget, QHeaderView, QFrame,
)

from frontend.ventana.widgets.base import TreeTableWidget, crear_footer_dialogo, _menu_icon
from frontend.ventana.iconos import icono


# =============================================================================
# CONSTANTES
# =============================================================================

from frontend.ventana.tipos_insumo import (
    ICONO_SVG as TIPO_ICONO_SVG,
    TIPOS_INSUMO,
    COLOR as COLOR_GRUPO,
)

COLUMNAS_EXP = ["Tipo", "Clave", "Descripción", "Unidad", "Cantidad", "P.U.", "Total", "%"]
EDITABLE_EXP = frozenset()

NIVEL_BASICO       = "basico"
NIVEL_COMPUESTO    = "compuesto"
NIVEL_PRIMER_NIVEL = "primer_nivel"

# Descripciones para las tarjetas de método de cálculo
NIVEL_INFO = {
    NIVEL_BASICO:       ("square",             "Insumos básicos",              "Materiales y artículos fundamentales del proyecto."),
    NIVEL_COMPUESTO:    ("layers",             "Insumos compuestos",           "Ítems ensamblados o fabricados con múltiples componentes."),
    NIVEL_PRIMER_NIVEL: ("corner-down-right",  "Primer nivel de composición",  "Desglose hasta el primer nivel de estructura del producto."),
}


# =============================================================================
# WIDGETS AUXILIARES
# =============================================================================

class _TarjetaRadio(QFrame):
    """Botón grande seleccionable: icono + nombre + descripción.
    Activo -> fondo highlight + texto highlightedText.
    Recibe un callable on_click(valor) en lugar de Signal para
    evitar problemas de propagación de eventos con subwidgets.
    """

    def __init__(self, svg_icon: str, nombre: str, descripcion: str, valor: str,
                 on_click, parent=None):
        """Inicializa tarjeta: icono + nombre + descripción, callback on_click(valor) al hacer clic."""
        super().__init__(parent)
        self._valor    = valor
        self._activo   = False
        self._on_click = on_click

        self.setMinimumHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        self._lbl_icono = QLabel()
        self._lbl_icono.setPixmap(icono(svg_icon, 18).pixmap(18, 18))
        hdr.addWidget(self._lbl_icono)
        self._lbl_nombre = QLabel(nombre)
        f = QFont()
        f.setPointSize(11)
        f.setBold(True)
        self._lbl_nombre.setFont(f)
        hdr.addWidget(self._lbl_nombre)
        hdr.addStretch()
        root.addLayout(hdr)

        self._lbl_desc = QLabel(descripcion)
        self._lbl_desc.setWordWrap(True)
        root.addWidget(self._lbl_desc)

        for w in (self._lbl_icono, self._lbl_nombre, self._lbl_desc):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._refresh_style()

    def mousePressEvent(self, event):
        """Ejecuta callback on_click con el valor de la tarjeta y consume el evento."""
        self._on_click(self._valor)
        event.accept()

    def valor(self) -> str:
        """Devuelve el valor asociado a esta tarjeta (nivel de cálculo)."""
        return self._valor

    def set_checked(self, checked: bool):
        """Marca/desmarca la tarjeta y refresca el estilo visual."""
        self._activo = checked
        self._refresh_style()

    def is_checked(self) -> bool:
        """True si la tarjeta está seleccionada."""
        return self._activo

    def _refresh_style(self):
        """Aplica colores highlight o default según estado activo/inactivo."""
        pal = self.palette()
        if self._activo:
            bg  = pal.color(QPalette.ColorRole.Highlight).name()
            fg  = pal.color(QPalette.ColorRole.HighlightedText).name()
            self.setStyleSheet(
                f"background: {bg};"
                f"border: 1px solid {pal.color(QPalette.ColorRole.Mid).name()};"
                f"border-radius: 8px;"
            )
            self._lbl_nombre.setStyleSheet(
                f"color: {fg}; font-size: 11pt; font-weight: bold;"
                "background: transparent; border: none;"
            )
            self._lbl_desc.setStyleSheet(
                f"color: {fg}; font-size: 9pt;"
                "background: transparent; border: none;"
            )
        else:
            self.setStyleSheet(
                "background: transparent;"
                f"border: 1px solid {pal.color(QPalette.ColorRole.Mid).name()};"
                "border-radius: 8px;"
            )
            self._lbl_nombre.setStyleSheet(
                "font-size: 11pt; font-weight: bold;"
                "background: transparent; border: none;"
            )
            self._lbl_desc.setStyleSheet(
                "font-size: 9pt;"
                "background: transparent; border: none;"
            )
        self._lbl_icono.setStyleSheet(
            "font-size: 22px; background: transparent; border: none;"
        )


class _TarjetaCheck(QWidget):
    """Fila simple: QCheckBox + icono + nombre, sin bordes extra."""

    def __init__(self, svg_icon: str, nombre: str, tipo_id: int, parent=None):
        """Fila con QCheckBox + icono + nombre para filtrar por tipo de insumo."""
        super().__init__(parent)
        self._tipo_id = tipo_id

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._cb = QCheckBox(f" {nombre}")
        if svg_icon:
            self._cb.setIcon(icono(svg_icon, 16))
        self._cb.setChecked(True)
        root.addWidget(self._cb)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def tipo_id(self) -> int:
        """ID del tipo de insumo (1=Materiales, 2=MO, 4=Herramienta, ...)."""
        return self._tipo_id

    def is_checked(self) -> bool:
        """True si el checkbox está marcado."""
        return self._cb.isChecked()

    def set_checked(self, checked: bool):
        """Marca/desmarca el checkbox."""
        self._cb.setChecked(checked)

    def mousePressEvent(self, event):
        """Alterna el checkbox al hacer clic en el widget completo."""
        self._cb.setChecked(not self._cb.isChecked())
        super().mousePressEvent(event)


def _separador_v() -> QFrame:
    """Línea vertical separadora para layouts de dos columnas."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setStyleSheet("color: palette(mid);")
    return sep


def _label_seccion(texto: str) -> QLabel:
    """Etiqueta de título de sección (mayúsculas, bold, letter-spacing)."""
    lbl = QLabel(texto.upper())
    lbl.setStyleSheet(
        "font-size: 8pt; font-weight: bold;"
        "color: palette(text); letter-spacing: 1px; margin-bottom: 4px;"
    )
    return lbl


# =============================================================================
# DIÁLOGO DE OPCIONES
# =============================================================================

class DialogoExplosion(QDialog):
    """Ventana de configuración de la explosión de insumos.

    Layout de dos columnas:
      -- Método de cálculo -----|- Composición del desglose ---
      |  [tarjeta radio x 3]    |  [tarjeta check x 8]  2 col |
      ---------------------------------------------------------
    """

    def __init__(self, parent=None):
        """Diálogo modal para elegir nivel de desglose y tipos de insumo a explotar."""
        super().__init__(parent)
        self.setWindowTitle("Explosión de Insumos")
        self.setModal(True)
        self.setMinimumWidth(680)
        self.setMaximumWidth(720)

        self.nivel     = NIVEL_BASICO
        self.tipos_ids = [t[0] for t in TIPOS_INSUMO]
        self._build_ui()

    # -- Construcción de UI ----------------------------------------

    def _build_ui(self):
        """Ensambla layout vertical: banner + dos columnas + pie."""
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 14, 16, 14)

        # Banner informativo
        root.addWidget(self._build_banner())

        # Cuerpo: dos columnas
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(0)
        cuerpo.addLayout(self._build_col_calculo(), 4)
        cuerpo.addWidget(_separador_v())
        cuerpo.addLayout(self._build_col_tipos(), 5)
        root.addLayout(cuerpo)

        # Pie de diálogo
        root.addWidget(self._build_footer())

    def _build_banner(self) -> QWidget:
        """Banner informativo con icono y advertencia de tiempo de proceso."""
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: palette(alternateBase);"
            "         border: 1px solid palette(mid);"
            "         border-radius: 6px; }"
        )
        hbox = QHBoxLayout(frame)
        hbox.setContentsMargins(10, 8, 10, 8)
        hbox.setSpacing(8)
        ico = QLabel()
        ico.setPixmap(icono("info", 16).pixmap(16, 16))
        ico.setStyleSheet("border: none; background: transparent;")
        hbox.addWidget(ico)
        msg = QLabel(
            "Esta operación puede tardar varios segundos "
            "dependiendo de la cantidad de información procesada."
        )
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 9pt; border: none; background: transparent;")
        hbox.addWidget(msg, 1)
        return frame

    def _build_col_calculo(self) -> QVBoxLayout:
        """Columna izquierda: tarjetas de selección del método de cálculo."""
        col = QVBoxLayout()
        col.setContentsMargins(0, 4, 12, 4)
        col.setSpacing(8)
        col.addWidget(_label_seccion("Método de cálculo"))

        self._tarjetas_nivel: list[_TarjetaRadio] = []
        for valor, (svg_icon, nombre, desc) in NIVEL_INFO.items():
            t = _TarjetaRadio(svg_icon, nombre, desc, valor, self._on_nivel_click)
            self._tarjetas_nivel.append(t)
            col.addWidget(t)

        self._tarjetas_nivel[0].set_checked(True)
        col.addStretch()
        return col

    def _on_nivel_click(self, valor):
        """Maneja clic en tarjeta de nivel: desmarca las demás, marca la seleccionada."""
        for t in self._tarjetas_nivel:
            t.set_checked(t._valor == valor)

    def _build_col_tipos(self) -> QVBoxLayout:
        """Columna derecha: cuadrícula de checkboxes de tipos + botón toggle."""
        col = QVBoxLayout()
        col.setContentsMargins(12, 4, 0, 4)
        col.setSpacing(6)

        # Encabezado + botón toggle
        hdr = QHBoxLayout()
        hdr.addWidget(_label_seccion("Composición del desglose"))
        hdr.addStretch()
        self._btn_toggle = QPushButton("Deseleccionar todo")
        self._btn_toggle.setFixedHeight(26)
        self._btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle.clicked.connect(self._toggle_seleccion)
        hdr.addWidget(self._btn_toggle)
        col.addLayout(hdr)

        # Cuadrícula 2 columnas de tarjetas check
        grid = QGridLayout()
        grid.setSpacing(6)
        self._tarjetas_tipo: list[_TarjetaCheck] = []
        for idx, (tipo_id, nombre, _) in enumerate(TIPOS_INSUMO):
            svg_icon = TIPO_ICONO_SVG.get(tipo_id, "file-text")
            t = _TarjetaCheck(svg_icon, nombre, tipo_id, self)
            self._tarjetas_tipo.append(t)
            grid.addWidget(t, idx // 2, idx % 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        col.addLayout(grid)
        col.addStretch()
        return col

    def _build_footer(self):
        """Pie del diálogo: botones Cancelar + Calcular (footer estándar)."""
        return crear_footer_dialogo(self, texto_guardar="Calcular",
                                    on_guardar=self._on_accept)

    # -- Lógica ----------------------------------------------------

    def _toggle_seleccion(self):
        """Alterna entre seleccionar/deseleccionar todos los tipos y actualiza texto del botón."""
        alguna_marcada = any(t.is_checked() for t in self._tarjetas_tipo)
        nuevo = not alguna_marcada
        for t in self._tarjetas_tipo:
            t.set_checked(nuevo)
        self._btn_toggle.setText(
            "Deseleccionar todo" if nuevo else "Seleccionar todo"
        )

    def _on_accept(self):
        """Valida selección (mínimo 1 tipo), captura nivel y tipos_ids, y acepta el diálogo."""
        # Nivel seleccionado
        self.nivel = NIVEL_BASICO
        for t in self._tarjetas_nivel:
            if t.is_checked():
                self.nivel = t.valor()
                break

        self.tipos_ids = [t.tipo_id() for t in self._tarjetas_tipo if t.is_checked()]

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
    """Tabla de resultados plana con cada insumo mostrando su tipo.

    Columnas: Tipo (icono) | Clave | Descripción | Unidad | Cantidad | P.U. | Total | %
    Cada fila lleva el icono de su tipo. Subtotales por tipo destacados.
    """

    _HEADER_KEY = "explosion_columnas"

    def __init__(self, parent=None):
        """Tabla plana de resultados: Tipo, Clave, Descripción, Unidad, Cantidad, P.U., Total, %."""
        super().__init__(COLUMNAS_EXP, EDITABLE_EXP, flat=True, parent=parent)
        self.set_column_modes({
            0: (QHeaderView.ResizeMode.Interactive, 100),
            1: (QHeaderView.ResizeMode.Interactive, 75),
            2: (QHeaderView.ResizeMode.Interactive, 280),
            3: (QHeaderView.ResizeMode.Interactive, 45),
            4: (QHeaderView.ResizeMode.Interactive, 75),
            5: (QHeaderView.ResizeMode.Interactive, 75),
            6: (QHeaderView.ResizeMode.Interactive, 90),
            7: (QHeaderView.ResizeMode.Interactive, 100),
        })
        self.header().setMaximumSectionSize(400)
        self._search_cols = {0, 1, 2}
        self._restore_header_state()
        self.setColumnHidden(1, True)  # Clave oculta

    def poblar(self, filas: list[dict], total_global: float):
        """Llena la tabla agrupando filas por tipo de insumo, con subtotales y total general."""
        self.clear()
        if not filas:
            return

        grupos: dict[int, list[dict]] = {}
        orden_tipos: list[int] = []
        for f in filas:
            tid = f.get("tipo_id", 0)
            if tid not in grupos:
                grupos[tid] = []
                orden_tipos.append(tid)
            grupos[tid].append(f)

        es_primero = True
        for tid in orden_tipos:
            grupo = grupos[tid]
            svg_icon    = TIPO_ICONO_SVG.get(tid, "file-text")
            tipo_nombre = grupo[0].get("tipo_nombre", "")
            subtotal    = sum(f.get("total") or 0 for f in grupo)
            pct_subtotal = (subtotal / total_global * 100) if total_global else 0

            # Separador visual entre tipos
            if not es_primero:
                sep = self.add_row(["", "", "", "", "", "", "", ""], editable=False)
                sep.setHidden(False)
                for c in range(sep.columnCount()):
                    sep.setBackground(c, QColor(COLOR_GRUPO.get(tid, "#888888")))
                    sep.setSizeHint(0, QSize(0, 2))
                    sep.setForeground(c, QBrush(QColor(COLOR_GRUPO.get(tid, "#888888"))))
            es_primero = False

            for f in grupo:
                cantidad  = f.get("cantidad_total")
                pu        = f.get("pu")
                pct_base  = f.get("pct_base")
                pct_sufijo = f.get("pct_sufijo") or ""
                total     = f.get("total") or 0
                pct       = f.get("pct") or 0
                es_pct    = f.get("unidad", "").startswith("(%)")

                cant_txt = "—" if es_pct or cantidad is None else f"{cantidad:,.4f}"
                if es_pct:
                    sufijo = pct_sufijo if pct_sufijo else f.get("unidad", "")[3:] or ""
                    pu_txt = f"{pct_base*100:.2f}% {sufijo}" if pct_base is not None else "—"
                else:
                    pu_txt = "—" if pu is None else f"${pu:,.2f}"

                item = self.add_row([
                    tipo_nombre,
                    f.get("clave", ""),
                    f.get("descripcion", ""),
                    f.get("unidad", "") or "",
                    cant_txt,
                    pu_txt,
                    f"${total:,.2f}",
                    f"{pct:.2f}%",
                ], editable=False)
                item.setIcon(0, icono(svg_icon, 16, COLOR_GRUPO.get(tid)))
                item.setData(0, Qt.ItemDataRole.UserRole, f.get("insumo_id"))

            # Subtotal del tipo
            sub_item = self.add_row([
                "", f"Subtotal {tipo_nombre}", "", "", "", "",
                f"${subtotal:,.2f}",
                f"{pct_subtotal:.2f}%",
            ], editable=False)
            f = QFont()
            f.setBold(True)
            color = QColor(COLOR_GRUPO.get(tid, "#888888"))
            for c in range(sub_item.columnCount()):
                sub_item.setFont(c, f)
                sub_item.setForeground(c, QBrush(color))

        self._add_total_general(total_global)

    def _add_total_general(self, total_global: float):
        """Fila final con TOTAL GENERAL y 100 %."""
        item = self.add_row([
            "", "TOTAL GENERAL", "", "", "", "",
            f"${total_global:,.2f}",
            "100.00%",
        ], editable=False)
        f = QFont()
        f.setBold(True)
        for c in range(item.columnCount()):
            item.setFont(c, f)

    def conectar_eventos(self, event_bus, api):
        """Engancha esta tabla al ciclo de vida estándar (ver
        GUIA_INTERFAZ.md §7.6 y TablaArbol.conectar_eventos()).

        Stub deliberado: hoy la explosión es una foto fija tomada al
        momento de abrir la pestaña (ver PLAN_REPARACION.md #22-23), no se
        recalcula sola si cambian los datos de origen — el usuario vuelve
        a pedir "Explosión de insumos" para una foto nueva. Guardamos
        event_bus/api para que, si en el futuro se decide refrescar en
        caliente (p. ej. ante ProyectoRecalculado), solo haga falta
        agregar la suscripción aquí sin tocar los call sites.
        """
        self._event_bus = event_bus
        self._api = api

    def desconectar_eventos(self):
        """Idempotente: no falla si nunca se conectó o ya se desconectó."""
        self._event_bus = None
        self._api = None


# =============================================================================
# WIDGET CONTENEDOR (pestaña completa)
# =============================================================================

class PestañaExplosion(QWidget):
    """Pestaña completa: encabezado informativo + TablaExplosion."""

    def __init__(self, filas: list[dict], total_global: float, resumen: dict,
                 parent=None, on_apu_click=None, on_rastrear=None):
        """Pestaña completa: encabezado + tabla + conexiones a APU y rastreo."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._build_header(resumen))

        self._tabla = TablaExplosion()
        self._tabla.poblar(filas, total_global)
        layout.addWidget(self._tabla)

        if on_apu_click:
            self._tabla.itemDoubleClicked.connect(
                lambda item, col: self._on_apu_click(item, on_apu_click))

        if on_rastrear:
            self._tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self._tabla.customContextMenuRequested.connect(
                lambda pos: self._on_context_menu(pos, on_rastrear))

    def _on_apu_click(self, item, on_apu_click):
        """Doble clic en fila -> abre APU del insumo, ignorando subtotales y total.
        Usa el insumo_id guardado en UserRole (col 0), no el texto de la
        columna Clave — antes se pasaba ese texto a una búsqueda por 'clave'
        que en realidad buscaba conceptos del presupuesto, no insumos del
        catálogo, así que nunca coincidía de forma confiable.
        """
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not insumo_id:
            return
        on_apu_click(insumo_id)

    def _on_context_menu(self, pos, on_rastrear):
        """Menú contextual -> Copiar/Cortar/Pegar + Rastrear uso para el insumo bajo el cursor."""
        item = self._tabla.itemAt(pos)
        if not item:
            return
        self._tabla.setCurrentItem(item)
        menu = QMenu(self)
        self._tabla._add_clipboard_actions(menu)
        insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
        if insumo_id:
            act = menu.addAction(_menu_icon("search"), "Rastrear uso")
            act.triggered.connect(lambda: on_rastrear(insumo_id))
        menu.exec(self._tabla.mapToGlobal(pos))

    def _build_header(self, resumen: dict) -> QWidget:
        """Encabezado con nivel, cantidad de conceptos y tipos seleccionados."""
        w    = QWidget()
        hbox = QHBoxLayout(w)
        hbox.setContentsMargins(8, 2, 8, 2)

        nivel_txt = {
            NIVEL_BASICO:       "Insumos básicos",
            NIVEL_COMPUESTO:    "Insumos compuestos",
            NIVEL_PRIMER_NIVEL: "Primer nivel de composición",
        }.get(resumen.get("nivel", ""), "—")

        tipos_raw = resumen.get("tipos_nombres", "")
        tipos_con_icono = tipos_raw  # ya vienen con icono desde el diálogo
        lbl = QLabel(
            f"Nivel: <b>{nivel_txt}</b> · "
            f"Conceptos: <b>{resumen.get('n_conceptos', 0)}</b> · "
            f"Tipos: <b>{tipos_con_icono}</b>"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        hbox.addWidget(lbl)
        hbox.addStretch()
        return w

    def copy_selection(self):
        """Delega copia al portapapeles a la tabla interna."""
        return self._tabla.copy_selection()

    def poblar(self, filas: list[dict], total_global: float):
        """Delega a TablaExplosion.poblar() — ver GUIA_INTERFAZ.md §7.6.

        __init__ ya puebla la tabla una vez con los datos de construcción
        (la explosión llega calculada de antemano desde ExplosionMixin);
        este método queda disponible para repoblar sin recrear el widget,
        p. ej. si conectar_eventos() empieza a escuchar cambios más
        adelante (ver nota en TablaExplosion.conectar_eventos()).
        """
        self._tabla.poblar(filas, total_global)

    def conectar_eventos(self, event_bus, api):
        """Delega a TablaExplosion.conectar_eventos()."""
        self._tabla.conectar_eventos(event_bus, api)

    def desconectar_eventos(self):
        """Delega a TablaExplosion.desconectar_eventos().

        _cerrar_tab_widget() (ver mixins/navegacion.py) ya llama esto
        automáticamente en cualquier widget que lo tenga al cerrar una
        pestaña — no requiere wiring adicional.
        """
        self._tabla.desconectar_eventos()
