"""
visor.py
========
Visor CAD basado en QGraphicsView/QGraphicsScene.

Rendering delegado a ezdxf.addons.drawing (PyQtBackend) — resuelve
bloques anidados, rotaciones, arcos, elipses, texto y hatches correctamente.
Soporta pan/zoom, visibilidad por capas, snap y herramientas de medición.

Notas de diseño (por qué está hecho así, para no reintroducir bugs ya
encontrados):

- NO se usa QOpenGLWidget como viewport. QGraphicsView + QOpenGLWidget
  tiene problemas de parpadeo/tearing bien documentados (el compositing
  por FBO de QOpenGLWidget no siempre coincide con el ciclo de update
  regions de QGraphicsView). Para dibujo 2D vectorial como este, el
  viewport raster por defecto es más que suficiente en rendimiento y
  evita esa clase entera de bugs.
- NO se usa QGraphicsView.DontSavePainterState. Los items de PyQtBackend
  (_CosmeticPath/_CosmeticPolygon, usados para hatches/rellenos)
  modifican el transform de su brush dentro de paint() basándose en el
  zoom actual, sin restaurarlo explícitamente — dependen de que Qt
  restaure el estado del painter entre item e item. Con ese flag activo,
  el estado de un item se puede filtrar al siguiente, y como depende del
  zoom, el síntoma es justo "algo se ve mal / desaparece según el zoom".
- itemIndexMethod = NoIndex: el sceneRect se ajusta a mano después de
  poblar la escena (padding de 25%), lo que puede desincronizar el árbol
  BSP por defecto de QGraphicsScene y hacer que items cerca del borde
  se consideren "fuera de vista" incorrectamente.
- El zoom está acotado (min/max) para no acumular una escala tan extrema
  que la transformación pierda precisión numérica en punto flotante.
"""

from __future__ import annotations

import math
import logging

from PySide6.QtCore import Qt, QPointF, QRectF, QPoint, Signal
from PySide6.QtGui import (
    QPen, QColor, QBrush, QPainter, QWheelEvent, QMouseEvent,
    QTransform, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsPolygonItem,
    QLabel,
)

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.pyqt import (
    PyQtBackend, CorrespondingDXFEntity, CorrespondingDXFParentStack,
)

from backend.cad.lector_dxf import ACI_COLORS

from .ortho import snap_to_ortho
from .medicion import Pt2, calculate_distance, calculate_area, calculate_perimeter
from frontend.ventana.widgets.generador import medidas_efectivas


log = logging.getLogger(__name__)


# ── Herramientas de dibujo ────────────────────────────────────────

class CadTool:
    SELECT = "select"
    LINE = "line"
    POLYLINE = "polyline"
    POLYGON = "polygon"
    POINT = "point"
    COUNT = "count"
    CALIBRATE = "calibrate"


# Límites de zoom (escala absoluta de la transformación). Suficientemente
# amplio para inspeccionar detalles finos o alejarse a un plano completo,
# pero acotado para no degradar la precisión numérica de QTransform en
# zooms extremos (causa real, documentada en Qt, de glitches de render
# — incluyendo items que "desaparecen" — a escalas absurdas).
_MIN_SCALE = 1e-4
_MAX_SCALE = 1e5


# ── Widget del viewer ─────────────────────────────────────────────

class VisorCadWidget(QGraphicsView):
    """Visor CAD con pan, zoom, capas y herramientas de medición.

    Rendering delegado a ezdxf.addons.drawing (PyQtBackend) — resuelve
    expansión de bloques, rotación de arcos, alineación de texto y
    hatches correctamente (ver notas de módulo).
    """

    # Señales
    entity_clicked = Signal(str)          # entity_id
    point_clicked = Signal(float, float)  # world x, y (DXF coords, Y-up)
    snap_point = Signal(float, float)     # snapped world coords
    measurement_ready = Signal(float, str, str, list)  # (valor, tipo: distancia|area|punto|conteo, tipo_cad, puntos_mundo)
    medicion_click = Signal(int, str)     # renglon_id, campo — overlay de medición guardada clickeado en el plano
    medicion_editada = Signal(int, str, float, list)  # renglon_id, campo, nuevo valor, nuevos puntos [[x,y],...]

    # Claves de datos propias en QGraphicsItem.setData()/data() — enteros
    # arbitrarios que no colisionan con las claves que usa PyQtBackend
    # (CorrespondingDXFEntity/CorrespondingDXFParentStack) porque cada
    # clave es un slot independiente del item, no un espacio compartido.
    _ROLE_MEDICION_ID = 5001  # renglon_id dueño de este item de overlay
    _ROLE_MEDICION_CAMPO = 5003  # campo ('veces'|'largo'|'ancho'|'alto') que mide este overlay —
                                  # un renglón puede tener Largo, Ancho y Alto medidos cada uno
                                  # con su propia línea, así que un overlay se identifica por
                                  # (renglon_id, campo), no solo por renglon_id.
    _ROLE_GRIP_INDEX = 5002   # índice del punto que representa este grip

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setScene(self._scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        # Viewport raster por defecto (sin QOpenGLWidget): ver notas de
        # módulo. No llamar setViewport aquí — el widget por defecto ya
        # es el correcto para este caso de uso.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # para recibir Del/Backspace

        self.scale(1, -1)  # Y-up (convención DXF) en vez de Y-down (Qt)
        self.setBackgroundBrush(QBrush(QColor("#1a1a2e")))

        self._doc: ezdxf.document.Drawing | None = None
        self._render_context: RenderContext | None = None
        self._visible_layers: set[str] = set()
        self._item_layer_cache: dict[int, str] = {}
        self._scale = 1.0
        self._tool = CadTool.SELECT
        self._calibration_mode = False
        self._calibration_point_a: tuple[float, float] | None = None

        self._panning = False
        self._pan_start = QPointF()

        self._measure_points: list[QPointF] = []
        self._preview_items: list[QGraphicsItem] = []
        self._persisted_items: list[QGraphicsItem] = []
        self._ortho_preview: QPointF | None = None
        self._highlight_item: QGraphicsItem | None = None

        # Overlays persistentes de renglones origen="cad" (ver
        # set_medicion_overlays) — de dónde salió cada medición, dibujado
        # en el plano sin importar cuántas veces se reabra el proyecto,
        # y editable con grips (ver _mostrar_grips/_mover_grip).
        self._overlays_data: dict[int, dict] = {}
        self._overlay_seleccionado: tuple[int, str] | None = None
        self._grip_items: list[QGraphicsItem] = []
        self._grip_drag_idx: int | None = None
        self._grip_drag_clave: tuple[int, str] | None = None
        self._grip_drag_moved: bool = False
        self._grip_seleccionado_idx: int | None = None  # último grip clickeado (para Del)

        self._coord_label = QLabel(self)
        self._coord_label.setStyleSheet(
            "background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.4);"
            "font:10px monospace;padding:2px 6px;border:1px solid rgba(255,255,255,0.1);"
            "border-radius:4px;"
        )
        self._coord_label.setFixedHeight(20)
        self._coord_label.hide()

        self._zoom_label = QLabel(self)
        self._zoom_label.setStyleSheet(
            "background:rgba(255,255,255,0.1);color:rgba(255,255,255,0.5);"
            "font:11px monospace;padding:2px 6px;border:1px solid rgba(255,255,255,0.1);"
            "border-radius:4px;"
        )
        self._zoom_label.setFixedHeight(20)
        self._zoom_label.hide()

        # Resultado de una medición rápida (herramienta Línea): de solo
        # lectura — el usuario lo lee y lo escribe a mano en la tabla de
        # renglones. No crea ni modifica ningún renglón automáticamente.
        self._measure_label = QLabel(self)
        self._measure_label.setStyleSheet(
            "background:rgba(255,215,0,0.15);color:#FFD700;"
            "font:bold 12px monospace;padding:4px 10px;border:1px solid rgba(255,215,0,0.35);"
            "border-radius:4px;"
        )
        self._measure_label.setFixedHeight(24)
        self._measure_label.hide()

    # ── Grid ──────────────────────────────────────────────────────

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        vw = vr.width()
        vh = vr.height()
        if vw <= 0 or vh <= 0:
            return
        scale = abs(self.transform().m11())
        if scale <= 0:
            return
        raw_step = 50 / scale
        exp = math.floor(math.log10(raw_step)) if raw_step > 0 else 0
        minor_step = 10 ** exp
        major_step = minor_step * 10
        minor_px = minor_step * scale
        major_px = major_step * scale

        def _draw_grid(step: float, pen: QPen):
            painter.setPen(pen)
            x0 = math.floor(vr.left() / step) * step
            x1 = math.ceil(vr.right() / step) * step
            y0 = math.floor(min(vr.top(), vr.bottom()) / step) * step
            y1 = math.ceil(max(vr.top(), vr.bottom()) / step) * step
            # Límite defensivo: en documentos con extents anómalos o zoom
            # extremo, no dibujar un número absurdo de líneas.
            max_lines = 500
            n_x = int((x1 - x0) / step) + 1
            n_y = int((y1 - y0) / step) + 1
            if n_x > max_lines or n_y > max_lines:
                return
            x = x0
            while x <= x1:
                painter.drawLine(QPointF(x, y0), QPointF(x, y1))
                x += step
            y = y0
            while y <= y1:
                painter.drawLine(QPointF(x0, y), QPointF(x1, y))
                y += step

        if minor_px > 8:
            pen = QPen(QColor(255, 255, 255, 8), 0)
            pen.setCosmetic(True)
            _draw_grid(minor_step, pen)
        if major_px > 8:
            pen = QPen(QColor(255, 255, 255, 18), 0)
            pen.setCosmetic(True)
            _draw_grid(major_step, pen)

    # ── Data ───────────────────────────────────────────────────────

    def set_document(self, doc: ezdxf.document.Drawing):
        """Carga un documento DXF usando ezdxf para rendering nativo."""
        self._doc = doc
        self._render_context = RenderContext(doc)
        self._visible_layers = {layer.dxf.name for layer in doc.layers}
        self._redraw()

    def _redraw(self):
        """Re-renderiza la escena completa usando ezdxf (una sola vez)."""
        if self._doc is None:
            return

        # Los items de preview (medición) viven en la MISMA escena que se
        # está por limpiar. scene.clear() destruye los QGraphicsItem de
        # C++; si no se descarta también la lista Python que los
        # referenciaba, una llamada posterior a _draw_measure_preview()
        # intentaría remover/tocar objetos ya destruidos (crash).
        self._preview_items.clear()
        self._persisted_items.clear()
        self._highlight_item = None
        # scene.clear() va a destruir también los overlays e ítems de
        # grips de C++ — descartar las listas Python sin llamar
        # removeItem() sobre objetos que ya van a quedar destruidos.
        self._overlays_data.clear()
        self._grip_items.clear()
        self._overlay_seleccionado = None
        self._scene.clear()
        self._item_layer_cache.clear()

        # NOTA: aquí NO se usa set_layers_state() para filtrar por capa.
        # Frontend.draw_layout() llama internamente a
        # ctx.set_current_layout(), que reconstruye ctx.layers desde cero
        # y descarta cualquier estado de visibilidad que se haya puesto
        # antes — set_layers_state() simplemente no tenía efecto real.
        # En vez de pelear con eso, renderizamos TODO siempre (una sola
        # vez) y aplicamos la visibilidad por capa nosotros mismos sobre
        # los items ya creados (ver _apply_layer_visibility), usando la
        # capa real que PyQtBackend ya adjunta a cada item.
        backend = PyQtBackend(self._scene)
        frontend = Frontend(self._render_context, backend)
        frontend.draw_layout(self._doc.modelspace())  # finalize=True por default

        for item in self._scene.items():
            self._item_layer_cache[id(item)] = self._resolve_item_layer(item)

        r = self._scene.sceneRect()
        bx = r.width() * 0.25
        by = r.height() * 0.25
        self._scene.setSceneRect(r.adjusted(-bx, -by, bx, by))
        self.fit_in_view()
        self._apply_layer_visibility()

    @staticmethod
    def _resolve_item_layer(item) -> str:
        """Capa efectiva de un item de la escena, usando las referencias a
        la entidad DXF de origen que PyQtBackend ya adjunta a cada item.

        Si la entidad está en capa "0" (p.ej. una sub-entidad dentro de un
        bloque), hereda la capa del INSERT que la colocó — para eso se usa
        la pila de padres (CorrespondingDXFParentStack), recorrida del más
        cercano al más lejano, igual que hace AutoCAD.
        """
        entity = item.data(CorrespondingDXFEntity)
        if entity is None or not entity.dxf.hasattr("layer"):
            return "0"
        layer = entity.dxf.layer
        if layer != "0":
            return layer
        stack = item.data(CorrespondingDXFParentStack) or ()
        for ancestor in reversed(stack):
            if ancestor.dxf.hasattr("layer") and ancestor.dxf.layer != "0":
                return ancestor.dxf.layer
        return "0"

    def _apply_layer_visibility(self):
        """Aplica self._visible_layers sobre los items ya renderizados,
        sin volver a parsear ni renderizar el documento — esto es lo que
        hace que un toggle de capa sea instantáneo y no reinicie el
        zoom/pan (antes, cada toggle llamaba a _redraw() completo).
        """
        for item in self._scene.items():
            layer = self._item_layer_cache.get(id(item))
            if layer is None:
                continue
            item.setVisible(layer in self._visible_layers)

    def set_entities(self, entities, layers):
        """Compat shim: acepta la interfaz antigua pero ignora los datos.
        Llamar a set_document(doc) para renderizar correctamente.

        No dibuja nada — si algún caller llega aquí (hoy ninguno en este
        repo lo hace, ver Hallazgo 13 de la auditoría), el visor se queda
        vacío. Se deja este log en vez de un `pass` puro para que, si
        alguna vez se reintroduce un llamador, quede evidencia en vez de
        fallar en silencio total.
        """
        log.warning(
            "VisorCadWidget.set_entities() llamado (%d entidades, %d capas) "
            "pero es un compat shim que no renderiza nada — el visor "
            "quedará vacío. Usa set_document(doc) en su lugar.",
            len(entities) if entities else 0, len(layers) if layers else 0,
        )

    def set_layer_visibility(self, layer_name: str, visible: bool):
        if visible:
            self._visible_layers.add(layer_name)
        else:
            self._visible_layers.discard(layer_name)
        self._apply_layer_visibility()

    def show_all_layers(self):
        if self._doc is not None:
            self._visible_layers = {layer.dxf.name for layer in self._doc.layers}
        self._apply_layer_visibility()

    def hide_all_layers(self):
        self._visible_layers.clear()
        self._apply_layer_visibility()

    def get_layers(self) -> list[dict]:
        if self._render_context is None:
            return []
        result = []
        for name, props in self._render_context.layers.items():
            color = props.color
            if isinstance(color, int):
                color = ACI_COLORS.get(color, "#CCCCCC")
            result.append({
                "name": name,
                "color": color,
                "visible": name in self._visible_layers,
                "entity_count": 0,
            })
        return sorted(result, key=lambda l: l["name"])

    # ── Encuadre / zoom ─────────────────────────────────────────────

    def _fit_transform(self, rect: QRectF) -> QTransform | None:
        """Calcula (sin aplicarla) la transformación que encuadra ``rect``
        en el viewport actual, respetando la relación de aspecto y con el
        flip Y-up ya incorporado desde el inicio — en vez de calcular una
        transformación "a la Qt" (Y-down) y corregirla después inspeccionando
        el signo de m22() tras fitInView(), que es más frágil.
        """
        vp = self.viewport().rect()
        if not rect.isValid() or vp.width() <= 0 or vp.height() <= 0:
            return None
        if rect.width() <= 0 or rect.height() <= 0:
            return None

        sx = vp.width() / rect.width()
        sy = vp.height() / rect.height()
        s = min(sx, sy)
        s = max(_MIN_SCALE, min(_MAX_SCALE, s))

        t = QTransform()
        t.scale(s, -s)  # Y-up
        cx, cy = rect.center().x(), rect.center().y()
        t.translate(-cx, -cy)
        return t

    def fit_in_view(self):
        rect = self._scene.itemsBoundingRect()
        t = self._fit_transform(rect)
        if t is None:
            return
        self.setTransform(t)
        self.centerOn(rect.center())
        self._scale = abs(self.transform().m11())
        self._zoom_label.setText(f"{int(self._scale * 100)}%")
        self._zoom_label.show()

    def viewport_world_rect(self) -> QRectF:
        vp = self.mapToScene(self.viewport().rect())
        r = vp.boundingRect()
        lo = min(r.top(), r.bottom())
        hi = max(r.top(), r.bottom())
        return QRectF(r.left(), lo, r.width(), hi - lo)

    def visible_entity_ids(self) -> set[str]:
        return set()

    # ── Tools ──────────────────────────────────────────────────────

    def set_tool(self, tool: str):
        self._tool = tool
        self._measure_points.clear()
        self._ortho_preview = None
        self._measure_label.hide()
        self._clear_persisted()
        self._clear_highlight()
        if tool != CadTool.SELECT:
            self.seleccionar_medicion(None)
        if tool == CadTool.SELECT:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif tool in (CadTool.LINE, CadTool.POLYLINE, CadTool.POLYGON, CadTool.COUNT, CadTool.POINT):
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif tool == CadTool.CALIBRATE:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
            self._calibration_mode = True
            self._calibration_point_a = None

    # ── Zoom ───────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current = abs(self.transform().m11())
        target = current * factor
        # Recortar el factor para no salir de los límites en vez de
        # ignorar el evento — así el zoom "frena" suavemente en el
        # límite en lugar de quedar pegado sin feedback visual.
        if target < _MIN_SCALE:
            factor = (_MIN_SCALE / current) if current > 0 else 1.0
        elif target > _MAX_SCALE:
            factor = (_MAX_SCALE / current) if current > 0 else 1.0
        if abs(factor - 1.0) < 1e-9:
            return
        self.scale(factor, factor)
        self._scale = abs(self.transform().m11())
        self._zoom_label.setText(f"{int(self._scale * 100)}%")
        self._zoom_label.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        vw, vh = self.viewport().width(), self.viewport().height()
        self._coord_label.move(8, vh - 28)
        self._zoom_label.move(vw - 60, vh - 28)
        self._measure_label.move(8, 8)

    def _handle_select_click(self, screen_pos: QPoint, world: QPointF | None = None):
        item = self.itemAt(screen_pos)
        self._clear_highlight()

        # ¿Clic sobre el overlay de una medición guardada (renglón CAD)?
        # Se revisa antes que la selección normal de entidades DXF —
        # ambos tipos de item pueden compartir la misma zona de pantalla.
        # Un overlay se identifica por (renglon_id, campo): un renglón
        # puede tener Largo, Ancho y Alto medidos cada uno con su propia
        # línea independiente.
        rid = item.data(self._ROLE_MEDICION_ID) if item is not None else None
        campo = item.data(self._ROLE_MEDICION_CAMPO) if item is not None else None
        if rid is not None and campo is not None:
            clave = (rid, campo)
            self.seleccionar_medicion(clave)
            self.medicion_click.emit(rid, campo)
            return

        # Clic en espacio vacío con un CONTADOR ya seleccionado: en vez
        # de deseleccionarlo, se interpreta como "agregar otro elemento
        # contado" — permite seguir sumando puntos sin volver a la
        # herramienta Contador cada vez que se quiere corregir/completar
        # un conteo ya hecho.
        if item is None and world is not None and self._overlay_seleccionado is not None:
            data = self._overlays_data.get(self._overlay_seleccionado)
            if data and data.get("tipo_cad") == "contador":
                clave_activa = self._overlay_seleccionado
                snapped = self.snap_to_entity(world)
                pt = snapped if snapped else world
                data["puntos"].append([pt.x(), pt.y()])
                self._grip_seleccionado_idx = None
                self._dibujar_overlay(clave_activa)
                self._mostrar_grips(clave_activa)
                self._finalizar_edicion_medicion(clave_activa)
                return

        if self._overlay_seleccionado is not None:
            self.seleccionar_medicion(None)

        if item is None:
            return
        entity = item.data(CorrespondingDXFEntity)
        if entity is None:
            return
        self.entity_clicked.emit(entity.dxf.handle or "")
        self._show_highlight(item)

    def _show_highlight(self, item: QGraphicsItem):
        rect = item.sceneBoundingRect().adjusted(-2, -2, 2, 2)
        highlight = self._scene.addRect(rect)
        pen = QPen(QColor("#FFD700"), 1.5, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        highlight.setPen(pen)
        highlight.setBrush(QBrush(Qt.GlobalColor.transparent))
        highlight.setZValue(999)
        self._highlight_item = highlight

    def _clear_highlight(self):
        if self._highlight_item is not None:
            self._scene.removeItem(self._highlight_item)
            self._highlight_item = None

    # ── Overlays de medición persistentes (renglones origen="cad") ──
    #
    # A diferencia de _persisted_items (el trazo de la medición EN CURSO,
    # que se borra al iniciar la siguiente — ver _handle_measure_click),
    # esto dibuja TODOS los renglones ya guardados con origen="cad" de
    # forma permanente, para que el trazo de dónde salió cada cantidad
    # se vea en el plano sin importar cuántas veces se cierre y reabra
    # el proyecto. Se guarda además el detalle en self._overlays_data
    # para poder resaltar uno desde la tabla y editarlo con grips.

    def set_medicion_overlays(self, renglones: list[dict], archivo_actual: str | None = None):
        """Dibuja el overlay persistente de cada medición CAD guardada
        (una por celda — Veces/Largo/Ancho/Alto pueden venir cada una de
        su propia línea, ver medidas_efectivas) a partir de cad_medidas.
        Llamar después de set_document() (que limpia toda la escena).

        `archivo_actual`: nombre del DXF actualmente cargado — si una
        medición se hizo en un plano distinto (cad_origen_archivo no
        coincide, ej. el generador cambió de DXF ligado), su overlay se
        pinta en gris punteado en vez del naranja normal, para avisar
        que esas coordenadas probablemente ya no corresponden al plano
        que se está viendo."""
        # Quitar de la ESCENA los ítems del overlay anterior antes de
        # descartar el diccionario — self._overlays_data.clear() solo
        # borraba la referencia en Python; los QGraphicsItem ya
        # agregados a self._scene se quedaban huérfanos ahí pintados
        # para siempre. Esto es lo que dejaba una copia vieja "pegada"
        # en su posición original cada vez que se refrescaba (por
        # ejemplo, justo al soltar un grip tras mover un nodo).
        for data in self._overlays_data.values():
            for item in data.get("items", []):
                try:
                    self._scene.removeItem(item)
                except RuntimeError:
                    pass  # ya destruido por un scene.clear() (_redraw)
        self._overlays_data.clear()
        self._clear_grips()
        self._overlay_seleccionado = None
        for rn in renglones:
            if rn.get("origen") != "cad":
                continue
            rid = rn.get("id")
            if rid is None:
                continue
            # Un renglón puede tener Largo, Ancho y Alto medidos cada
            # uno con su propia línea — cada campo es un overlay
            # independiente, identificado por (renglon_id, campo).
            for campo, info in medidas_efectivas(rn).items():
                puntos = info.get("puntos") or []
                tipo_cad = info.get("tipo")
                # Contador con 0 puntos vigentes (se borraron todos con
                # Del) sigue registrándose sin overlay dibujado — para
                # poder seguir seleccionándolo y agregarle puntos de
                # nuevo. Línea/polilínea/área sin puntos no tienen sentido.
                if not puntos and tipo_cad != "contador":
                    continue
                origen_archivo = info.get("archivo")
                otro_archivo = bool(origen_archivo and archivo_actual and origen_archivo != archivo_actual)
                clave = (rid, campo)
                self._overlays_data[clave] = {
                    "tipo_cad":       tipo_cad,
                    "puntos":         [list(p) for p in puntos],
                    "origen_archivo": origen_archivo,
                    "otro_archivo":   otro_archivo,
                    "items":          [],
                }
                self._dibujar_overlay(clave)

    def _dibujar_overlay(self, clave: tuple[int, str]):
        """(Re)dibuja el overlay de una medición (renglon_id, campo)
        desde self._overlays_data[clave]["puntos"] — se llama tanto al
        cargar como en cada frame de arrastre de un grip (edición en
        vivo)."""
        data = self._overlays_data.get(clave)
        if not data:
            return
        rid, campo = clave
        for item in data["items"]:
            try:
                self._scene.removeItem(item)
            except RuntimeError:
                pass  # ya destruido por un scene.clear() (_redraw)
        puntos = data["puntos"]
        tipo_cad = data.get("tipo_cad")
        seleccionado = (clave == self._overlay_seleccionado)
        if data.get("otro_archivo"):
            color = QColor("#9E9E9E")
        elif seleccionado:
            color = QColor("#00E5FF")
        else:
            color = QColor("#FF8A00")
        tooltip = None
        if data.get("otro_archivo"):
            tooltip = (f"Medido en \"{data.get('origen_archivo')}\" — "
                       f"puede no coincidir con el plano actual")
        items: list[QGraphicsItem] = []

        if tipo_cad in ("linea", "polilinea"):
            pen = QPen(color, 2.0 if seleccionado else 1.5)
            pen.setCosmetic(True)
            if data.get("otro_archivo"):
                pen.setStyle(Qt.PenStyle.DashLine)
            for i in range(len(puntos) - 1):
                x1, y1 = puntos[i]
                x2, y2 = puntos[i + 1]
                line = QGraphicsLineItem(x1, y1, x2, y2)
                line.setPen(pen)
                line.setZValue(500)
                line.setData(self._ROLE_MEDICION_ID, rid)
                line.setData(self._ROLE_MEDICION_CAMPO, campo)
                if tooltip:
                    line.setToolTip(tooltip)
                self._scene.addItem(line)
                items.append(line)
        elif tipo_cad == "area":
            poly = QPolygonF([QPointF(x, y) for x, y in puntos])
            pol_item = QGraphicsPolygonItem(poly)
            pen = QPen(color, 2.0 if seleccionado else 1.5)
            pen.setCosmetic(True)
            if data.get("otro_archivo"):
                pen.setStyle(Qt.PenStyle.DashLine)
            pol_item.setPen(pen)
            relleno = QColor(color)
            relleno.setAlpha(40)
            pol_item.setBrush(QBrush(relleno))
            pol_item.setZValue(500)
            pol_item.setData(self._ROLE_MEDICION_ID, rid)
            pol_item.setData(self._ROLE_MEDICION_CAMPO, campo)
            if tooltip:
                pol_item.setToolTip(tooltip)
            self._scene.addItem(pol_item)
            items.append(pol_item)
        else:  # punto / contador — un marcador por cada punto guardado
            radio = 5.0 / max(self._scale, 1e-6)
            pen = QPen(color, 1.5)
            pen.setCosmetic(True)
            for x, y in puntos:
                ellipse = QGraphicsEllipseItem(x - radio, y - radio, radio * 2, radio * 2)
                ellipse.setPen(pen)
                ellipse.setBrush(QBrush(color))
                ellipse.setZValue(500)
                ellipse.setData(self._ROLE_MEDICION_ID, rid)
                ellipse.setData(self._ROLE_MEDICION_CAMPO, campo)
                if tooltip:
                    ellipse.setToolTip(tooltip)
                self._scene.addItem(ellipse)
                items.append(ellipse)

        data["items"] = items

    def seleccionar_medicion(self, clave: tuple[int, str] | None):
        """Resalta el overlay de UNA medición específica —(renglon_id,
        campo)— y, si la herramienta activa es Seleccionar, muestra sus
        grips para poder editarla. clave=None limpia la selección.

        Para resaltar TODAS las mediciones de una fila de la tabla sin
        saber cuál campo en particular, usar resaltar_renglon() en su
        lugar (traza tabla→plano) — esta función es para cuando se sabe
        exactamente cuál medición (un clic directo en el plano, o tras
        terminar de medir)."""
        anterior = self._overlay_seleccionado
        self._overlay_seleccionado = clave
        if anterior is not None and anterior in self._overlays_data:
            self._dibujar_overlay(anterior)
        self._clear_grips()
        if clave is None or clave not in self._overlays_data:
            return
        self._dibujar_overlay(clave)
        if self._tool == CadTool.SELECT:
            self._mostrar_grips(clave)
        self._centrar_en_medicion(clave)

    def resaltar_renglon(self, renglon_id: int | None):
        """Traza tabla→plano: al seleccionar una fila, resalta la
        PRIMERA medición CAD de esa fila que exista (Largo, si no
        Ancho, si no Alto, si no Veces). Si la fila tiene varias celdas
        medidas, esto solo elige una para mostrarle los grips; las
        demás se siguen viendo en el plano con su color normal —
        alcanza para ubicar la fila sin tener que adivinar cuál de sus
        celdas resaltar."""
        if renglon_id is None:
            self.seleccionar_medicion(None)
            return
        for campo in ("largo", "ancho", "alto", "veces"):
            clave = (renglon_id, campo)
            if clave in self._overlays_data:
                self.seleccionar_medicion(clave)
                return
        self.seleccionar_medicion(None)

    def _centrar_en_medicion(self, clave: tuple[int, str]):
        data = self._overlays_data.get(clave)
        if not data or not data["puntos"]:
            return
        xs = [p[0] for p in data["puntos"]]
        ys = [p[1] for p in data["puntos"]]
        self.centerOn(QPointF((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))

    # ── Edición de nodos (grips) ──────────────────────────────────

    def _mostrar_grips(self, clave: tuple[int, str]):
        idx_previo = self._grip_seleccionado_idx
        self._clear_grips()
        data = self._overlays_data.get(clave)
        if not data:
            return
        radio = 5.0 / max(self._scale, 1e-6)
        pen = QPen(QColor("#FFFFFF"), 1.5)
        pen.setCosmetic(True)
        brush_normal = QBrush(QColor("#00E5FF"))
        brush_sel = QBrush(QColor("#FF3D3D"))  # rojo = el que borra Del/Backspace
        for idx, (x, y) in enumerate(data["puntos"]):
            grip = QGraphicsEllipseItem(x - radio, y - radio, radio * 2, radio * 2)
            grip.setPen(pen)
            grip.setBrush(brush_sel if idx == idx_previo else brush_normal)
            grip.setZValue(1500)
            grip.setData(self._ROLE_GRIP_INDEX, idx)
            self._scene.addItem(grip)
            self._grip_items.append(grip)
        # _clear_grips() de arriba resetea _grip_seleccionado_idx — se
        # repone acá para no perder cuál seguía marcado tras redibujar
        # (ej. al mover otro nodo del mismo trazo).
        if idx_previo is not None and idx_previo < len(data["puntos"]):
            self._grip_seleccionado_idx = idx_previo

    def _clear_grips(self):
        for item in self._grip_items:
            try:
                self._scene.removeItem(item)
            except RuntimeError:
                pass
        self._grip_items = []
        self._grip_seleccionado_idx = None

    def _iniciar_arrastre_grip(self, screen_pos: QPoint) -> bool:
        """Si screen_pos cae sobre un grip del renglón seleccionado,
        arranca su arrastre y devuelve True (para que mousePressEvent
        no siga con la selección normal)."""
        if self._overlay_seleccionado is None:
            return False
        item = self.itemAt(screen_pos)
        if item is None:
            return False
        idx = item.data(self._ROLE_GRIP_INDEX)
        if idx is None:
            return False
        self._grip_drag_idx = idx
        self._grip_drag_clave = self._overlay_seleccionado
        self._grip_drag_moved = False
        self._grip_seleccionado_idx = idx  # resalta en rojo desde que se agarra, no solo al soltar
        return True

    def _mover_grip(self, clave: tuple[int, str], idx: int, world: QPointF):
        data = self._overlays_data.get(clave)
        if not data or idx >= len(data["puntos"]):
            return
        data["puntos"][idx] = [world.x(), world.y()]
        self._grip_drag_moved = True
        self._dibujar_overlay(clave)
        self._mostrar_grips(clave)

    def _finalizar_edicion_medicion(self, clave: tuple[int, str] | None):
        """Al soltar un grip: recalcula el valor con la misma fórmula
        que la medición original (medicion.py) y emite medicion_editada
        con el (renglon_id, campo) exactos — mover nodos corrige la
        medición, nunca cambia a qué celda apunta."""
        if clave is None:
            return
        data = self._overlays_data.get(clave)
        if not data:
            return
        rid, campo = clave
        puntos = data["puntos"]
        tipo_cad = data.get("tipo_cad")
        pts2 = [Pt2(x, y) for x, y in puntos]
        if tipo_cad == "linea" and len(pts2) >= 2:
            valor = calculate_distance(pts2[0], pts2[1])
        elif tipo_cad == "polilinea":
            valor = calculate_perimeter(pts2, closed=False)
        elif tipo_cad == "area":
            valor = calculate_area(pts2)
        elif tipo_cad == "contador":
            # El conteo ES la cantidad de puntos vigentes — agregar o
            # borrar uno con Del/Backspace cambia el número solo, sin
            # tener que volver a contar todo desde cero.
            valor = float(len(puntos))
        else:
            valor = None  # punto: se corrige la posición, no hay valor que recalcular
        if valor is not None:
            self.medicion_editada.emit(rid, campo, valor, [[p[0], p[1]] for p in puntos])

    def _eliminar_grip_seleccionado(self) -> bool:
        """Del/Backspace: borra el punto actualmente marcado en rojo.
        Solo aplica a contador — línea/polilínea/área tienen una
        cantidad de nodos que define la forma medida (borrar uno ahí
        rompería el trazo, no corregiría un elemento contado de más).
        Devuelve True si borró algo, para que keyPressEvent no siga con
        el comportamiento default del widget."""
        clave = self._overlay_seleccionado
        idx = self._grip_seleccionado_idx
        if clave is None or idx is None:
            return False
        data = self._overlays_data.get(clave)
        if not data or data.get("tipo_cad") != "contador":
            return False
        if idx >= len(data["puntos"]):
            return False
        del data["puntos"][idx]
        self._grip_seleccionado_idx = None
        self._dibujar_overlay(clave)
        self._mostrar_grips(clave)
        self._finalizar_edicion_medicion(clave)
        return True

    def _persist_items(self):
        """Mueve los items de preview a la lista persistente (sobreviven al zoom/pan)."""
        self._persisted_items.extend(self._preview_items)
        self._preview_items.clear()

    def _clear_persisted(self):
        """Elimina los items de medición persistentes de la escena."""
        for item in self._persisted_items:
            self._scene.removeItem(item)
        self._persisted_items.clear()

    # ── Pan ────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            world = self._map_to_world(event.position())
            self.point_clicked.emit(world.x(), world.y())

            if self._tool == CadTool.SELECT:
                self.setFocus()  # para que Del funcione sin tener que clickear la vista primero
                if self._iniciar_arrastre_grip(event.position().toPoint()):
                    return
                self._handle_select_click(event.position().toPoint(), world)
                return

            if self._tool == CadTool.CALIBRATE:
                self._handle_calibration_click(world)
                return

            if self._tool in (CadTool.LINE, CadTool.POLYLINE, CadTool.POLYGON, CadTool.COUNT, CadTool.POINT):
                self._handle_measure_click(world)
                return

        # Click derecho: finalizar polilínea o polígono
        if event.button() == Qt.MouseButton.RightButton:
            if self._tool == CadTool.POLYLINE and len(self._measure_points) >= 2:
                self._finalize_polyline()
                return
            if self._tool == CadTool.POLYGON and len(self._measure_points) >= 3:
                self._finalize_polygon()
                return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tool == CadTool.POLYLINE and len(self._measure_points) >= 2:
                self._finalize_polyline()
                return
            if self._tool == CadTool.POLYGON and len(self._measure_points) >= 3:
                self._finalize_polygon()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._measure_points:
                self._measure_points.clear()
                self._ortho_preview = None
                self._measure_label.hide()
                self._draw_measure_preview()
                return
            if self._overlay_seleccionado is not None:
                self.seleccionar_medicion(None)
                return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._tool == CadTool.POLYLINE and len(self._measure_points) >= 2:
                self._finalize_polyline()
                return
            if self._tool == CadTool.POLYGON and len(self._measure_points) >= 3:
                self._finalize_polygon()
                return
            if self._overlay_seleccionado is not None:
                # Enter = dar por terminada la edición de esta medición
                # (quita los grips y la deselecciona), igual que clickear
                # en espacio vacío — para no depender de tener que volver
                # a clickear el plano solo para salir del modo edición.
                self.seleccionar_medicion(None)
                return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self._eliminar_grip_seleccionado():
                return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._grip_drag_idx is not None:
            world = self._map_to_world(event.position())
            snapped = self.snap_to_entity(world)
            pt = snapped if snapped else world
            self._mover_grip(self._grip_drag_clave, self._grip_drag_idx, pt)
            return

        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            return

        world = self._map_to_world(event.position())
        if self._doc is not None:
            self._coord_label.setText(f"X: {world.x():.2f}  Y: {world.y():.2f}")
            self._coord_label.show()

        if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                and self._measure_points and self._tool in (CadTool.LINE, CadTool.POLYGON)):
            anchor = self._measure_points[-1]
            snapped_x, snapped_y = snap_to_ortho(
                anchor.x(), anchor.y(), world.x(), world.y(),
            )
            self._ortho_preview = QPointF(snapped_x, snapped_y)
            self._draw_measure_preview()
        elif (self._tool == CadTool.POLYGON
                and self._measure_points
                and len(self._measure_points) >= 3):
            self._draw_measure_preview()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._grip_drag_idx is not None:
            clave, idx, movio = self._grip_drag_clave, self._grip_drag_idx, self._grip_drag_moved
            self._grip_drag_idx = None
            self._grip_drag_clave = None
            self._grip_drag_moved = False
            # Un clic sobre un grip SIN arrastrarlo lo deja "seleccionado"
            # (para poder borrarlo con Del/Backspace) sin disparar un
            # guardado — solo si realmente se movió se recalcula y persiste.
            self._grip_seleccionado_idx = idx
            if movio:
                self._finalizar_edicion_medicion(clave)
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor if self._tool == CadTool.SELECT
                           else Qt.CursorShape.CrossCursor)
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._coord_label.hide()

    # ── Coordinate mapping ─────────────────────────────────────────

    def _map_to_world(self, screen_pos: QPointF) -> QPointF:
        return self.mapToScene(screen_pos.toPoint())

    # ── Snap ───────────────────────────────────────────────────────

    def snap_to_entity(self, world_pos: QPointF, tolerance_px: float = 10.0) -> QPointF | None:
        if self._doc is None:
            return None
        # Convertir tolerancia de píxeles a unidades del mundo
        scale = abs(self.transform().m11())
        tolerance = tolerance_px / scale if scale > 0 else tolerance_px
        best = None
        best_dist = tolerance

        for entity in self._doc.modelspace():
            etype = entity.dxftype()
            candidates = []

            if etype == "LINE":
                s = entity.dxf.start
                e = entity.dxf.end
                candidates.append(QPointF(s.x, s.y))
                candidates.append(QPointF(e.x, e.y))
                candidates.append(QPointF((s.x + e.x) / 2, (s.y + e.y) / 2))

            elif etype == "LWPOLYLINE":
                pts = list(entity.get_points(format="xy"))
                n = len(pts)
                for p in pts:
                    candidates.append(QPointF(p[0], p[1]))
                last = n if entity.closed else n - 1
                for i in range(last):
                    a, b = pts[i], pts[(i + 1) % n]
                    candidates.append(QPointF((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))

            elif etype in ("CIRCLE", "ARC", "ELLIPSE"):
                c = entity.dxf.center
                candidates.append(QPointF(c.x, c.y))

            elif etype == "POINT":
                p = entity.dxf.location
                candidates.append(QPointF(p.x, p.y))

            for pt in candidates:
                dx = pt.x() - world_pos.x()
                dy = pt.y() - world_pos.y()
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < best_dist:
                    best_dist = dist
                    best = pt

        if best:
            self.snap_point.emit(best.x(), best.y())
        return best

    # ── Measurement handling ───────────────────────────────────────

    def _handle_measure_click(self, world: QPointF):
        snapped = self.snap_to_entity(world)
        pt = snapped if snapped else world

        # Primera_click de una nueva medición: borrar la anterior
        if not self._measure_points and self._persisted_items:
            self._clear_persisted()

        self._measure_points.append(pt)

        if self._tool == CadTool.LINE and len(self._measure_points) >= 2:
            self._draw_measure_preview()
            p1, p2 = self._measure_points[0], self._measure_points[1]
            dist = calculate_distance(Pt2(p1.x(), p1.y()), Pt2(p2.x(), p2.y()))
            self._measure_label.setText(f"Distancia: {dist:.4f}")
            self._measure_label.adjustSize()
            self._measure_label.show()
            self._persist_items()
            puntos = [[p.x(), p.y()] for p in self._measure_points]
            self._measure_points.clear()
            self._ortho_preview = None
            self.measurement_ready.emit(dist, "distancia", "linea", puntos)
            return

        if (self._tool == CadTool.POLYGON
                and len(self._measure_points) >= 3):
            first = self._measure_points[0]
            if abs(pt.x() - first.x()) < 1e-6 and abs(pt.y() - first.y()) < 1e-6:
                self._finalize_polygon()
                return

        # Polilínea: solo acumula puntos — a diferencia de Línea (se cierra
        # sola en el segundo clic) y de Polígono (se cierra clicando cerca
        # del primer punto), acá el cierre es explícito: clic derecho,
        # doble clic, o Enter (ver mousePressEvent/mouseDoubleClickEvent/
        # keyPressEvent). Un trazo abierto no tiene un "punto de cierre"
        # natural en el que basarse.

        elif self._tool == CadTool.POINT:
            self.point_clicked.emit(pt.x(), pt.y())
            self._measure_points.clear()
            self.measurement_ready.emit(1.0, "punto", "punto", [[pt.x(), pt.y()]])

        elif self._tool == CadTool.COUNT:
            self.point_clicked.emit(pt.x(), pt.y())
            self._measure_points.clear()
            self.measurement_ready.emit(1.0, "conteo", "contador", [[pt.x(), pt.y()]])

        self._draw_measure_preview()

    def _handle_calibration_click(self, world: QPointF):
        if self._calibration_point_a is None:
            self._calibration_point_a = (world.x(), world.y())
        else:
            self.point_clicked.emit(world.x(), world.y())
            self._calibration_point_a = None

    def _finalize_polyline(self):
        """Cierra la polilínea y muestra su longitud total (suma de todos
        los segmentos, sin cerrar el último punto con el primero — a
        diferencia de _finalize_polygon)."""
        pts = [Pt2(p.x(), p.y()) for p in self._measure_points]
        total = calculate_perimeter(pts, closed=False)
        self._measure_label.setText(f"Longitud total: {total:.4f}")
        self._measure_label.adjustSize()
        self._measure_label.show()
        self._persist_items()
        puntos = [[p.x(), p.y()] for p in self._measure_points]
        self._measure_points.clear()
        self._ortho_preview = None
        self._draw_measure_preview()
        # Mismo tipo "distancia" que Línea: para quien consume la señal
        # (_on_cad_measurement en mixins/generador.py) una polilínea es
        # solo una distancia medida con más de dos puntos — mismo destino
        # (la celda Largo seleccionada), mismo modo ("set").
        self.measurement_ready.emit(total, "distancia", "polilinea", puntos)

    def _finalize_polygon(self):
        """Cierra el polígono y muestra área + perímetro."""
        pts = [Pt2(p.x(), p.y()) for p in self._measure_points]
        area = calculate_area(pts)
        perim = calculate_perimeter(pts, closed=True)
        self._measure_label.setText(
            f"Área: {area:.4f}  |  Perímetro: {perim:.4f}"
        )
        self._measure_label.adjustSize()
        self._measure_label.show()
        self._persist_items()
        puntos = [[p.x(), p.y()] for p in self._measure_points]
        self._measure_points.clear()
        self._ortho_preview = None
        self._draw_measure_preview()
        self.measurement_ready.emit(area, "area", "area", puntos)

    def _draw_measure_preview(self):
        for item in self._preview_items:
            self._scene.removeItem(item)
        self._preview_items.clear()

        if not self._measure_points:
            return

        # Líneas entre puntos consecutivos
        pen_line = QPen(QColor("#FFD700"), 1.5)
        pen_line.setCosmetic(True)
        for i in range(len(self._measure_points) - 1):
            p1 = self._measure_points[i]
            p2 = self._measure_points[i + 1]
            line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
            line.setPen(pen_line)
            line.setZValue(1000)
            self._scene.addItem(line)
            self._preview_items.append(line)

        # Cierre visual del polígono (último → primero)
        if (self._tool == CadTool.POLYGON
                and len(self._measure_points) >= 3
                and not self._ortho_preview):
            p1 = self._measure_points[-1]
            p2 = self._measure_points[0]
            pen_close = QPen(QColor("#FFD700"), 1, Qt.PenStyle.DotLine)
            pen_close.setCosmetic(True)
            line = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
            line.setPen(pen_close)
            line.setZValue(1000)
            self._scene.addItem(line)
            self._preview_items.append(line)

        # Puntos — radio fijo de 4 px en pantalla
        radio = 4.0 / max(self._scale, 1e-6)
        pen_dot = QPen(QColor("#FFD700"), 0)
        pen_dot.setCosmetic(True)
        for pt in self._measure_points:
            ellipse = QGraphicsEllipseItem(
                pt.x() - radio, pt.y() - radio, radio * 2, radio * 2,
            )
            ellipse.setPen(pen_dot)
            ellipse.setBrush(QBrush(QColor("#FFD700")))
            ellipse.setZValue(1001)
            self._scene.addItem(ellipse)
            self._preview_items.append(ellipse)

        # Preview ortho (seguimiento del mouse con Shift)
        if self._measure_points and self._ortho_preview:
            anchor = self._measure_points[-1]
            line = QGraphicsLineItem(
                anchor.x(), anchor.y(),
                self._ortho_preview.x(), self._ortho_preview.y(),
            )
            pen_ortho = QPen(QColor("#FFD700"), 1, Qt.PenStyle.DashLine)
            pen_ortho.setCosmetic(True)
            line.setPen(pen_ortho)
            line.setZValue(1000)
            self._scene.addItem(line)
            self._preview_items.append(line)
