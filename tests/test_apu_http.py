"""Pytest para paridad local-vs-HTTP de APU — migrado de smoke_apu_http."""
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
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio, orden)
        VALUES (1, 1, 5, '*', 10, 1)
    """)
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio, orden)
        VALUES (-3, 2, 2, '*', 20, 1)
    """)
    db.conn.commit()


def _ejercitar_apu(api) -> dict:
    matriz_id, desc = api.resolver_matriz(nodo_id=1)
    assert matriz_id == 1
    apu_concepto = api.apu(nodo_id=1)
    assert apu_concepto is not None
    assert len(apu_concepto["detalle"]) == 1
    comp_id_inicial = apu_concepto["detalle"][0]["id"]

    nuevo_id = api.apu_agregar_componente(matriz_id=1, insumo_id=2, valor=3, operador="*")
    apu_concepto2 = api.apu(nodo_id=1)
    assert len(apu_concepto2["detalle"]) == 2
    assert any(r["id"] == nuevo_id for r in apu_concepto2["detalle"])

    api.apu_actualizar_operador(nuevo_id, "/")
    fila_nueva = [r for r in api.apu(nodo_id=1)["detalle"] if r["id"] == nuevo_id][0]
    assert fila_nueva["operador"] == "/"

    api.apu_actualizar_valor(nuevo_id, valor=0, formula="2 * 4")
    fila_v = [r for r in api.apu(nodo_id=1)["detalle"] if r["id"] == nuevo_id][0]
    assert abs(fila_v["valor"] - 8.0) < 0.001

    api.apu_reasignar_componente(comp_id_inicial, nuevo_insumo_id=2)
    fila_r = [r for r in api.apu(nodo_id=1)["detalle"] if r["id"] == comp_id_inicial][0]
    assert fila_r["insumo_id"] == 2

    api.apu_actualizar_precio_componente(insumo_id=1, precio=15.5)

    matriz_id_c, desc_c = api.resolver_matriz(insumo_id=3)
    assert matriz_id_c == -3
    apu_compuesto = api.apu(insumo_id=3)
    assert apu_compuesto is not None
    assert len(apu_compuesto["detalle"]) == 1

    assert api.apu(insumo_id=1) is None

    return {
        "detalle_concepto_len": len(api.apu(nodo_id=1)["detalle"]),
        "detalle_compuesto_len": len(apu_compuesto["detalle"]),
        "valor_nuevo_componente": round(fila_v["valor"], 4),
        "operador_nuevo_componente": fila_v["operador"],
        "insumo_reasignado": fila_r["insumo_id"],
    }


def test_paridad_local_vs_http_apu(servidor_http):
    import server.servidor as srv
    tmp_base = tempfile.mkdtemp(prefix="test_apu_http_")
    try:
        nombre_a = "test_apu_http_local"
        path_a = Rutas.db_proyecto(nombre_a)
        if path_a.exists():
            path_a.unlink()
        db_a = Database.abrir(path_a)
        _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
        ds_a = DataService(db_a, crear_registry(db_a), EventBus())
        api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

        resultado_local = _ejercitar_apu(api_local)
        db_a.close()

        nombre_b = "test_apu_http_remoto"
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

        resultado_http = _ejercitar_apu(api_http)
        assert resultado_local == resultado_http

        db_check = Database.abrir(path_b)
        ds_check = DataService(db_check, crear_registry(db_check), EventBus())
        assert ds_check.deshacer(usuario_id=1, proyecto_id=1)
        db_check.close()

        db_placeholder.close()
    finally:
        for nombre in ("test_apu_http_local", "test_apu_http_remoto"):
            srv._proyectos.pop(nombre, None)
            p = Rutas.db_proyecto(nombre)
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)
