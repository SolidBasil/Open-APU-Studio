"""
smoke_indirectos_http.py
==========================
Prueba de humo de la migración de "indirectos" a la API HTTP
(_BackendHTTP + ApiCliente + endpoints nuevos en server/servidor.py).

Arranca un servidor uvicorn real en un thread de background (igual que
lo haría la app en modo "servidor embebido"), y ejercita el flujo
completo de indirectos dos veces — una vez con Api en modo LOCAL, otra
con Api en modo HTTP contra el servidor real — sobre dos proyectos
idénticos, y compara que ambos caminos den exactamente el mismo
resultado. Esto es lo que realmente importa de esta migración: que HTTP
no sea una implementación distinta con su propio comportamiento, sino
la misma lógica hablando por la red.

Cubre:
    - indirectos_insertar (con inyección de proyecto_id), _lista,
      _guardar, _eliminar, _calcular_totales, _cargar_plantilla vía HTTP
    - indirectos_aplicar_a_sobrecosto vía HTTP, incluyendo que el
      ValueError (costo directo = 0) se traduce de vuelta correctamente
      desde el 422 HTTP — no un httpx.HTTPStatusError distinto
    - Paridad exacta local vs HTTP para el mismo escenario

Uso:
    python3 tests/smoke_indirectos_http.py
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
    """Siembra un proyecto con costo directo real, listo para probar
    tanto indirectos como aplicar_a_sobrecosto (necesita costo_directo > 0)."""
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, activo)
        VALUES (1, 1, 1, 'Cemento', 'kg', 200, 200, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo,
             insumo_id, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto', 1000, 200000, 1)
    """)
    db.conn.commit()


def _ejercitar_indirectos(api) -> dict:
    """El mismo flujo completo, sin importar si `api` está en modo local
    o HTTP — eso es justo lo que se está probando."""
    api.proyecto_guardar({"duracion_obra_dias": 30})

    id_res = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Personal", "concepto": "Residente",
        "periodo_dias": 30, "importe": 20000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    lista_antes = api.indirectos_lista("campo")
    assert any(r["id"] == id_res and r.get("proyecto_id") == 1 for r in lista_antes), \
        "el indirecto insertado debía listarse con proyecto_id inyectado"

    api.indirectos_guardar(id_res, {"importe": 22000})

    n_plantilla = api.indirectos_cargar_plantilla("oficina")
    assert n_plantilla > 0

    resultado_totales = api.indirectos_calcular_totales()
    assert resultado_totales["afectados_por_duracion_faltante"] == []

    resultado_ci = api.indirectos_aplicar_a_sobrecosto()

    # limpieza parcial: eliminar el indirecto de prueba y confirmar que se va
    api.indirectos_eliminar(id_res)
    lista_despues = api.indirectos_lista("campo")
    assert not any(r["id"] == id_res for r in lista_despues)

    return {
        "n_plantilla": n_plantilla,
        "pct_indirectos_campo": round(resultado_ci["pct_indirectos_campo"], 2),
        "costo_directo_total": resultado_ci["costo_directo_total"],
    }


def main():
    tmp_base = tempfile.mkdtemp(prefix="smoke_indirectos_http_")
    from backend.database.db import Database, Rutas
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    # ── Proyecto A: modo LOCAL ──────────────────────────────────────
    nombre_a = "smoke_indirectos_http_local"
    path_a = Rutas.db_proyecto(nombre_a)
    if path_a.exists():
        path_a.unlink()
    db_a = Database.abrir(path_a)
    _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
    ds_a = DataService(db_a, crear_registry(db_a), EventBus())
    api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)
    assert api_local._use_http is False

    resultado_local = _ejercitar_indirectos(api_local)
    print(f"OK (local): {resultado_local}")
    db_a.close()

    # ── Proyecto B: modo HTTP, contra un servidor uvicorn real ──────
    nombre_b = "smoke_indirectos_http_remoto"
    path_b = Rutas.db_proyecto(nombre_b)
    if path_b.exists():
        path_b.unlink()
    db_b = Database.abrir(path_b)
    _crear_proyecto(nombre_b, db_b, db_b.conn.cursor())
    db_b.close()  # el servidor abre su propia conexión al mismo archivo

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
        assert api_http._nombre_proyecto == nombre_b

        resultado_http = _ejercitar_indirectos(api_http)
        print(f"OK (HTTP):  {resultado_http}")

        assert resultado_local == resultado_http, (
            f"el modo HTTP debía dar exactamente el mismo resultado que local:\n"
            f"  local: {resultado_local}\n"
            f"  http:  {resultado_http}"
        )
        print("OK: paridad exacta entre backend local y HTTP para indirectos")

        nombre_c = "smoke_indirectos_http_error"
        path_c = Rutas.db_proyecto(nombre_c)
        if path_c.exists():
            path_c.unlink()
        db_c = Database.abrir(path_c)
        cur_c = db_c.conn.cursor()
        cur_c.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre_c}')")
        db_c.conn.commit()
        db_c.close()

        api_http_c = Api(
            db_placeholder.conn, path_c, proyecto_id=1, data_service=ds_placeholder,
            servidor_url=f"http://127.0.0.1:{puerto}",
        )
        try:
            api_http_c.indirectos_aplicar_a_sobrecosto()
            raise AssertionError("debía lanzar ValueError con costo directo 0, vía HTTP")
        except ValueError as e:
            print(f"OK: ValueError (costo directo 0) se traduce correctamente desde el 422 HTTP ({e})")

        db_placeholder.close()
        path_c.unlink()

        print("\nTODAS LAS PRUEBAS DE LA MIGRACIÓN HTTP DE INDIRECTOS PASARON")
    finally:
        server_uv.should_exit = True
        hilo.join(timeout=5)
        for p in (path_a, path_b):
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
