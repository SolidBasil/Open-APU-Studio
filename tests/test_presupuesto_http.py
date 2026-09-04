"""Pytest para paridad local-vs-HTTP de presupuesto — migrado de smoke_presupuesto_http."""
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
    assert nodo_cap["wbs"] not in (None, "")
    assert nodo_conc["wbs"] not in (None, "")
    assert nodo_conc["nivel"] > nodo_cap["nivel"]

    api.concepto_actualizar_cantidad(conc_id, cantidad=0, formula="2 * 4")
    assert abs(api.nodo_total(conc_id) - (8 * 10)) < 0.01

    api.concepto_actualizar_descripcion(conc_id, "Cemento gris tipo I")
    assert api.nodo_descripcion_actual(conc_id) == "Cemento gris tipo I"
    api.concepto_actualizar_unidad(conc_id, "ton")

    api.agrupador_actualizar_descripcion(cap_id, "Capítulo 1 renombrado")
    assert api.nodo_descripcion_actual(cap_id) == "Capítulo 1 renombrado"

    conc_id2 = api.agregar_nodo(tipo="concepto", padre_id=cap_id, insumo_id=1, cantidad=2)
    api.concepto_reasignar_insumo(conc_id2, nuevo_insumo_id=1)

    ids_antes = set(api.todos_concepto_ids())
    assert {conc_id, conc_id2} <= ids_antes
    assert any(c["id"] == conc_id2 for c in api.conceptos_planos())

    api.eliminar_nodo(conc_id2)
    ids_despues = set(api.todos_concepto_ids())
    assert conc_id2 not in ids_despues
    assert conc_id in ids_despues

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
    assert any(n["descripcion"] == "Fuera de presupuesto" for n in arbol_extra)
    assert not any(n["descripcion"] == "Fuera de presupuesto" for n in arbol_normal)

    return {
        "wbs_capitulo": nodo_cap["wbs"],
        "wbs_concepto": nodo_conc["wbs"],
        "nivel_concepto": nodo_conc["nivel"],
        "descripcion_concepto": api.nodo_descripcion_actual(conc_id),
        "descripcion_capitulo": api.nodo_descripcion_actual(cap_id),
        "n_conceptos_finales": len(ids_despues & {conc_id, conc_id2}),
        "n_extra": len(arbol_extra),
        "n_normal_sin_extra": len(arbol_normal),
    }


def test_paridad_local_vs_http_presupuesto(servidor_http):
    import server.servidor as srv
    tmp_base = tempfile.mkdtemp(prefix="test_presupuesto_http_")
    try:
        nombre_a = "test_presupuesto_http_local"
        path_a = Rutas.db_proyecto(nombre_a)
        if path_a.exists():
            path_a.unlink()
        db_a = Database.abrir(path_a)
        _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
        ds_a = DataService(db_a, crear_registry(db_a), EventBus())
        api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

        resultado_local = _ejercitar_presupuesto(api_local)
        db_a.close()

        nombre_b = "test_presupuesto_http_remoto"
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

        resultado_http = _ejercitar_presupuesto(api_http)
        assert resultado_local == resultado_http

        db_placeholder.close()
    finally:
        for nombre in ("test_presupuesto_http_local", "test_presupuesto_http_remoto"):
            srv._proyectos.pop(nombre, None)
            p = Rutas.db_proyecto(nombre)
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)
