"""
event_bus.py
============
Bus de eventos semánticos para Open APU Studio.

Emite notificaciones tras cada escritura exitosa (post-commit).
Los eventos contienen el registro completo, no solo los campos modificados.

Reglas:
- No se encadenan eventos (un handler no puede emitir otro evento).
- Cada handler se ejecuta en try/except — un widget roto no rompe la cadena.
- Los eventos representan cambios CONFIRMADOS, no cambios intentados.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Callable


# ── Eventos semánticos ─────────────────────────────────────────────

class Evento:
    """Base para todos los eventos. No instanciar directamente."""


@dataclass
class InsumoActualizado(Evento):
    insumo_id: int
    cambios: dict[str, Any]
    registro: dict[str, Any]


@dataclass
class ConceptoActualizado(Evento):
    concepto_id: int
    cambios: dict[str, Any]
    registro: dict[str, Any]


@dataclass
class ApuComponenteActualizado(Evento):
    componente_id: int
    cambios: dict[str, Any]
    registro: dict[str, Any]


@dataclass
class FactoresSobrecostoActualizados(Evento):
    proyecto_id: int
    registro: dict[str, Any]


@dataclass
class NodoInsertado(Evento):
    nodo_id: int
    tipo: str
    padre_id: int | None


@dataclass
class NodoEliminado(Evento):
    nodo_id: int
    tipo: str


@dataclass
class ProyectoRecalculado(Evento):
    proyecto_id: int


@dataclass
class NotaInsertada(Evento):
    nota_id: int
    concepto_id: int


@dataclass
class NotaResuelta(Evento):
    nota_id: int


# ── Bus de eventos ─────────────────────────────────────────────────

class EventBus:
    """Bus de eventos simple. Suscribe callbacks a tipos de evento.

    Uso:
        bus = EventBus()
        bus.suscribir(InsumoActualizado, mi_handler)

        # Después de un COMMIT exitoso:
        bus.emit(InsumoActualizado(insumo_id=42, cambios={...}, registro={...}))
    """

    def __init__(self):
        self._suscriptores: dict[type[Evento], list[Callable]] = {}

    def suscribir(self, tipo_evento: type[Evento], callback: Callable) -> None:
        """Registra un callback para un tipo de evento."""
        self._suscriptores.setdefault(tipo_evento, []).append(callback)

    def emit(self, evento: Evento) -> None:
        """Emitir evento a todos los suscriptores registrados.

        Cada callback se ejecuta en try/except individual.
        Un handler que lanza excepción no detiene a los demás.
        """
        for cb in self._suscriptores.get(type(evento), []):
            try:
                cb(evento)
            except Exception:
                traceback.print_exc()

    def suscriptores_count(self, tipo_evento: type[Evento]) -> int:
        """Número de suscriptores para un tipo de evento (útil para debugging)."""
        return len(self._suscriptores.get(tipo_evento, []))
