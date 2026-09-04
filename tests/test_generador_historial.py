"""Pytest para historial en métodos custom de generadores — migrado de smoke_generador_historial (N6)."""
from backend.database.services.data_service import DataService
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus


def _ds(db):
    return DataService(db, crear_registry(db), EventBus())


def _dos_generadores(ds):
    gen_a = ds.insertar("generadores", proyecto_id=1, nombre="Generador A", unidad="m2")
    gen_b = ds.insertar("generadores", proyecto_id=1, nombre="Generador B", unidad="m2")
    return gen_a, gen_b


def test_eliminar_renglon_deshacible(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    gen_a, _ = _dos_generadores(ds)
    renglon_id = ds.guardar_renglon_generador(gen_a, veces=2, largo=3, ancho=2, alto=1)
    ds.eliminar_renglon_generador(renglon_id, usuario_id=1)
    fila2 = cur.execute(
        "SELECT activo FROM generador_renglones WHERE id=?", [renglon_id]).fetchone()
    assert fila2["activo"] == 0
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    fila3 = cur.execute(
        "SELECT activo FROM generador_renglones WHERE id=?", [renglon_id]).fetchone()
    assert fila3["activo"] == 1


def test_reasignar_generador_deshacible(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    gen_a, _ = _dos_generadores(ds)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 'Concepto 1', 0, 0, 1)
    """)
    db.conn.commit()
    assert cur.execute(
        "SELECT concepto_id FROM generadores WHERE id=?", [gen_a]).fetchone()["concepto_id"] is None
    ds.reasignar_generador(gen_a, nuevo_concepto_id=1, usuario_id=1)
    assert cur.execute(
        "SELECT concepto_id FROM generadores WHERE id=?", [gen_a]).fetchone()["concepto_id"] == 1
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    assert cur.execute(
        "SELECT concepto_id FROM generadores WHERE id=?", [gen_a]).fetchone()["concepto_id"] is None


def test_mover_renglon_control(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    ds = _ds(db)
    gen_a, gen_b = _dos_generadores(ds)
    renglon2 = ds.guardar_renglon_generador(gen_a, veces=1, largo=5, ancho=1, alto=1)
    assert ds.mover_renglones_generador([renglon2], gen_b, antes_de_id=None, copiar=False, usuario_id=1)
    assert cur.execute(
        "SELECT generador_id FROM generador_renglones WHERE id=?", [renglon2]
    ).fetchone()["generador_id"] == gen_b
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
