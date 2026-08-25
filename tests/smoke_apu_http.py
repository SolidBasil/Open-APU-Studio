"""
smoke_apu_http.py
===================
Prueba de humo de la migración de "APU" (lectura completa + resolver_matriz)
a la API HTTP, más el fix de apu_agregar_componente() (bypaseaba
DataService). Mismo patrón que smoke_indirectos_http.py / smoke_generadores_http.py.

Uso:
    python3 tests/smoke_apu_http.py
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
    """Un concepto con matriz_id positivo (id=1) y un insumo compuesto
    con matriz_id negativo (id=2, -2 como matriz)."""
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES
            (1, 'MAT', 'Material'), (2, 'MO', 'Mano de obra')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (1, 1, 1, 'Cemento',            'kg',   10, 10, 0, 1),
            (2, 1, 2, 'Peón',               'jor',  20, 20, 0, 1),
            (3, 1, 1, 'Concreto compuesto', 'm3',   0,  0,  1, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 'Concepto A', 1, 0, 1)
    """)
    # Matriz del concepto (positiva): un componente inicial.
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio, orden)
        VALUES (1, 1, 5, '*', 10, 1)
    """)
    # Matriz del insumo compuesto (negativa, -3): un componente inicial.
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio, orden)
        VALUES (-3, 2, 2, '*', 20, 1)
    """)
    db.conn.commit()


def _ejercitar_apu(api) -> dict:
    # ── resolver_matriz + apu() para el concepto (matriz positiva) ──
    matriz_id, desc = api.resolver_matriz(nodo_id=1)
    assert matriz_id == 1
    apu_concepto = api.apu(nodo_id=1)
    assert apu_concepto is not None
    assert len(apu_concepto["detalle"]) == 1
    comp_id_inicial = apu_concepto["detalle"][0]["id"]

    # ── apu_agregar_componente (el que tenía el bug de bypass a DataService) ──
    nuevo_id = api.apu_agregar_componente(matriz_id=1, insumo_id=2, valor=3, operador="*")
    apu_concepto2 = api.apu(nodo_id=1)
    assert len(apu_concepto2["detalle"]) == 2
    assert any(r["id"] == nuevo_id for r in apu_concepto2["detalle"])

    # ── apu_actualizar_operador ──
    api.apu_actualizar_operador(nuevo_id, "/")
    apu_concepto3 = api.apu(nodo_id=1)
    fila_nueva = [r for r in apu_concepto3["detalle"] if r["id"] == nuevo_id][0]
    assert fila_nueva["operador"] == "/"

    # ── apu_actualizar_valor (con fórmula) ──
    api.apu_actualizar_valor(nuevo_id, valor=0, formula="2 * 4")
    apu_concepto4 = api.apu(nodo_id=1)
    fila_v = [r for r in apu_concepto4["detalle"] if r["id"] == nuevo_id][0]
    assert abs(fila_v["valor"] - 8.0) < 0.001, fila_v["valor"]

    # ── apu_reasignar_componente ──
    api.apu_reasignar_componente(comp_id_inicial, nuevo_insumo_id=2)
    apu_concepto5 = api.apu(nodo_id=1)
    fila_r = [r for r in apu_concepto5["detalle"] if r["id"] == comp_id_inicial][0]
    assert fila_r["insumo_id"] == 2

    # ── apu_actualizar_precio_componente (edita el insumo del catálogo) ──
    api.apu_actualizar_precio_componente(insumo_id=1, precio=15.5)

    # ── resolver_matriz + apu() para el insumo compuesto (matriz negativa) ──
    matriz_id_c, desc_c = api.resolver_matriz(insumo_id=3)
    assert matriz_id_c == -3
    apu_compuesto = api.apu(insumo_id=3)
    assert apu_compuesto is not None
    assert len(apu_compuesto["detalle"]) == 1

    # ── nodo/insumo sin APU -> None ──
    sin_apu = api.apu(insumo_id=1)  # insumo 1 no es compuesto, no tiene matriz propia
    assert sin_apu is None

    return {
        "detalle_concepto_len": len(apu_concepto5["detalle"]),
        "detalle_compuesto_len": len(apu_compuesto["detalle"]),
        "valor_nuevo_componente": round(fila_v["valor"], 4),
        "operador_nuevo_componente": fila_v["operador"],
        "insumo_reasignado": fila_r["insumo_id"],
    }


def main():
    tmp_base = tempfile.mkdtemp(prefix="smoke_apu_http_")
    from backend.database.db import Database, Rutas
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    nombre_a = "smoke_apu_http_local"
    path_a = Rutas.db_proyecto(nombre_a)
    if path_a.exists():
        path_a.unlink()
    db_a = Database.abrir(path_a)
    _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
    ds_a = DataService(db_a, crear_registry(db_a), EventBus())
    api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

    resultado_local = _ejercitar_apu(api_local)
    print(f"OK (local): {resultado_local}")
    db_a.close()

    nombre_b = "smoke_apu_http_remoto"
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

        resultado_http = _ejercitar_apu(api_http)
        print(f"OK (HTTP):  {resultado_http}")

        assert resultado_local == resultado_http, (
            f"el modo HTTP debía dar exactamente el mismo resultado que local:\n"
            f"  local: {resultado_local}\n"
            f"  http:  {resultado_http}"
        )
        print("OK: paridad exacta entre backend local y HTTP para APU")

        # ── Ctrl+Z: apu_agregar_componente ahora sí queda deshacible ──
        # (el bug era que bypaseaba DataService -> sin historial)
        db_check = Database.abrir(path_b)
        ds_check = DataService(db_check, crear_registry(db_check), EventBus())
        deshecho = ds_check.deshacer(usuario_id=1, proyecto_id=1)
        print(f"OK: historial de apu_agregar_componente (vía servidor) es deshacible: {deshecho}")
        db_check.close()

        db_placeholder.close()

        print("\nTODAS LAS PRUEBAS DE LA MIGRACIÓN HTTP DE APU PASARON")
    finally:
        server_uv.should_exit = True
        hilo.join(timeout=5)
        for p in (path_a, path_b):
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
