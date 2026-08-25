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
    """Cliente HTTP delgado que replica la interfaz de api.py.

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

    def _get(self, path: str, **kwargs) -> Any:
        r = self._client.get(self._url(path), **kwargs)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, json: dict | None = None, **kwargs) -> Any:
        r = self._client.post(self._url(path), json=json, **kwargs)
        r.raise_for_status()
        return r.json()

    # ── Lecturas ───────────────────────────────────────────────────

    def arbol(self, extra: bool = False) -> list[dict]:
        return self._get("/arbol", params={"extra": extra})

    def buscar(self, entidad: str, registro_id: int) -> dict | None:
        if entidad == "estructura_presupuesto":
            return self._get(f"/nodo/{registro_id}")
        if entidad == "insumos":
            return self._get(f"/insumo/{registro_id}")
        if entidad == "apu_matrices":
            return self._get(f"/apu/{registro_id}")
        raise ValueError(f"buscar() no soporta entidad '{entidad}'")

    def proximo_orden(self, padre_id: int | None = None) -> float:
        params = {}
        if padre_id is not None:
            params["padre_id"] = padre_id
        r = self._get("/proximo_orden", params=params)
        return r["orden"]

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        try:
            return self._get(f"/insumo_por_hash/{hash_val}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ── Escrituras ─────────────────────────────────────────────────

    def actualizar(self, entidad: str, registro_id: int, **campos: Any) -> None:
        self._post("/actualizar", json={
            "entidad": entidad,
            "registro_id": registro_id,
            "campos": campos,
        })

    def insertar(self, entidad: str, **campos: Any) -> int:
        r = self._post("/insertar", json={
            "entidad": entidad,
            "campos": campos,
        })
        return r["id"]

    def eliminar(self, entidad: str, registro_id: int) -> None:
        self._post("/eliminar", json={
            "entidad": entidad,
            "registro_id": registro_id,
        })

    def recalcular(self) -> None:
        self._post("/recalcular")

    def reindexar(self) -> None:
        # Antes llamaba a /recalcular (solo recalcula costos, no
        # wbs/nivel) — ver el fix del bug en server/servidor.py::reindexar().
        self._post("/reindexar")

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        r = self._post("/factores_sobrecosto", json={"valores": valores})
        return r["factor_total"]

    # ── Indirectos ─────────────────────────────────────────────────
    # guardar/insertar/eliminar de indirectos usan actualizar()/insertar()/
    # eliminar() genéricos de arriba (entidad="indirectos") — no necesitan
    # métodos propios aquí.

    def indirectos_lista(self, tipo: str | None = None) -> list[dict]:
        params = {}
        if tipo:
            params["tipo"] = tipo
        return self._get("/indirectos", params=params)

    def indirectos_calcular_totales(self) -> dict:
        return self._post("/indirectos/calcular_totales")

    def indirectos_cargar_plantilla(self, tipo: str) -> int:
        r = self._post("/indirectos/cargar_plantilla", json={"tipo": tipo})
        return r["insertados"]

    def indirectos_aplicar_a_sobrecosto(self) -> dict:
        try:
            return self._post("/indirectos/aplicar_a_sobrecosto")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                # El servidor devuelve 422 para el mismo caso que
                # _BackendLocal levanta ValueError (costo directo = 0) —
                # se traduce de vuelta para que el caller (que hace
                # `except ValueError`, ver navegacion.py) funcione igual
                # sin importar qué backend esté activo.
                detalle = e.response.json().get("detail", str(e))
                raise ValueError(detalle) from e
            raise

    # ── APU ────────────────────────────────────────────────────────

    # ── Variables de fórmula ──────────────────────────────────────
    # Decimal no es JSON-serializable: variables_resueltas()/formula_evaluar()
    # se mandan como string por la red y se reconstruyen a Decimal del
    # lado de _BackendHTTP (no aquí — ApiCliente devuelve los tipos
    # "crudos" de la respuesta HTTP, la reconstrucción es tarea del backend).

    def variables_listar(self) -> list[dict]:
        return self._get("/variables")

    def variables_crear(self, nombre: str, expresion: str, descripcion: str) -> int:
        try:
            r = self._post("/variables", json={
                "nombre": nombre, "expresion": expresion, "descripcion": descripcion,
            })
            return r["id"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise ValueError(e.response.json().get("detail", str(e))) from e
            raise

    def variables_actualizar(self, variable_id: int, campos: dict) -> None:
        try:
            self._post(f"/variables/{variable_id}", json={"campos": campos})
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise ValueError(e.response.json().get("detail", str(e))) from e
            raise

    def variables_eliminar(self, variable_id: int) -> dict:
        try:
            return self._post(f"/variables/{variable_id}/eliminar")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise ValueError(e.response.json().get("detail", str(e))) from e
            raise

    def variables_resueltas(self) -> dict:
        try:
            return self._get("/variables/resueltas")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise ValueError(e.response.json().get("detail", str(e))) from e
            raise

    def formula_evaluar(self, expr: str) -> str:
        try:
            r = self._post("/variables/evaluar", json={"expresion": expr})
            return r["resultado"]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                raise ValueError(e.response.json().get("detail", str(e))) from e
            raise

    def apu_completo(self, nodo_id: int | None = None, insumo_id: int | None = None) -> dict:
        params = {}
        if nodo_id is not None:
            params["nodo_id"] = nodo_id
        if insumo_id is not None:
            params["insumo_id"] = insumo_id
        return self._get("/apu_completo", params=params)

    # ── Generadores ────────────────────────────────────────────────
    # crear/actualizar_cad de un generador usan insertar()/actualizar()
    # genéricos de arriba (entidad="generadores") — no necesitan métodos
    # propios aquí.

    def generadores_por_concepto(self, concepto_id: int | None) -> list[dict]:
        params = {}
        if concepto_id is not None:
            params["concepto_id"] = concepto_id
        return self._get("/generadores", params=params)

    def generador_por_id(self, generador_id: int) -> dict | None:
        return self._get(f"/generadores/{generador_id}")

    def generador_renglones(self, generador_id: int) -> list[dict]:
        return self._get(f"/generadores/{generador_id}/renglones")

    def generador_renglon_guardar(self, generador_id: int, renglon_id: int | None,
                                   campos: dict) -> int:
        r = self._post(
            f"/generadores/{generador_id}/renglon",
            json={"renglon_id": renglon_id, "campos": campos},
        )
        return r["renglon_id"]

    def generador_renglon_eliminar(self, renglon_id: int) -> None:
        self._post(f"/generadores/renglon/{renglon_id}/eliminar")

    def generador_mover_renglones(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool) -> bool:
        r = self._post(
            "/generadores/mover_renglones",
            json={
                "ids": ids, "nuevo_generador_id": nuevo_generador_id,
                "antes_de_id": antes_de_id, "copiar": copiar,
            },
        )
        return r["ok"]

    # ── Lecturas de dominio ────────────────────────────────────────

    def insumos(self, tipo: str | None = None) -> list[dict]:
        params = {}
        if tipo:
            params["tipo"] = tipo
        return self._get("/insumos", params=params)

    def insumos_con_apu(self) -> list[int]:
        return self._get("/insumos_con_apu")

    def familias(self) -> list[dict]:
        return self._get("/familias")

    def subfamilias(self, familia_id: int) -> list[dict]:
        return self._get(f"/subfamilias/{familia_id}")

    def factores_sobrecosto_obtener(self) -> dict:
        return self._get("/factores_sobrecosto")

    def rastrear(self, insumo_id: int) -> list[dict]:
        return self._get(f"/rastrear/{insumo_id}")

    def todos_concepto_ids(self) -> list[int]:
        return self._get("/todos_concepto_ids")

    def conceptos_planos(self) -> list[dict]:
        return self._get("/conceptos_planos")

    def descendientes(self, nodo_id: int) -> list[dict]:
        return self._get(f"/descendientes/{nodo_id}")

    def explotar(self, concepto_ids: list[int], nivel: str,
                 tipos_ids: list[int]) -> tuple[list[dict], float]:
        r = self._post("/explotar", json={
            "concepto_ids": concepto_ids,
            "nivel": nivel,
            "tipos_ids": tipos_ids,
        })
        return r["filas"], r["total"]

    def close(self):
        self._client.close()

    # ── SRV-10: Deshacer / Rehacer ────────────────────────────────

    def deshacer(self, usuario_id: int = 1) -> bool:
        r = self._post("/deshacer", json={"usuario_id": usuario_id})
        return r["ok"]

    def rehacer(self, usuario_id: int = 1) -> bool:
        r = self._post("/rehacer", json={"usuario_id": usuario_id})
        return r["ok"]
