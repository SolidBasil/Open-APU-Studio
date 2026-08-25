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
from dataclasses import dataclass
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
    usuario_id: int = 1  # SRV-08: quién disparó el recálculo


@dataclass
class ProyectoAbierto(Evento):
    """Se emite cuando un proyecto queda completamente wireado (EventBus,
    DataService, Api ya instalados) — al abrir, importar o duplicar y abrir
    un .db. Ver GestionProyectosMixin._wire_servicios().

    No sustituye a poblar()/conectar_eventos() de los widgets que arma cada
    pestaña: esos ya reciben el Api/EventBus correctos al construirse. Este
    evento es para subsistemas que necesiten reaccionar a "hay un proyecto
    nuevo abierto" sin depender de que se reconstruya un widget en concreto
    (p. ej. título de ventana, undo stack, barra de estado)."""
    proyecto_id: int
    db_path: str


@dataclass
class GeneradorActualizado(Evento):
    """Se emite cuando un generador o sus renglones cambian.
    carries generador_id + conceptos_ids afectados para que el
    frontend refresque tanto el panel de generadores como el árbol."""
    generador_id: int
    conceptos_ids: list[int]


@dataclass
class VariableFormulaActualizada(Evento):
    variable_id: int
    cambios: dict[str, Any]
    registro: dict[str, Any]


@dataclass
class IndirectoActualizado(Evento):
    """Se emite tras crear, actualizar, eliminar o recalcular un indirecto
    (campo/oficina). proyecto_id (no el id del indirecto individual) es lo
    que necesita el panel de indirectos y cualquier widget de sobrecostos
    para saber qué proyecto refrescar."""
    proyecto_id: int


@dataclass
class ProyectoCerrado(Evento):
    """Se emite justo antes de desmontar los servicios (EventBus,
    DataService, Api) del proyecto que se está cerrando. Ver
    GestionProyectosMixin._on_cerrar_proyecto() / _on_eliminar_proyecto()."""
    proyecto_id: int


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

    def desuscribir(self, tipo_evento: type[Evento], callback: Callable) -> None:
        """Retira un callback registrado previamente.

        Los widgets deben llamar esto al ser removidos de la UI (ver
        TablaArbol/TablaInsumos.desconectar_eventos()) — de lo contrario
        quedan "zombis": el objeto Python sigue vivo (referenciado por esta
        misma lista) aunque su contraparte Qt/C++ ya fue destruida al
        quitar la pestaña, y la próxima vez que se emita un evento
        RuntimeError: libshiboken... object already deleted.

        No lanza si el callback ya no está registrado (idempotente).
        """
        lista = self._suscriptores.get(tipo_evento)
        if lista and callback in lista:
            lista.remove(callback)

    def emit(self, evento: Evento) -> None:
        """Emitir evento a todos los suscriptores registrados.

        Cada callback se ejecuta en try/except individual.
        Un handler que lanza excepción no detiene a los demás.

        Red de seguridad: si un callback falla porque su widget Qt ya fue
        destruido (viste un RuntimeError de shiboken/"already deleted" —
        típico de un widget removido de una pestaña sin desuscribirse), se
        da de baja automáticamente para que no vuelva a fallar en cada
        evento futuro. Esto no reemplaza desconectar_eventos() en el sitio
        correcto (ver widgets/arbol.py e insumos.py); es solo para que un
        descuido no deje errores repitiéndose para siempre.
        """
        subs = self._suscriptores.get(type(evento), [])
        for cb in list(subs):
            try:
                cb(evento)
            except RuntimeError as e:
                if "already deleted" in str(e):
                    self.desuscribir(type(evento), cb)
                else:
                    traceback.print_exc()
            except Exception:
                traceback.print_exc()
