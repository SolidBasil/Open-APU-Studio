"""
lector_dxf.py
=============
Parser de archivos DXF usando ezdxf.

Normaliza entidades DXF a una lista de dicts tipados para el viewer.
Soporta: LINE, LWPOLYLINE, CIRCLE, ARC, TEXT, MTEXT, INSERT (bloques).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import ezdxf
import ezdxf.colors as _ezcolors
from ezdxf.entities import (
    DXFGraphic, Line, LWPolyline, Circle, Arc, Text, MText, Insert,
    Hatch, Ellipse, Dimension, Point,
)

# Profundidad máxima de recursión al expandir INSERT anidados (bloques
# dentro de bloques, o flechas de cota que a su vez son bloques).
_MAX_INSERT_DEPTH = 6


# ── Modelo de entidad normalizada ──────────────────────────────────

@dataclass
class DxfEntity:
    """Entidad DXF normalizada para el viewer."""
    id: str
    type: str  # LINE, LWPOLYLINE, CIRCLE, ARC, TEXT, MTEXT, INSERT
    layer: str
    color: int | str  # ACI index o hex string
    start: dict | None = None   # {x, y} para LINE, ARC (center)
    end: dict | None = None     # {x, y} para LINE
    center: dict | None = None  # {x, y} para CIRCLE, ARC
    radius: float | None = None
    start_angle: float | None = None  # grados, para ARC
    end_angle: float | None = None
    vertices: list[dict] | None = None  # [{x,y}, ...] para LWPOLYLINE
    closed: bool = False
    text: str | None = None
    height: float | None = None
    rotation: float | None = None
    block_name: str | None = None
    extrusion: dict | None = None
    major_radius: float | None = None
    minor_radius: float | None = None
    major_axis: dict | None = None
    ratio: float | None = None
    start_param: float | None = None  # radianes; barrido parcial de ELLIPSE (arco elíptico)
    end_param: float | None = None
    pattern_name: str | None = None
    solid_fill: bool = False
    pattern_angle: float = 0.0
    pattern_scale: float = 1.0
    layout: str | None = None
    halign: int | None = None  # 0=Left, 1=Center, 2=Right, 3=Aligned, 4=Middle, 5=Fit
    valign: int | None = None  # 0=Baseline, 1=Bottom, 2=Middle, 3=Top
    align_point: dict | None = None  # {x, y} segundo punto de alineación (Aligned/Fit)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DxfLayer:
    """Capa del DXF."""
    name: str
    color: int | str
    visible: bool = True
    entity_count: int = 0


@dataclass
class DxfParseResult:
    """Resultado de parsear un archivo DXF."""
    entities: list[DxfEntity]
    layers: list[DxfLayer]
    extents_min: dict  # {x, y}
    extents_max: dict  # {x, y}
    units: str  # m, mm, cm, etc.
    doc: object | None = None  # ezdxf.Drawing para rendering nativo


# ── ACI color table (paleta real de AutoCAD, vía ezdxf.colors) ─────
#
# ezdxf ya trae embebida la tabla ACI (Autocad Color Index) oficial de
# 256 colores en ezdxf.colors.aci2rgb(). La versión anterior de este
# módulo generaba una aproximación sintética (rampa de tono/brillo)
# que NO coincide con la paleta real de AutoCAD para la mayoría de los
# índices 10-249 (p.ej. ACI 249 real es (88,19,23), muy distinto de lo
# que produce una rampa HSV genérica). Usamos la tabla real para que
# los colores sean 100% fieles al DWG/DXF de origen.

def _rgb_to_hex(rgb) -> str:
    r, g, b = rgb
    return f"#{r:02X}{g:02X}{b:02X}"


def _build_aci_table() -> dict[int, str]:
    t: dict[int, str] = {}
    for idx in range(256):
        try:
            t[idx] = _rgb_to_hex(_ezcolors.aci2rgb(idx))
        except Exception:
            t[idx] = "#CCCCCC"
    return t


ACI_COLORS = _build_aci_table()


def _true_color_hex(entity) -> str | None:
    """Devuelve el true color (RGB de 24 bits) de la entidad como hex,
    o None si la entidad no tiene uno asignado (usa ACI/BYLAYER/BYBLOCK)."""
    try:
        rgb = entity.rgb  # None si no tiene dxf.true_color
    except Exception:
        rgb = None
    return _rgb_to_hex(rgb) if rgb else None


def _resolve_color(entity: DXFGraphic, layer_color: int | str = 7,
                    byblock_color: int | str | None = None) -> int | str:
    """Resuelve el color real de una entidad.

    Prioridad (igual que AutoCAD):
      1. True color (RGB de 24 bits) si está definido — muy común en
         DXF exportados desde Civil3D/Revit y en capas "true color".
      2. ACI 256 = BYLAYER → color de la capa (``layer_color``).
      3. ACI 0 = BYBLOCK → color heredado del INSERT que referencia el
         bloque (``byblock_color``), si se conoce; si no, color de capa.
      4. ACI explícito (1-255).
    """
    true_hex = _true_color_hex(entity)
    if true_hex:
        return true_hex

    try:
        c = entity.dxf.color
        if isinstance(c, int):
            if c == 256:  # BYLAYER
                return layer_color
            if c == 0:  # BYBLOCK
                return byblock_color if byblock_color is not None else layer_color
            return c
        return str(c)
    except Exception:
        return layer_color


def _layer_effective_color(layer) -> int | str:
    """Color efectivo de una capa: true color si lo tiene, si no ACI."""
    try:
        rgb = layer.rgb
        if rgb:
            return _rgb_to_hex(rgb)
    except Exception:
        pass
    return layer.color if hasattr(layer.dxf, "color") else 7


def _vec2_to_dict(v) -> dict | None:
    """Convierte Vec2 o tupla a dict {x, y}."""
    if v is None:
        return None
    return {"x": float(v[0]), "y": float(v[1])}


def _polyline_path_vertices(path) -> list[dict]:
    """Vértices de un boundary path tipo PolylinePath (frontera dibujada
    directamente como polilínea cerrada)."""
    try:
        return [{"x": float(v[0]), "y": float(v[1])} for v in path.vertices]
    except Exception:
        return []


def _edge_path_vertices(path) -> list[dict]:
    """Vértices de un boundary path tipo EdgePath: la frontera está
    compuesta de segmentos de LINE/ARC/ELLIPSE/SPLINE (el caso más común
    en hatches reales creados con 'seleccionar punto interno' en AutoCAD,
    ya que EdgePath no tiene atributo .vertices como PolylinePath).
    """
    from ezdxf.entities.boundary_paths import LineEdge

    pts: list[dict] = []
    try:
        edges = path.edges
    except Exception:
        return pts

    for edge in edges:
        try:
            if isinstance(edge, LineEdge):
                pts.append({"x": float(edge.start[0]), "y": float(edge.start[1])})
                pts.append({"x": float(edge.end[0]), "y": float(edge.end[1])})
            else:
                # ArcEdge / EllipseEdge / SplineEdge exponen construction_tool(),
                # que trae su propio .flattening(distancia) para tesela el
                # tramo curvo en puntos.
                ct = edge.construction_tool()
                for v in ct.flattening(0.2):
                    pts.append({"x": float(v[0]), "y": float(v[1])})
        except Exception:
            continue
    return pts


def _polygon_area(pts: list[dict]) -> float:
    """Área (shoelace) de un polígono simple; usada para elegir el loop
    de frontera principal cuando un HATCH trae varios (p.ej. contorno
    exterior + isla/hueco interior)."""
    if len(pts) < 3:
        return 0.0
    total = 0.0
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        total += pts[i]["x"] * pts[j]["y"] - pts[j]["x"] * pts[i]["y"]
    return abs(total) / 2.0


def _dispatch_entity(entity, layer_map: dict[str, "DxfLayer"], ensure_layer,
                      next_id, out: list["DxfEntity"],
                      byblock_color: int | str | None, depth: int) -> None:
    """Normaliza una entidad DXF (o una sub-entidad de un INSERT/DIMENSION
    ya expandida) y la agrega a ``out``. Recursivo para INSERT/DIMENSION.
    """
    layer_name = entity.dxf.layer if entity.dxf.hasattr("layer") else "0"
    layer = ensure_layer(layer_name)
    layer.entity_count += 1
    color = _resolve_color(entity, layer.color, byblock_color=byblock_color)
    eid = next_id()

    if isinstance(entity, Insert):
        _expand_insert(entity, layer_map, ensure_layer, next_id, out,
                        parent_layer=layer_name, parent_color=color, depth=depth)
        return

    if isinstance(entity, Dimension):
        _expand_dimension(entity, layer_map, ensure_layer, next_id, out,
                           layer_name=layer_name, color=color, eid=eid)
        return

    leaf = _leaf_entity(entity, eid, layer_name, color)
    if leaf is not None:
        out.append(leaf)


def _leaf_entity(entity, eid: str, layer_name: str, color) -> "DxfEntity | None":
    """Construye un DxfEntity para tipos "hoja" (sin expansión recursiva):
    LINE, LWPOLYLINE, POINT, CIRCLE, ARC, TEXT, MTEXT, HATCH, ELLIPSE."""

    if isinstance(entity, Line):
        return DxfEntity(
            id=eid, type="LINE", layer=layer_name, color=color,
            start=_vec2_to_dict(entity.dxf.start),
            end=_vec2_to_dict(entity.dxf.end),
        )

    if isinstance(entity, LWPolyline):
        pts = [{"x": float(p[0]), "y": float(p[1])}
               for p in entity.get_points(format="xy")]
        return DxfEntity(
            id=eid, type="LWPOLYLINE", layer=layer_name, color=color,
            vertices=pts, closed=entity.closed,
        )

    if isinstance(entity, Point):
        return DxfEntity(
            id=eid, type="POINT", layer=layer_name, color=color,
            start=_vec2_to_dict(entity.dxf.location),
        )

    # Arc must be checked BEFORE Circle because Arc is a subclass of Circle;
    # otherwise isinstance(entity, Circle) catches arcs and they render as full circles.
    if isinstance(entity, Arc):
        return DxfEntity(
            id=eid, type="ARC", layer=layer_name, color=color,
            center=_vec2_to_dict(entity.dxf.center),
            radius=float(entity.dxf.radius),
            start_angle=float(entity.dxf.start_angle),
            end_angle=float(entity.dxf.end_angle),
        )

    if isinstance(entity, Circle):
        return DxfEntity(
            id=eid, type="CIRCLE", layer=layer_name, color=color,
            center=_vec2_to_dict(entity.dxf.center),
            radius=float(entity.dxf.radius),
        )

    if isinstance(entity, Text):
        halign = int(entity.dxf.halign) if entity.dxf.hasattr("halign") else 0
        valign = int(entity.dxf.valign) if entity.dxf.hasattr("valign") else 0
        # Cuando hay alineación (halign o valign != 0), el punto de inserción
        # es el punto de alineación. El insert real se calcula después.
        insert = _vec2_to_dict(entity.dxf.insert)
        align_point = None
        if halign != 0 or valign != 0:
            align_point = _vec2_to_dict(entity.dxf.insert)
            # Para ALIGNED/FIT (halign 3/5), usar align_point como referencia
            if hasattr(entity.dxf, "align_point") and entity.dxf.hasattr("align_point"):
                align_point = _vec2_to_dict(entity.dxf.align_point)
        return DxfEntity(
            id=eid, type="TEXT", layer=layer_name, color=color,
            start=insert,
            text=entity.dxf.text if entity.dxf.hasattr("text") else "",
            height=float(entity.dxf.height) if entity.dxf.hasattr("height") else 2.5,
            rotation=float(entity.dxf.rotation) if entity.dxf.hasattr("rotation") else 0,
            halign=halign, valign=valign, align_point=align_point,
        )

    if isinstance(entity, MText):
        # OJO: entity.text devuelve el texto CRUDO con códigos de formato
        # embebidos (\P, \C1;, {\fArial|b0;...}, etc.). plain_text() los
        # limpia y es lo que en realidad se debe mostrar.
        try:
            text = entity.plain_text()
        except Exception:
            text = entity.text if hasattr(entity, "text") else ""
        # get_rotation() resuelve tanto dxf.rotation como el vector
        # text_direction (muy común en DXF exportados desde Civil3D/Revit,
        # y con el que dxf.hasattr("rotation") da False).
        try:
            rotation = float(entity.get_rotation())
        except Exception:
            rotation = float(entity.dxf.rotation) if entity.dxf.hasattr("rotation") else 0.0
        # MTEXT attachment_point: 1-9 combina halign+valign
        ap = int(entity.dxf.attachment_point) if entity.dxf.hasattr("attachment_point") else 1
        _MTEXT_HA = {1: 0, 2: 1, 3: 2, 4: 0, 5: 1, 6: 2, 7: 0, 8: 1, 9: 2}
        _MTEXT_VA = {1: 3, 2: 3, 3: 3, 4: 2, 5: 2, 6: 2, 7: 1, 8: 1, 9: 1}
        return DxfEntity(
            id=eid, type="MTEXT", layer=layer_name, color=color,
            start=_vec2_to_dict(entity.dxf.insert),
            text=text,
            height=float(entity.dxf.char_height) if entity.dxf.hasattr("char_height") else 2.5,
            rotation=rotation,
            halign=_MTEXT_HA.get(ap, 0), valign=_MTEXT_VA.get(ap, 0),
        )

    if isinstance(entity, Hatch):
        try:
            loops: list[list[dict]] = []
            for path in entity.paths:
                verts = _polyline_path_vertices(path)
                if len(verts) < 3:
                    verts = _edge_path_vertices(path)
                if len(verts) >= 3:
                    loops.append(verts)
            if loops:
                best = max(loops, key=_polygon_area)
                pat = entity.dxf.pattern_name if entity.dxf.hasattr("pattern_name") else None
                solid = bool(entity.dxf.solid_fill) if entity.dxf.hasattr("solid_fill") else (pat is None)
                p_angle = float(entity.dxf.pattern_angle) if entity.dxf.hasattr("pattern_angle") else 0.0
                p_scale = float(entity.dxf.pattern_scale) if entity.dxf.hasattr("pattern_scale") else 1.0
                return DxfEntity(
                    id=eid, type="HATCH", layer=layer_name, color=color,
                    vertices=best, pattern_name=pat,
                    solid_fill=solid, pattern_angle=p_angle, pattern_scale=p_scale,
                )
        except Exception:
            pass
        return None

    if isinstance(entity, Ellipse):
        major_axis = _vec2_to_dict(entity.dxf.major_axis) if entity.dxf.hasattr("major_axis") else None
        ratio_val = float(entity.dxf.ratio) if entity.dxf.hasattr("ratio") else None
        major_r = minor_r = None
        if major_axis:
            major_r = math.hypot(major_axis["x"], major_axis["y"])
            if ratio_val is not None:
                minor_r = major_r * ratio_val
        # start_param/end_param: barrido en radianes dentro de la parametrización
        # propia de la elipse. Una elipse "completa" normalmente trae 0 y 2π;
        # un ARC dentro de un bloque con escala no uniforme se puede convertir
        # a un ELLIPSE parcial por ezdxf al expandir el INSERT, así que hay que
        # respetar este rango o se dibuja un óvalo/círculo completo donde debía
        # ir solo un arco (p.ej. ganchos/dobleces de varilla en símbolos).
        sp = float(entity.dxf.start_param) if entity.dxf.hasattr("start_param") else 0.0
        ep = float(entity.dxf.end_param) if entity.dxf.hasattr("end_param") else 2 * math.pi
        return DxfEntity(
            id=eid, type="ELLIPSE", layer=layer_name, color=color,
            center=_vec2_to_dict(entity.dxf.center),
            major_radius=major_r, minor_radius=minor_r,
            major_axis=major_axis, ratio=ratio_val,
            start_param=sp, end_param=ep,
        )

    return None


def _expand_insert(insert_entity, layer_map, ensure_layer, next_id, out,
                    parent_layer: str, parent_color, depth: int) -> None:
    """Expande un INSERT (bloque) a su geometría real transformada
    (posición, escala, rotación ya aplicadas) usando virtual_entities()
    de ezdxf, en vez de dibujar solo un marcador genérico.

    Las sub-entidades de un bloque que están en layer "0" o con color
    BYBLOCK heredan la capa/color del INSERT que las coloca (igual que
    hace AutoCAD); esto se resuelve aquí manualmente porque
    virtual_entities() no lo hace automáticamente.
    """
    if depth >= _MAX_INSERT_DEPTH:
        return

    subs = None
    try:
        subs = list(insert_entity.virtual_entities())
    except Exception as exc:
        logging.warning("virtual_entities() failed for block '%s': %s",
                        insert_entity.dxf.name if insert_entity.dxf.hasattr("name") else "?", exc)
        subs = None

    if not subs:
        # Fallback: no se pudo resolver el bloque (definición faltante,
        # bloque externo no cargado, etc.) — al menos mostramos un
        # marcador con el nombre para que no desaparezca silenciosamente.
        start = _vec2_to_dict(insert_entity.dxf.insert)
        out.append(DxfEntity(
            id=next_id(), type="INSERT", layer=parent_layer, color=parent_color,
            start=start,
            block_name=insert_entity.dxf.name if insert_entity.dxf.hasattr("name") else "",
            rotation=float(insert_entity.dxf.rotation) if insert_entity.dxf.hasattr("rotation") else 0,
        ))
        return

    for sub in subs:
        if not sub.is_alive:
            continue
        sub_layer_raw = sub.dxf.layer if sub.dxf.hasattr("layer") else "0"
        effective_layer = parent_layer if sub_layer_raw in ("0", "", None) else sub_layer_raw
        layer = ensure_layer(effective_layer)

        sub_color = _resolve_color(sub, layer.color, byblock_color=parent_color)
        layer.entity_count += 1

        if isinstance(sub, Insert):
            _expand_insert(sub, layer_map, ensure_layer, next_id, out,
                            parent_layer=effective_layer, parent_color=sub_color,
                            depth=depth + 1)
            continue
        if isinstance(sub, Dimension):
            _expand_dimension(sub, layer_map, ensure_layer, next_id, out,
                               layer_name=effective_layer, color=sub_color,
                               eid=next_id())
            continue

        leaf = _leaf_entity(sub, next_id(), effective_layer, sub_color)
        if leaf is not None:
            out.append(leaf)


def _expand_dimension(dim_entity, layer_map, ensure_layer, next_id, out,
                      layer_name: str, color, eid: str) -> None:
    """Expande una DIMENSION (cota) a su geometría real (líneas de cota,
    líneas de extensión, flechas, texto de medida) vía virtual_entities().

    Una entidad DIMENSION en DXF normalmente NO trae la geometría
    dibujable directamente en sus campos: solo los "defpoints" (puntos
    de definición) y el texto/estilo. La geometría real se genera bajo
    demanda en un bloque anónimo; hay que forzar su generación con
    ``render()`` antes de poder expandirla con virtual_entities().
    """
    try:
        dim_entity.render()
    except Exception:
        pass

    try:
        subs = list(dim_entity.virtual_entities())
    except Exception:
        subs = []

    if subs:
        for sub in subs:
            if not sub.is_alive:
                continue
            sub_layer_raw = sub.dxf.layer if sub.dxf.hasattr("layer") else "0"
            # Los puntos de definición (capa "Defpoints") son auxiliares,
            # invisibles por convención en AutoCAD — no se dibujan.
            if sub_layer_raw == "Defpoints" or isinstance(sub, Point):
                continue
            effective_layer = layer_name if sub_layer_raw in ("0", "", None) else sub_layer_raw
            layer = ensure_layer(effective_layer)
            sub_color = _resolve_color(sub, layer.color, byblock_color=color)
            layer.entity_count += 1

            if isinstance(sub, Insert):
                _expand_insert(sub, layer_map, ensure_layer, next_id, out,
                                parent_layer=effective_layer, parent_color=sub_color,
                                depth=1)
                continue

            leaf = _leaf_entity(sub, next_id(), effective_layer, sub_color)
            if leaf is not None:
                out.append(leaf)
        return

    # Fallback: no se pudo renderizar la geometría real (dimstyle roto,
    # bloque de geometría ausente, etc.) — al menos dibujamos una línea
    # simple entre los puntos de definición con el texto de medida.
    try:
        p1 = _vec2_to_dict(dim_entity.dxf.defpoint2) if dim_entity.dxf.hasattr("defpoint2") else None
        p2 = _vec2_to_dict(dim_entity.dxf.defpoint3) if dim_entity.dxf.hasattr("defpoint3") else None
        dp = _vec2_to_dict(dim_entity.dxf.defpoint) if dim_entity.dxf.hasattr("defpoint") else None
        txt = dim_entity.dxf.text if dim_entity.dxf.hasattr("text") else ""
        meas = dim_entity.get_measurement() if hasattr(dim_entity, "get_measurement") else None
        if p1 and p2:
            out.append(DxfEntity(
                id=eid, type="DIMENSION", layer=layer_name, color=color,
                start=p1, end=p2, center=dp,
                text=txt if txt and txt != "<>" else (f"{meas:.2f}" if meas is not None else ""),
                height=2.5,
            ))
    except Exception:
        pass


# ── Parser principal ──────────────────────────────────────────────

def parse_dxf(data: bytes | str | Path) -> DxfParseResult:
    """Parsea un archivo DXF y devuelve entidades normalizadas.

    Args:
        data: bytes del DXF, ruta como string, o Path.
    """
    if isinstance(data, bytes):
        doc = ezdxf.readbytes(data)
    elif isinstance(data, (str, Path)):
        doc = ezdxf.readfile(str(data))
    else:
        raise ValueError(f"Tipo de entrada no soportado: {type(data)}")

    msp = doc.modelspace()

    # Detectar unidades
    units = _detect_units(doc)

    # Collect layers (color efectivo: true color si existe, si no ACI)
    layer_map: dict[str, DxfLayer] = {}
    for layer in doc.layers:
        name = layer.dxf.name
        layer_map[name] = DxfLayer(name=name, color=_layer_effective_color(layer))

    def _ensure_layer(name: str) -> DxfLayer:
        if name not in layer_map:
            layer_map[name] = DxfLayer(name=name, color=7)
        return layer_map[name]

    # Contador de ids compartido por todas las entidades, incluidas las
    # expandidas recursivamente desde INSERT/DIMENSION.
    _id_counter = [0]

    def _next_id() -> str:
        _id_counter[0] += 1
        return f"e{_id_counter[0]}"

    entities: list[DxfEntity] = []

    for entity in msp:
        if not entity.is_alive:
            continue
        _dispatch_entity(entity, layer_map, _ensure_layer, _next_id, entities,
                          byblock_color=None, depth=0)

    # Compute extents
    extents_min, extents_max = _compute_extents(entities)

    return DxfParseResult(
        entities=entities,
        layers=sorted(layer_map.values(), key=lambda l: l.name),
        extents_min=extents_min,
        extents_max=extents_max,
        units=units,
        doc=doc,
    )


def _detect_units(doc) -> str:
    """Detecta las unidades del DXF desde $INSUNITS."""
    try:
        insunits = doc.header.get("$INSUNITS", 0)
        _map = {
            0: "unitless", 1: "inches", 2: "feet", 3: "miles",
            4: "mm", 5: "cm", 6: "m", 7: "km",
        }
        return _map.get(insunits, "unitless")
    except Exception:
        return "unitless"


def _compute_extents(entities: list[DxfEntity]) -> tuple[dict, dict]:
    """Calcula extents mínimos y máximos de todas las entidades."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for e in entities:
        pts = []
        if e.start:
            pts.append(e.start)
        if e.end:
            pts.append(e.end)
        if e.center:
            pts.append(e.center)
            if e.radius:
                min_x = min(min_x, e.center["x"] - e.radius)
                max_x = max(max_x, e.center["x"] + e.radius)
                min_y = min(min_y, e.center["y"] - e.radius)
                max_y = max(max_y, e.center["y"] + e.radius)
        if e.vertices:
            pts.extend(e.vertices)

        for p in pts:
            min_x = min(min_x, p["x"])
            max_x = max(max_x, p["x"])
            min_y = min(min_y, p["y"])
            max_y = max(max_y, p["y"])

    if min_x == float("inf"):
        return {"x": 0, "y": 0}, {"x": 100, "y": 100}

    return {"x": min_x, "y": min_y}, {"x": max_x, "y": max_y}


def entities_to_json(entities: list[DxfEntity]) -> str:
    """Serializa entidades a JSON para传输 al frontend."""
    return json.dumps([e.to_dict() for e in entities], ensure_ascii=False)
