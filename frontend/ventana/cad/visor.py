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
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsLineItem, QGraphicsEllipseItem,
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


log = logging.getLogger(__name__)


# ── Herramientas de dibujo ────────────────────────────────────────

class CadTool:
    SELECT = "select"
    LINE = "line"
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
    measurement_ready = Signal(float, str)  # (valor, tipo: distancia|area|punto|conteo)

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
        """
        pass

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
        if tool == CadTool.SELECT:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif tool in (CadTool.LINE, CadTool.POLYGON, CadTool.COUNT, CadTool.POINT):
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

    def _handle_select_click(self, screen_pos: QPoint):
        item = self.itemAt(screen_pos)
        self._clear_highlight()
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
                self._handle_select_click(event.position().toPoint())
                return

            if self._tool == CadTool.CALIBRATE:
                self._handle_calibration_click(world)
                return

            if self._tool in (CadTool.LINE, CadTool.POLYGON, CadTool.COUNT, CadTool.POINT):
                self._handle_measure_click(world)
                return

        # Click derecho: finalizar polígono
        if (event.button() == Qt.MouseButton.RightButton
                and self._tool == CadTool.POLYGON
                and len(self._measure_points) >= 3):
            self._finalize_polygon()
            return

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._tool == CadTool.POLYGON
                and len(self._measure_points) >= 3):
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
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if (self._tool == CadTool.POLYGON
                    and len(self._measure_points) >= 3):
                self._finalize_polygon()
                return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
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
            self._measure_label.setText(f"📏 Distancia: {dist:.4f}")
            self._measure_label.adjustSize()
            self._measure_label.show()
            self._persist_items()
            self._measure_points.clear()
            self._ortho_preview = None
            self.measurement_ready.emit(dist, "distancia")
            return

        if (self._tool == CadTool.POLYGON
                and len(self._measure_points) >= 3):
            first = self._measure_points[0]
            if abs(pt.x() - first.x()) < 1e-6 and abs(pt.y() - first.y()) < 1e-6:
                self._finalize_polygon()
                return

        elif self._tool == CadTool.POINT:
            self.point_clicked.emit(pt.x(), pt.y())
            self._measure_points.clear()
            self.measurement_ready.emit(1.0, "punto")

        elif self._tool == CadTool.COUNT:
            self.point_clicked.emit(pt.x(), pt.y())
            self._measure_points.clear()
            self.measurement_ready.emit(1.0, "conteo")

        self._draw_measure_preview()

    def _handle_calibration_click(self, world: QPointF):
        if self._calibration_point_a is None:
            self._calibration_point_a = (world.x(), world.y())
        else:
            self.point_clicked.emit(world.x(), world.y())
            self._calibration_point_a = None

    def _finalize_polygon(self):
        """Cierra el polígono y muestra área + perímetro."""
        pts = [Pt2(p.x(), p.y()) for p in self._measure_points]
        area = calculate_area(pts)
        perim = calculate_perimeter(pts, closed=True)
        self._measure_label.setText(
            f"📐 Área: {area:.4f}  |  Perímetro: {perim:.4f}"
        )
        self._measure_label.adjustSize()
        self._measure_label.show()
        self._persist_items()
        self._measure_points.clear()
        self._ortho_preview = None
        self._draw_measure_preview()
        self.measurement_ready.emit(area, "area")

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
