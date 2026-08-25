"""
ortho.py
========
Ángulo de bloqueo a 45° para dibujo con Shift presionado.

Cuando el usuario mantiene Shift mientras coloca el siguiente punto,
el cursor se snapping al rayo más cercano en 0°/45°/90°/135° desde
el último punto comprometido. Comportamiento CAD "ortho" sin toggle.
"""

from __future__ import annotations

import math

ANGLE_LOCK_STEP_DEG = 45
_STEP_RAD = math.radians(ANGLE_LOCK_STEP_DEG)


def snap_to_ortho(anchor_x: float, anchor_y: float,
                  cursor_x: float, cursor_y: float) -> tuple[float, float]:
    """Snap cursor al rayo 45° más cercano desde anchor.

    Preserva la distancia raw; solo cambia la dirección.
    Si anchor y cursor coinciden, retorna anchor.
    """
    dx = cursor_x - anchor_x
    dy = cursor_y - anchor_y
    dist = math.hypot(dx, dy)
    if dist == 0:
        return anchor_x, anchor_y
    raw = math.atan2(dy, dx)
    snapped = round(raw / _STEP_RAD) * _STEP_RAD
    return anchor_x + dist * math.cos(snapped), anchor_y + dist * math.sin(snapped)


def snap_angle_degrees(anchor_x: float, anchor_y: float,
                       cursor_x: float, cursor_y: float) -> float:
    """Retorna el ángulo snapped en grados [-180, 180]."""
    dx = cursor_x - anchor_x
    dy = cursor_y - anchor_y
    raw = math.atan2(dy, dx)
    snapped = round(raw / _STEP_RAD) * _STEP_RAD
    return math.degrees(snapped)
