"""
services/
========
Servicios de aplicación — coordinan validación, transacciones, repos y eventos.

Ningún servicio conoce SQL. Ningún repositorio conoce eventos.
"""

from .repository_registry import RepositoryRegistry
from .data_service import DataService

__all__ = ["RepositoryRegistry", "DataService"]
