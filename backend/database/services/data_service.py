"""
data_service.py
===============
Servicio único de escritura para Open APU Studio.

Coordina: validar → transacción → repo → commit → evento.

Ningún servicio conoce SQL. Ningún repositorio conoce eventos.
Los eventos se emiten después del COMMIT exitoso.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from backend.database.event_bus import (
    EventBus, Evento,
    InsumoActualizado, ConceptoActualizado, ApuComponenteActualizado,
    FactoresSobrecostoActualizados, NodoInsertado, NodoEliminado,
)
from backend.database.schema_registry import SchemaRegistry, ValidationError

if TYPE_CHECKING:
    from backend.database.db import Database
    from backend.database.services.repository_registry import RepositoryRegistry


class DataServiceError(Exception):
    """Base para errores del servicio de datos."""


class RepositoryError(DataServiceError):
    """Error en operación de repositorio."""


class ConflictError(DataServiceError):
    """Conflicto de concurrencia."""


# Mapa de entidad → clase de evento para operaciones de actualización
_EVENTO_POR_ENTIDAD: dict[str, type[Evento]] = {
    "insumos": InsumoActualizado,
    "estructura_presupuesto": ConceptoActualizado,
    "apu_matrices": ApuComponenteActualizado,
    "factores_sobrecosto": FactoresSobrecostoActualizados,
}


class DataService:
    """Servicio único de escritura.

    Args:
        db: Database del proyecto abierto
        registry: RepositoryRegistry con los repos ya registrados
        event_bus: EventBus para notificar cambios
    """

    def __init__(self, db: Database, registry: RepositoryRegistry,
                 event_bus: EventBus):
        self._db = db
        self._registry = registry
        self._schema = SchemaRegistry()
        self._event_bus = event_bus

    # ── Actualizar ──────────────────────────────────────────────────

    def actualizar(self, entidad: str, registro_id: int, **campos: Any) -> None:
        """Actualiza campos de un registro y emite evento post-commit.

        Flujo: validar → transacción → repo.update() → repo.buscar() → commit → emit
        """
        try:
            self._schema.validate(entidad, campos)
        except ValidationError:
            raise
        except Exception as e:
            raise DataServiceError(str(e)) from e

        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                repo.update(registro_id, campos)
                registro = repo.buscar(registro_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        evento = self._evento(entidad, registro_id, campos, registro)
        self._event_bus.emit(evento)

    # ── Insertar ────────────────────────────────────────────────────

    def insertar(self, entidad: str, **campos: Any) -> int:
        """Inserta un registro y emite evento post-commit.

        Retorna: id del registro insertado.
        """
        try:
            self._schema.validate(entidad, campos)
        except ValidationError:
            raise
        except Exception as e:
            raise DataServiceError(str(e)) from e

        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                registro_id = repo.insert(campos)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(NodoInsertado(registro_id, entidad, campos.get("padre_id")))
        return registro_id

    # ── Eliminar ────────────────────────────────────────────────────

    def eliminar(self, entidad: str, registro_id: int) -> None:
        """Elimina (soft-delete) un registro y emite evento post-commit."""
        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                repo.delete(registro_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(NodoEliminado(registro_id, entidad))

    # ── Helpers internos ────────────────────────────────────────────

    def _evento(self, entidad: str, id: int, cambios: dict,
                registro: dict | None) -> Evento:
        """Resuelve el tipo de evento según la entidad."""
        tipo = _EVENTO_POR_ENTIDAD.get(entidad)
        if tipo is None:
            return Evento()
        if entidad == "factores_sobrecosto":
            return tipo(proyecto_id=id, registro=registro)
        return tipo(id, cambios, registro)
