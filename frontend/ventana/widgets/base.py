"""
base.py
=======
Widget base reutilizable: TreeTableWidget con conectores visuales,
filtrado, edición y clipboard.

Uso:
    from frontend.widgets.base import TreeTableWidget
"""

UNIDADES = [
    "Pza", "kg", "g", "t", "m", "m²", "m³", "cm", "cm²", "cm³",
    "L", "mL", "gal", "saco", "bulto", "rollo", "hoja", "panel",
    "placa", "tubo", "varilla", "lote", "juego", "kit", "caja",
    "cubeta", "tambor", "viaje", "carga", "servicio",
    "dia", "hr", "h", "jor", "jor8", "turno", "mes", "semana",
    "(%)MAT", "(%)MO", "(%)EQ", "Eq", "HM", "HH",     "km", "km-m³", "ha", "glb", "u", "lote",
]

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QApplication, QStyledItemDelegate, QMenu,
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox,
    QLabel, QGroupBox, QScrollArea, QWidget, QDialogButtonBox,
    QFrame, QPushButton,
)
from PySide6.QtCore import Qt, QByteArray, QPoint, QTimer
from PySide6.QtGui import QBrush, QColor, QKeySequence, QPainter, QPen

import re
from dataclasses import dataclass
from backend.database.db import Config


# ── Catálogo de columnas (favoritas / personalizar) ───────────────

@dataclass(frozen=True)
class ColumnaDef:
    """Definición de una columna dentro del catálogo completo de una tabla.

    Una tabla puede tener muchas más columnas de las que tiene sentido
    mostrar en el menú rápido de clic derecho (ver Insumos: ~30 campos
    posibles). El catálogo separa tres cosas independientes:
      - favorita_default:   si aparece en el menú rápido por defecto
      - visible_default:    si se muestra en la tabla por defecto
      - imprimible_default: si se incluye en el reporte LaTeX/PDF por defecto
    El usuario puede cambiar las tres desde "Personalizar columnas…", y
    marcar como favorita/imprimible una columna que hoy no lo es (o
    viceversa) sin tocar los otros dos atributos.

    idx debe coincidir con la posición real de la columna en la lista
    `columns` pasada al constructor de TreeTableWidget.
    """
    idx: int
    label: str
    categoria: str
    favorita_default: bool = True
    visible_default: bool = True
    imprimible_default: bool = True


class PersonalizarColumnasDialog(QDialog):
    """Diálogo genérico: elegir qué columnas son favoritas (aparecen en el
    menú rápido de clic derecho) y cuáles están visibles ahora mismo.

    Reutilizable por cualquier TreeTableWidget que defina COLUMNAS_CATALOGO.
    Los cambios se aplican de inmediato sobre `tabla` — no hay botón
    "Aplicar", solo "Cerrar", igual que el menú rápido de hoy.
    """

    def __init__(self, tabla: "TreeTableWidget", parent=None):
        super().__init__(parent or tabla)
        self.setWindowTitle("Personalizar columnas")
        self.setMinimumSize(440, 560)
        self._tabla = tabla
        self._favoritas = tabla._favoritas()  # set[int] mutable en memoria, se persiste en cada cambio
        self._imprimibles = tabla._imprimibles()  # idem, para la columna "Imprimible"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        leyenda = QLabel(
            "★ Favorita — aparece en el menú rápido de clic derecho.\n"
            "🖶 Imprimible — se incluye en el reporte LaTeX/PDF."
        )
        leyenda.setStyleSheet("color: #8A97A3; font-size: 11px;")
        layout.addWidget(leyenda)

        from frontend.ventana.iconos import search_input
        buscador_wrapper, buscador = search_input("Buscar columna…", "dlgSearch")
        buscador.textChanged.connect(self._filtrar)
        layout.addWidget(buscador_wrapper)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(2)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self._grupos = []  # [(QGroupBox, [(fila_widget, ColumnaDef), ...])]
        self._construir_filas(tabla.COLUMNAS_CATALOGO)
        self._content_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

    def _construir_filas(self, catalogo: list[ColumnaDef]):
        """Agrupa las columnas por categoría preservando el orden de aparición
        en el catálogo (cada tabla decide ese orden al definirlo)."""
        categorias: dict[str, list[ColumnaDef]] = {}
        for col in catalogo:
            categorias.setdefault(col.categoria, []).append(col)

        for nombre_categoria, columnas in categorias.items():
            grupo = QGroupBox(nombre_categoria)
            gl = QVBoxLayout(grupo)
            gl.setContentsMargins(4, 8, 4, 0)
            gl.setSpacing(2)
            filas = []
            for col in columnas:
                fila = QWidget()
                fl = QHBoxLayout(fila)
                fl.setContentsMargins(4, 0, 4, 0)
                fl.setSpacing(10)

                es_fav = col.idx in self._favoritas
                star = QLabel("★" if es_fav else "☆")
                star.setToolTip("Favorita: aparece en el menú rápido de clic derecho")
                star.setCursor(Qt.CursorShape.PointingHandCursor)
                star.setAlignment(Qt.AlignmentFlag.AlignCenter)
                star.setFixedWidth(24)
                self._pintar_star(star, es_fav)
                star.mousePressEvent = lambda _e, s=star, c=col.idx: self._toggle_star(s, c)

                chk_vis = QCheckBox()
                chk_vis.setChecked(not self._tabla.isColumnHidden(col.idx))
                chk_vis.toggled.connect(
                    lambda checked, c=col.idx: self._tabla.setColumnHidden(c, not checked))

                chk_imp = QCheckBox("🖶")
                chk_imp.setToolTip("Imprimible: se incluye en el reporte LaTeX/PDF")
                chk_imp.setChecked(col.idx in self._imprimibles)
                chk_imp.toggled.connect(
                    lambda checked, c=col.idx: self._toggle_imprimible(c, checked))

                lbl = QLabel(col.label)
                fl.addWidget(lbl, 1)
                fl.addWidget(star)
                fl.addWidget(chk_vis)
                fl.addWidget(chk_imp)
                gl.addWidget(fila)
                filas.append((fila, col, star))
            self._content_layout.addWidget(grupo)
            self._grupos.append((grupo, filas))

    def _pintar_star(self, star: QLabel, es_fav: bool):
        star.setText("★" if es_fav else "☆")
        star.setStyleSheet(
            "QLabel { color: #F0C060; font-size: 18px; padding: 2px 4px; border-radius: 3px; }"
            f"QLabel:hover {{ background-color: {SEL_BG}; }}"
            if es_fav else
            "QLabel { color: #6B7884; font-size: 18px; padding: 2px 4px; border-radius: 3px; }"
            f"QLabel:hover {{ background-color: {SEL_BG}; }}"
        )

    def _toggle_star(self, star: QLabel, col_idx: int):
        es_fav = col_idx not in self._favoritas
        if es_fav:
            self._favoritas.add(col_idx)
        else:
            self._favoritas.discard(col_idx)
        self._tabla._guardar_favoritas(self._favoritas)
        self._pintar_star(star, es_fav)

    def _toggle_imprimible(self, col_idx: int, checked: bool):
        if checked:
            self._imprimibles.add(col_idx)
        else:
            self._imprimibles.discard(col_idx)
        self._tabla._guardar_imprimibles(self._imprimibles)

    def _filtrar(self, texto: str):
        """Filtra filas por nombre de columna; oculta categorías vacías."""
        texto = texto.strip().lower()
        for grupo, filas in self._grupos:
            alguna_visible = False
            for fila, col, _star in filas:
                coincide = not texto or texto in col.label.lower()
                fila.setVisible(coincide)
                alguna_visible = alguna_visible or coincide
            grupo.setVisible(alguna_visible)


# ── Expresiones regulares ──────────────────────────────────────────

# Derivado de tipos_insumo.ICONO — no hardcodear emojis aquí.
from frontend.ventana.colores import SEL_BG, LINE, WARNING
from frontend.ventana.tipos_insumo import ICONO as _TIPO_ICONO
from frontend.ventana.iconos import icono as _icono

_PREFIJOS = "".join(_TIPO_ICONO.values())
SISTEMA_PREFIJOS = re.compile(rf"^[{re.escape(_PREFIJOS)}]\s?") if _PREFIJOS else re.compile(r"^\Z")


def _menu_icon(nombre: str, size: int = 16):
    """Icono Lucide para acciones de menú contextual."""
    return _icono(nombre, size)


def crear_header_dialogo(icono_nombre: str, titulo: str) -> QFrame:
    """Header estándar de diálogo: ícono + título en una franja de 48px.
    Ver DialogoAjustes/DialogoConfigImpresion — antes cada uno construía
    esto a mano, byte por byte igual salvo el ícono y el texto."""
    hdr = QFrame()
    hdr.setObjectName("dlgAjustesHeader")
    hdr.setFixedHeight(48)
    row = QHBoxLayout(hdr)
    row.setContentsMargins(16, 0, 16, 0)

    icon = QLabel()
    icon.setPixmap(_icono(icono_nombre, 18).pixmap(18, 18))
    icon.setObjectName("dlgIcon")
    row.addWidget(icon)

    title = QLabel(titulo)
    title.setObjectName("dlgHeader")
    row.addWidget(title)
    row.addStretch()
    return hdr


def crear_footer_dialogo(dialogo, texto_guardar: str = "Guardar",
                         on_guardar=None, botones_extra=None) -> QFrame:
    """Footer estándar de diálogo: [botones_extra...] ····· Cancelar Guardar.

    `on_guardar`, si se da, se conecta al botón de guardar en vez de
    `dialogo.accept` (para diálogos que necesitan validar antes de cerrar
    — ver DialogoConfigImpresion._guardar()).
    `botones_extra`: QPushButton ya armados, se insertan antes del
    espaciador (ej. "Restablecer" en DialogoConfigImpresion).
    """
    footer = QFrame()
    footer.setObjectName("dlgAjustesFooter")
    row = QHBoxLayout(footer)
    row.setContentsMargins(16, 10, 16, 10)

    for btn in (botones_extra or []):
        row.addWidget(btn)

    row.addStretch()

    btn_cancel = QPushButton("Cancelar")
    btn_cancel.setObjectName("dlgCancel")
    btn_cancel.clicked.connect(dialogo.reject)
    row.addWidget(btn_cancel)

    btn_save = QPushButton(texto_guardar)
    btn_save.setObjectName("btnPrimario")
    btn_save.clicked.connect(on_guardar or dialogo.accept)
    row.addWidget(btn_save)

    return footer


# ── Constantes de conectores ──────────────────────────────────────

LINE_COLOR = QColor(LINE)
LINE_WIDTH  = 1.5
EMPTY_ROLE = Qt.ItemDataRole.UserRole + 60  # fila visual vacía (no existe en DB)

# ── Roles de datos ──────────────────────────────────────────────────

FORMULA_ROLE = Qt.ItemDataRole.UserRole + 20


# ── Corte pendiente (portapapeles) ────────────────────────────────
# Solo puede haber un corte pendiente a la vez en toda la app — el
# portapapeles del sistema es único, así que iniciar un nuevo Cortar/
# Copiar (en cualquier tabla) cancela el corte anterior sin borrar nada.

_CORTE_ACTIVO: "TreeTableWidget | None" = None


def _cancelar_corte_activo():
    """Cancela el corte pendiente activo, si hay alguno, en cualquier tabla."""
    global _CORTE_ACTIVO
    if _CORTE_ACTIVO is not None:
        tabla = _CORTE_ACTIVO
        _CORTE_ACTIVO = None
        tabla._corte_pendiente = None
        tabla.viewport().update()


def _limpiar_celda_excel(valor: str) -> str:
    """Quita comillas envolventes que Excel agrega cuando una celda contiene
    comas o saltos de línea, des-escapando comillas dobles internas (""→")."""
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == '"' and valor[-1] == '"':
        valor = valor[1:-1].replace('""', '"')
    return valor


def _parsear_portapapeles(texto: str) -> list[list[str]]:
    """Divide el texto del portapapeles en una cuadrícula de filas/columnas —
    así es como Excel (y la mayoría de hojas de cálculo) copian celdas: tabs
    entre columnas, saltos de línea entre filas. Un texto sin tabs ni saltos
    de línea da como resultado una cuadrícula de 1×1 (pegado simple de celda)."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    if texto.endswith("\n"):
        texto = texto[:-1]  # Excel casi siempre agrega un salto de línea final sobrante
    return [[_limpiar_celda_excel(c) for c in linea.split("\t")]
            for linea in texto.split("\n")]


# ── Utilidades de texto ───────────────────────────────────────────

def _strip_icons(text: str) -> str:
    """Quita prefijos del sistema (iconos de tipo) sin afectar datos del usuario.
    Necesario para copiar/exportar datos limpios sin marcadores visuales.
    """
    return SISTEMA_PREFIJOS.sub("", text)


# ── Dibujado de conectores jerárquicos ────────────────────────────

def draw_tree_connectors(tree, painter, rect, index, line_color=LINE_COLOR):
    """Dibuja conectores visuales entre nodos jerárquicos.
    Por cada nivel dibuja una línea vertical si hay nodos debajo,
    y una línea horizontal hacia el contenido del nodo actual.
    """
    info = []
    idx  = index
    while True:
        parent = idx.parent()
        total  = idx.model().rowCount(parent)
        row    = idx.row()
        # ponytail: ignorar fila vacía al contar nodos debajo
        has_below = False
        for r in range(row + 1, total):
            sibling = tree.itemFromIndex(idx.model().index(r, 0, parent))
            if not (sibling and sibling.data(0, EMPTY_ROLE)):
                has_below = True
                break
        info.append({
            "has_below":    has_below,
            "has_children": idx.model().hasChildren(idx),
        })
        if not parent.isValid():
            break
        idx = parent

    cur_depth = len(info) - 1
    indent    = tree.indentation()
    mid_y     = rect.top() + rect.height() // 2
    pen       = QPen(line_color, LINE_WIDTH)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(pen)

    for k in range(1, len(info)):
        if not info[k]["has_below"]:
            continue
        d = cur_depth - k
        x = d * indent + indent // 2
        painter.drawLine(x, rect.top(), x, rect.bottom())

    x            = cur_depth * indent + indent // 2
    branch_right = (cur_depth + 1) * indent

    if cur_depth > 0 or index.row() > 0:
        painter.drawLine(x, rect.top(), x, mid_y)
        painter.drawLine(x, mid_y, branch_right, mid_y)
        if info[0]["has_below"]:
            painter.drawLine(x, mid_y, x, rect.bottom())
    elif info[0]["has_below"]:
        painter.drawLine(x, mid_y, branch_right, mid_y)
        painter.drawLine(x, mid_y, x, rect.bottom())

    painter.restore()


# ── Delegado de edición ───────────────────────────────────────────

class _Delegate(QStyledItemDelegate):
    """Delegado que controla qué celda es editable según columna y, opcionalmente,
    según el tipo de nodo (fila) al que pertenece.

    Comportamiento tipo Excel:
    - La celda ya seleccionada se edita con un clic adicional (SelectedClicked)
      o con F2 / cualquier tecla alfanumérica.
    - Al confirmar con Enter o Tab, el foco avanza a la siguiente celda editable
      del mismo item o del item siguiente. El árbol emite commitData para que
      paneles.py persista el valor antes de mover el foco.

    IMPORTANTE: este delegado es compartido por TODAS las tablas que usan
    TreeTableWidget (árbol de presupuesto, detalle de APU, catálogo de
    insumos, rastreo, conceptos planos, etc.), cada una con columnas muy
    distintas. Por eso NO debe asumir qué significa una columna en
    particular (p. ej. "la columna 2 siempre es Tipo") — eso rompía la
    detección en tablas donde esa misma columna es Descripción o Unidad,
    habilitando edición donde no correspondía.

    Si una tabla necesita que las columnas editables varíen según el tipo
    de fila (como el árbol de presupuesto: capítulo vs concepto), debe
    pasar `editable_cols_fn` al construir el TreeTableWidget: una función
    `item -> set[int]` que la propia tabla define usando datos explícitos
    del item (p. ej. un rol de datos), nunca texto de columnas visibles.
    Si no se pasa, se usa el set estático `editable_cols` para todas las filas.
    """

    def __init__(self, parent, editable_cols, editable_cols_fn=None, column_editors=None):
        super().__init__(parent)
        self._editable_cols = editable_cols
        self._editable_cols_fn = editable_cols_fn
        # ponytail: column_editors = {col: callable(parent) -> QWidget}
        self._column_editors = column_editors or {}

    def _cols_for_item(self, item) -> set[int]:
        """Devuelve el set de columnas editables para un item concreto."""
        if item is None:
            return set()
        if self._editable_cols_fn is not None:
            return self._editable_cols_fn(item) or set()
        return self._editable_cols

    def _es_editable(self, index) -> bool:
        item = self.parent().itemFromIndex(index)
        return index.column() in self._cols_for_item(item)

    def paint(self, painter, option, index):
        """Pinta la celda normal y, si su fila está en corte pendiente,
        agrega un borde punteado (ver TreeTableWidget._corte_pendiente).

        El borde marca la FILA completa (todas las columnas visibles) de
        cualquier item que tenga al menos una celda en corte — aunque solo
        las columnas editables se vayan a borrar al pegar, visualmente el
        usuario cortó la fila que seleccionó, no una celda suelta.

        Para que un bloque de varias filas se vea como un solo borde
        alrededor de todo el perímetro (y no un recuadro por celda), cada
        celda solo dibuja los lados que quedan en el borde exterior del
        bloque: arriba/abajo se omiten si la fila vecina (itemAbove/
        itemBelow) también está en el corte, e izquierda/derecha solo se
        dibujan en la primera/última columna visible.
        """
        super().paint(painter, option, index)
        self._dibujar_borde_corte(painter, option, index)

    def _dibujar_borde_corte(self, painter, option, index):
        """Dibuja el borde punteado de corte pendiente para (item, columna)
        si corresponde — separado de paint() para poder probarlo sin un
        QPainter real."""
        tw = self.parent()
        corte = getattr(tw, "_corte_pendiente", None)
        if not corte:
            return
        item = tw.itemFromIndex(index)
        if item is None:
            return
        filas_en_corte = {it for it, _c in corte}
        if item not in filas_en_corte:
            return

        col = index.column()
        cols_visibles = [c for c in range(tw.columnCount()) if not tw.isColumnHidden(c)]
        if not cols_visibles:
            return

        # En árboles jerárquicos, option.rect de la columna 0 arranca DESPUÉS
        # de la indentación/flecha de expandir (Qt las dibuja aparte, fuera
        # del delegado) — si usáramos ese rect tal cual, el borde dejaría un
        # hueco a la izquierda y la columna Estructura se vería como si no
        # estuviera marcada. Por eso el ancho horizontal se calcula con la
        # posición/ancho reales de la columna, no con option.rect (que solo
        # es confiable para el alto de la fila, no afectado por indentación).
        x0 = tw.columnViewportPosition(col)
        x1 = x0 + tw.columnWidth(col) - 1
        top = option.rect.top()
        bottom = option.rect.bottom()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        pen = QPen(QColor(WARNING), 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        if tw.itemAbove(item) not in filas_en_corte:
            painter.drawLine(QPoint(x0, top), QPoint(x1, top))
        if tw.itemBelow(item) not in filas_en_corte:
            painter.drawLine(QPoint(x0, bottom), QPoint(x1, bottom))
        if col == cols_visibles[0]:
            painter.drawLine(QPoint(x0, top), QPoint(x0, bottom))
        if col == cols_visibles[-1]:
            painter.drawLine(QPoint(x1, top), QPoint(x1, bottom))
        painter.restore()

    def createEditor(self, parent, option, index):
        """Crea editor solo si la celda es editable para ese tipo de nodo."""
        if not self._es_editable(index):
            return None
        col = index.column()
        if col in self._column_editors:
            editor = self._column_editors[col](parent)
            from PySide6.QtWidgets import QComboBox
            from PySide6.QtCore import QTimer
            if isinstance(editor, QComboBox):
                editor.activated.connect(lambda: self._on_combo_selected(editor))
                # ponytail: ancho del popup = ancho del contenido más largo
                fm = editor.fontMetrics()
                max_w = max((fm.horizontalAdvance(editor.itemText(i)) for i in range(editor.count())), default=0)
                editor.setMinimumWidth(max_w + 40)
                QTimer.singleShot(0, editor.showPopup)
            return editor
        editor = super().createEditor(parent, option, index)
        if editor:
            from PySide6.QtWidgets import QLineEdit
            if isinstance(editor, QLineEdit):
                editor.selectAll()
        return editor

    def _on_combo_selected(self, editor):
        """Cierra popup primero, luego confirma y cierra el editor."""
        editor.hidePopup()
        QTimer.singleShot(0, lambda: self._commit_and_close(editor))

    def _commit_and_close(self, editor):
        """Cierra el editor QComboBox confirmando el valor seleccionado."""
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)

    def setEditorData(self, editor, index):
        """Limpia formato para QLineEdit; selecciona valor actual para QComboBox."""
        from PySide6.QtWidgets import QComboBox
        if isinstance(editor, QComboBox):
            texto = index.data(Qt.ItemDataRole.DisplayRole) or ""
            texto_limpio = texto.split(" › ")[0].strip() if " › " in texto else texto.strip()
            idx = editor.findText(texto_limpio)
            editor.setCurrentIndex(idx if idx >= 0 else 0)
        elif isinstance(editor, QLineEdit):
            texto = index.data(FORMULA_ROLE) or index.data(Qt.ItemDataRole.DisplayRole) or ""
            texto = texto.lstrip("\u25b6").strip()
            editor.setText(texto)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """Escribe el valor del QComboBox al modelo (texto + userData en UserRole).

        ponytail: UserRole ANTES de EditRole para que cuando itemChanged
        dispare _on_insumo_editado, UserRole ya tenga el valor correcto.
        Si escribíamos EditRole primero, el handler leía el tipo_id viejo
        y lo guardaba de vuelta — la combo solo funcionaba una vez.
        """
        from PySide6.QtWidgets import QComboBox
        if isinstance(editor, QComboBox):
            if editor.currentData() is not None:
                model.setData(index, editor.currentData(), Qt.ItemDataRole.UserRole)
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def commitAndMove(self, editor, hint):
        """Confirma el editor y mueve el foco a la siguiente celda editable."""
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)
        tw = self.parent()
        if not isinstance(tw, QTreeWidget):
            return
        current = tw.currentIndex()
        item = tw.itemFromIndex(current)
        editable_cols = sorted(self._cols_for_item(item))
        if not editable_cols:
            return
        # Buscar la siguiente columna editable en el mismo item
        next_col = next((c for c in editable_cols if c > current.column()), None)
        if next_col is not None:
            tw.setCurrentIndex(tw.model().index(current.row(), next_col, current.parent()))
            tw.edit(tw.currentIndex())
            return
        # Si no hay más columnas en este item, ir al siguiente item en la primera col editable
        next_item = tw.itemBelow(item) if hint == QStyledItemDelegate.EndEditHint.EditNextItem \
                    else tw.itemAbove(item)
        if next_item:
            next_editable = sorted(self._cols_for_item(next_item))
            if next_editable:
                idx = tw.indexFromItem(next_item, next_editable[0])
                tw.setCurrentIndex(idx)
                tw.scrollToItem(next_item)
                tw.edit(idx)

    def eventFilter(self, editor, event):
        """Intercepta Enter (cerrar), Tab (mover foco), Escape (cancelar) y Ctrl+Z/Y (undo/redo)."""
        from PySide6.QtWidgets import QComboBox
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if isinstance(editor, QComboBox) and editor.isPopupVisible():
                    editor.hidePopup()
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.NoHint)
                return True
            if key == Qt.Key.Key_Escape:
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                return True
            if key == Qt.Key.Key_Tab:
                self.commitAndMove(editor, QStyledItemDelegate.EndEditHint.EditNextItem)
                return True
            if key == Qt.Key.Key_Backtab:
                self.commitAndMove(editor, QStyledItemDelegate.EndEditHint.EditPreviousItem)
                return True
            if key == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                win = self.parent().window()
                if hasattr(win, '_on_deshacer'):
                    win._on_deshacer()
                return True
            if key == Qt.Key.Key_Y and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                win = self.parent().window()
                if hasattr(win, '_on_rehacer'):
                    win._on_rehacer()
                return True
        return super().eventFilter(editor, event)


# ── Widget tabla base ─────────────────────────────────────────────

class TreeTableWidget(QTreeWidget):

    _HEADER_KEY = None  # ponytail: subclases definen su clave de persistencia
    _CATALOGO_KEY = None  # clave de persistencia de "favoritas" (Config), si aplica
    COLUMNAS_CATALOGO: list[ColumnaDef] = []  # subclases lo definen para habilitar
    # el menú "favoritas + Personalizar columnas…". Tablas que lo dejan vacío
    # conservan el menú simple de siempre (todas las columnas, sin agrupar).

    # ── Constructor ───────────────────────────────────────────────

    def __init__(self, columns, editable_cols=frozenset(), flat=False,
                 line_color=None, parent=None, editable_cols_fn=None,
                 column_editors=None, paste_col_fn=None):
        """Inicializa QTreeWidget con columnas, editabilidad, modo plano/jerárquico y cabecera.

        editable_cols_fn: función opcional `item -> set[int]` para tablas donde
        las columnas editables dependen del tipo de fila (ver arbol.py). Si no
        se pasa, editable_cols aplica igual a todas las filas.
        column_editors: dict `{col: callable(parent) -> QWidget}` para dropdowns
        u otros editores custom en columnas específicas.
        paste_col_fn: dict opcional `{col: callable(str) -> tuple[str, Any] | None}`
        para columnas cuyo valor guardado no es el texto tal cual (ej. columnas
        con combo respaldado por un id en UserRole, como Tipo/Familia en
        Catálogo de Insumos). El callable recibe el texto pegado y devuelve
        (texto_a_mostrar, dato_para_userrole), o None si el texto pegado no se
        pudo interpretar — en ese caso la celda no se toca. Sin resolver para
        una columna, pegar escribe el texto tal cual (comportamiento anterior).
        Ver _escribir_celda_pegada().
        """
        super().__init__(parent)
        self._flat          = flat
        self._line_color    = line_color or LINE_COLOR
        self._editable_cols = editable_cols
        self._editable_cols_fn = editable_cols_fn
        self._paste_col_fn = paste_col_fn or {}
        self._search_cols: set[int] | None = None  # None = buscar en todas
        self._corte_pendiente: set[tuple] | None = None  # {(item, col), ...} — ver _cut()

        self.setColumnCount(len(columns))
        self.setHeaderLabels(columns)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setIndentation(24 if not flat else 0)
        self.setRootIsDecorated(not flat)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._applying_modes = False
        self.setMouseTracking(True)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.SelectedClicked   # clic en celda ya seleccionada
            | QAbstractItemView.EditTrigger.EditKeyPressed  # F2
            | QAbstractItemView.EditTrigger.AnyKeyPressed   # cualquier tecla alfanumérica
            | QAbstractItemView.EditTrigger.DoubleClicked   # doble clic
        )
        self.setItemDelegate(_Delegate(self, editable_cols, editable_cols_fn, column_editors))

        h = self.header()
        h.setStretchLastSection(False)
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(self._header_context_menu)
        h.sectionResized.connect(self._save_header_state)
        h.sectionMoved.connect(self._save_header_state)
        for c in range(len(columns)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)

    # ── Modos de columna ──────────────────────────────────────────

    def set_column_modes(self, modes: dict):
        """Aplica anchos y modos de redimensión a las columnas.

        Guarda la configuración y la aplica ahora y también en showEvent,
        porque Qt ignora resizeSection antes de que el widget sea visible.
        Las columnas con modo Stretch se convierten internamente a Interactive
        con un ancho proporcional — así el usuario puede redimensionar todas.
        """
        self._pending_modes = modes   # guardado para re-aplicar en showEvent
        self._apply_column_modes()

    def _apply_column_modes(self):
        """Aplica anchos y modos de redimension pendientes a cada columna."""
        modes = getattr(self, "_pending_modes", None)
        if not modes:
            return
        self._applying_modes = True
        h = self.header()
        # Primero todo Interactive para que resizeSection funcione
        for c in range(self.columnCount()):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        # Aplicar anchos
        for c, (mode, width) in modes.items():
            if width is not None:
                h.resizeSection(c, width)
        self._applying_modes = False
        # Aplicar modos finales — Stretch se deja como Interactive
        # para que el usuario pueda redimensionar cualquier columna
        for c, (mode, width) in modes.items():
            if mode == QHeaderView.ResizeMode.Stretch:
                # Stretch no permite drag — usamos Interactive con ancho ya seteado
                h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            else:
                h.setSectionResizeMode(c, mode)

    def showEvent(self, event):
        """Restaura estado guardado del usuario; si no hay, aplica anchos por defecto."""
        super().showEvent(event)
        if self._HEADER_KEY and self._restore_header_state():
            return
        self._apply_column_modes()

    # ── Persistencia de cabecera ──────────────────────────────────

    def _save_header_state(self):
        """Guarda estado del header en config.json como base64."""
        if not self._HEADER_KEY or getattr(self, '_applying_modes', False):
            return
        raw = self.header().saveState()
        Config.set(self._HEADER_KEY, raw.toBase64().data().decode("ascii"))

    def _restore_header_state(self) -> bool:
        """Restaura estado del header desde config.json si existe. Retorna True si restauró."""
        if not self._HEADER_KEY:
            return False
        saved = Config.get(self._HEADER_KEY)
        if saved:
            self.header().restoreState(QByteArray.fromBase64(saved.encode("ascii")))
            return True
        return False

    # ── Menú contextual de cabecera ───────────────────────────────

    # ── Favoritas (catálogo de columnas) ──────────────────────────

    def _favoritas(self) -> set[int]:
        """Índices de columna marcados como favoritos (aparecen en el menú
        rápido). Si nunca se guardó nada, usa favorita_default del catálogo.
        Tablas sin COLUMNAS_CATALOGO no usan este mecanismo."""
        if not self.COLUMNAS_CATALOGO:
            return set(range(self.columnCount()))
        saved = Config.get(self._CATALOGO_KEY) if self._CATALOGO_KEY else None
        if saved is not None:
            return set(saved)
        return {c.idx for c in self.COLUMNAS_CATALOGO if c.favorita_default}

    def _guardar_favoritas(self, favoritas: set[int]) -> None:
        """Persiste el set de favoritas. No-op si la tabla no define _CATALOGO_KEY."""
        if self._CATALOGO_KEY:
            Config.set(self._CATALOGO_KEY, sorted(favoritas))

    # ── Imprimibles (catálogo de columnas) ──────────────────────────
    # Tercer filtro independiente de favorita/visible: qué columnas se
    # incluyen al generar el reporte LaTeX/PDF. Se persiste bajo una
    # clave derivada de _CATALOGO_KEY (mismo esquema que favoritas).

    def _imprimibles_key(self) -> str | None:
        if not self._CATALOGO_KEY:
            return None
        if self._CATALOGO_KEY.endswith("_favoritas"):
            return self._CATALOGO_KEY[: -len("favoritas")] + "imprimibles"
        return f"{self._CATALOGO_KEY}_imprimibles"

    def _imprimibles(self) -> set[int]:
        """Índices de columna marcados como imprimibles (se incluyen en el
        reporte LaTeX/PDF). Si nunca se guardó nada, usa imprimible_default
        del catálogo. Tablas sin COLUMNAS_CATALOGO no usan este mecanismo."""
        if not self.COLUMNAS_CATALOGO:
            return set(range(self.columnCount()))
        clave = self._imprimibles_key()
        saved = Config.get(clave) if clave else None
        if saved is not None:
            return set(saved)
        return {c.idx for c in self.COLUMNAS_CATALOGO if c.imprimible_default}

    def _guardar_imprimibles(self, imprimibles: set[int]) -> None:
        """Persiste el set de imprimibles. No-op si la tabla no define _CATALOGO_KEY."""
        clave = self._imprimibles_key()
        if clave:
            Config.set(clave, sorted(imprimibles))

    def columnas_para_imprimir(self) -> list[dict]:
        """Columnas marcadas como imprimibles, en el orden visual actual
        (respeta si el usuario arrastró encabezados) y con su ancho actual
        en píxeles — lo que el generador de reportes (LaTeX) necesita para
        armar una tabla que refleje la personalización de columnas.

        Solo devuelve algo útil para tablas con COLUMNAS_CATALOGO; el resto
        devuelve lista vacía.
        """
        if not self.COLUMNAS_CATALOGO:
            return []
        imprimibles = self._imprimibles()
        por_idx = {c.idx: c for c in self.COLUMNAS_CATALOGO}
        h = self.header()
        columnas = []
        for visual in range(self.columnCount()):
            idx = h.logicalIndex(visual)
            if idx not in imprimibles or idx not in por_idx:
                continue
            columnas.append({
                "idx":      idx,
                "label":    por_idx[idx].label,
                "ancho_px": self.header().sectionSize(idx),
            })
        return columnas

    # ── Menú contextual de cabecera ───────────────────────────────

    def _header_context_menu(self, pos):
        """Menú contextual sobre cabecera para mostrar/ocultar columnas.

        Si la tabla define COLUMNAS_CATALOGO, el menú rápido solo lista las
        columnas favoritas y agrega "Personalizar columnas…" al final para
        elegir entre todo el catálogo. Si no, se mantiene el menú simple
        (todas las columnas, sin agrupar) para no romper tablas que aún no
        migraron a este esquema.
        """
        if self.COLUMNAS_CATALOGO:
            self._header_context_menu_catalogo(pos)
        else:
            self._header_context_menu_simple(pos)

    def _header_context_menu_simple(self, pos):
        menu = QMenu(self)
        for c in range(self.columnCount()):
            name = self.headerItem().text(c)
            if not name:
                continue
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(not self.isColumnHidden(c))
            act.toggled.connect(lambda checked, col=c: self.setColumnHidden(col, not checked))
        menu.exec(self.header().mapToGlobal(pos))
        self._save_header_state()

    def _header_context_menu_catalogo(self, pos):
        favoritas = self._favoritas()
        menu = QMenu(self)
        for col in self.COLUMNAS_CATALOGO:
            if col.idx not in favoritas:
                continue
            act = menu.addAction(col.label)
            act.setCheckable(True)
            act.setChecked(not self.isColumnHidden(col.idx))
            act.toggled.connect(
                lambda checked, c=col.idx: self.setColumnHidden(c, not checked))
        menu.addSeparator()
        personalizar_act = menu.addAction(_menu_icon("settings"), "Personalizar columnas…")
        personalizar_act.triggered.connect(self._abrir_personalizar_columnas)
        menu.exec(self.header().mapToGlobal(pos))
        self._save_header_state()

    def _abrir_personalizar_columnas(self):
        dlg = PersonalizarColumnasDialog(self)
        dlg.exec()
        self._save_header_state()

    # ── Inserción de filas ────────────────────────────────────────

    def add_row(self, data, parent=None, editable=True):
        """Agrega fila al árbol con valores de data; editable=False la bloquea.

        Si el nivel donde se agrega termina en una fila placeholder "agregar
        nueva" (EMPTY_ROLE — ver Insumos/Árbol de presupuesto), la fila se
        inserta ANTES de ese placeholder en vez de después: como
        QTreeWidgetItem(parent, data) siempre agrega al final absoluto, sin
        esto cualquier fila nueva (creada a mano o por crear_fila_pegado)
        terminaría colándose debajo de "Nuevo insumo..."/"Nuevo capítulo...".
        """
        parent = parent or self
        item = QTreeWidgetItem(data)
        if isinstance(parent, TreeTableWidget):
            count = parent.topLevelItemCount()
            if count > 0 and parent.topLevelItem(count - 1).data(0, EMPTY_ROLE):
                parent.insertTopLevelItem(count - 1, item)
            else:
                parent.addTopLevelItem(item)
        else:
            count = parent.childCount()
            if count > 0 and parent.child(count - 1).data(0, EMPTY_ROLE):
                parent.insertChild(count - 1, item)
            else:
                parent.addChild(item)
        if editable:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    # ── Dibujado de ramas ─────────────────────────────────────────

    def drawBranches(self, painter, rect, index):
        """Dibuja conectores jerárquicos entre nodos si el modo no es plano."""
        item = self.itemFromIndex(index)
        if item and item.data(0, EMPTY_ROLE):
            return
        super().drawBranches(painter, rect, index)
        if not self._flat:
            draw_tree_connectors(self, painter, rect, index, self._line_color)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() != Qt.MouseButton.LeftButton:
            return
        item = self.itemAt(event.pos())
        if item and item.childCount() > 0 and self.columnAt(event.pos().x()) == 0:
            vrect = self.visualRect(self.indexFromItem(item))
            if event.position().x() >= vrect.x():
                self._toggle_current_expanded()

    # ── Control de expansión / visibilidad ────────────────────────

    def show_primer_nivel(self):
        """Colapsa todo mostrando solo el primer nivel (raíces)."""
        self._show_all()
        self.collapseAll()

    def show_solo_agrupadores(self):
        """Muestra solo nodos con hijos (agrupadores), oculta hojas."""
        self._show_all()
        self.expandAll()
        for i in range(self.topLevelItemCount()):
            self._hide_leaves(self.topLevelItem(i))

    def show_todo(self):
        """Muestra todos los nodos expandidos completamente."""
        self._show_all()
        self.expandAll()

    def show_nivel(self, depth: int):
        """Expande items hasta profundidad N (recorrido manual del árbol).
        depth=0 → solo raíces colapsadas (igual que Primer nivel)
        depth=1 → raíces expandidas (hijos visibles)
        depth=2 → + nietos visibles
        etc.
        """
        self._show_all()
        self.collapseAll()
        for i in range(self.topLevelItemCount()):
            self._expand_depth(self.topLevelItem(i), depth, 0)

    @staticmethod
    def _expand_depth(item, max_depth, current):
        """Expande item y sus hijos recursivamente hasta max_depth.
        Reemplaza a expandToDepth() de Qt que da resultados inconsistentes
        entre versiones cuando hay items raíz múltiples (nivel 0 + nivel 1).
        """
        if current >= max_depth:
            return
        item.setExpanded(True)
        for i in range(item.childCount()):
            TreeTableWidget._expand_depth(item.child(i), max_depth, current + 1)

    @staticmethod
    def _hide_leaves(item):
        """Recursivamente oculta nodos hoja (sin hijos)."""
        if item.childCount() == 0:
            item.setHidden(True)
        else:
            for i in range(item.childCount()):
                TreeTableWidget._hide_leaves(item.child(i))

    # ── Sincronizar columnas ocultas con búsqueda ──────────────────

    def setColumnHidden(self, column: int, hidden: bool):
        """Al ocultar una columna, la saca de _search_cols para que la
        búsqueda no la incluya sin que el usuario pueda desmarcarla."""
        super().setColumnHidden(column, hidden)
        if hidden and self._search_cols is not None and column in self._search_cols:
            self._search_cols.discard(column)

    # ── Filtrado de filas (multi-columna) ────────────────────────
    # Busca en todas las columnas de _search_cols (None = todas).
    # Cada widget define sus columnas por defecto y el usuario
    # las ajusta desde el menú contextual de la barra de búsqueda.

    def filter_rows(self, text):
        """Filtra filas visibles buscando text en las columnas configuradas (_search_cols)."""
        if not text:
            self._show_all()
            return
        text = text.lower()
        cols = self._search_cols if self._search_cols is not None else {c for c in range(self.columnCount()) if not self.isColumnHidden(c)}
        for i in range(self.topLevelItemCount()):
            self._filter_item_multi(self.topLevelItem(i), text, cols)

    # ── Mostrar todo / filtrar internos ───────────────────────────

    def _show_all(self, parent=None):
        """Muestra todos los items (quita cualquier ocultación) recursivamente."""
        items = ([self.topLevelItem(i) for i in range(self.topLevelItemCount())]
                 if parent is None
                 else [parent.child(i) for i in range(parent.childCount())])
        for item in items:
            item.setHidden(False)
            if item.childCount():
                self._show_all(item)

    # Recorre recursivamente el árbol; un item es visible si él o
    # alguno de sus hijos coincide en CUALQUIERA de las columnas.
    def _filter_item_multi(self, item, text, cols):
        """Evalúa si item o algún hijo coincide; actualiza visibilidad. Retorna True si es visible."""
        match = any(text in item.text(c).lower() for c in cols)
        any_child_visible = False
        for i in range(item.childCount()):
            if self._filter_item_multi(item.child(i), text, cols):
                any_child_visible = True
        visible = match or any_child_visible
        item.setHidden(not visible)
        return visible

    # ── Columnas de búsqueda ──────────────────────────────────────

    def get_searchable_columns(self) -> list[tuple[int, str]]:
        """Columnas que pueden incluirse en la búsqueda: (índice, etiqueta).
        Se usa en el menú contextual de la barra de búsqueda.
        Las subclases pueden sobreescribir para limitar las opciones.
        """
        return [(c, self.headerItem().text(c))
                for c in range(self.columnCount())
                if self.headerItem().text(c)]

    def get_search_columns(self) -> set[int] | None:
        """Columnas donde se filtra. None = buscar en todas."""
        return self._search_cols

    def set_search_columns(self, cols: set[int] | None):
        """Cambia las columnas de búsqueda. None = buscar en todas."""
        self._search_cols = cols

    # ── Manejo de teclado ─────────────────────────────────────────

    def selectAll(self):
        """Selecciona solo los ítems visibles (respeta filtros activos).
        Qt nativo selecciona también los ocultos, lo que produce resultados
        inesperados al copiar o al contar filas seleccionadas.
        """
        self.clearSelection()
        def _select_visible(parent_item):
            count = (self.topLevelItemCount() if parent_item is None
                     else parent_item.childCount())
            for i in range(count):
                item = (self.topLevelItem(i) if parent_item is None
                        else parent_item.child(i))
                if not item.isHidden():
                    item.setSelected(True)
                    if item.childCount():
                        _select_visible(item)
        _select_visible(None)

    def keyPressEvent(self, event):
        """Captura Ctrl+C/X/V/A/Z/Y, navegación de columnas con Izq/Der y
        expandir/colapsar con Espacio; delega lo demás al comportamiento nativo.

        Antes, Izquierda/Derecha expandían y colapsaban el ítem actual (comportamiento
        nativo de QTreeWidget). Se reasignan a navegación entre columnas — más útil en
        una tabla con muchas columnas — y esa función pasa a la tecla Espacio.
        """
        key = event.key()
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy()
        elif event.matches(QKeySequence.StandardKey.Cut):
            self._cut()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self._paste()
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            self.selectAll()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self._undo()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self._redo()
        elif key == Qt.Key.Key_Left:
            self._move_current_column(-1)
        elif key == Qt.Key.Key_Right:
            self._move_current_column(1)
        elif key == Qt.Key.Key_Space:
            self._toggle_current_expanded()
        elif key == Qt.Key.Key_Escape:
            self._cancelar_corte_pendiente_si_hay()
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def _visible_columns(self) -> list[int]:
        """Índices de columnas visibles, en orden, respetando columnas ocultas
        por personalización (ver menú 'Personalizar columnas…')."""
        return [c for c in range(self.columnCount()) if not self.isColumnHidden(c)]

    def _move_current_column(self, delta: int):
        """Mueve el foco de celda a la columna visible anterior (-1) o siguiente (+1),
        sin salir de la fila actual. Ignora columnas ocultas."""
        cols = self._visible_columns()
        if not cols:
            return
        current = self.currentIndex()
        if not current.isValid():
            return
        try:
            pos = cols.index(current.column())
        except ValueError:
            # El foco estaba en una columna oculta u otro estado inesperado:
            # aterrizar en el extremo hacia el que se navega.
            pos = 0 if delta > 0 else len(cols) - 1
        pos = max(0, min(len(cols) - 1, pos + delta))
        new_col = cols[pos]
        self.setCurrentIndex(self.model().index(current.row(), new_col, current.parent()))

    def _toggle_current_expanded(self):
        """Espacio: alterna expandir/colapsar el ítem actual (reemplaza el uso
        nativo de Izquierda/Derecha para esta acción). No hace nada en ítems hoja."""
        item = self.currentItem()
        if item is not None and item.childCount() > 0:
            item.setExpanded(not item.isExpanded())

    def _undo(self):
        """Ctrl+Z: delega al handler de la ventana principal."""
        win = self.window()
        if hasattr(win, '_on_deshacer'):
            win._on_deshacer()

    def _redo(self):
        """Ctrl+Y: delega al handler de la ventana principal."""
        win = self.window()
        if hasattr(win, '_on_rehacer'):
            win._on_rehacer()

    @staticmethod
    def _item_sort_key(item):
        """Genera clave de orden según posición en el árbol (índices desde raíz)."""
        path = []
        while item:
            parent = item.parent()
            idx = parent.indexOfChild(item) if parent else item.treeWidget().indexOfTopLevelItem(item)
            path.append(idx)
            item = parent
        return tuple(reversed(path))

    # ── Portapapeles (copiar / pegar) ─────────────────────────────

    def _es_fila_vacia(self, item) -> bool:
        """True si item es la fila placeholder de 'agregar nueva fila'
        (marcada con EMPTY_ROLE por Insumos/Árbol de presupuesto) — no
        existe en la base de datos, es solo un gancho de UI para crear una
        fila real al hacer clic. Cortar/pegar deben tratarla como si no
        existiera en absoluto: no se corta, no se le escribe directamente
        (ver _editable_cols_for), y al pegar de más filas dispara la
        creación de una fila real (crear_fila_pegado) en vez de escribir
        encima del placeholder — ver _pegar_cuadricula."""
        return bool(item is not None and item.data(0, EMPTY_ROLE))

    def _editable_cols_for(self, item) -> set[int]:
        """Columnas editables para un item concreto — respeta editable_cols_fn
        cuando la tabla lo define (columnas editables que dependen del tipo de
        fila, ej. capítulo vs concepto en el árbol de presupuesto). Antes,
        cortar/pegar consultaban directamente self._editable_cols (el set
        estático) e ignoraban editable_cols_fn, permitiendo cortar/pegar en
        columnas que para esa fila en particular no eran editables.

        La fila placeholder (EMPTY_ROLE) nunca es editable aquí, aunque su
        tabla declare columnas editables estáticas (ej. Insumos) — si no,
        pegar un bloque que alcance esa fila escribiría datos reales sobre
        el placeholder "Nuevo insumo..." en vez de crear una fila nueva."""
        if item is None or self._es_fila_vacia(item):
            return set()
        if self._editable_cols_fn is not None:
            return self._editable_cols_fn(item) or set()
        return self._editable_cols

    def copy_selection(self) -> bool:
        """
        Copy selected rows as TSV (tab-separated values) to clipboard.
        Returns True if something was copied.
        Called by Ctrl+C and toolbar 'Copiar' button.
        Only copies visible columns — hidden columns (like Desc. Corta, Creado, etc.)
        are excluded from the output.
        """
        items = self.selectedItems()
        if not items:
            return False

        items.sort(key=self._item_sort_key)

        cols = [c for c in range(self.columnCount()) if not self.isColumnHidden(c)]
        header = [_strip_icons(self.headerItem().text(c)) for c in cols]
        lines = ["\t".join(header)]
        for item in items:
            lines.append("\t".join(_strip_icons(item.text(c)) for c in cols))

        QApplication.clipboard().setText("\n".join(lines))
        return True

    def _copy(self):
        """Copia selección al portapapeles como TSV; si no hay selección copia celda actual.
        Cancela cualquier corte pendiente — una nueva operación de portapapeles
        reemplaza a la anterior (mismo comportamiento que Excel)."""
        _cancelar_corte_activo()
        if self.copy_selection():
            return
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0:
            return
        QApplication.clipboard().setText(_strip_icons(item.text(col)))

    def _cut(self):
        """Corta: copia la selección al portapapeles y la marca como 'corte
        pendiente' (borde punteado) — el contenido NO se borra todavía.
        Solo entran al corte las celdas de columnas editables para su fila
        (columnas calculadas/no editables se copian pero no se marcan, ya
        que no se pueden vaciar). El borrado real ocurre al completar un
        Pegar sobre este corte (ver _paste). Esc, o iniciar otro Copiar/
        Cortar en cualquier tabla, cancela el corte sin borrar nada."""
        items = self.selectedItems()
        if items:
            items = sorted(items, key=self._item_sort_key)
            cols_visibles = [c for c in range(self.columnCount()) if not self.isColumnHidden(c)]
            celdas = {(it, c) for it in items for c in cols_visibles
                      if c in self._editable_cols_for(it)}
        else:
            item = self.currentItem()
            col  = self.currentColumn()
            if not item or col < 0 or col not in self._editable_cols_for(item):
                return
            celdas = {(item, col)}

        if not celdas:
            return

        _cancelar_corte_activo()
        if not self.copy_selection():
            item, col = next(iter(celdas))
            QApplication.clipboard().setText(_strip_icons(item.text(col)))

        self._corte_pendiente = celdas
        global _CORTE_ACTIVO
        _CORTE_ACTIVO = self
        self.viewport().update()

    def _cancelar_corte_pendiente_si_hay(self):
        """Esc: cancela el corte pendiente de esta tabla, si lo hay."""
        if self._corte_pendiente:
            _cancelar_corte_activo()

    def _consumir_corte_pendiente(self, celda_destino_final: tuple | None):
        """Si hay un corte pendiente activo (de esta tabla o de otra), lo
        consume: borra el contenido de las celdas cortadas —salvo la celda de
        destino final, si coincide con alguna de ellas, para no autoborrar lo
        que se acaba de pegar— y limpia el estado."""
        global _CORTE_ACTIVO
        if _CORTE_ACTIVO is None:
            return
        origen = _CORTE_ACTIVO
        celdas = origen._corte_pendiente or set()
        _CORTE_ACTIVO = None
        origen._corte_pendiente = None
        for it, c in celdas:
            if (it, c) != celda_destino_final:
                it.setText(c, "")
        origen.viewport().update()

    def _paste(self):
        """Pega el contenido del portapapeles en la celda actual.

        Si el texto es una sola celda (sin tabs ni saltos de línea), pega
        igual que siempre. Si es una cuadrícula —un bloque copiado de Excel,
        con tabs entre columnas y saltos de línea entre filas— la expande
        desde la celda actual hacia abajo (filas visibles) y hacia la derecha
        (columnas editables visibles), saltando columnas no editables dentro
        del rango. Por ahora NO crea filas nuevas si el bloque trae más filas
        de las que hay disponibles debajo — se avisa y se descarta el resto.

        Si el pegado se origina en un corte pendiente (de esta tabla u otra),
        al completarse borra el contenido de las celdas cortadas.

        Todas las escrituras de un mismo pegado (incluido el borrado del
        origen si venía de un corte) quedan agrupadas en una sola entrada
        de deshacer (ver Api.iniciar_sesion_undo).
        """
        text = QApplication.clipboard().text()
        if not text:
            return
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0:
            return

        filas = _parsear_portapapeles(text)
        filas = self._descartar_fila_encabezado(filas)
        if not filas:
            return
        win = self.window()
        api = getattr(win, '_api', None)
        if api is not None:
            api.iniciar_sesion_undo()
        try:
            if len(filas) == 1 and len(filas[0]) <= 1:
                if col not in self._editable_cols_for(item):
                    return
                valor = filas[0][0] if filas[0] else ""
                self._escribir_celda_pegada(item, col, valor)
                self._consumir_corte_pendiente((item, col))
                return

            self._pegar_cuadricula(item, col, filas)
        finally:
            if api is not None:
                api.cerrar_sesion_undo()

    def _descartar_fila_encabezado(self, filas: list[list[str]]) -> list[list[str]]:
        """copy_selection() antepone una fila de encabezados al TSV copiado
        (para que se vea bien si el destino es Excel) — pero si el pegado
        vuelve a esta misma app, esa fila NO es un dato y no debe tratarse
        como tal: pegarla escribe basura (ej. el texto "Estructura", el
        encabezado de la primera columna, cayendo en una celda de Cantidad
        que espera un número o fórmula, y revienta la validación).

        Si la primera fila del bloque pegado coincide exactamente con los
        encabezados visibles de esta tabla, se descarta antes de escribir.
        Si el pegado viene de otra tabla con encabezados distintos, o de
        Excel (que no antepone encabezados propios de esta app), la
        primera fila no coincide y se deja intacta.
        """
        if not filas:
            return filas
        cols_visibles = [c for c in range(self.columnCount()) if not self.isColumnHidden(c)]
        encabezados = [_strip_icons(self.headerItem().text(c)) for c in cols_visibles]
        if filas[0] == encabezados:
            return filas[1:]
        return filas

    def _escribir_celda_pegada(self, item, col: int, valor: str) -> bool:
        """Escribe un valor pegado en (item, col), usando el resolver de
        paste_col_fn si la columna lo tiene registrado (columnas respaldadas
        por un id en UserRole, ej. Tipo/Familia — pegar solo el texto ahí no
        alcanza, hay que resolver a qué id corresponde y guardarlo también,
        o el guardado real se perdería/corrompería). Si el resolver no
        reconoce el texto pegado, no toca la celda y devuelve False."""
        resolver = self._paste_col_fn.get(col)
        if resolver is None:
            item.setText(col, valor)
            return True
        resultado = resolver(valor)
        if resultado is None:
            return False
        texto, dato = resultado
        # UserRole ANTES que el texto — mismo motivo que en _Delegate.setModelData:
        # setText() dispara itemChanged sincrónicamente, y el handler que persiste
        # el cambio (ej. _on_insumo_editado) lee UserRole en ese momento. Si el
        # texto se escribe primero, el handler todavía ve el UserRole viejo.
        item.setData(col, Qt.ItemDataRole.UserRole, dato)
        item.setText(col, texto)
        return True

    def crear_fila_pegado(self, item_referencia, datos_fila: dict[int, str]):
        """Hook: las subclases lo implementan para crear una fila real (vía
        Api, igual que el botón/flujo "Agregar") cuando un pegado necesita
        más filas de las que hay disponibles debajo del cursor.

        item_referencia: última fila existente antes de necesitar una nueva
        — en tablas jerárquicas, sirve para heredar tipo/nivel/padre (nunca
        se debe inventar una estructura nueva).
        datos_fila: {columna: texto_pegado} solo para las columnas editables
        de item_referencia.

        Devuelve el QTreeWidgetItem recién creado (ya con sus valores, vía
        el evento que dispara la propia llamada a la Api), o None si esta
        tabla no soporta crear filas por pegado o los datos pegados no
        alcanzan para crear una (ej. falta un campo obligatorio) — la clase
        base nunca inventa datos de negocio. Implementación por defecto:
        no soportado.
        """
        return None

    def _pegar_cuadricula(self, item_inicial, col_inicial: int, filas: list[list[str]]):
        """Escribe una cuadrícula de valores empezando en (item_inicial,
        col_inicial). Cada fila del bloque pegado va a la siguiente fila
        visible de la tabla (itemBelow); dentro de cada fila, los valores se
        reparten en las columnas editables visibles desde col_inicial en
        adelante, en orden, saltando las que no son editables para esa fila
        (ver editable_cols_fn — algunas tablas tienen columnas editables
        distintas según el tipo de fila). Los valores que sobran para una
        fila porque esta tiene menos columnas editables que las pegadas se
        descartan en silencio.

        Si el bloque trae más filas de las que hay debajo —o la tabla tiene
        una fila placeholder "agregar nueva" (EMPTY_ROLE) al final, como
        Insumos/Árbol de presupuesto— intenta crear filas nuevas vía
        crear_fila_pegado() (ver ese método) usando la última fila real
        como referencia, en vez de escribir encima del placeholder. Si la
        tabla no soporta crear filas, o los datos pegados no alcanzan para
        crear una, esa fila (y las siguientes que tampoco tengan destino)
        se descarta con aviso.
        """
        fila_actual = item_inicial
        referencia = item_inicial
        ultima_celda = None
        filas_sin_destino = 0
        filas_creadas = 0
        for valores in filas:
            if fila_actual is None or self._es_fila_vacia(fila_actual):
                cols_editables = [c for c in range(self.columnCount())
                                   if c >= col_inicial and not self.isColumnHidden(c)
                                   and c in self._editable_cols_for(referencia)]
                datos_fila = {c: v for v, c in zip(valores, cols_editables) if v.strip()}
                nueva = self.crear_fila_pegado(referencia, datos_fila) if datos_fila else None
                if nueva is None:
                    filas_sin_destino += 1
                    continue
                filas_creadas += 1
                referencia = nueva
                fila_actual = self.itemBelow(nueva)
                continue
            cols_editables = [c for c in range(self.columnCount())
                               if c >= col_inicial and not self.isColumnHidden(c)
                               and c in self._editable_cols_for(fila_actual)]
            for valor, c in zip(valores, cols_editables):
                if self._escribir_celda_pegada(fila_actual, c, valor):
                    ultima_celda = (fila_actual, c)
            referencia = fila_actual
            fila_actual = self.itemBelow(fila_actual)

        if filas_sin_destino:
            from PySide6.QtWidgets import QMessageBox
            pegadas = len(filas) - filas_sin_destino
            detalle = f" ({filas_creadas} fila(s) nueva(s) creada(s))" if filas_creadas else ""
            QMessageBox.information(
                self, "Pegar",
                f"Se completaron {pegadas} de {len(filas)} filas{detalle}. "
                f"Las {filas_sin_destino} restantes no se pudieron escribir: "
                "faltan datos requeridos en lo pegado, o esta tabla no crea "
                "filas nuevas al pegar."
            )

        if ultima_celda:
            self._consumir_corte_pendiente(ultima_celda)

    # ── Menú contextual (click derecho) ─────────────────────────────

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return
        item = self.itemFromIndex(index)
        col  = index.column()
        if item not in self.selectedItems():
            self.setCurrentItem(item, col)
        menu = QMenu(self)
        copy_act = menu.addAction(_menu_icon("clipboard"), "Copiar")
        copy_act.setShortcut(QKeySequence.StandardKey.Copy)
        copy_act.triggered.connect(self._copy)
        if col in self._editable_cols_for(item):
            cut_act = menu.addAction(_menu_icon("scissors"), "Cortar")
            cut_act.setShortcut(QKeySequence.StandardKey.Cut)
            cut_act.triggered.connect(self._cut)
            paste_act = menu.addAction(_menu_icon("file-text"), "Pegar")
            paste_act.setShortcut(QKeySequence.StandardKey.Paste)
            paste_act.triggered.connect(self._paste)
        menu.addSeparator()
        sel_act = menu.addAction(_menu_icon("check-square"), "Seleccionar todo")
        sel_act.setShortcut(QKeySequence.StandardKey.SelectAll)
        sel_act.triggered.connect(self.selectAll)
        self._context_menu_actions(menu)
        if not menu.isEmpty():
            menu.exec(event.globalPos())

    def _context_menu_actions(self, menu: QMenu):
        """Hook: subclases agregan acciones extra al menú contextual."""
        pass

    @staticmethod
    def _estilizar_fila_vacia(item):
        """Aplica el estilo estándar (cursiva, gris) a una fila placeholder
        tipo "Nuevo capítulo...", "Nuevo insumo...", "Nuevo renglón..." —
        ver _add_empty_row() en arbol.py, insumos.py, generador.py."""
        for c in range(item.columnCount()):
            f = item.font(c)
            f.setItalic(True)
            item.setFont(c, f)
            item.setForeground(c, QBrush(QColor("#556070")))

    # ── EventBus: conectar / desconectar (declarativo) ──────────────
    #
    # Subclases que necesitan reaccionar a eventos del proyecto abierto
    # declaran EVENTOS_SUSCRITOS como un dict {EventoClass: 'nombre_metodo'}
    # en vez de reimplementar conectar_eventos/desconectar_eventos — ver
    # TablaArbol, TablaInsumos, TablaApuDetalle para ejemplos. Varios
    # eventos pueden apuntar al mismo método si les toca la misma reacción
    # (ver TablaApuDetalle: tres eventos → un solo refresco diferido).

    EVENTOS_SUSCRITOS: dict = {}  # subclases lo sobreescriben

    def conectar_eventos(self, event_bus, api):
        """Suscribe este widget al EventBus del proyecto abierto según
        EVENTOS_SUSCRITOS.

        Debe llamarse una sola vez, justo después de poblar(), con el
        EventBus y el Api vigentes en ese momento (ver paneles.py). Como
        cada apertura de proyecto crea un EventBus nuevo, cada widget se
        reconstruye desde cero en cada apertura y por lo tanto siempre
        queda enganchado al bus correcto.

        IMPORTANTE: quien remueva este widget de una pestaña (removeTab,
        reemplazo por pestaña temporal del sidebar, etc.) DEBE llamar a
        desconectar_eventos() antes — si no, el widget queda "zombi":
        sigue registrado en el bus con su objeto Qt ya destruido, y la
        próxima emisión de evento revienta con
        RuntimeError: libshiboken...already deleted.
        """
        self._api = api
        self._event_bus = event_bus
        for evento_cls, metodo in self.EVENTOS_SUSCRITOS.items():
            event_bus.suscribir(evento_cls, getattr(self, metodo))

    def desconectar_eventos(self):
        """Retira las suscripciones hechas por conectar_eventos().
        Idempotente: no falla si nunca se conectó o ya se desconectó."""
        bus = getattr(self, '_event_bus', None)
        if bus is None:
            return
        for evento_cls, metodo in self.EVENTOS_SUSCRITOS.items():
            bus.desuscribir(evento_cls, getattr(self, metodo))
        self._event_bus = None
