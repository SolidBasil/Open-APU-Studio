"""
main.py
=======
Servidor HTTP para Open APU Studio — FastAPI + uvicorn.

Modos de uso:
  Standalone:  python -m server.servidor --port 8000
  Embebido:    python -m server.servidor --embedded --port 0

En modo embebido, imprime PUERTO:XXXXX por stdout antes de aceptar
conexiones (protocolo SRV-12) y solo escucha en localhost.

SRV-01: El servidor es el ÚNICO proceso que toca el .db.
SRV-02: El cliente siempre habla HTTP — este endpoint es el backend.
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# ponytail: imports del backend — el server ES backend, no frontend
from backend.database.db import Database, Rutas
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import RepositoryRegistry
from backend.database.services.data_service import DataService
from backend.database.repos import (
    InsumoRepo, NodoRepo, ApuMatricesRepo, ProyectoRepo,
    FactoresSobrecostoRepo, FamiliaRepo, SubfamiliaRepo,
    RecalculoRepo, ExplosionRepo, HistorialRepo,
)
from backend.database.exceptions import (
    ValidationError, DataServiceError, RepositoryError,
)

# ── App FastAPI ────────────────────────────────────────────────────

app = FastAPI(title="Open APU Studio — Server")


# ── WebSocket: ConnectionManager (SRV-05) ─────────────────────────

class ConnectionManager:
    """Gestiona conexiones WebSocket agrupadas por proyecto."""

    def __init__(self):
        self._conexiones: dict[str, list[WebSocket]] = {}

    async def conectar(self, proyecto: str, ws: WebSocket):
        await ws.accept()
        self._conexiones.setdefault(proyecto, []).append(ws)

    def desconectar(self, proyecto: str, ws: WebSocket):
        conns = self._conexiones.get(proyecto, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, proyecto: str, mensaje: dict):
        conns = self._conexiones.get(proyecto, [])
        muertos = []
        for ws in conns:
            try:
                await ws.send_json(mensaje)
            except Exception:
                muertos.append(ws)
        for ws in muertos:
            conns.remove(ws)


ws_manager = ConnectionManager()


def _serializar_evento(evento) -> dict:
    """Convierte un Evento a dict plano para enviar por WebSocket."""
    from dataclasses import asdict
    tipo = type(evento).__name__
    try:
        data = asdict(evento)
    except TypeError:
        data = {"proyecto_id": getattr(evento, "proyecto_id", None)}
    return {"evento": tipo, "data": data}


@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return HTTPException(status_code=422, detail=str(exc))


@app.exception_handler(RepositoryError)
async def repository_error_handler(request, exc):
    return HTTPException(status_code=500, detail=str(exc))


@app.exception_handler(DataServiceError)
async def data_service_error_handler(request, exc):
    return HTTPException(status_code=500, detail=str(exc))


# ── Modelos Pydantic ──────────────────────────────────────────────


class ActualizarRequest(BaseModel):
    entidad: str
    registro_id: int
    campos: dict
    usuario_id: int = 1


class InsertarRequest(BaseModel):
    entidad: str
    campos: dict
    usuario_id: int = 1


class EliminarRequest(BaseModel):
    entidad: str
    registro_id: int
    usuario_id: int = 1


class ExplotarRequest(BaseModel):
    concepto_ids: list[int]
    nivel: str
    tipos_ids: list[int]


class FactoresSobrecostoRequest(BaseModel):
    valores: dict


class DescripcionRequest(BaseModel):
    descripcion: str


# ── Conexiones por proyecto ────────────────────────────────────────

# ponytail: cache simple — una Database + servicios por nombre de proyecto.
# Fase 9 (SRV-04 completo) reemplaza esto con cola de escritura por proyecto.

_proyectos: dict[str, dict] = {}


def _obtener_servicios(nombre: str) -> dict:
    """Obtiene o crea Database + DataService para un proyecto."""
    if nombre in _proyectos:
        return _proyectos[nombre]

    db_path = Rutas.db_proyecto(nombre)
    if not db_path.exists():
        raise KeyError(f"Proyecto '{nombre}' no encontrado")

    db = Database.abrir(db_path)
    event_bus = EventBus()
    registry = RepositoryRegistry(db)
    registry.registrar("insumos", InsumoRepo)
    registry.registrar("estructura_presupuesto", NodoRepo)
    registry.registrar("apu_matrices", ApuMatricesRepo)
    registry.registrar("proyectos", ProyectoRepo)
    registry.registrar("factores_sobrecosto", FactoresSobrecostoRepo)
    registry.registrar("familias", FamiliaRepo)
    registry.registrar("subfamilias", SubfamiliaRepo)
    ds = DataService(db, registry, event_bus)

    servicios = {"db": db, "ds": ds, "event_bus": event_bus, "registry": registry}
    _proyectos[nombre] = servicios

    # SRV-08: invalidar historial de otros usuarios al recalcular
    from backend.database.event_bus import ProyectoRecalculado
    from backend.database.repos.historial import HistorialRepo

    def _srv08_handler(evento):
        h_repo = HistorialRepo(db.conn)
        h_repo.invalidar_sesiones_usuario(evento.usuario_id)

    event_bus.suscribir(ProyectoRecalculado, _srv08_handler)

    return servicios


# ── Endpoints de escritura ─────────────────────────────────────────


@app.post("/proyectos/{nombre}/actualizar")
def actualizar(nombre: str, req: ActualizarRequest, bt: BackgroundTasks):
    """SRV-01: escritura única vía DataService."""
    svc = _obtener_servicios(nombre)
    try:
        svc["ds"].actualizar(req.entidad, req.registro_id,
                             usuario_id=req.usuario_id, **req.campos)
    except (ValidationError, RepositoryError) as e:
        raise HTTPException(status_code=422 if isinstance(e, ValidationError) else 500,
                            detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": True}


@app.post("/proyectos/{nombre}/insertar")
def insertar(nombre: str, req: InsertarRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    try:
        nuevo_id = svc["ds"].insertar(req.entidad, usuario_id=req.usuario_id,
                                       **req.campos)
    except (ValidationError, RepositoryError) as e:
        raise HTTPException(status_code=422 if isinstance(e, ValidationError) else 500,
                            detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": True, "id": nuevo_id}


@app.post("/proyectos/{nombre}/eliminar")
def eliminar(nombre: str, req: EliminarRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    try:
        svc["ds"].eliminar(req.entidad, req.registro_id, usuario_id=req.usuario_id)
    except RepositoryError as e:
        raise HTTPException(status_code=500, detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": True}


@app.post("/proyectos/{nombre}/recalcular")
def recalcular(nombre: str, bt: BackgroundTasks):
    """Recálculo completo del proyecto (transacción atómica)."""
    svc = _obtener_servicios(nombre)
    with svc["db"].transaction():
        RecalculoRepo(svc["db"].conn).recalcular_proyecto(1)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": True}


@app.post("/proyectos/{nombre}/factores_sobrecosto")
def factores_sobrecosto(nombre: str, req: FactoresSobrecostoRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    with svc["db"].transaction():
        factor = FactoresSobrecostoRepo(svc["db"].conn).guardar(1, **req.valores)
        RecalculoRepo(svc["db"].conn).recalcular_proyecto(1)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": True, "factor_total": factor}


class UndoRequest(BaseModel):
    usuario_id: int = 1


@app.post("/proyectos/{nombre}/deshacer")
def deshacer(nombre: str, req: UndoRequest, bt: BackgroundTasks):
    """SRV-10: deshace la última operación del usuario."""
    svc = _obtener_servicios(nombre)
    ok = svc["ds"].deshacer(usuario_id=req.usuario_id)
    if ok:
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": ok}


@app.post("/proyectos/{nombre}/rehacer")
def rehacer(nombre: str, req: UndoRequest, bt: BackgroundTasks):
    """SRV-10: rehace la última operación deshecha."""
    svc = _obtener_servicios(nombre)
    ok = svc["ds"].rehacer(usuario_id=req.usuario_id)
    if ok:
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "cambio"})
    return {"ok": ok}


# ── Endpoints de lectura ──────────────────────────────────────────


@app.get("/proyectos/{nombre}/arbol")
def arbol(nombre: str):
    svc = _obtener_servicios(nombre)
    return NodoRepo(svc["db"].conn).arbol(1)


@app.get("/proyectos/{nombre}/insumos")
def insumos(nombre: str, tipo: str | None = None):
    svc = _obtener_servicios(nombre)
    repo = InsumoRepo(svc["db"].conn)
    return repo.por_tipo(1, tipo) if tipo else repo.todos(1)


@app.get("/proyectos/{nombre}/apu/{matriz_id}")
def apu_detalle(nombre: str, matriz_id: int):
    svc = _obtener_servicios(nombre)
    return ApuMatricesRepo(svc["db"].conn).con_detalle(matriz_id)


@app.get("/proyectos/{nombre}/nodo/{nodo_id}")
def nodo_buscar(nombre: str, nodo_id: int):
    svc = _obtener_servicios(nombre)
    nodo = NodoRepo(svc["db"].conn).buscar(nodo_id)
    if not nodo:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    return nodo


@app.get("/proyectos/{nombre}/insumo/{insumo_id}")
def insumo_buscar(nombre: str, insumo_id: int):
    svc = _obtener_servicios(nombre)
    insumo = InsumoRepo(svc["db"].conn).buscar(insumo_id)
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
    return insumo


@app.get("/proyectos/{nombre}/insumos_con_apu")
def insumos_con_apu(nombre: str):
    svc = _obtener_servicios(nombre)
    return list(InsumoRepo(svc["db"].conn).ids_con_apu(1))


@app.get("/proyectos/{nombre}/familias")
def familias(nombre: str):
    svc = _obtener_servicios(nombre)
    return FamiliaRepo(svc["db"].conn).todas()


@app.get("/proyectos/{nombre}/subfamilias/{familia_id}")
def subfamilias(nombre: str, familia_id: int):
    svc = _obtener_servicios(nombre)
    return SubfamiliaRepo(svc["db"].conn).por_familia(familia_id)


@app.get("/proyectos/{nombre}/factores_sobrecosto")
def factores_sobrecosto_obtener(nombre: str):
    svc = _obtener_servicios(nombre)
    return FactoresSobrecostoRepo(svc["db"].conn).obtener(1) or {}


@app.post("/proyectos/{nombre}/explotar")
def explotar(nombre: str, req: ExplotarRequest):
    svc = _obtener_servicios(nombre)
    filas, total = ExplosionRepo(svc["db"].conn).calcular(
        proyecto_id=1, concepto_ids=req.concepto_ids,
        nivel=req.nivel, tipos_ids=req.tipos_ids,
    )
    return {"filas": filas, "total": total}


@app.get("/proyectos/{nombre}/proximo_orden")
def proximo_orden(nombre: str, padre_id: int | None = None):
    svc = _obtener_servicios(nombre)
    return {"orden": NodoRepo(svc["db"].conn).proximo_orden(1, padre_id)}


@app.get("/proyectos/{nombre}/rastrear/{insumo_id}")
def rastrear(nombre: str, insumo_id: int):
    svc = _obtener_servicios(nombre)
    return InsumoRepo(svc["db"].conn).donde_se_usa(insumo_id)


@app.get("/proyectos/{nombre}/todos_concepto_ids")
def todos_concepto_ids(nombre: str):
    svc = _obtener_servicios(nombre)
    return NodoRepo(svc["db"].conn).ids_por_tipo(1, tipo="concepto")


@app.get("/proyectos/{nombre}/conceptos_planos")
def conceptos_planos(nombre: str):
    svc = _obtener_servicios(nombre)
    return NodoRepo(svc["db"].conn).todos(1, tipo="concepto")


@app.get("/proyectos/{nombre}/descendientes/{nodo_id}")
def descendientes(nombre: str, nodo_id: int):
    svc = _obtener_servicios(nombre)
    return NodoRepo(svc["db"].conn).descendientes(nodo_id)


@app.get("/proyectos/{nombre}/insumo_por_hash/{hash_val}")
def insumo_por_hash(nombre: str, hash_val: str):
    svc = _obtener_servicios(nombre)
    return InsumoRepo(svc["db"].conn).buscar_por_hash(hash_val, 1)


@app.post("/proyectos/{nombre}/buscar_insumo_hash")
def buscar_insumo_hash(nombre: str, req: DescripcionRequest):
    """Busca insumo por hash de descripción."""
    from backend.database.repos.base import generar_hash
    h = generar_hash(req.descripcion)
    svc = _obtener_servicios(nombre)
    return InsumoRepo(svc["db"].conn).buscar_por_hash(h, 1)


# ── WebSocket (SRV-05) ────────────────────────────────────────────


@app.websocket("/proyectos/{nombre}/ws")
async def websocket_endpoint(nombre: str, ws: WebSocket):
    await ws_manager.conectar(nombre, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.desconectar(nombre, ws)


# ── Arranque ──────────────────────────────────────────────────────


def _find_free_port():
    """SRV-12: pide al SO un puerto libre (bind a 0)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description="Open APU Studio Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--embedded", action="store_true",
                        help="Modo embebido: solo localhost, imprime PUERTO por stdout")
    args = parser.parse_args()

    host = "127.0.0.1" if args.embedded else "0.0.0.0"
    port = args.port

    if args.embedded and port == 0:
        port = _find_free_port()

    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    if args.embedded:
        ready = threading.Event()

        def _run():
            ready.set()
            server.run()

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        ready.wait(timeout=5)
        # SRV-12: imprime puerto real — el padre lo lee de stdout
        sys.stdout.write(f"PUERTO:{port}\n")
        sys.stdout.flush()
        thread.join()
    else:
        server.run()


if __name__ == "__main__":
    main()
