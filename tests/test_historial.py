"""Pytest para historial de creación — migrado de smoke_insertar_historial."""
import pytest

from frontend.ventana.api import Api

from backend.database.services.data_service import DataService, _TABLAS_CON_SOFT_DELETE
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus
from backend.database.repos.historial import CAMPO_CREADO


def _ds(db):
    return DataService(db, crear_registry(db), EventBus())


def test_tablas_soft_delete_completo():
    esperado = {
        "estructura_presupuesto", "generador_renglones",
        "insumos", "familias", "subfamilias", "indirectos", "generadores",
    }
    assert not (esperado - _TABLAS_CON_SOFT_DELETE)


def test_insertar_deshacer_rehacer_soft(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    iid = ds.insertar(
        "insumos", proyecto_id=1, tipo_id=1, descripcion="Insumo de prueba",
        unidad="pza", costo_directo=100, costo_final=100, activo=1,
    )
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    fila = cur.execute("SELECT activo FROM insumos WHERE id = ?", [iid]).fetchone()
    assert fila is not None and fila["activo"] == 0
    assert ds.rehacer(usuario_id=1, proyecto_id=1)
    fila = cur.execute("SELECT activo FROM insumos WHERE id = ?", [iid]).fetchone()
    assert fila["activo"] == 1


def test_insertar_deshacer_sin_soft_delete(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    vid = ds.insertar("variables_formula", proyecto_id=1, nombre="var_test", expresion="1")
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    assert cur.execute("SELECT id FROM variables_formula WHERE id = ?", [vid]).fetchone() is None
    assert ds.rehacer(usuario_id=1, proyecto_id=1)
    assert cur.execute("SELECT id FROM variables_formula WHERE id = ?", [vid]).fetchone() is None


def test_usuario_id_se_reenvia_a_historial(api, db_tmp):
    """Regresión 1.1: `Api.insumo_actualizar_campo(..., usuario_id=N)` debe
    reenviar N a DataService (historial + limpiar_deshachadas). Antes el
    forward se descartaba en `_BackendLocal`/`_BackendHTTP` y el historial
    registraba siempre usuario 1."""
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("INSERT INTO usuarios (id, nombre) VALUES (42, 'Usuario 42')")
    cur.execute("INSERT INTO usuarios (id, nombre) VALUES (43, 'Usuario 43')")
    db.conn.commit()
    uid = api.insumo_insertar(tipo_id=1, descripcion="Cemento", unidad="kg",
                              costo=10, usuario_id=42)
    fila = cur.execute(
        "SELECT usuario_id FROM historial WHERE campo = ? "
        "AND registro_id = ? ORDER BY id DESC LIMIT 1", [CAMPO_CREADO, uid]).fetchone()
    assert fila is not None and fila["usuario_id"] == 42

    api.insumo_actualizar_campo(uid, "descripcion", "Cemento gris", usuario_id=42)
    fila = cur.execute(
        "SELECT usuario_id FROM historial WHERE tabla = 'insumos' "
        "AND registro_id = ? AND campo = 'descripcion' "
        "ORDER BY id DESC LIMIT 1", [uid]).fetchone()
    assert fila is not None and fila["usuario_id"] == 42

    api.insumo_actualizar_precio(uid, 12.5, usuario_id=43)
    fila = cur.execute(
        "SELECT DISTINCT usuario_id FROM historial WHERE tabla = 'insumos' "
        "AND registro_id = ? AND campo = 'costo_mn'", [uid]).fetchone()
    assert fila is not None and fila["usuario_id"] == 43


@pytest.mark.parametrize("entidad,campos", [
    ("familias", {"nombre": "Familia test", "activo": 1}),
    ("indirectos", {
        "proyecto_id": 1, "tipo": "campo", "categoria": "X",
        "concepto": "Y", "periodo_dias": 1, "importe": 1,
        "pct_participacion": 100, "total": 0, "activo": 1,
    }),
])
def test_insertar_deshacer_otras_entidades(db_tmp, entidad, campos):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    rid = ds.insertar(entidad, **campos)
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    fila = cur.execute(f"SELECT activo FROM {entidad} WHERE id = ?", [rid]).fetchone()
    assert fila is not None and fila["activo"] == 0
    assert ds.rehacer(usuario_id=1, proyecto_id=1)
    fila = cur.execute(f"SELECT activo FROM {entidad} WHERE id = ?", [rid]).fetchone()
    assert fila["activo"] == 1


# ── Regresión 1.1: forward de `usuario_id` en el cable HTTP ─────────────


class _ClienteFake:
    """Reemplaza ApiCliente: registra `_get`/`_post`/`actualizar`/`insertar`
    sin tocar red. `_get` devuelve None (404 de insumo_por_hash)."""

    def __init__(self):
        self.logs = []

    def _get(self, path, **kwargs):
        return None

    def _post(self, path, json=None, **kwargs):
        self.logs.append({"tipo": "post", "path": path, "json": json})
        return {"id": 7, "ok": True}

    def actualizar(self, entidad, registro_id, **kwargs):
        self.logs.append({"tipo": "actualizar", "kwargs": kwargs})

    def insertar(self, entidad, **kwargs):
        self.logs.append({"tipo": "insertar", "kwargs": kwargs})
        return {"id": 7}


def test_usuario_id_viaja_por_red(db_tmp):
    db, tmp = db_tmp
    ds = _ds(db)
    api_http = Api(db.conn, tmp, proyecto_id=1, data_service=ds,
                   servidor_url="http://127.0.0.1:1")
    fake = _ClienteFake()
    api_http._cliente = fake
    assert api_http._use_http is True

    api_http.insumo_insertar(tipo_id=1, descripcion="Cemento", unidad="kg",
                             costo=10, usuario_id=42)
    api_http.insumo_actualizar_campo(1, "descripcion", "Cemento gris", usuario_id=43)
    api_http.insumo_actualizar_precio(1, 12.5, usuario_id=44)
    api_http.insumo_actualizar_precios(1, 12.5, 1.0, usuario_id=45)
    api_http.deshacer(usuario_id=46)

    logs = fake.logs
    insertar_json = next(l["kwargs"] for l in logs if l["tipo"] == "insertar")
    assert insertar_json["usuario_id"] == 42

    actualizar = next(l["kwargs"] for l in logs if l["tipo"] == "actualizar")
    assert actualizar["usuario_id"] == 43

    recalc = [l["json"] for l in logs
              if l["tipo"] == "post" and l["path"] == "/actualizar_y_recalcular"]
    assert any(j["usuario_id"] == 44 for j in recalc)
    assert any(j["usuario_id"] == 45 for j in recalc)

    deshacer = next(l["json"] for l in logs
                    if l.get("path") == "/deshacer")
    assert deshacer["usuario_id"] == 46
