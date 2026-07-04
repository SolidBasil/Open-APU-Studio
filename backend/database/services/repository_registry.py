"""
repository_registry.py
======================
Registro de repositorios por nombre de entidad.

Cada instancia está ligada a un Database (no es singleton).
Agregar una tabla = registrar el repo aquí. No se toca DataService.

Uso:
    registry = RepositoryRegistry(db)
    registry.registrar("insumos", InsumoRepo)
    repo = registry.obtener("insumos")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.database.db import Database
    from backend.database.repos.base import RepoBase


class RepositoryRegistry:
    """Registra y resuelve repositorios por nombre de entidad."""

    def __init__(self, db: Database):
        self._db = db
        self._repos: dict[str, RepoBase] = {}

    def registrar(self, entidad: str, repo_cls: type) -> None:
        """Crea y almacena la instancia del repo para una entidad."""
        self._repos[entidad] = repo_cls(self._db)

    def obtener(self, entidad: str) -> RepoBase:
        """Retorna el repositorio registrado para la entidad."""
        if entidad not in self._repos:
            raise KeyError(f"No hay repositorio registrado para '{entidad}'")
        return self._repos[entidad]

    def entidades(self) -> list[str]:
        """Lista de entidades registradas (debugging)."""
        return list(self._repos.keys())
