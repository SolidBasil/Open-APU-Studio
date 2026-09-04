"""Pytest para mover/copiar renglones — migrado de smoke_generador_dragdrop."""
from backend.database.repos.generador import GeneradorRepo
from backend.database.services.data_service import DataService
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus


def _montar(api, db_tmp):
    from backend.database.db import Database
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
        VALUES
            (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1',  NULL, 0),
            (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 0, 0),
            (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 0, 0)
    """)
    db.conn.commit()
    gen_a = api.generador_crear(nombre="Gen A", concepto_id=2, unidad="m2")
    gen_b = api.generador_crear(nombre="Gen B", concepto_id=3, unidad="m2")
    r1 = api.generador_renglon_guardar(gen_a, eje="1", tramo="A-B", veces=1, largo=10, ancho=2)
    r2 = api.generador_renglon_guardar(gen_a, eje="2", tramo="B-C", veces=1, largo=5, ancho=2)
    r3 = api.generador_renglon_guardar(gen_b, eje="1", tramo="X-Y", veces=1, largo=4, ancho=3)
    assert api.concepto_cantidad(2) == 30.0
    assert api.concepto_cantidad(3) == 12.0
    return gen_a, gen_b, r1, r2, r3


def _ds(db):
    return DataService(db, crear_registry(db), EventBus())


def test_reordenar_mismo_generador(api, db_tmp):
    db, _ = db_tmp
    gen_a, gen_b, r1, r2, r3 = _montar(api, db_tmp)
    assert api.generador_mover_renglones([r2], gen_a, r1, copiar=False)
    assert GeneradorRepo(db.conn).hermanos_de(gen_a) == [r2, r1]


def test_mover_entre_generadores_y_deshacer(api, db_tmp):
    db, _ = db_tmp
    gen_a, gen_b, r1, r2, r3 = _montar(api, db_tmp)
    repo = GeneradorRepo(db.conn)
    assert api.generador_mover_renglones([r1], gen_b, None, copiar=False)
    assert repo.buscar_renglon(r1)["generador_id"] == gen_b
    assert api.concepto_cantidad(2) == 10.0
    assert api.concepto_cantidad(3) == 32.0
    assert _ds(db).deshacer(usuario_id=1, proyecto_id=1)
    assert repo.buscar_renglon(r1)["generador_id"] == gen_a
    assert api.concepto_cantidad(2) == 30.0
    assert api.concepto_cantidad(3) == 12.0


def test_copiar_y_deshacer_rehacer(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    gen_a, gen_b, r1, r2, r3 = _montar(api, db_tmp)
    repo = GeneradorRepo(db.conn)
    ids_antes = {r["id"] for r in db.conn.execute("SELECT id FROM generador_renglones").fetchall()}
    assert api.generador_mover_renglones([r3], gen_a, None, copiar=True)
    nuevos = {r["id"] for r in db.conn.execute("SELECT id FROM generador_renglones").fetchall()} - ids_antes
    assert len(nuevos) == 1
    nuevo_id = nuevos.pop()
    assert repo.buscar_renglon(nuevo_id)["generador_id"] == gen_a
    assert repo.buscar_renglon(r3)["generador_id"] == gen_b
    assert api.concepto_cantidad(2) == 42.0
    assert _ds(db).deshacer(usuario_id=1, proyecto_id=1)
    fila = cur.execute(
        "SELECT activo FROM generador_renglones WHERE id = ?", [nuevo_id]).fetchone()
    assert fila["activo"] == 0
    assert api.concepto_cantidad(2) == 30.0
    assert _ds(db).rehacer(usuario_id=1, proyecto_id=1)
    fila = cur.execute(
        "SELECT activo FROM generador_renglones WHERE id = ?", [nuevo_id]).fetchone()
    assert fila["activo"] == 1
    assert api.concepto_cantidad(2) == 42.0
