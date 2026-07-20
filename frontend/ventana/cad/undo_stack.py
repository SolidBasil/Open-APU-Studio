"""
undo_stack.py
=============
Pila de undo/redo lineal para mutaciones de anotaciones DWG.

Cada entrada captura suficiente info para revertir la mutación:
  - create → undo borra la anotación
  - delete → undo re-crea desde snapshot
  - edit   → undo patchea back to ``before``; redo aplica ``after``

Capacidad máxima: MAX_STACK (50). Las entradas más viejas se descartan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_STACK = 50


@dataclass
class AnnotationSnapshot:
    id: str
    annotation_type: str
    points: list[dict] = field(default_factory=list)
    text: str | None = None
    color: str = "#000000"
    measurement_value: float | None = None
    measurement_unit: str | None = None
    layer_name: str | None = None


@dataclass
class UndoEntry:
    kind: str  # "create" | "delete" | "edit"
    id: str = ""
    snapshot: AnnotationSnapshot | None = None
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)


@dataclass
class UndoState:
    undo: list[UndoEntry] = field(default_factory=list)
    redo: list[UndoEntry] = field(default_factory=list)


def empty_undo_state() -> UndoState:
    return UndoState()


def push_undo(state: UndoState, entry: UndoEntry) -> UndoState:
    """Push nueva entrada. Limpia el redo tail (comportamiento lineal estándar)."""
    next_undo = state.undo + [entry]
    while len(next_undo) > MAX_STACK:
        next_undo.pop(0)
    return UndoState(undo=next_undo, redo=[])


def pop_undo(state: UndoState) -> tuple[UndoState, UndoEntry | None]:
    """Mueve la entrada top de undo a redo. Retorna (nueva_state, entrada)."""
    if not state.undo:
        return state, None
    entry = state.undo[-1]
    next_undo = state.undo[:-1]
    next_redo = state.redo + [entry]
    while len(next_redo) > MAX_STACK:
        next_redo.pop(0)
    return UndoState(undo=next_undo, redo=next_redo), entry


def pop_redo(state: UndoState) -> tuple[UndoState, UndoEntry | None]:
    """Mueve la entrada top de redo a undo. Retorna (nueva_state, entrada)."""
    if not state.redo:
        return state, None
    entry = state.redo[-1]
    next_redo = state.redo[:-1]
    next_undo = state.undo + [entry]
    while len(next_undo) > MAX_STACK:
        next_undo.pop(0)
    return UndoState(undo=next_undo, redo=next_redo), entry


def can_undo(state: UndoState) -> bool:
    return len(state.undo) > 0


def can_redo(state: UndoState) -> bool:
    return len(state.redo) > 0


def snapshot_from(ann: dict) -> AnnotationSnapshot:
    """Construye un snapshot desde un dict de anotación."""
    return AnnotationSnapshot(
        id=ann.get("id", ""),
        annotation_type=ann.get("type", ann.get("annotation_type", "")),
        points=ann.get("points", []),
        text=ann.get("text"),
        color=ann.get("color", "#000000"),
        measurement_value=ann.get("measurement_value"),
        measurement_unit=ann.get("measurement_unit"),
        layer_name=ann.get("layer_name"),
    )
