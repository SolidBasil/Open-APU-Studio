"""
auto_quantify.py
================
Cuantificación automática por capa de entidades DXF.

Cada entidad se mide según su tipo (LINE → longitud, LWPOLYLINE cerrado → área,
CIRCLE → área, ARC → longitud de arco, ELLIPSE → área) y se agrega por capa.
Se selecciona la medida "headline" por capa: área > longitud > conteo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .medicion import Pt2, calculate_area, calculate_distance, calculate_perimeter


TAU = math.pi * 2
EPS = 1e-9


@dataclass
class LayerQuantity:
    layer: str
    area: float = 0.0
    length: float = 0.0
    count: int = 0
    primary: str = "count"  # "area" | "length" | "count"
    quantity: float = 0.0
    unit: str = "nr"
    available: list[str] = field(default_factory=list)


def _arc_sweep(start_angle: float = 0.0, end_angle: float = 0.0) -> float:
    """Sweep angle de un arco en radianes, normalizado a (0, 2π]."""
    s = end_angle - start_angle
    while s <= 0:
        s += TAU
    while s > TAU + EPS:
        s -= TAU
    return s


def _ellipse_radii(entity: dict) -> tuple[float, float] | None:
    """Major/minor radii de una elipse desde formato ezdxf."""
    if entity.get("major_radius") is not None and entity.get("minor_radius") is not None:
        return entity["major_radius"], entity["minor_radius"]
    ma = entity.get("major_axis")
    ratio = entity.get("ratio")
    if ma and ratio is not None:
        a = math.hypot(ma["x"], ma["y"])
        return a, a * ratio
    return None


def unit_for_measure(measure: str) -> str:
    """Unidad legible para una medida."""
    return {"area": "m²", "length": "m"}.get(measure, "nr")


def _pick_primary(area: float, length: float) -> str:
    if area > EPS:
        return "area"
    if length > EPS:
        return "length"
    return "count"


def quantify_by_layer(entities: list[dict], scale: float = 1.0) -> list[LayerQuantity]:
    """Agrega entidades por capa en área/longitud/conteo.

    ``scale`` convierte unidades DXF crudas a metros: lineales × scale,
    areales × scale².
    """
    buckets: dict[str, dict] = {}

    for e in entities:
        layer = e.get("layer") or "0"
        b = buckets.setdefault(layer, {"area": 0.0, "length": 0.0, "count": 0})
        b["count"] += 1
        etype = e.get("type", "")

        if etype == "LWPOLYLINE":
            verts = e.get("vertices")
            if verts and len(verts) >= 2:
                pts = [Pt2(v["x"], v["y"]) for v in verts]
                if e.get("closed") and len(pts) >= 3:
                    b["area"] += calculate_area(pts)
                else:
                    b["length"] += calculate_perimeter(pts, False)

        elif etype == "HATCH":
            verts = e.get("vertices")
            if verts and len(verts) >= 3:
                pts = [Pt2(v["x"], v["y"]) for v in verts]
                b["area"] += calculate_area(pts)

        elif etype == "LINE":
            s, end = e.get("start"), e.get("end")
            if s and end:
                b["length"] += calculate_distance(Pt2(s["x"], s["y"]), Pt2(end["x"], end["y"]))

        elif etype == "CIRCLE":
            r = e.get("radius")
            if r is not None:
                b["area"] += math.pi * r * r

        elif etype == "ARC":
            r = e.get("radius")
            if r is not None:
                b["length"] += r * _arc_sweep(e.get("start_angle", 0), e.get("end_angle", 0))

        elif etype == "ELLIPSE":
            radii = _ellipse_radii(e)
            if radii:
                a, b_val = radii
                b["area"] += math.pi * a * b_val

    area_scale = scale * scale
    r3 = lambda n: round(n * 1000) / 1000
    rank = {"area": 0, "length": 1, "count": 2}

    result = []
    for layer, v in buckets.items():
        area = r3(v["area"] * area_scale)
        length = r3(v["length"] * scale)
        count = v["count"]
        primary = _pick_primary(area, length)
        available = []
        if area > EPS:
            available.append("area")
        if length > EPS:
            available.append("length")
        available.append("count")
        quantity = area if primary == "area" else length if primary == "length" else count
        result.append(LayerQuantity(
            layer=layer, area=area, length=length, count=count,
            primary=primary, quantity=quantity, unit=unit_for_measure(primary),
            available=available,
        ))

    result.sort(key=lambda x: (rank.get(x.primary, 9), -x.quantity))
    return result


def quantity_for(row: LayerQuantity, measure: str) -> float:
    """Cantidad de una capa bajo una medida explícita."""
    if measure == "area":
        return row.area
    if measure == "length":
        return row.length
    return row.count
