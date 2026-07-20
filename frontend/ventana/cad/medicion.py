"""
medicion.py
===========
Herramientas de medición para el visor CAD.

Funciones puras de cálculo geométrico: distancia, área, perímetro,
snap candidates, y formato de resultados.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Pt2:
    x: float
    y: float


def calculate_distance(p1: Pt2, p2: Pt2) -> float:
    """Distancia euclidiana entre dos puntos."""
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    return math.sqrt(dx * dx + dy * dy)


def calculate_area(points: list[Pt2]) -> float:
    """Área de polígono cerrado (Shoelace formula)."""
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        area += points[i].x * points[j].y
        area -= points[j].x * points[i].y
    return abs(area) / 2.0


def calculate_perimeter(points: list[Pt2], closed: bool = False) -> float:
    """Perímetro de polilínea."""
    if len(points) < 2:
        return 0.0
    total = 0.0
    for i in range(len(points) - 1):
        total += calculate_distance(points[i], points[i + 1])
    if closed and len(points) >= 3:
        total += calculate_distance(points[-1], points[0])
    return total


def point_to_segment_distance(p: Pt2, a: Pt2, b: Pt2) -> float:
    """Distancia mínima de un punto a un segmento AB."""
    dx = b.x - a.x
    dy = b.y - a.y
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return calculate_distance(p, a)
    t = max(0, min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len_sq))
    proj = Pt2(a.x + t * dx, a.y + t * dy)
    return calculate_distance(p, proj)


def segment_midpoint(a: Pt2, b: Pt2) -> Pt2:
    """Punto medio de un segmento."""
    return Pt2((a.x + b.x) / 2, (a.y + b.y) / 2)


def polygon_centroid(points: list[Pt2]) -> Pt2:
    """Centroide de un polígono."""
    if not points:
        return Pt2(0, 0)
    cx = sum(p.x for p in points) / len(points)
    cy = sum(p.y for p in points) / len(points)
    return Pt2(cx, cy)


def point_in_polygon(p: Pt2, vertices: list[Pt2]) -> bool:
    """Test ray-casting point-in-polygon."""
    inside = False
    n = len(vertices)
    for i in range(n):
        j = (i - 1) % n
        vi = vertices[i]
        vj = vertices[j]
        if ((vi.y > p.y) != (vj.y > p.y) and
                p.x < (vj.x - vi.x) * (p.y - vi.y) / (vj.y - vi.y) + vi.x):
            inside = not inside
    return inside


def is_self_intersecting(points: list[Pt2]) -> bool:
    """Detecta si un polígono se auto-intersecta."""
    n = len(points)
    if n < 4:
        return False
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # skip adjacent
            a1 = points[i]
            a2 = points[(i + 1) % n]
            b1 = points[j]
            b2 = points[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _segments_intersect(a1: Pt2, a2: Pt2, b1: Pt2, b2: Pt2) -> bool:
    """Test de intersección entre dos segmentos."""
    def orient(p, q, r):
        val = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)
        if val > 1e-12:
            return 1
        if val < -1e-12:
            return -1
        return 0

    def on_seg(p, q, r):
        return (min(p.x, r.x) - 1e-9 <= q.x <= max(p.x, r.x) + 1e-9 and
                min(p.y, r.y) - 1e-9 <= q.y <= max(p.y, r.y) + 1e-9)

    o1 = orient(a1, a2, b1)
    o2 = orient(a1, a2, b2)
    o3 = orient(b1, b2, a1)
    o4 = orient(b1, b2, a2)

    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_seg(a1, b1, a2):
        return True
    if o2 == 0 and on_seg(a1, b2, a2):
        return True
    if o3 == 0 and on_seg(b1, a1, b2):
        return True
    if o4 == 0 and on_seg(b1, a2, b2):
        return True
    return False


def format_measurement(value: float, unit: str) -> str:
    """Formatea una medición con unidad."""
    if not math.isfinite(value):
        return f"0 {unit}"
    if unit in ("m²", "m2", "ft²", "ft2"):
        if abs(value) < 0.01:
            return f"{value:.4f} {unit}"
        if abs(value) < 1:
            return f"{value:.3f} {unit}"
        return f"{value:.2f} {unit}"
    if value >= 1000:
        return f"{value / 1000:.2f} k{unit}"
    if value != 0 and abs(value) < 0.01:
        return f"{value * 1000:.2f} m{unit}"
    return f"{value:.2f} {unit}"


def unit_factor_to_meters(units: str) -> float:
    """Convierte un string de unidad a factor metros."""
    units = units.lower().strip()
    return {
        "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000,
        "inches": 0.0254, "in": 0.0254,
        "feet": 0.3048, "ft": 0.3048,
    }.get(units, 1.0)
