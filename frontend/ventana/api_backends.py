"""
api_backends.py
================
Backends de Api: separan la implementación local (SQLite directo) de la
implementación HTTP (vía servidor embebido) que hoy conviven mezcladas
como `if self._use_http: ... else: ...` dentro de cada método de Api.

Cada backend implementa el mismo conjunto de métodos que expone Api.
Api delega al backend activo en vez de repetir el if/else en cada método.

Migración en progreso — ver docs/DUPLICACION_Y_DEUDA.md. Por ahora cubre
FACTORES DE SOBRECOSTO e INSUMOS; el resto de Api sigue con el patrón
viejo hasta terminar la migración sección por sección.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frontend.ventana.api import Api


class _BackendLocal:
    """Implementación local (SQLite directo vía DataService/repos)."""

    def __init__(self, api: "Api"):
        self._api = api

    # ── FACTORES DE SOBRECOSTO ──────────────────────────────────────

    def factores_sobrecosto_obtener(self) -> dict:
        from backend.database.repos import FactoresSobrecostoRepo
        return FactoresSobrecostoRepo(self._api._conn).obtener(self._api._pid) or {}

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        from backend.database.event_bus import FactoresSobrecostoActualizados, ProyectoRecalculado
        from backend.database.repos import FactoresSobrecostoRepo, RecalculoRepo
        with self._api._ds.transaccion():
            factor = FactoresSobrecostoRepo(self._api._conn).guardar(self._api._pid, **valores)
            self._api._ds.emitir(FactoresSobrecostoActualizados(self._api._pid, valores))
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return factor

    # ── INSUMOS ──────────────────────────────────────────────────────

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        from backend.database.repos import InsumoRepo
        repo = InsumoRepo(self._api._conn)
        return repo.por_tipo(self._api._pid, tipo_clave) if tipo_clave else repo.todos(self._api._pid)

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).buscar_por_hash(hash_val, self._api._pid)

    def recalcular_proyecto(self) -> dict:
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        with self._api._ds.transaccion():
            resultado = RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return resultado

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).donde_se_usa(insumo_id)


class _BackendHTTP:
    """Implementación vía servidor embebido (ApiCliente)."""

    def __init__(self, api: "Api"):
        self._api = api

    # ── FACTORES DE SOBRECOSTO ──────────────────────────────────────

    def factores_sobrecosto_obtener(self) -> dict:
        return self._api._http().factores_sobrecosto_obtener()

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        from backend.database.event_bus import FactoresSobrecostoActualizados, ProyectoRecalculado
        factor = self._api._http().factores_sobrecosto_guardar(valores)
        self._api._ds.emitir(FactoresSobrecostoActualizados(self._api._pid, valores))
        self._api._http().recalcular()
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return factor

    # ── INSUMOS ──────────────────────────────────────────────────────

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        return self._api._http().insumos(tipo=tipo_clave)

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        return self._api._http().insumo_por_hash(hash_val)

    def recalcular_proyecto(self) -> dict:
        self._api._http().recalcular()
        from backend.database.event_bus import ProyectoRecalculado
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return {}

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        return self._api._http().rastrear(insumo_id)
