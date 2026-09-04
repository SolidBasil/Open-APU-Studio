"""Pytest para paridad local-vs-HTTP de generadores — migrado de smoke_generadores_http."""
import shutil
import tempfile

from backend.database.db import Database, Rutas
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api


def _crear_proyecto(nombre, db, cur):
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 'Concepto A', 0, 0, 1)
    """)
    db.conn.commit()


def _ejercitar_generadores(api) -> dict:
    gen_a = api.generador_crear(nombre="Muros", concepto_id=1, unidad="m2")
    gen_b = api.generador_crear(nombre="Muros 2", concepto_id=None, unidad="m2")

    assert api.generador_por_id(gen_a)["nombre"] == "Muros"

    lista = api.generadores_por_concepto(1)
    assert any(g["id"] == gen_a for g in lista)
    assert not any(g["id"] == gen_b for g in lista)

    api.generador_actualizar_cad(gen_a, "/ruta/falsa.dxf")
    assert api.generador_por_id(gen_a)["cad_archivo_path"] == "/ruta/falsa.dxf"

    r1 = api.generador_renglon_guardar(gen_a, veces=2, largo=5, ancho=3, alto=2.5)
    r2 = api.generador_renglon_guardar(gen_a, veces=1, largo=4, ancho=2, alto=2.5)

    renglones = api.generador_renglones(gen_a)
    assert {r["id"] for r in renglones} == {r1, r2}
    subtotal_r1 = [r for r in renglones if r["id"] == r1][0]["subtotal"]
    assert abs(subtotal_r1 - (2 * 5 * 3 * 2.5)) < 0.001

    api.generador_renglon_guardar(gen_a, renglon_id=r1, veces=10, largo=5, ancho=3, alto=2.5)
    renglones2 = api.generador_renglones(gen_a)
    subtotal_r1_v2 = [r for r in renglones2 if r["id"] == r1][0]["subtotal"]
    assert abs(subtotal_r1_v2 - (10 * 5 * 3 * 2.5)) < 0.001

    assert api.generador_mover_renglones([r2], gen_b, None, False) is True
    assert r2 not in {r["id"] for r in api.generador_renglones(gen_a)}
    assert r2 in {r["id"] for r in api.generador_renglones(gen_b)}

    api.generador_renglon_eliminar(r1)
    assert r1 not in {r["id"] for r in api.generador_renglones(gen_a)}

    # Reasignar generador entre conceptos (deuda 1.2): el concepto
    # destino pasa a sumar, y al desvincular vuelve al valor anterior.
    gen_c = api.generador_crear(nombre="Cielo", concepto_id=None, unidad="m2")
    api.generador_renglon_guardar(gen_c, veces=2, largo=3, ancho=4, alto=1)
    cantidad_antes = float(api.concepto_cantidad(1) or 0)
    api.generador_reasignar(gen_c, 1)
    assert abs(float(api.concepto_cantidad(1) or 0) - (cantidad_antes + 24.0)) < 0.001
    assert api.generador_por_id(gen_c)["concepto_id"] == 1
    api.generador_reasignar(gen_c, None)
    assert abs(float(api.concepto_cantidad(1) or 0) - cantidad_antes) < 0.001
    assert api.generador_por_id(gen_c)["concepto_id"] is None

    return {
        "cantidad_total_a": round(float(api.generador_por_id(gen_a)["cantidad_total"]), 4),
        "cantidad_total_b": round(float(api.generador_por_id(gen_b)["cantidad_total"]), 4),
        "cantidad_final_concepto_a": round(float(api.concepto_cantidad(1) or 0), 4),
    }


def test_paridad_local_vs_http_generadores(servidor_http):
    import server.servidor as srv
    tmp_base = tempfile.mkdtemp(prefix="test_generadores_http_")
    try:
        nombre_a = "test_generadores_http_local"
        path_a = Rutas.db_proyecto(nombre_a)
        if path_a.exists():
            path_a.unlink()
        db_a = Database.abrir(path_a)
        _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
        ds_a = DataService(db_a, crear_registry(db_a), EventBus())
        api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

        resultado_local = _ejercitar_generadores(api_local)
        db_a.close()

        nombre_b = "test_generadores_http_remoto"
        path_b = Rutas.db_proyecto(nombre_b)
        if path_b.exists():
            path_b.unlink()
        db_b = Database.abrir(path_b)
        _crear_proyecto(nombre_b, db_b, db_b.conn.cursor())
        db_b.close()

        db_placeholder = Database.abrir(path_a)
        ds_placeholder = DataService(db_placeholder, crear_registry(db_placeholder), EventBus())
        api_http = Api(
            db_placeholder.conn, path_b, proyecto_id=1, data_service=ds_placeholder,
            servidor_url=servidor_http,
        )
        assert api_http._use_http is True

        resultado_http = _ejercitar_generadores(api_http)
        assert resultado_local == resultado_http

        db_placeholder.close()
    finally:
        for nombre in ("test_generadores_http_local", "test_generadores_http_remoto"):
            srv._proyectos.pop(nombre, None)
            p = Rutas.db_proyecto(nombre)
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)
