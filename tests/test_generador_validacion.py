"""Pytest para validación de generadores — migrado de smoke_generador_validacion."""
import pytest

from backend.database.services.data_service import DataService
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus
from backend.database.exceptions import ValidationError


def _ds(db):
    return DataService(db, crear_registry(db), EventBus())


def _gen(ds):
    return ds.insertar("generadores", proyecto_id=1, nombre="Muros", unidad="m2")


def test_dimensiones_negativas_rechazadas(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    gen_id = _gen(ds)
    with pytest.raises(ValidationError):
        ds.guardar_renglon_generador(gen_id, veces=1, largo=-5, ancho=3, alto=2.5)
    with pytest.raises(ValidationError):
        ds.guardar_renglon_generador(gen_id, veces=1, largo=5, ancho=-3, alto=2.5)
    with pytest.raises(ValidationError):
        ds.guardar_renglon_generador(gen_id, veces=1, largo=5, ancho=3, alto=-2.5)
    n = cur.execute(
        "SELECT COUNT(*) AS n FROM generador_renglones WHERE generador_id = ?", [gen_id]
    ).fetchone()
    assert n["n"] == 0


def test_renglon_valido_y_solo_veces(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    gen_id = _gen(ds)
    rid = ds.guardar_renglon_generador(gen_id, veces=2, largo=5, ancho=3, alto=2.5)
    fila = cur.execute(
        "SELECT subtotal FROM generador_renglones WHERE id = ?", [rid]).fetchone()
    assert abs(fila["subtotal"] - (2 * 5 * 3 * 2.5)) < 0.001
    rid2 = ds.guardar_renglon_generador(gen_id, veces=4)
    fila2 = cur.execute(
        "SELECT subtotal, largo, ancho, alto FROM generador_renglones WHERE id = ?", [rid2]
    ).fetchone()
    assert fila2["largo"] is None and fila2["ancho"] is None and fila2["alto"] is None
    assert abs(fila2["subtotal"] - 4.0) < 0.001


def test_veces_negativo_permitido_deduccion(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    gen_id = _gen(ds)
    rid3 = ds.guardar_renglon_generador(gen_id, veces=-1, largo=2, ancho=1, alto=2.1)
    fila3 = cur.execute(
        "SELECT subtotal FROM generador_renglones WHERE id = ?", [rid3]).fetchone()
    assert fila3["subtotal"] < 0


def test_generador_nombre_valida_tipo(db_tmp):
    db, _ = db_tmp
    ds = _ds(db)
    with pytest.raises(ValidationError):
        ds.insertar("generadores", proyecto_id=1, nombre=123, unidad="m2")
