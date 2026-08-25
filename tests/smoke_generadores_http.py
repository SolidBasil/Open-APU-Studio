"""
smoke_generadores_http.py
===========================
Prueba de humo de la migración de "generadores" a la API HTTP — mismo
patrón que smoke_indirectos_http.py: arranca un servidor uvicorn real
en background y compara el flujo completo (crear, renglones, mover,
eliminar) entre modo local y modo HTTP sobre proyectos idénticos.

Uso:
    python3 tests/smoke_generadores_http.py
"""
import os
import sys
import time
import socket
import shutil
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


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

    gen_leido = api.generador_por_id(gen_a)
    assert gen_leido["nombre"] == "Muros"

    lista = api.generadores_por_concepto(1)
    assert any(g["id"] == gen_a for g in lista)
    assert not any(g["id"] == gen_b for g in lista)  # gen_b no tiene concepto_id=1

    api.generador_actualizar_cad(gen_a, "/ruta/falsa.dxf")
    assert api.generador_por_id(gen_a)["cad_archivo_path"] == "/ruta/falsa.dxf"

    r1 = api.generador_renglon_guardar(gen_a, veces=2, largo=5, ancho=3, alto=2.5)
    r2 = api.generador_renglon_guardar(gen_a, veces=1, largo=4, ancho=2, alto=2.5)

    renglones = api.generador_renglones(gen_a)
    assert {r["id"] for r in renglones} == {r1, r2}
    subtotal_r1 = [r for r in renglones if r["id"] == r1][0]["subtotal"]
    assert abs(subtotal_r1 - (2 * 5 * 3 * 2.5)) < 0.001

    # actualizar un renglón existente (pasar renglon_id)
    api.generador_renglon_guardar(gen_a, renglon_id=r1, veces=10, largo=5, ancho=3, alto=2.5)
    renglones2 = api.generador_renglones(gen_a)
    subtotal_r1_v2 = [r for r in renglones2 if r["id"] == r1][0]["subtotal"]
    assert abs(subtotal_r1_v2 - (10 * 5 * 3 * 2.5)) < 0.001

    # mover r2 al generador B
    ok = api.generador_mover_renglones([r2], gen_b, None, False)
    assert ok is True
    renglones_a = api.generador_renglones(gen_a)
    renglones_b = api.generador_renglones(gen_b)
    assert r2 not in {r["id"] for r in renglones_a}
    assert r2 in {r["id"] for r in renglones_b}

    # eliminar r1
    api.generador_renglon_eliminar(r1)
    renglones_final = api.generador_renglones(gen_a)
    assert r1 not in {r["id"] for r in renglones_final}

    return {
        "cantidad_total_a": round(float(api.generador_por_id(gen_a)["cantidad_total"]), 4),
        "cantidad_total_b": round(float(api.generador_por_id(gen_b)["cantidad_total"]), 4),
    }


def main():
    tmp_base = tempfile.mkdtemp(prefix="smoke_generadores_http_")
    from backend.database.db import Database, Rutas
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    nombre_a = "smoke_generadores_http_local"
    path_a = Rutas.db_proyecto(nombre_a)
    if path_a.exists():
        path_a.unlink()
    db_a = Database.abrir(path_a)
    _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
    ds_a = DataService(db_a, crear_registry(db_a), EventBus())
    api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

    resultado_local = _ejercitar_generadores(api_local)
    print(f"OK (local): {resultado_local}")
    db_a.close()

    nombre_b = "smoke_generadores_http_remoto"
    path_b = Rutas.db_proyecto(nombre_b)
    if path_b.exists():
        path_b.unlink()
    db_b = Database.abrir(path_b)
    _crear_proyecto(nombre_b, db_b, db_b.conn.cursor())
    db_b.close()

    import uvicorn
    import server.servidor as srv
    srv._proyectos.clear()

    puerto = _puerto_libre()
    config = uvicorn.Config(srv.app, host="127.0.0.1", port=puerto, log_level="error")
    server_uv = uvicorn.Server(config)
    hilo = threading.Thread(target=server_uv.run, daemon=True)
    hilo.start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("el servidor de prueba no arrancó a tiempo")

    try:
        db_placeholder = Database.abrir(path_a)
        ds_placeholder = DataService(db_placeholder, crear_registry(db_placeholder), EventBus())
        api_http = Api(
            db_placeholder.conn, path_b, proyecto_id=1, data_service=ds_placeholder,
            servidor_url=f"http://127.0.0.1:{puerto}",
        )
        assert api_http._use_http is True

        resultado_http = _ejercitar_generadores(api_http)
        print(f"OK (HTTP):  {resultado_http}")

        assert resultado_local == resultado_http, (
            f"el modo HTTP debía dar exactamente el mismo resultado que local:\n"
            f"  local: {resultado_local}\n"
            f"  http:  {resultado_http}"
        )
        print("OK: paridad exacta entre backend local y HTTP para generadores")

        db_placeholder.close()

        print("\nTODAS LAS PRUEBAS DE LA MIGRACIÓN HTTP DE GENERADORES PASARON")
    finally:
        server_uv.should_exit = True
        hilo.join(timeout=5)
        for p in (path_a, path_b):
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
