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

crear_registry(db) es el único punto de wiring de todos los repos
conocidos — lo usan tanto la app de escritorio (gestion_proyectos.py)
como el servidor embebido (server/servidor.py). Agregar un repo nuevo
se hace aquí, no en cada uno de los llamadores.
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


def crear_registry(db: Database) -> RepositoryRegistry:
    """Crea un RepositoryRegistry con todos los repos conocidos ya registrados.

    Único punto de wiring: cualquier flujo que abra un .db (app de
    escritorio, importar, servidor embebido) debe llamar aquí en lugar
    de repetir el bloque de registrar(...).
    """
    from backend.database.repos import (
        InsumoRepo, NodoRepo, ApuMatricesRepo, ProyectoRepo,
        FactoresSobrecostoRepo, FamiliaRepo, SubfamiliaRepo,
        GeneradorRepo, VariableFormulaRepo,
    )

    registry = RepositoryRegistry(db)
    registry.registrar("insumos", InsumoRepo)
    registry.registrar("estructura_presupuesto", NodoRepo)
    registry.registrar("apu_matrices", ApuMatricesRepo)
    registry.registrar("proyectos", ProyectoRepo)
    registry.registrar("factores_sobrecosto", FactoresSobrecostoRepo)
    registry.registrar("familias", FamiliaRepo)
    registry.registrar("subfamilias", SubfamiliaRepo)
    registry.registrar("generadores", GeneradorRepo)
    registry.registrar("variables_formula", VariableFormulaRepo)
    return registry
