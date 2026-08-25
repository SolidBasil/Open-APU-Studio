"""
smoke_presupuesto_http.py
===========================
Prueba de humo de la migración de "presupuesto" (árbol de
estructura_presupuesto) a la API HTTP. A diferencia de indirectos/
generadores/APU, este módulo YA tenía soporte HTTP completo en todos
sus métodos (patrón viejo `if self._use_http:` inline) — el trabajo acá
fue encontrar y corregir un bug real: ApiCliente.reindexar() llamaba al
endpoint equivocado.

Uso:
    python3 tests/smoke_presupuesto_http.py
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
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, activo)
        VALUES (1, 1, 1, 'Cemento', 'kg', 10, 10, 1)
    """)
    db.conn.commit()


def _buscar(arbol, nodo_id):
    for n in arbol:
        if n["id"] == nodo_id:
            return n
        if n.get("hijos"):
            r = _buscar(n["hijos"], nodo_id)
            if r:
                return r
    return None


def _ejercitar_presupuesto(api) -> dict:
    cap_id = api.agregar_nodo(tipo="capitulo", padre_id=None, descripcion="Capítulo 1")
    conc_id = api.agregar_nodo(tipo="concepto", padre_id=cap_id, insumo_id=1, cantidad=5)

    arbol = api.presupuesto_arbol()
    nodo_cap = _buscar(arbol, cap_id)
    nodo_conc = _buscar(arbol, conc_id)
    assert nodo_cap["wbs"] not in (None, ""), f"capítulo sin wbs asignado: {nodo_cap}"
    assert nodo_conc["wbs"] not in (None, ""), f"concepto sin wbs asignado: {nodo_conc}"
    assert nodo_conc["nivel"] > nodo_cap["nivel"], "el concepto debía quedar un nivel más abajo"

    api.concepto_actualizar_cantidad(conc_id, cantidad=0, formula="2 * 4")
    total_tras_formula = api.nodo_total(conc_id)
    assert abs(total_tras_formula - (8 * 10)) < 0.01, total_tras_formula

    api.concepto_actualizar_descripcion(conc_id, "Cemento gris tipo I")
    assert api.nodo_descripcion_actual(conc_id) == "Cemento gris tipo I"
    api.concepto_actualizar_unidad(conc_id, "ton")

    api.agrupador_actualizar_descripcion(cap_id, "Capítulo 1 renombrado")
    assert api.nodo_descripcion_actual(cap_id) == "Capítulo 1 renombrado"

    conc_id2 = api.agregar_nodo(tipo="concepto", padre_id=cap_id, insumo_id=1, cantidad=2)
    api.concepto_reasignar_insumo(conc_id2, nuevo_insumo_id=1)

    ids_antes = set(api.todos_concepto_ids())
    assert {conc_id, conc_id2} <= ids_antes

    planos_antes = api.conceptos_planos()
    assert any(c["id"] == conc_id2 for c in planos_antes)

    api.eliminar_nodo(conc_id2)
    ids_despues = set(api.todos_concepto_ids())
    assert conc_id2 not in ids_despues
    assert conc_id in ids_despues

    # ── extra=True: el otro bug encontrado (se perdía en la cadena HTTP) ──
    # Insertar un nodo es_extra=1 directo por SQL (no hay un
    # agregar_nodo(es_extra=True) expuesto) para tener algo real que
    # distinga los dos árboles — antes del fix, extra=True devolvía
    # siempre el árbol PRINCIPAL en modo HTTP (el parámetro se perdía en
    # el camino), así que este nodo hubiera aparecido donde no debía.
    conn = api._conn if not api._use_http else None
    if conn is not None:
        conn.execute(
            "INSERT INTO estructura_presupuesto "
            "(proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, "
            " cantidad, total, es_extra, activo) "
            "VALUES (1, NULL, 'X1', 0, 99, 'capitulo', 'Fuera de presupuesto', 0, 0, 1, 1)"
        )
        conn.commit()
    else:
        import sqlite3
        conn_directa = sqlite3.connect(str(api._db_path))
        conn_directa.execute(
            "INSERT INTO estructura_presupuesto "
            "(proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, "
            " cantidad, total, es_extra, activo) "
            "VALUES (1, NULL, 'X1', 0, 99, 'capitulo', 'Fuera de presupuesto', 0, 0, 1, 1)"
        )
        conn_directa.commit()
        conn_directa.close()

    arbol_extra = api.presupuesto_arbol(extra=True)
    arbol_normal = api.presupuesto_arbol(extra=False)
    assert any(n["descripcion"] == "Fuera de presupuesto" for n in arbol_extra), (
        f"el nodo es_extra=1 debía aparecer en presupuesto_arbol(extra=True): {arbol_extra}"
    )
    assert not any(n["descripcion"] == "Fuera de presupuesto" for n in arbol_normal), (
        "el nodo es_extra=1 NO debía aparecer en presupuesto_arbol(extra=False) "
        "— si aparece, es el bug de 'extra' perdiéndose en la cadena HTTP"
    )

    return {
        "wbs_capitulo": nodo_cap["wbs"],
        "wbs_concepto": nodo_conc["wbs"],
        "nivel_concepto": nodo_conc["nivel"],
        "total_tras_formula": round(total_tras_formula, 2),
        "descripcion_concepto": api.nodo_descripcion_actual(conc_id),
        "descripcion_capitulo": api.nodo_descripcion_actual(cap_id),
        "n_conceptos_finales": len(ids_despues & {conc_id, conc_id2}),
        "n_extra": len(arbol_extra),
        "n_normal_sin_extra": len(arbol_normal),
    }


def main():
    tmp_base = tempfile.mkdtemp(prefix="smoke_presupuesto_http_")
    from backend.database.db import Database, Rutas
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    nombre_a = "smoke_presupuesto_http_local"
    path_a = Rutas.db_proyecto(nombre_a)
    if path_a.exists():
        path_a.unlink()
    db_a = Database.abrir(path_a)
    _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
    ds_a = DataService(db_a, crear_registry(db_a), EventBus())
    api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

    resultado_local = _ejercitar_presupuesto(api_local)
    print(f"OK (local): {resultado_local}")
    db_a.close()

    nombre_b = "smoke_presupuesto_http_remoto"
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

        resultado_http = _ejercitar_presupuesto(api_http)
        print(f"OK (HTTP):  {resultado_http}")

        assert resultado_local == resultado_http, (
            f"el modo HTTP debía dar exactamente el mismo resultado que local:\n"
            f"  local: {resultado_local}\n"
            f"  http:  {resultado_http}"
        )
        print("OK: paridad exacta entre backend local y HTTP para presupuesto")
        print(f"OK: reindexar() vía HTTP asignó wbs/nivel correctamente "
              f"(wbs concepto={resultado_http['wbs_concepto']!r}, "
              f"nivel={resultado_http['nivel_concepto']}) — antes del fix quedaba "
              f"wbs='' y nivel=0 para siempre")

        db_placeholder.close()

        print("\nTODAS LAS PRUEBAS DE LA MIGRACIÓN HTTP DE PRESUPUESTO PASARON")
    finally:
        server_uv.should_exit = True
        hilo.join(timeout=5)
        for p in (path_a, path_b):
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
