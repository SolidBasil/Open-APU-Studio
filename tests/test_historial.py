"""Pytest para historial de creación — migrado de smoke_insertar_historial."""
import pytest

from backend.database.services.data_service import DataService, _TABLAS_CON_SOFT_DELETE
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus


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
