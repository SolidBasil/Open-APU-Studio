"""Pytest para paridad local-vs-HTTP de indirectos — migrado de smoke_indirectos_http."""
import shutil
import tempfile

import pytest

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
    api.proyecto_guardar({"duracion_obra_dias": 30})

    id_res = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Personal", "concepto": "Residente",
        "periodo_dias": 30, "importe": 20000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    lista_antes = api.indirectos_lista("campo")
    assert any(r["id"] == id_res and r.get("proyecto_id") == 1 for r in lista_antes)

    api.indirectos_guardar(id_res, {"importe": 22000})

    assert api.indirectos_cargar_plantilla("oficina") > 0

    resultado_totales = api.indirectos_calcular_totales()
    assert resultado_totales["afectados_por_duracion_faltante"] == []

    resultado_ci = api.indirectos_aplicar_a_sobrecosto()

    api.indirectos_eliminar(id_res)
    assert not any(r["id"] == id_res for r in api.indirectos_lista("campo"))

    return {
        "pct_indirectos_campo": round(resultado_ci["pct_indirectos_campo"], 2),
        "costo_directo_total": resultado_ci["costo_directo_total"],
    }


def test_paridad_local_vs_http_indirectos(servidor_http):
    import server.servidor as srv
    tmp_base = tempfile.mkdtemp(prefix="test_indirectos_http_")
    try:
        nombre_a = "test_indirectos_http_local"
        path_a = Rutas.db_proyecto(nombre_a)
        if path_a.exists():
            path_a.unlink()
        db_a = Database.abrir(path_a)
        _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
        ds_a = DataService(db_a, crear_registry(db_a), EventBus())
        api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)
        assert api_local._use_http is False

        resultado_local = _ejercitar_indirectos(api_local)
        db_a.close()

        nombre_b = "test_indirectos_http_remoto"
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
        assert api_http._nombre_proyecto == nombre_b

        resultado_http = _ejercitar_indirectos(api_http)
        assert resultado_local == resultado_http

        nombre_c = "test_indirectos_http_error"
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
            servidor_url=servidor_http,
        )
        with pytest.raises(ValueError):
            api_http_c.indirectos_aplicar_a_sobrecosto()

        db_placeholder.close()
        path_c.unlink()
    finally:
        for nombre in ("test_indirectos_http_local", "test_indirectos_http_remoto",
                       "test_indirectos_http_error"):
            srv._proyectos.pop(nombre, None)
            p = Rutas.db_proyecto(nombre)
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)
