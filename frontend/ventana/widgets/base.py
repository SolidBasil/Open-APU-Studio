"""
base.py
=======
Widget base reutilizable: TreeTableWidget con conectores visuales,
filtrado, edición y clipboard.

Uso:
    from frontend.widgets.base import TreeTableWidget
"""

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
    QHeaderView, QApplication, QStyledItemDelegate, QMenu,
)
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen

import re
from backend.database.db import Config


# ── Expresiones regulares ──────────────────────────────────────────

SISTEMA_PREFIJOS = re.compile(rf"^[{re.escape('▶🧱👷🔧🚜⚙️📄📚')}]\s?")


# ── Constantes de conectores ──────────────────────────────────────

LINE_COLOR = QColor("#5E92B8")
LINE_WIDTH  = 1.5


# ── Utilidades de texto ───────────────────────────────────────────

def _strip_icons(text: str) -> str:
    """Quita prefijos del sistema (▶ y emojis de tipo) sin afectar datos del usuario.
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
        info.append({
            "has_below":    row < total - 1,
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

    def __init__(self, parent, editable_cols, editable_cols_fn=None):
        super().__init__(parent)
        self._editable_cols = editable_cols
        self._editable_cols_fn = editable_cols_fn

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

    def createEditor(self, parent, option, index):
        """Crea editor solo si la celda es editable para ese tipo de nodo."""
        if self._es_editable(index):
            editor = super().createEditor(parent, option, index)
            if editor:
                # Seleccionar todo el texto al abrir el editor (como Excel)
                from PySide6.QtWidgets import QLineEdit
                if isinstance(editor, QLineEdit):
                    editor.selectAll()
            return editor
        return None

    def setEditorData(self, editor, index):
        """Limpia el formato ($, comas) para editar el valor numérico en bruto."""
        from PySide6.QtWidgets import QLineEdit
        if isinstance(editor, QLineEdit):
            texto = index.data(Qt.ItemDataRole.DisplayRole) or ""
            # Quitar prefijo $ y separadores de miles para editar número limpio
            texto = texto.replace("$", "").replace(",", "").strip()
            editor.setText(texto)
        else:
            super().setEditorData(editor, index)

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
        """Intercepta Enter y Tab para confirmar y mover foco."""
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commitAndMove(editor, QStyledItemDelegate.EndEditHint.EditNextItem)
                return True
            if key == Qt.Key.Key_Tab:
                self.commitAndMove(editor, QStyledItemDelegate.EndEditHint.EditNextItem)
                return True
            if key == Qt.Key.Key_Backtab:
                self.commitAndMove(editor, QStyledItemDelegate.EndEditHint.EditPreviousItem)
                return True
        return super().eventFilter(editor, event)


# ── Widget tabla base ─────────────────────────────────────────────

class TreeTableWidget(QTreeWidget):

    _HEADER_KEY = None  # ponytail: subclases definen su clave de persistencia

    # ── Constructor ───────────────────────────────────────────────

    def __init__(self, columns, editable_cols=frozenset(), flat=False,
                 line_color=None, parent=None, editable_cols_fn=None):
        """Inicializa QTreeWidget con columnas, editabilidad, modo plano/jerárquico y cabecera.

        editable_cols_fn: función opcional `item -> set[int]` para tablas donde
        las columnas editables dependen del tipo de fila (ver arbol.py). Si no
        se pasa, editable_cols aplica igual a todas las filas.
        """
        super().__init__(parent)
        self._flat          = flat
        self._line_color    = line_color or LINE_COLOR
        self._editable_cols = editable_cols
        self._editable_cols_fn = editable_cols_fn
        self._search_cols: set[int] | None = None  # None = buscar en todas

        self.setColumnCount(len(columns))
        self.setHeaderLabels(columns)
        self.setAlternatingRowColors(True)
        self.setAnimated(True)
        self.setIndentation(24 if not flat else 0)
        self.setRootIsDecorated(not flat)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setMouseTracking(True)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.SelectedClicked   # clic en celda ya seleccionada
            | QAbstractItemView.EditTrigger.EditKeyPressed  # F2
            | QAbstractItemView.EditTrigger.AnyKeyPressed   # cualquier tecla alfanumérica
            | QAbstractItemView.EditTrigger.DoubleClicked   # doble clic
        )
        self.setItemDelegate(_Delegate(self, editable_cols, editable_cols_fn))

        h = self.header()
        h.setStretchLastSection(False)
        h.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h.customContextMenuRequested.connect(self._header_context_menu)
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
        h = self.header()
        # Primero todo Interactive para que resizeSection funcione
        for c in range(self.columnCount()):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
        # Aplicar anchos
        for c, (mode, width) in modes.items():
            if width is not None:
                h.resizeSection(c, width)
        # Aplicar modos finales — Stretch se deja como Interactive
        # para que el usuario pueda redimensionar cualquier columna
        for c, (mode, width) in modes.items():
            if mode == QHeaderView.ResizeMode.Stretch:
                # Stretch no permite drag — usamos Interactive con ancho ya seteado
                h.setSectionResizeMode(c, QHeaderView.ResizeMode.Interactive)
            else:
                h.setSectionResizeMode(c, mode)

    def showEvent(self, event):
        """Re-aplica modos de columna al mostrar (Qt ignora resizeSection antes de ser visible)."""
        super().showEvent(event)
        self._apply_column_modes()

    # ── Persistencia de cabecera ──────────────────────────────────

    def _save_header_state(self):
        """Guarda estado del header en config.json como base64."""
        if not self._HEADER_KEY:
            return
        raw = self.header().saveState()
        Config.set(self._HEADER_KEY, raw.toBase64().data().decode("ascii"))

    def _restore_header_state(self):
        """Restaura estado del header desde config.json si existe."""
        if not self._HEADER_KEY:
            return
        saved = Config.get(self._HEADER_KEY)
        if saved:
            self.header().restoreState(QByteArray.fromBase64(saved.encode("ascii")))

    # ── Menú contextual de cabecera ───────────────────────────────

    def _header_context_menu(self, pos):
        """Menú contextual sobre cabecera para mostrar/ocultar columnas."""
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

    # ── Inserción de filas ────────────────────────────────────────

    def add_row(self, data, parent=None, editable=True):
        """Agrega fila al árbol con valores de data; editable=False la bloquea."""
        parent = parent or self
        item   = QTreeWidgetItem(parent, data)
        if editable:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    # ── Dibujado de ramas ─────────────────────────────────────────

    def drawBranches(self, painter, rect, index):
        """Dibuja conectores jerárquicos entre nodos si el modo no es plano."""
        super().drawBranches(painter, rect, index)
        if not self._flat:
            draw_tree_connectors(self, painter, rect, index, self._line_color)

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
        cols = self._search_cols if self._search_cols is not None else set(range(self.columnCount()))
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
        """Captura Ctrl+C (copiar) y Ctrl+V (pegar); delega lo demás al comportamiento nativo."""
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self._paste()
        else:
            super().keyPressEvent(event)

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
        """Copia selección al portapapeles como TSV; si no hay selección copia celda actual."""
        if self.copy_selection():
            return
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0:
            return
        QApplication.clipboard().setText(_strip_icons(item.text(col)))

    def _cut(self):
        """Corta: copia celda al portapapeles y la limpia."""
        self._copy()
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0:
            return
        item.setText(col, "")

    def _paste(self):
        """Pega texto del portapapeles en la celda actual si la columna es editable."""
        text = QApplication.clipboard().text()
        if not text:
            return
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0 or col not in self._editable_cols:
            return
        item.setText(col, text.strip().split("\n")[0].strip())

    # ── Menú contextual (click derecho) ─────────────────────────────

    def contextMenuEvent(self, event):
        item = self.currentItem()
        col  = self.currentColumn()
        if not item or col < 0:
            return
        menu = QMenu(self)
        menu.addAction("Copiar", self._copy)
        if col in self._editable_cols:
            menu.addAction("Cortar", self._cut)
            menu.addAction("Pegar", self._paste)
        self._context_menu_actions(menu)
        if not menu.isEmpty():
            menu.exec(event.globalPos())

    def _context_menu_actions(self, menu: QMenu):
        """Hook: subclases agregan acciones extra al menú contextual."""
        pass
