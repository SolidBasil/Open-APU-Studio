"""
api_cliente.py
==============
Cliente HTTP para el servidor de Open APU Studio.

Usado por api.py cuando tiene `servidor_url` configurado — Fases 4-5
de la ruta de implementación multiusuario. Cada método replica la
misma interfaz que los repos del lado del servidor, pero habla por
HTTP en vez de llamar a DataService en el mismo proceso.

SRV-02: el cliente SIEMPRE habla HTTP — la diferencia entre offline,
"mi propio servidor" y "servidor de otro" es solo la URL, no el código.
"""

from __future__ import annotations

from typing import Any

import httpx

class ApiCliente:
    """Cliente HTTP delgado: transporte puro (Fase 3/R9).

    Solo `_get`/`_post` + CRUD genérico (`buscar/actualizar/insertar/
    eliminar/recalcular/reindexar`) + archivos (`subir/descargar`).
    El mapeo operación→endpoint vive en `_BackendHTTP`, no aquí.
    Traduce 422 → ValueError de dominio (R5); el resto se propaga.

    Args:
        base_url — URL del servidor (ej. http://127.0.0.1:8000)
        nombre_proyecto — nombre del .db (sin extensión)
    """

    def __init__(self, base_url: str, nombre_proyecto: str):
        self._base = base_url.rstrip("/")
        self._proyecto = nombre_proyecto
        self._client = httpx.Client(timeout=30.0)

    def _url(self, path: str) -> str:
        return f"{self._base}/proyectos/{self._proyecto}{path}"

    def _traducir_error(self, e: httpx.HTTPStatusError) -> None:
        """Fase D (R5): 422 del servidor → ValueError de dominio.

        Centraliza la traducción que antes repetía cada método de
        _BackendHTTP. Los 500+ siguen como HTTPStatusError (bug de
        servidor: debe ser ruidoso, no ValueError).
        """
        if e.response.status_code == 422:
            try:
                detalle = e.response.json().get("detail", str(e))
            except Exception:
                detalle = str(e)
            raise ValueError(detalle) from e
        raise e

    def _get(self, path: str, **kwargs) -> Any:
        try:
            r = self._client.get(self._url(path), **kwargs)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._traducir_error(e)
        return r.json()

    def _post(self, path: str, json: dict | None = None, **kwargs) -> Any:
        try:
            r = self._client.post(self._url(path), json=json, **kwargs)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            self._traducir_error(e)
        return r.json()

    # ── Lecturas ───────────────────────────────────────────────────

    def buscar(self, entidad: str, registro_id: int) -> dict | None:
        if entidad == "estructura_presupuesto":
            return self._get(f"/nodo/{registro_id}")
        if entidad == "insumos":
            return self._get(f"/insumo/{registro_id}")
        if entidad == "apu_matrices":
            return self._get(f"/apu/{registro_id}")
        raise ValueError(f"buscar() no soporta entidad '{entidad}'")

    def actualizar(self, entidad: str, registro_id: int,
                     sesion_token: str | None = None, **campos: Any) -> None:
        self._post("/actualizar", json={
            "entidad": entidad,
            "registro_id": registro_id,
            "campos": campos,
            "sesion_token": sesion_token,
        })

    def insertar(self, entidad: str, sesion_token: str | None = None,
                 **campos: Any) -> int:
        r = self._post("/insertar", json={
            "entidad": entidad,
            "campos": campos,
            "sesion_token": sesion_token,
        })
        return r["id"]

    def eliminar(self, entidad: str, registro_id: int,
                 sesion_token: str | None = None) -> None:
        self._post("/eliminar", json={
            "entidad": entidad,
            "registro_id": registro_id,
            "sesion_token": sesion_token,
        })

    def recalcular(self) -> None:
        self._post("/recalcular")

    def reindexar(self) -> None:
        # Antes llamaba a /recalcular (solo recalcula costos, no
        # wbs/nivel) — ver el fix del bug en server/servidor.py::reindexar().
        self._post("/reindexar")

    def close(self):
        self._client.close()

    # ── Archivos (Fase E: CAD remoto — transporte genérico) ──────────

    def subir_archivo(self, path: str, filename: str, contenido: bytes) -> dict:
        """Sube bytes como multipart (R9: transporte, sin lógica de dominio)."""
        r = self._client.post(
            self._url(path),
            files={"archivo": (filename, contenido)},
        )
        r.raise_for_status()
        return r.json()

    def descargar_archivo(self, path: str) -> bytes:
        """Descarga bytes crudos (404 → HTTPStatusError, lo maneja el backend)."""
        r = self._client.get(self._url(path))
        r.raise_for_status()
        return r.content

    # ── SRV-10: Deshacer / Rehacer ────────────────────────────────

