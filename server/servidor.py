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

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# ponytail: imports del backend — el server ES backend, no frontend
from backend.database.db import Database, Rutas
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from backend.database.repos import (
    InsumoRepo, NodoRepo, ApuMatricesRepo, FactoresSobrecostoRepo, FamiliaRepo, SubfamiliaRepo,
    RecalculoRepo, ExplosionRepo, IndirectoRepo, PLANTILLA_CAMPO, PLANTILLA_OFICINA,
    VariableFormulaRepo,
)
from backend.database.repos.generador import GeneradorRepo
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


from starlette.responses import JSONResponse


@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    # Bug preexistente encontrado en la pasada de verificación final (no
    # introducido en esta sesión, pero confirmado real con un TypeError
    # reproducible): un exception_handler de FastAPI/Starlette debe
    # devolver un Response de verdad — HTTPException NO es un Response,
    # es solo un vehículo para levantar un error dentro de un endpoint.
    # Devolver HTTPException aquí crasheaba con
    # "TypeError: 'HTTPException' object is not callable" en cuanto
    # CUALQUIER endpoint sin su propio try/except dependía de este
    # manejador global — devolvía un 500 crudo sin el detail real, en
    # vez del 422 con mensaje claro que se pretendía.
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RepositoryError)
async def repository_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(DataServiceError)
async def data_service_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


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


class PlantillaRequest(BaseModel):
    tipo: str  # "campo" | "oficina"


class RenglonRequest(BaseModel):
    renglon_id: int | None = None
    campos: dict


class MoverRenglonesRequest(BaseModel):
    ids: list[int]
    nuevo_generador_id: int
    antes_de_id: int | None = None
    copiar: bool = False


class VariableCrearRequest(BaseModel):
    nombre: str
    expresion: str = ""
    descripcion: str = ""


class VariableActualizarRequest(BaseModel):
    campos: dict


class EvaluarRequest(BaseModel):
    expresion: str


# ── Conexiones por proyecto ────────────────────────────────────────

# ponytail: cache simple — una Database + servicios por nombre de proyecto.
# Fase 9 (SRV-04 completo) reemplaza esto con cola de escritura por proyecto.

_proyectos: dict[str, dict] = {}
# Lock que protege la creación de entradas en _proyectos — sin esto, dos
# requests concurrentes pidiendo el MISMO proyecto por primera vez podrían
# pasar el "if nombre in _proyectos" a la vez y crear dos Database/conexiones
# distintas para el mismo archivo .db.
_registro_lock = threading.Lock()


def _obtener_servicios(nombre: str) -> dict:
    """Obtiene o crea Database + DataService para un proyecto.

    check_same_thread=False (ver Database._abrir()) porque FastAPI corre
    los endpoints síncronos en un thread pool: sin esto, la conexión
    creada en un thread no se podría usar desde otro cuando lleguen
    requests concurrentes para el mismo proyecto — sqlite3 lo rechaza de
    entrada con ProgrammingError.

    Eso por sí solo NO hace la conexión segura para uso concurrente real
    (el driver sqlite3 no serializa internamente) — por eso cada entrada
    de _proyectos trae también su propio `threading.Lock()`
    ("lock" en el dict devuelto). CADA endpoint que toque `svc["db"]` o
    `svc["ds"]` debe envolver esa parte en `with svc["lock"]:`.
    """
    if nombre in _proyectos:
        return _proyectos[nombre]

    with _registro_lock:
        if nombre in _proyectos:  # otro thread pudo haberlo creado mientras esperábamos el lock
            return _proyectos[nombre]

        db_path = Rutas.db_proyecto(nombre)
        if not db_path.exists():
            raise KeyError(f"Proyecto '{nombre}' no encontrado")

        db = Database.abrir(db_path, check_same_thread=False)
        event_bus = EventBus()
        registry = crear_registry(db)
        ds = DataService(db, registry, event_bus)

        servicios = {
            "db": db, "ds": ds, "event_bus": event_bus, "registry": registry,
            "lock": threading.Lock(),
        }
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
        with svc["lock"]:
            svc["ds"].actualizar(req.entidad, req.registro_id,
                                 usuario_id=req.usuario_id, **req.campos)
    except (ValidationError, RepositoryError) as e:
        raise HTTPException(status_code=422 if isinstance(e, ValidationError) else 500,
                            detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    if req.entidad == "insumos":
        try:
            from backend.database.repos import InsumoRepo
            reg = InsumoRepo(svc["db"].conn).buscar(req.registro_id) or {}
            bt.add_task(ws_manager.broadcast, nombre, {"evento": "InsumoActualizado", "data": {"insumo_id": req.registro_id, "cambios": req.campos, "registro": reg}})
        except Exception:
            pass
    return {"ok": True}


@app.post("/proyectos/{nombre}/insertar")
def insertar(nombre: str, req: InsertarRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    try:
        with svc["lock"]:
            nuevo_id = svc["ds"].insertar(req.entidad, usuario_id=req.usuario_id,
                                           **req.campos)
    except (ValidationError, RepositoryError) as e:
        raise HTTPException(status_code=422 if isinstance(e, ValidationError) else 500,
                            detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    if req.entidad == "insumos":
        try:
            from backend.database.repos import InsumoRepo
            reg = InsumoRepo(svc["db"].conn).buscar(nuevo_id) or {}
            bt.add_task(ws_manager.broadcast, nombre, {"evento": "InsumoActualizado", "data": {"insumo_id": nuevo_id, "cambios": req.campos, "registro": reg}})
        except Exception:
            pass
    return {"ok": True, "id": nuevo_id}


@app.post("/proyectos/{nombre}/eliminar")
def eliminar(nombre: str, req: EliminarRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    try:
        with svc["lock"]:
            svc["ds"].eliminar(req.entidad, req.registro_id, usuario_id=req.usuario_id)
    except RepositoryError as e:
        raise HTTPException(status_code=500, detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    if req.entidad == "insumos":
        try:
            bt.add_task(ws_manager.broadcast, nombre, {"evento": "InsumoActualizado", "data": {"insumo_id": req.registro_id, "cambios": {}, "registro": {}}})
        except Exception:
            pass
    return {"ok": True}


@app.post("/proyectos/{nombre}/recalcular")
def recalcular(nombre: str, bt: BackgroundTasks):
    """Recálculo completo del proyecto (transacción atómica)."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        with svc["db"].transaction():
            RecalculoRepo(svc["db"].conn).recalcular_proyecto(1)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True}


@app.post("/proyectos/{nombre}/reindexar")
def reindexar(nombre: str, bt: BackgroundTasks):
    """Recalcula wbs/nivel de todo el árbol desde padre_id+orden.

    Bug encontrado al migrar presupuesto a HTTP: ApiCliente.reindexar()
    llamaba a /recalcular (que solo recalcula costos, no wbs/nivel) en
    vez de a esto — cualquier nodo creado vía HTTP (agregar_nodo())
    quedaba con wbs="" y nivel=0 para siempre, sin ningún error visible,
    hasta que algo más disparara un reindex completo por otro lado (ver
    NodoRepo.reindexar(), la única función que escribe wbs/nivel)."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        with svc["db"].transaction():
            NodoRepo(svc["db"].conn).reindexar(1)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True}


@app.post("/proyectos/{nombre}/factores_sobrecosto")
def factores_sobrecosto(nombre: str, req: FactoresSobrecostoRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        with svc["db"].transaction():
            factor = FactoresSobrecostoRepo(svc["db"].conn).guardar(1, **req.valores)
            RecalculoRepo(svc["db"].conn).recalcular_proyecto(1)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    try:
        from backend.database.repos import FactoresSobrecostoRepo
        reg = FactoresSobrecostoRepo(svc["db"].conn).obtener(1) or {}
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "FactoresSobrecostoActualizados", "data": {"proyecto_id": 1, "registro": reg}})
    except Exception:
        pass
    return {"ok": True, "factor_total": factor}


# ── Indirectos ───────────────────────────────────────────────────────
# guardar/insertar/eliminar de una fila ya funcionan vía los endpoints
# genéricos /actualizar, /insertar, /eliminar (entidad="indirectos", ya
# registrada en crear_registry() desde el Hallazgo 1) — no necesitan
# rutas propias. Estos cuatro son las operaciones que sí son especiales
# (lista con filtro, cálculo masivo, plantilla, %CI→sobrecosto), en el
# mismo espíritu que /factores_sobrecosto arriba.

@app.get("/proyectos/{nombre}/indirectos")
def indirectos_lista(nombre: str, tipo: str | None = None):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return IndirectoRepo(svc["db"].conn).todos(1, tipo)


@app.post("/proyectos/{nombre}/indirectos/calcular_totales")
def indirectos_calcular_totales(nombre: str, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        with svc["db"].transaction():
            resultado = IndirectoRepo(svc["db"].conn).calcular_totales(1)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return resultado


@app.post("/proyectos/{nombre}/indirectos/cargar_plantilla")
def indirectos_cargar_plantilla(nombre: str, req: PlantillaRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    plantilla = PLANTILLA_CAMPO if req.tipo == "campo" else PLANTILLA_OFICINA
    insertados = 0
    with svc["lock"]:
        repo = IndirectoRepo(svc["db"].conn)
        existentes = {(i["concepto"], i["categoria"]) for i in repo.todos(1, req.tipo)}
        orden = 0
        with svc["db"].transaction():
            for cat, concepto, periodo, importe in plantilla:
                orden += 1
                if (concepto, cat) not in existentes:
                    # svc["ds"].insertar() (no repo.insert() directo) para
                    # que quede validado y con historial (Ctrl+Z) — mismo
                    # criterio que Api.indirectos_cargar_plantilla() del
                    # lado local. Anidar transacciones es seguro (SAVEPOINT).
                    svc["ds"].insertar(
                        "indirectos",
                        proyecto_id=1, tipo=req.tipo, categoria=cat,
                        orden=orden, concepto=concepto, periodo_dias=periodo,
                        importe=importe, pct_participacion=100.0,
                        total=0.0, activo=1,
                        limpiar_redo=(insertados == 0),
                    )
                    insertados += 1
    if insertados:
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True, "insertados": insertados}


@app.post("/proyectos/{nombre}/indirectos/aplicar_a_sobrecosto")
def indirectos_aplicar_a_sobrecosto(nombre: str, bt: BackgroundTasks):
    """Traslada indirectos a %CI en factores_sobrecosto — misma lógica
    que Api/_BackendLocal.indirectos_aplicar_a_sobrecosto() (ver
    api_backends.py), reimplementada aquí porque el servidor trabaja
    directo con repos/DataService, no con un objeto Api."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        repo = IndirectoRepo(svc["db"].conn)
        with svc["db"].transaction():
            resultado_totales = repo.calcular_totales(1)

        costo_directo = repo.costo_directo_total(1)
        total_campo = repo.total_por_tipo(1, "campo")
        total_oficina = repo.total_por_tipo(1, "oficina")

        if costo_directo <= 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No se puede calcular el %CI: el costo directo del "
                    "presupuesto es 0. Captura conceptos con insumo y "
                    "cantidad antes de aplicar los indirectos a los "
                    "sobrecostos."
                ),
            )

        pct_campo = round(total_campo / costo_directo * 100, 4)
        pct_oficina = round(total_oficina / costo_directo * 100, 4)

        actuales = FactoresSobrecostoRepo(svc["db"].conn).obtener(1) or {}
        valores = {
            "pct_indirectos_campo": pct_campo,
            "pct_indirectos_oficina": pct_oficina,
            "pct_financiamiento": actuales.get("pct_financiamiento") or 0,
            "pct_utilidad": actuales.get("pct_utilidad") or 0,
            "pct_cargos_adicionales": actuales.get("pct_cargos_adicionales") or 0,
        }
        with svc["db"].transaction():
            factor_total = FactoresSobrecostoRepo(svc["db"].conn).guardar(1, **valores)
            RecalculoRepo(svc["db"].conn).recalcular_proyecto(1)

    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {
        "pct_indirectos_campo": pct_campo,
        "pct_indirectos_oficina": pct_oficina,
        "costo_directo_total": costo_directo,
        "total_indirectos_campo": total_campo,
        "total_indirectos_oficina": total_oficina,
        "factor_total": factor_total,
        "duracion_obra_dias": resultado_totales["duracion_obra_dias"],
        "afectados_por_duracion_faltante": resultado_totales["afectados_por_duracion_faltante"],
    }


# ── Generadores ──────────────────────────────────────────────────────
# crear/actualizar_cad de un generador ya funcionan vía los endpoints
# genéricos /insertar, /actualizar (entidad="generadores"). Renglones y
# operaciones a medida (guardar_renglon_generador recalcula
# cantidad_total + cascada de presupuesto, no es un CRUD de una fila)
# necesitan rutas propias, igual que indirectos arriba.

@app.get("/proyectos/{nombre}/generadores")
def generadores_por_concepto(nombre: str, concepto_id: int | None = None):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return GeneradorRepo(svc["db"].conn).listar_por_concepto(1, concepto_id)


@app.get("/proyectos/{nombre}/generadores/{generador_id}")
def generador_por_id(nombre: str, generador_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        gen = GeneradorRepo(svc["db"].conn).buscar(generador_id)
    if not gen:
        raise HTTPException(status_code=404, detail="Generador no encontrado")
    return gen


@app.get("/proyectos/{nombre}/generadores/{generador_id}/renglones")
def generador_renglones(nombre: str, generador_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return GeneradorRepo(svc["db"].conn).listar_renglones(generador_id)


@app.post("/proyectos/{nombre}/generadores/{generador_id}/renglon")
def generador_renglon_guardar(nombre: str, generador_id: int, req: RenglonRequest,
                              bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    try:
        with svc["lock"]:
            renglon_id = svc["ds"].guardar_renglon_generador(
                generador_id, renglon_id=req.renglon_id, **req.campos
            )
    except (ValidationError, RepositoryError) as e:
        raise HTTPException(status_code=422 if isinstance(e, ValidationError) else 500,
                            detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True, "renglon_id": renglon_id}


@app.post("/proyectos/{nombre}/generadores/renglon/{renglon_id}/eliminar")
def generador_renglon_eliminar(nombre: str, renglon_id: int, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        svc["ds"].eliminar_renglon_generador(renglon_id)
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True}


@app.post("/proyectos/{nombre}/generadores/mover_renglones")
def generador_mover_renglones(nombre: str, req: MoverRenglonesRequest, bt: BackgroundTasks):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        ok = svc["ds"].mover_renglones_generador(
            req.ids, req.nuevo_generador_id, req.antes_de_id, req.copiar
        )
    if ok:
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": ok}


class UndoRequest(BaseModel):
    usuario_id: int = 1


@app.post("/proyectos/{nombre}/deshacer")
def deshacer(nombre: str, req: UndoRequest, bt: BackgroundTasks):
    """SRV-10: deshace la última operación del usuario."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        ok = svc["ds"].deshacer(usuario_id=req.usuario_id)
    if ok:
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": ok}


@app.post("/proyectos/{nombre}/rehacer")
def rehacer(nombre: str, req: UndoRequest, bt: BackgroundTasks):
    """SRV-10: rehace la última operación deshecha."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        ok = svc["ds"].rehacer(usuario_id=req.usuario_id)
    if ok:
        bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": ok}


# ── Endpoints de lectura ──────────────────────────────────────────


@app.get("/proyectos/{nombre}/arbol")
def arbol(nombre: str, extra: bool = False):
    """extra=True devuelve los nodos fuera de presupuesto (es_extra=1)
    en vez del árbol principal. Bug encontrado al migrar presupuesto a
    HTTP: este parámetro nunca llegaba hasta aquí — ApiCliente.arbol()
    no lo aceptaba, así que presupuesto_arbol(extra=True) siempre
    devolvía el árbol principal en modo HTTP, en silencio."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return NodoRepo(svc["db"].conn).arbol(1, extra=extra)


@app.get("/proyectos/{nombre}/insumos")
def insumos(nombre: str, tipo: str | None = None):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        repo = InsumoRepo(svc["db"].conn)
        return repo.por_tipo(1, tipo) if tipo else repo.todos(1)


@app.get("/proyectos/{nombre}/apu/{matriz_id}")
def apu_detalle(nombre: str, matriz_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return ApuMatricesRepo(svc["db"].conn).con_detalle(matriz_id)



# ── Variables de fórmula ─────────────────────────────────────────────
# crear/actualizar necesitan la misma validación (formato de nombre,
# duplicados, detección de ciclo) que el lado local — reimplementada
# aquí porque el servidor trabaja con repos/DataService, no con Api.
# variables_resueltas()/formula_evaluar() trabajan con Decimal, que no
# es JSON-serializable de forma exacta (jsonable_encoder lo convertiría
# a float, perdiendo precisión) — se manda como string explícitamente.

def _variables_actuales(conn, pid: int) -> dict:
    return {v["nombre"]: v["expresion"] or "" for v in VariableFormulaRepo(conn).por_proyecto(pid)}


@app.get("/proyectos/{nombre}/variables")
def variables_listar(nombre: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return VariableFormulaRepo(svc["db"].conn).por_proyecto(1)


@app.post("/proyectos/{nombre}/variables")
def variables_crear(nombre: str, req: VariableCrearRequest, bt: BackgroundTasks):
    import re
    if not re.match(r'^[A-Za-z_]\w*$', req.nombre):
        raise HTTPException(
            status_code=422,
            detail=(f"'{req.nombre}' no es un nombre de variable válido. "
                    "Debe empezar con letra o _ y contener solo letras, dígitos o _."),
        )
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        repo = VariableFormulaRepo(svc["db"].conn)
        if repo.buscar_por_nombre(1, req.nombre):
            raise HTTPException(
                status_code=422,
                detail=f"Ya existe una variable con el nombre '{req.nombre}'",
            )
        nuevo_id = svc["ds"].insertar(
            "variables_formula", proyecto_id=1,
            nombre=req.nombre, expresion=req.expresion, descripcion=req.descripcion,
        )
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True, "id": nuevo_id}


@app.post("/proyectos/{nombre}/variables/evaluar")
def formula_evaluar(nombre: str, req: EvaluarRequest):
    # OJO orden: esta ruta ESTÁTICA ("/variables/evaluar") debe declararse
    # ANTES que la genérica "/variables/{variable_id}" de abajo — FastAPI
    # empareja rutas en el orden en que se registran, así que si esto
    # fuera después, un POST a /variables/evaluar intentaría parsear
    # "evaluar" como variable_id (int) y fallaría con 422 antes de llegar
    # aquí. Encontrado por el propio test de esta migración.
    from backend.formulas import resolver_variables, evaluar_formula, ErrorFormula
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        variables = _variables_actuales(svc["db"].conn, 1)
    try:
        resueltas = resolver_variables(variables)
        resultado = evaluar_formula(req.expresion, resueltas)
    except ErrorFormula as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"resultado": str(resultado)}


@app.post("/proyectos/{nombre}/variables/{variable_id}")
def variables_actualizar(nombre: str, variable_id: int, req: VariableActualizarRequest,
                         bt: BackgroundTasks):
    from backend.formulas import resolver_variables, ErrorFormula
    campos = req.campos
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        repo = VariableFormulaRepo(svc["db"].conn)

        if "nombre" in campos:
            import re
            nuevo_nombre = campos["nombre"]
            if not re.match(r'^[A-Za-z_]\w*$', nuevo_nombre):
                raise HTTPException(
                    status_code=422,
                    detail=(f"'{nuevo_nombre}' no es un nombre de variable válido. "
                            "Debe empezar con letra o _ y contener solo letras, dígitos o _."),
                )
            duplicado = repo.buscar_por_nombre(1, nuevo_nombre)
            if duplicado and duplicado["id"] != variable_id:
                raise HTTPException(
                    status_code=422,
                    detail=f"Ya existe una variable con el nombre '{nuevo_nombre}'",
                )

        if "expresion" in campos or "nombre" in campos:
            todas = repo.por_proyecto(1)
            nuevas = {}
            for v in todas:
                key = v["nombre"]
                val = campos.get("expresion") if v["id"] == variable_id and "expresion" in campos else v.get("expresion", "")
                key_nuevo = campos.get("nombre") if v["id"] == variable_id and "nombre" in campos else key
                nuevas[key_nuevo] = val
            try:
                resolver_variables(nuevas)
            except ErrorFormula as e:
                raise HTTPException(status_code=422, detail=str(e))

        try:
            svc["ds"].actualizar("variables_formula", variable_id, **campos)
        except (ValidationError, RepositoryError) as e:
            raise HTTPException(status_code=422 if isinstance(e, ValidationError) else 500,
                                detail=str(e))
    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return {"ok": True}


@app.post("/proyectos/{nombre}/variables/{variable_id}/eliminar")
def variables_eliminar(nombre: str, variable_id: int, bt: BackgroundTasks):
    """Misma lógica que Api/_BackendLocal.variables_eliminar() (Hallazgo 5):
    sustituye el último valor conocido de la variable en cualquier fórmula
    que la referencie antes de borrarla."""
    from decimal import Decimal
    from backend.formulas import (
        nombres_referenciados, sustituir_variable_eliminada,
        resolver_variables, evaluar_formula, ErrorFormula,
    )
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        conn = svc["db"].conn
        ds = svc["ds"]
        repo = VariableFormulaRepo(conn)
        variable = repo.buscar(variable_id)
        if variable is None:
            raise HTTPException(status_code=404, detail=f"No existe la variable con id {variable_id}")
        nombre_var = variable["nombre"]

        todas = repo.por_proyecto(1)
        expresiones = {v["nombre"]: v["expresion"] or "" for v in todas}
        try:
            resueltas = resolver_variables(expresiones)
            ultimo_valor = resueltas.get(nombre_var, Decimal(0))
            puede_sustituir = True
        except ErrorFormula:
            resueltas = {}
            ultimo_valor = None
            puede_sustituir = False

        afectadas = {
            "variables": [], "conceptos": [], "componentes_apu": [],
            "omitido_por_error_previo": not puede_sustituir,
        }

        def _referencia(expr):
            try:
                return nombre_var in nombres_referenciados(expr)
            except ErrorFormula:
                return False

        with svc["db"].transaction():
            if puede_sustituir:
                for v in todas:
                    if v["id"] == variable_id:
                        continue
                    expr = v["expresion"] or ""
                    if expr.strip() and _referencia(expr):
                        nueva_expr = sustituir_variable_eliminada(expr, nombre_var, ultimo_valor)
                        ds.actualizar("variables_formula", v["id"], expresion=nueva_expr)
                        afectadas["variables"].append(v["nombre"])

                conceptos = conn.execute(
                    "SELECT id, formula FROM estructura_presupuesto "
                    "WHERE proyecto_id = 1 AND formula IS NOT NULL AND formula != '' AND activo = 1"
                ).fetchall()
                for row in conceptos:
                    if not _referencia(row["formula"]):
                        continue
                    nueva_formula = sustituir_variable_eliminada(row["formula"], nombre_var, ultimo_valor)
                    campos = {"formula": nueva_formula}
                    try:
                        campos["cantidad"] = float(evaluar_formula(nueva_formula, resueltas))
                    except ErrorFormula:
                        pass
                    ds.actualizar("estructura_presupuesto", row["id"], **campos)
                    afectadas["conceptos"].append(row["id"])

                for row in ApuMatricesRepo(conn).con_formula_por_proyecto(1):
                    if not _referencia(row["formula"]):
                        continue
                    nueva_formula = sustituir_variable_eliminada(row["formula"], nombre_var, ultimo_valor)
                    campos = {"formula": nueva_formula}
                    try:
                        campos["valor"] = float(evaluar_formula(nueva_formula, resueltas))
                    except ErrorFormula:
                        pass
                    ds.actualizar("apu_matrices", row["id"], **campos)
                    afectadas["componentes_apu"].append(row["id"])

            ds.eliminar("variables_formula", variable_id)

            if afectadas["conceptos"] or afectadas["componentes_apu"]:
                RecalculoRepo(conn).recalcular_proyecto(1)

    bt.add_task(ws_manager.broadcast, nombre, {"evento": "ProyectoRecalculado", "data": {"proyecto_id": 1, "usuario_id": 1}})
    return afectadas


@app.get("/proyectos/{nombre}/variables/resueltas")
def variables_resueltas(nombre: str):
    from backend.formulas import resolver_variables, ErrorFormula
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        variables = _variables_actuales(svc["db"].conn, 1)
    try:
        resueltas = resolver_variables(variables)
    except ErrorFormula as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {k: str(v) for k, v in resueltas.items()}


@app.get("/proyectos/{nombre}/apu_completo")
def apu_completo(nombre: str, nodo_id: int | None = None, insumo_id: int | None = None):
    """Resuelve matriz_id (positivo=concepto, negativo=insumo compuesto) y
    devuelve su detalle — misma lógica que Api.resolver_matriz() +
    Api.apu() del lado local, sin el enriquecimiento de UI (tipo_icono),
    que se queda en el cliente por ser un detalle de presentación, no de
    negocio. Devuelve {"matriz_id": None, ...} si no hay APU asociado."""
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        conn = svc["db"].conn
        matriz_id, descripcion = None, ""

        if nodo_id is not None:
            nodo = NodoRepo(conn).buscar(nodo_id)
            if nodo and nodo.get("proyecto_id") == 1:
                insumo_id_nodo = nodo.get("insumo_id")
                if insumo_id_nodo:
                    insumo = InsumoRepo(conn).buscar(insumo_id_nodo)
                    if insumo and insumo.get("es_compuesto"):
                        neg_id = -insumo["id"]
                        if ApuMatricesRepo(conn).por_matriz(neg_id):
                            matriz_id, descripcion = neg_id, nodo.get("descripcion") or ""
                if matriz_id is None:
                    candidato = nodo["id"]
                    if ApuMatricesRepo(conn).por_matriz(candidato):
                        matriz_id, descripcion = candidato, nodo.get("descripcion") or ""
        elif insumo_id is not None:
            insumo = InsumoRepo(conn).buscar(insumo_id)
            if insumo and insumo.get("es_compuesto"):
                matriz_id = -insumo["id"]
                descripcion = insumo.get("descripcion") or insumo.get("descripcion_corta") or ""

        if matriz_id is None:
            return {"matriz_id": None, "descripcion": "", "detalle": [], "totales": None}

        data = ApuMatricesRepo(conn).con_detalle(matriz_id)

    return {
        "matriz_id": matriz_id,
        "descripcion": descripcion,
        "detalle": data["detalle"],
        "totales": data.get("totales"),
    }


@app.get("/proyectos/{nombre}/nodo/{nodo_id}")
def nodo_buscar(nombre: str, nodo_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        nodo = NodoRepo(svc["db"].conn).buscar(nodo_id)
    if not nodo:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    return nodo


@app.get("/proyectos/{nombre}/insumo/{insumo_id}")
def insumo_buscar(nombre: str, insumo_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        insumo = InsumoRepo(svc["db"].conn).buscar(insumo_id)
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
    return insumo


@app.get("/proyectos/{nombre}/insumos_con_apu")
def insumos_con_apu(nombre: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return list(InsumoRepo(svc["db"].conn).ids_con_apu(1))


@app.get("/proyectos/{nombre}/familias")
def familias(nombre: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return FamiliaRepo(svc["db"].conn).todas()


@app.get("/proyectos/{nombre}/subfamilias/{familia_id}")
def subfamilias(nombre: str, familia_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return SubfamiliaRepo(svc["db"].conn).por_familia(familia_id)


@app.get("/proyectos/{nombre}/factores_sobrecosto")
def factores_sobrecosto_obtener(nombre: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return FactoresSobrecostoRepo(svc["db"].conn).obtener(1) or {}


@app.post("/proyectos/{nombre}/explotar")
def explotar(nombre: str, req: ExplotarRequest):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        filas, total = ExplosionRepo(svc["db"].conn).calcular(
            proyecto_id=1, concepto_ids=req.concepto_ids,
            nivel=req.nivel, tipos_ids=req.tipos_ids,
        )
    return {"filas": filas, "total": total}


@app.get("/proyectos/{nombre}/proximo_orden")
def proximo_orden(nombre: str, padre_id: int | None = None):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return {"orden": NodoRepo(svc["db"].conn).proximo_orden(1, padre_id)}


@app.get("/proyectos/{nombre}/rastrear/{insumo_id}")
def rastrear(nombre: str, insumo_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return InsumoRepo(svc["db"].conn).donde_se_usa(insumo_id)


@app.get("/proyectos/{nombre}/todos_concepto_ids")
def todos_concepto_ids(nombre: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return NodoRepo(svc["db"].conn).ids_por_tipo(1, tipo="concepto")


@app.get("/proyectos/{nombre}/conceptos_planos")
def conceptos_planos(nombre: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return NodoRepo(svc["db"].conn).todos(1, tipo="concepto")


@app.get("/proyectos/{nombre}/descendientes/{nodo_id}")
def descendientes(nombre: str, nodo_id: int):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return NodoRepo(svc["db"].conn).descendientes(nodo_id)


@app.get("/proyectos/{nombre}/insumo_por_hash/{hash_val}")
def insumo_por_hash(nombre: str, hash_val: str):
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
        return InsumoRepo(svc["db"].conn).buscar_por_hash(hash_val, 1)


@app.post("/proyectos/{nombre}/buscar_insumo_hash")
def buscar_insumo_hash(nombre: str, req: DescripcionRequest):
    """Busca insumo por hash de descripción."""
    from backend.database.repos.base import generar_hash
    h = generar_hash(req.descripcion)
    svc = _obtener_servicios(nombre)
    with svc["lock"]:
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
