"""
busqueda_texto.py
=================
Búsqueda de texto sobre entidades TEXT/MTEXT en el dibujo DXF.

A diferencia del PDF (que reconstruye text runs de pdf.js), un DXF ya
lleva TEXT/MTEXT con su contenido y punto de inserción en unidades de dibujo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextMatch:
    entity_id: str
    text: str
    snippet: str
    box: dict  # {minX, minY, maxX, maxY}
    center: dict  # {x, y}
    index: int = 0


SNIPPET_RADIUS = 28


def text_box_for_entity(entity: dict) -> dict | None:
    """Estima el box world-space de una entidad TEXT."""
    if entity.get("type") != "TEXT":
        return None
    start = entity.get("start")
    text = entity.get("text")
    if not start or not text:
        return None
    h = entity.get("height", 2.5) or 2.5
    lines = text.split("\n")
    longest = max(len(line) for line in lines) if lines else 0
    width = max(h, h * longest * 0.6)
    height = h * len(lines) * 1.3
    return {
        "minX": start["x"],
        "maxX": start["x"] + width,
        "minY": start["y"],
        "maxY": start["y"] + height,
    }


def _build_snippet(run_text: str, match_start: int, match_len: int) -> str:
    flat = re.sub(r"\s+", " ", run_text)
    start = max(0, match_start - SNIPPET_RADIUS)
    end = min(len(run_text), match_start + match_len + SNIPPET_RADIUS)
    s = re.sub(r"\s+", " ", run_text[start:end]).strip()
    if start > 0:
        s = f"…{s}"
    if end < len(run_text):
        s = f"{s}…"
    return s or flat.strip()


def find_text_matches(entities: list[dict], query: str) -> list[TextMatch]:
    """Encuentra entidades TEXT cuyo contenido contiene ``query`` (case-insensitive).

    Retorna en orden de lectura: mayor Y primero, luego menor X.
    """
    q = query.strip().lower()
    if not q:
        return []

    hits: list[dict] = []
    for e in entities:
        if e.get("type") != "TEXT":
            continue
        text = e.get("text", "")
        start = e.get("start")
        if not text or not start:
            continue
        pos = text.lower().find(q)
        if pos == -1:
            continue
        box = text_box_for_entity(e)
        if not box:
            continue
        hits.append({
            "entity_id": e.get("id", ""),
            "text": text,
            "snippet": _build_snippet(text, pos, len(q)),
            "box": box,
            "center": {
                "x": (box["minX"] + box["maxX"]) / 2,
                "y": (box["minY"] + box["maxY"]) / 2,
            },
        })

    hits.sort(key=lambda h: (-h["center"]["y"], h["center"]["x"]))
    return [TextMatch(**h, index=i) for i, h in enumerate(hits)]
