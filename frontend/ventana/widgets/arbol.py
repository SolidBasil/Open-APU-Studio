"""
arbol.py
========
Tabla jerárquica del presupuesto (capítulos + conceptos).

Uso:
    from frontend.widgets.arbol import TablaArbol
"""

from PySide6.QtCore import Qt, Signal, QPoint, QMimeData, QTimer
from PySide6.QtGui import QColor, QBrush, QDrag, QPainter, QFont, QPixmap, QPen, QKeySequence

from PySide6.QtWidgets import QHeaderView, QAbstractItemView, QLineEdit, QCompleter

from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef, ColType, UNIDADES, FORMULA_ROLE, EMPTY_ROLE, COPY_ROLE, _menu_icon, blocked_signals


# ── Icono desde tipo_id (Lucide SVG) ─────────────────────────────

from frontend.ventana.iconos import icono
from frontend.ventana.colores import ACCENT, SUCCESS, WARNING, ERROR, PURPURA
from frontend.ventana.tipos_insumo import ICONO_SVG as _ICONOS_TIPO_SVG, COLOR as _COLOR_TIPO


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
EDITABLE    = frozenset()               # editable_cols_fn define edición por fila
_AGRUP_COLS = {0, 1, 4, 8}

# Catálogo para el esquema de favoritas + "Personalizar columnas…" (ver
# widgets/base.py PersonalizarColumnasDialog). idx debe coincidir con la
# posición en COLUMNAS de arriba. _VISIBLE ya no se lista a mano: se
# deriva del catálogo (visible_default) en __init__.
COLUMNAS_CATALOGO = [
    ColumnaDef(0,  "Estructura",  "Identificación", tipo=ColType.TEXT,  favorita_default=True,  visible_default=True,  imprimible_default=False),
    ColumnaDef(1,  "Nivel",       "Identificación", tipo=ColType.TEXT,  favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(2,  "Tipo",        "Identificación", tipo=ColType.CHOICE, choices=("capítulo", "concepto"),  favorita_default=True,  visible_default=False, imprimible_default=False),
    ColumnaDef(3,  "Clave",       "Identificación", tipo=ColType.TEXT,  favorita_default=False, visible_default=False, imprimible_default=False),
    ColumnaDef(4,  "Descripción", "Identificación", tipo=ColType.TEXT,  favorita_default=True,  visible_default=True,  imprimible_default=True),

    ColumnaDef(5,  "Unidad",      "Cálculo", tipo=ColType.CHOICE, choices=UNIDADES,  favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(6,  "Cant",        "Cálculo", tipo=ColType.NUMERIC,  favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(7,  "P.U.",        "Cálculo", tipo=ColType.NUMERIC,  favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(8,  "Total",       "Cálculo", tipo=ColType.NUMERIC,  favorita_default=True,  visible_default=True,  imprimible_default=True),
    ColumnaDef(13, "Orden",       "Cálculo", tipo=ColType.NUMERIC,  favorita_default=False, visible_default=False, imprimible_default=False),
    ColumnaDef(14, "Fórmula",     "Cálculo", tipo=ColType.TEXT,     favorita_default=False, visible_default=False, imprimible_default=False),

    ColumnaDef(9,  "Estado",      "Seguimiento", tipo=ColType.CHOICE, choices=("Sin revisar", "En revisión", "Verificado", "Cuestionado"),  favorita_default=True,  visible_default=True,  imprimible_default=False),
    ColumnaDef(10, "Notas",       "Seguimiento", tipo=ColType.TEXT,   favorita_default=True,  visible_default=True,  imprimible_default=False),

    ColumnaDef(11, "Creado",      "Auditoría", tipo=ColType.DATE,  favorita_default=False, visible_default=False, imprimible_default=False),
    ColumnaDef(12, "Modificado",  "Auditoría", tipo=ColType.DATE,  favorita_default=False, visible_default=False, imprimible_default=False),
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
    "":         {4},         # fila vacía final: Descripción = buscar insumo
    "capitulo": {4, 10},      # Descripción, Notas
    "concepto": {3, 6, 10},   # Clave, Cant, Notas
}


def _editable_cols_arbol(item) -> set[int]:
    """Columnas editables para una fila del árbol de presupuesto, según su tipo."""
    tipo = item.data(0, TIPO_ROLE)
    return _EDITABLE_POR_TIPO.get(tipo, set())

# ── Colores por nivel jerárquico ─────────────────────────────────

COLORES_NIVEL = [
    PURPURA,    # 0: púrpura  — capítulo raíz
    ACCENT,     # 1: azul
    "#5E9CA0",  # 2: teal
    WARNING,    # 3: beige cálido
    SUCCESS,    # 4: verde
    ERROR,      # 5+: vino
]

from backend.database.repos.presupuesto import ESTADO_NOMBRE, ESTADO_COLOR
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
    abrir_generador = Signal(int)  # concepto_id
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
        "abrir_generador":     "_on_abrir_generador",
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
                          editable_cols_fn=_editable_cols_arbol,
                          paste_col_fn={3: self._resolver_insumo_pegado,
                                        4: self._resolver_insumo_pegado},
                          column_editors={4: self._crear_editor_descripcion})
        # Estructura (0) y Nivel (1) se angostaron respecto al default previo
        # (160/160): Estructura solo dibuja líneas de árbol + un ícono de
        # 20px (ver drawBranches/setIcon(0,...) más abajo) — no lleva texto
        # propio, así que 160px era más de lo que su contenido necesita
        # incluso con jerarquías de 4-5 niveles (indentación 24px/nivel, ver
        # base.py setIndentation). Nivel muestra el WBS ("1.1.1.16"), que
        # rara vez pasa de 8-10 caracteres. El ancho liberado (50px) se le
        # suma a Descripción, la columna que más lectura recibe y la que se
        # veía truncada en el uso real (ver captura de pantalla del ago 2026).
        anchos = [110, 130, 140, 180, 670, 110, 130, 180, 180, 140, 200, 260, 260]
        anchos += [140, 320]  # Orden, Fórmula
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate(anchos)
        })
        # IMPORTANTE: este máximo debe quedar por encima de TODOS los
        # anchos de `anchos` de arriba (especialmente Descripción, la
        # columna más ancha). setMaximumSectionSize() recorta de inmediato
        # cualquier sección ya seteada que lo exceda — antes este valor
        # (400) era menor que el ancho por defecto de Descripción (500),
        # así que la columna nunca llegaba a mostrarse con el ancho que el
        # propio código pedía. También limita cuánto puede agrandarla el
        # usuario a mano arrastrando el borde.
        self.header().setMaximumSectionSize(900)
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

        # ── Drag and drop al estilo OPUS ──────────────────────────
        # Arrastrar la selección (uno o varios renglones, capítulos o
        # conceptos) y soltarla sobre otro capítulo o entre dos renglones
        # los mueve ahí. Con Ctrl presionado, los copia en vez de
        # moverlos (ver dropEvent()). Todo el manejo es propio — no se
        # delega en el modelo interno de Qt (setDragDropMode solo se usa
        # para obtener el indicador visual de dónde va a caer) porque la
        # operación real vive en la base de datos (padre_id/orden), no en
        # los QTreeWidgetItem.
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._drop_objetivo = None  # (item, 'arriba'|'dentro'|'abajo') — ver paintEvent

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

    def _crear_editor_descripcion(self, parent):
        """Editor de la columna Descripción (4): QLineEdit con autocompletado
        contra las descripciones del catálogo de insumos.

        Se usa tanto para capítulos (texto libre — el completer es solo una
        sugerencia, escribir cualquier cosa nueva sigue funcionando igual)
        como para la fila vacía final (donde escribir el nombre de un
        insumo existente crea un concepto nuevo ligado a él — ver
        _on_fila_vacia_editada en mixins/apu.py). No se usa para conceptos
        reales: ahí Descripción no es editable (ver _EDITABLE_POR_TIPO),
        se re-liga por Clave/pegado (ver _resolver_insumo_pegado).
        """
        editor = QLineEdit(parent)
        editor.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        descripciones = []
        api = getattr(self, "_api", None)
        if api is not None:
            try:
                descripciones = sorted({
                    i["descripcion"] for i in api.insumos() if i.get("descripcion")
                })
            except Exception:
                descripciones = []
        completer = QCompleter(descripciones, editor)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        editor.setCompleter(completer)
        QTimer.singleShot(0, editor.selectAll)
        return editor

    def _al_click_fila_vacia(self):
        """No-op: con la fila vacía editable (ver _add_empty_row), un clic
        simple solo selecciona la celda como en cualquier tabla — ya no
        abre un diálogo modal aparte. Escribir en Descripción es lo que
        crea el concepto (ver _on_fila_vacia_editada en mixins/apu.py).
        Agregar un capítulo sigue disponible por su propio botón/atajo
        ("Agregar agrupador"), sin pasar por esta fila."""
        pass

    def _on_item_clicked(self, item, column):
        """Fila placeholder → _al_click_fila_vacia. El estado (col 9) ya NO
        cicla con un click: misclicks provocaban cambios de revisión falsos.
        El ciclo va en DOBLE click (ver mouseDoubleClickEvent) y el estado
        exacto se elige desde el menú contextual (_agregar_submenu_estado)."""
        if item.data(0, EMPTY_ROLE):
            self._al_click_fila_vacia()

    def _ciclar_estado(self, item):
        """Cicla 0→1→2→3→0 en columna Estado."""
        nodo_id = item.data(0, ID_ROLE)
        if nodo_id is None:
            return
        estado = 0
        txt = item.text(9)
        for k, v in ESTADO_NOMBRE.items():
            if v == txt:
                estado = k
                break
        nuevo = (estado + 1) % 4
        self._cambiar_estado(nodo_id, nuevo)

    # ── Drag and drop al estilo OPUS ─────────────────────────────
    # Arrastrar renglones (capítulos y/o conceptos, selección múltiple
    # incluida) y soltarlos sobre otro capítulo, o entre dos renglones
    # para controlar la posición exacta. Mueve por default; con Ctrl
    # presionado, copia (duplica) en vez de mover — ver
    # ApuMixin._on_drop_arbol (mixins/navegacion.py), que hace el trabajo
    # real contra la base de datos.

    def _fila_destino_valida(self, item) -> bool:
        """True si item puede recibir un drop: cualquier renglón real
        (capítulo o concepto), pero no la fila vacía placeholder ni None."""
        return item is not None and item is not getattr(self, '_empty_row_item', None)

    def startDrag(self, supportedActions):
        """Reemplaza el "fantasma" de arrastre por defecto de Qt — que
        renderiza los renglones seleccionados tal cual y tapa buena parte
        de la vista debajo del mouse — por un ícono compacto (portapapeles
        con un contador si son varios), igual que arrastrar archivos en un
        explorador de archivos. El destino del drop (dropEvent) no
        depende de este ícono para nada, solo de la selección real."""
        if not self._puede_iniciar_drag():
            return
        arrastrados = [it for it in self.selectedItems() if self._fila_destino_valida(it)]
        if not arrastrados:
            return
        mime = QMimeData()
        mime.setText(f"{len(arrastrados)} elemento(s) de Presupuesto")
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self._pixmap_arrastre(len(arrastrados)))
        drag.setHotSpot(QPoint(12, 12))
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction,
                  Qt.DropAction.MoveAction)

    def _pixmap_arrastre(self, cantidad: int) -> QPixmap:
        """Ícono de 40x40 para el arrastre: portapapeles, más un contador
        en circulito si son varios renglones. Se ve igual muevas o
        copies — el sistema ya distingue con el cursor (+) al copiar."""
        size = 40
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        icono("clipboard", size=28).paint(painter, 3, 3, 28, 28)
        if cantidad > 1:
            radio = 11
            centro = QPoint(size - radio - 1, size - radio - 1)
            painter.setBrush(QColor(ACCENT))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(centro, radio, radio)
            fuente = QFont()
            fuente.setBold(True)
            fuente.setPointSize(9)
            painter.setFont(fuente)
            painter.setPen(QColor("white"))
            texto = str(cantidad) if cantidad < 100 else "99+"
            painter.drawText(centro.x() - radio, centro.y() - radio,
                              radio * 2, radio * 2,
                              Qt.AlignmentFlag.AlignCenter, texto)
        painter.end()
        return pix

    def dragEnterEvent(self, event):
        """Acepta el arrastre si viene de este mismo árbol. Sin este
        override, el dragEnterEvent por defecto de Qt rechaza el
        QMimeData personalizado que usamos para el ícono compacto del
        arrastre (ver startDrag) — no coincide con el formato interno que
        Qt espera para mover filas — y eso deja el cursor en "prohibido"
        durante todo el arrastre, sin importar dónde sueltes."""
        if event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _calcular_posicion_drop(self, item, y_evento: int) -> str:
        """Traduce la posición vertical del cursor dentro del renglón
        'item' a 'arriba' / 'dentro' / 'abajo' (tercios de su alto) — el
        mismo criterio para el indicador visual (dragMoveEvent/paintEvent)
        y para la acción real (dropEvent), así lo que se ve siempre
        coincide con lo que pasa al soltar."""
        rect = self.visualItemRect(item)
        if rect.height() <= 0:
            return "abajo"
        tercio = rect.height() / 3
        if y_evento < rect.top() + tercio:
            return "arriba"
        if y_evento > rect.bottom() - tercio:
            return "abajo"
        return "dentro"

    def dragMoveEvent(self, event):
        """Actualiza el objetivo del drop para el indicador visual propio
        (ver paintEvent) y decide si se puede soltar ahí. No se delega en
        el mecanismo de indicador de Qt (dropIndicatorShown/
        dropIndicatorPosition): como dragEnterEvent no llama a super() —
        Qt nunca entra en su estado interno "arrastrando" — su indicador
        nunca se dibuja aunque se acepte el evento. Pintamos el nuestro en
        su lugar, siempre visible independientemente de ese estado."""
        item = self.itemAt(event.position().toPoint())
        if event.source() is not self or not self._fila_destino_valida(item):
            self._drop_objetivo = None
            self.viewport().update()
            event.ignore()
            return
        posicion = self._calcular_posicion_drop(item, event.position().toPoint().y())
        if posicion == "dentro" and item.data(0, TIPO_ROLE) != "capitulo":
            # Un concepto no puede recibir hijos — si el cursor cae en el
            # tercio central de un concepto, tratarlo como "abajo" (entre
            # renglones) en vez de rechazar de plano.
            posicion = "abajo"
        self._drop_objetivo = (item, posicion)
        self.viewport().update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drop_objetivo = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event):
        """Dibuja, encima del árbol normal, el indicador de a dónde va a
        caer el drag en curso: una línea entre dos renglones (con un
        circulito al inicio, igual que Word/Excel), o un marco redondeado
        alrededor de un capítulo cuando el drop cae "dentro" de él."""
        super().paintEvent(event)
        objetivo = getattr(self, '_drop_objetivo', None)
        if objetivo is None:
            return
        item, posicion = objetivo
        rect = self.visualItemRect(item)
        if not rect.isValid():
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(ACCENT)
        if posicion == "dentro":
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
        else:
            y = rect.top() if posicion == "arriba" else rect.bottom()
            pen = QPen(color, 3)
            painter.setPen(pen)
            painter.drawLine(rect.left(), y, self.viewport().width(), y)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(rect.left(), y), 3, 3)
        painter.end()

    def dropEvent(self, event):
        """Calcula (nuevo_padre_id, antes_de_id) a partir de la misma
        posición ('arriba'/'dentro'/'abajo', ver _calcular_posicion_drop)
        que muestra el indicador visual, y delega el cambio real en la
        ventana (self.window()._on_drop_arbol) — este widget no toca la
        base de datos directamente, igual que el resto de operaciones de
        mover.

        No se llama a super().dropEvent(): el modelo interno de Qt no
        sabe nada de padre_id/orden en la base de datos, así que dejar
        que reordene los QTreeWidgetItem por su cuenta dejaría la vista
        desincronizada hasta el próximo refresco. En vez de eso, todo el
        refresco visual llega solo, vía el evento ProyectoRecalculado que
        emite _on_drop_arbol al terminar (mismo mecanismo que Subir/Bajar/
        Izquierda/Derecha)."""
        self._drop_objetivo = None
        self.viewport().update()

        item_destino = self.itemAt(event.position().toPoint())
        if event.source() is not self or not self._fila_destino_valida(item_destino):
            event.ignore()
            return

        arrastrados = [it for it in self.selectedItems() if self._fila_destino_valida(it)]
        if not arrastrados:
            ids_arrastrados = list(getattr(self, '_drag_sel_ids', []))
        else:
            # selectedItems() de Qt trae los renglones en el orden en que se
            # seleccionaron, no en el orden visual — si el usuario seleccionó
            # de abajo hacia arriba (ej. Shift+clic empezando por el último),
            # el bloque quedaba insertado al revés. Se reordena por posición
            # en pantalla antes de usarlo.
            arrastrados.sort(key=lambda it: self.visualItemRect(it).top())
            ids_arrastrados = [it.data(0, ID_ROLE) for it in arrastrados]
        ids_arrastrados = [nid for nid in ids_arrastrados if nid is not None]
        if not ids_arrastrados:
            event.ignore()
            return
        if arrastrados and item_destino in arrastrados:
            event.ignore()
            return

        posicion = self._calcular_posicion_drop(item_destino, event.position().toPoint().y())
        if posicion == "dentro" and item_destino.data(0, TIPO_ROLE) != "capitulo":
            posicion = "abajo"

        if posicion == "dentro":
            nuevo_padre_id = item_destino.data(0, ID_ROLE)
            antes_de_id = None  # al final de los hijos de ese capítulo
        else:
            padre_item = item_destino.parent()
            nuevo_padre_id = padre_item.data(0, ID_ROLE) if padre_item is not None else None
            hermanos_widget = (
                [padre_item.child(i) for i in range(padre_item.childCount())]
                if padre_item is not None else
                [self.topLevelItem(i) for i in range(self.topLevelItemCount())]
            )
            idx = hermanos_widget.index(item_destino)
            if posicion == "arriba":
                antes_de_id = item_destino.data(0, ID_ROLE)
            else:  # abajo
                siguiente = hermanos_widget[idx + 1] if idx + 1 < len(hermanos_widget) else None
                antes_de_id = siguiente.data(0, ID_ROLE) if siguiente is not None else None

        copiar = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        ventana = self.window()
        handler = getattr(ventana, '_on_drop_arbol', None)
        if handler is None:
            event.ignore()
            return
        ok = handler(ids_arrastrados, nuevo_padre_id, antes_de_id, copiar)
        if ok:
            event.acceptProposedAction()
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is None:
            super().mouseDoubleClickEvent(event)
            return
        col = self.columnAt(int(event.position().toPoint().x()))
        nodo_id = item.data(0, ID_ROLE)
        if col == 9 and nodo_id:
            # Doble click en Estado → cicla semáforo (deliberado; el click
            # simple provocaba cambios falsos por misclick).
            self._ciclar_estado(item)
            return
        if col == 6 and item.data(0, TIPO_ROLE) == "concepto" and nodo_id:
            gens = self._api.generadores_por_concepto(nodo_id) if self._api else []
            if gens:
                self.itemDoubleClicked.emit(item, col)
                return
        super().mouseDoubleClickEvent(event)

    def _resolver_insumo_pegado(self, item, col: int, valor: str):
        """paste_col_fn compartido de Clave (3) y Descripción (4) para
        conceptos: ambas ligan al mismo insumo, así que cualquiera de las
        dos acepta el valor pegado y resuelve al insumo correcto — no solo
        Clave, que está oculta por defecto. Esto es lo que hace falta para
        que copiar una fila normal del Presupuesto (o del Catálogo de
        Insumos, con Descripción visible) y pegarla relíe el concepto al
        insumo correcto, en vez de no hacer nada porque la columna que sí
        resolvía estaba oculta.

        Unidad (5) NO participa: a diferencia de Clave/Descripción, el
        texto de una unidad ("m3", "pza") no identifica un insumo — lo
        comparten decenas de insumos distintos. Una vez que el concepto
        se re-liga vía Clave o Descripción, Unidad se refresca sola desde
        el insumo correcto (ProyectoRecalculado repuebla el árbol).

        Capítulos: Descripción (4) sigue siendo texto libre normal, sin
        pasar por ningún insumo — Clave nunca es editable ahí, así que ni
        siquiera se intenta (ver _paste_cols_for).

        Reconoce el valor pegado, en orden:
          1. Un id de insumo puro (dígitos) — pegado interno vía COPY_ROLE
             de la columna Clave (ver copy_selection/add_registro).
          2. El hash de deduplicación de un insumo tal cual (pegado desde
             la columna Hash del Catálogo de Insumos).
          3. El propio texto hasheado con el mismo algoritmo que usa el
             catálogo para deduplicar — resuelve el caso más común: pegar
             la Descripción de una fila copiada, sin exponer ninguna
             columna oculta.

        Si nada resuelve, no se toca la celda: nunca se inventa un insumo
        nuevo ni se deja el concepto con datos huérfanos."""
        tipo = item.data(0, TIPO_ROLE)
        if tipo != "concepto":
            if tipo == "capitulo" and col == 4:
                return (valor, None)  # Descripción de capítulo: texto libre
            return None
        if col not in (3, 4):
            return None
        v = (valor or "").strip()
        if not v:
            return None
        api = getattr(self, '_api', None)
        if api is None:
            return None
        ins = None
        if v.isdigit():
            ins = api.campo_valor("insumos", "id", int(v))
        if ins is None:
            ins = api.insumo_por_hash(v)
        if ins is None:
            from backend.database.core import generar_hash
            ins = api.insumo_por_hash(generar_hash(v))
        if ins is None:
            return None
        insumo_id = ins.get("id")
        if col == 3:
            return (ins.get("clave_opus") or v, insumo_id)
        return (ins.get("descripcion") or "", insumo_id)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F2:
            item = self.currentItem()
            col = self.currentColumn()
            if item and col in {3, 4, 5}:
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
        menu.addSeparator()

        act = menu.addAction(_menu_icon("square-plus"), "Agregar agrupador")
        act.setShortcut(QKeySequence("Ctrl+Insert"))
        act.triggered.connect(self.agregar_agrupador)

        act = menu.addAction(_menu_icon("plus"), "Agregar concepto")
        act.setShortcut(QKeySequence("Insert"))
        act.triggered.connect(self.agregar_concepto)

        if self.selectedItems():
            act = menu.addAction(_menu_icon("x"), "Eliminar")
            act.setShortcut(QKeySequence("Delete"))
            act.triggered.connect(self.eliminar_seleccion)

        if len(self.selectedItems()) != 1:
            return
        item = self.currentItem()
        if not item:
            return
        nodo_id = item.data(0, ID_ROLE)
        if nodo_id:
            self._agregar_submenu_estado(menu, nodo_id, item.data(0, TIPO_ROLE))

        tipo = item.data(0, TIPO_ROLE)
        if tipo != "concepto":
            return
        insumo_id = item.data(0, INSUMO_ROLE)
        if insumo_id:
            act = menu.addAction(_menu_icon("search"), "Rastrear uso")
            act.triggered.connect(lambda: self.rastrear_insumo.emit(insumo_id))
            act = menu.addAction(_menu_icon("edit"), "Modificar insumo")
            act.setShortcut(QKeySequence("F2"))
            act.triggered.connect(lambda: self.modificar_insumo.emit(insumo_id))
        if nodo_id:
            act = menu.addAction(_menu_icon("refresh-cw"), "Cambiar insumo")
            act.setShortcut(QKeySequence("F5"))
            act.triggered.connect(lambda: self.cambiar_insumo.emit(nodo_id))
            act = menu.addAction(_menu_icon("link"), "Desglozar")
            act.triggered.connect(lambda: self.desglozar_nodo.emit(nodo_id))
        if nodo_id and tipo == "concepto":
            act = menu.addAction(_menu_icon("calculator"), "Abrir generador")
            act.triggered.connect(lambda: self.abrir_generador.emit(nodo_id))

    def _agregar_submenu_estado(self, menu, nodo_id, tipo):
        """Submenú 'Estado de revisión' — semáforo de seguimiento (ver
        ESTADO_NOMBRE/ESTADO_COLOR en repos/presupuesto.py). Disponible
        tanto para capítulos como para conceptos."""
        etiqueta = "capítulo" if tipo == "capitulo" else "concepto"
        sub = menu.addMenu(_menu_icon("flag"), "Estado de revisión")
        for valor, nombre in ESTADO_NOMBRE.items():
            act = sub.addAction(self._crear_icono_circulo(ESTADO_COLOR[valor], 14), nombre)
            act.setToolTip(f"Marcar este {etiqueta} como \"{nombre}\"")
            act.triggered.connect(lambda checked=False, v=valor: self._cambiar_estado(nodo_id, v))

    def _cambiar_estado(self, nodo_id, nuevo_estado):
        """Actualiza el campo 'estado' de un nodo (capítulo o concepto).
        El refresco visual del semáforo llega vía ConceptoActualizado —
        ver _on_concepto_actualizado()."""
        if self._api:
            self._api.concepto_actualizar(nodo_id, estado=nuevo_estado)

    # ── Construcción de celdas desde dict ─────────────────────────

    @staticmethod
    def _crear_icono_circulo(color_hex: str, size: int = 12):
        from PySide6.QtGui import QPixmap, QPainter, QBrush, QColor, QIcon
        from PySide6.QtCore import Qt
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(color_hex)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, size - 2, size - 2)
        p.end()
        return QIcon(pixmap)

    def _set_icono_estado(self, item, n):
        """Ícono de semáforo en la columna Estado (9), según n['estado']:
        0=Sin revisar (gris), 1=En revisión (naranja), 2=Verificado (verde),
        3=Cuestionado (rojo). Ver ESTADO_COLOR en repos/presupuesto.py."""
        estado = n.get("estado") or 0
        item.setIcon(9, self._crear_icono_circulo(ESTADO_COLOR.get(estado, ESTADO_COLOR[0])))

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
        self._set_icono_estado(item, n)
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
        item.setData(3, COPY_ROLE, str(n.get("insumo_id") or ""))
        item.setData(6, FORMULA_ROLE, n.get("formula") or "")
        tid = n.get("tipo_id")
        item.setIcon(0, icono(_ICONOS_TIPO_SVG.get(tid, "file-text"), 20, _COLOR_TIPO.get(tid)))
        self._set_icono_estado(item, n)
        return item

    # ── Poblado del árbol ─────────────────────────────────────────

    def poblar(self, nodos_raiz: list[dict]):
        """Puebla el árbol completo desde lista de nodos raíz devuelta por NodoRepo.arbol()."""
        self.clear()
        self._poblar_nodos(nodos_raiz, None)
        self._add_empty_row()

    def _add_empty_row(self):
        """Fila visual vacía al final del árbol — no existe en BD.

        Descripción (col 4) es editable: escribir el nombre de un insumo
        del catálogo crea un concepto nuevo ligado a él (con autocompletado
        — ver _crear_editor_descripcion); si lo escrito no matchea ningún
        insumo, se abre el selector ya con ese texto como búsqueda inicial
        en vez de un diálogo en blanco (ver _on_fila_vacia_editada en
        mixins/apu.py). Agregar un capítulo tiene su propio botón/atajo
        ("Agregar agrupador"), no pasa por esta fila.
        """
        item = self.add_row(
            ["", "", "", "", "",
             "", "", "", "", "", "", "", "", "", ""],
            editable=True,
        )
        item.setData(0, EMPTY_ROLE, True)
        item.setData(0, ID_ROLE, None)
        item.setData(0, TIPO_ROLE, "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled
                                    & ~Qt.ItemFlag.ItemIsDropEnabled)
        self._estilizar_fila_vacia(item)
        item.setToolTip(4, "Escribe el nombre de un insumo del catálogo "
                            "para agregarlo como concepto nuevo")
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
            with blocked_signals(self):
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
                if "estado" in evento.cambios:
                    item.setText(9, ESTADO_NOMBRE.get(registro.get("estado"), ""))
                    self._set_icono_estado(item, registro)
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
            win = self.window()
            texto_busqueda = win._search_input.text() if (
                win is not None and hasattr(win, '_search_input')
            ) else None

            def _refrescar_seguro():
                try:
                    with blocked_signals(self):
                        nodos = self._api.presupuesto_arbol(extra=self._extra)
                        self.poblar(nodos)
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
                        self.filter_rows(texto_busqueda)
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
