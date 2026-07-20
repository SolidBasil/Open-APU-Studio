"""
agregacion.py
=============
Agregación de mediciones para selecciones múltiples de entidades DXF.

Σ área / Σ perímetro / Σ longitud sobre un conjunto heterogéneo de entidades.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .medicion import Pt2, calculate_area, calculate_distance, calculate_perimeter


@dataclass
class GroupAggregate:
    area: float = 0.0
    perimeter: float = 0.0
    length: float = 0.0
    count: int = 0
    by_type: dict[str, int] = field(default_factory=dict)


def aggregate_entities(entities: list[dict], scale: float = 1.0) -> GroupAggregate:
    """Σ measurements para un grupo de entidades.

    Reglas:
      - LWPOLYLINE cerrado → área + perímetro
      - LWPOLYLINE abierto → longitud
      - LINE → longitud
      - CIRCLE → área (π·r²)
      - ARC / ELLIPSE / HATCH / TEXT / INSERT / POINT → solo conteo
    """
    if not entities:
        return GroupAggregate()

    agg = GroupAggregate()

    for e in entities:
        etype = e.get("type", "")
        agg.by_type[etype] = agg.by_type.get(etype, 0) + 1

        if etype == "LWPOLYLINE":
            verts = e.get("vertices")
            if verts and len(verts) >= 2:
                pts = [Pt2(v["x"], v["y"]) for v in verts]
                closed = bool(e.get("closed"))
                if closed and len(pts) >= 3:
                    agg.area += calculate_area(pts)
                    agg.perimeter += calculate_perimeter(pts, True)
                else:
                    agg.length += calculate_perimeter(pts, False)
            agg.count += 1

        elif etype == "LINE":
            s, end = e.get("start"), e.get("end")
            if s and end:
                agg.length += calculate_distance(Pt2(s["x"], s["y"]), Pt2(end["x"], end["y"]))
            agg.count += 1

        elif etype == "CIRCLE":
            r = e.get("radius")
            if r is not None:
                agg.area += math.pi * r * r
            agg.count += 1

    area_scale = scale * scale
    r3 = lambda n: round(n * 1000) / 1000
    agg.area = r3(agg.area * area_scale)
    agg.perimeter = r3(agg.perimeter * scale)
    agg.length = r3(agg.length * scale)
    return agg
