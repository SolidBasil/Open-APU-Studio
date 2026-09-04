"""Pytest para paridad local-vs-HTTP de variables — migrado de smoke_variables_http."""
import shutil
import tempfile
from decimal import Decimal

import pytest

from backend.database.db import Database, Rutas
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api


def _crear_proyecto(nombre, db, cur):
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    db.conn.commit()


def _ejercitar_variables(api) -> dict:
    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")
    id_area = api.variables_crear("area_muro", expresion="ancho_muro * altura")
    id_independiente = api.variables_crear("factor_desperdicio", expresion="1.05")

    lista = api.variables_listar()
    assert {v["nombre"] for v in lista} == {"ancho_muro", "altura", "area_muro", "factor_desperdicio"}

    resueltas = api.variables_resueltas()
    assert isinstance(resueltas["area_muro"], Decimal)
    assert resueltas["area_muro"] == Decimal("9.8")

    valor_formula = api.formula_evaluar("ancho_muro * 2")
    assert isinstance(valor_formula, Decimal)
    assert valor_formula == Decimal("7.0")

    with pytest.raises(ValueError):
        api.variables_crear("ancho_muro", expresion="1")
    assert len(api.variables_listar()) == 4

    with pytest.raises(ValueError):
        api.variables_actualizar(id_independiente, nombre="ancho_muro")

    with pytest.raises(ValueError):
        api.variables_actualizar(id_altura, nombre="altura_muro")

    api.variables_actualizar(id_independiente, nombre="desperdicio_muro")
    nombres = {v["nombre"] for v in api.variables_listar()}
    assert "desperdicio_muro" in nombres and "factor_desperdicio" not in nombres

    resultado = api.variables_eliminar(id_ancho)
    assert "area_muro" in resultado["variables"]
    resueltas2 = api.variables_resueltas()
    assert resueltas2["area_muro"] == Decimal("9.8")

    return {
        "n_variables_final": len(api.variables_listar()),
        "area_muro_resuelta": str(resueltas2["area_muro"]),
        "valor_formula": str(valor_formula),
    }


def test_paridad_local_vs_http_variables(servidor_http):
    import server.servidor as srv
    tmp_base = tempfile.mkdtemp(prefix="test_variables_http_")
    try:
        nombre_a = "test_variables_http_local"
        path_a = Rutas.db_proyecto(nombre_a)
        if path_a.exists():
            path_a.unlink()
        db_a = Database.abrir(path_a)
        _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
        ds_a = DataService(db_a, crear_registry(db_a), EventBus())
        api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

        resultado_local = _ejercitar_variables(api_local)
        db_a.close()

        nombre_b = "test_variables_http_remoto"
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

        resultado_http = _ejercitar_variables(api_http)
        assert resultado_local == resultado_http

        import sqlite3
        conn_directa = sqlite3.connect(str(path_b))
        conn_directa.execute("""
            INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
            ON CONFLICT(id) DO NOTHING
        """)
        conn_directa.execute("""
            INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                                  costo_directo, costo_final, activo)
            VALUES (1, 1, 1, 'Cemento', 'kg', 10, 10, 1)
        """)
        conn_directa.execute("""
            INSERT INTO estructura_presupuesto
                (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, insumo_id,
                 descripcion, cantidad, total, activo)
            VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto', 0, 0, 1)
        """)
        conn_directa.commit()
        conn_directa.close()

        api_http.concepto_actualizar_cantidad(1, cantidad=0, formula="altura * 2")
        assert abs(api_http.nodo_total(1) - (5.6 * 10)) < 0.01

        db_placeholder.close()
    finally:
        for nombre in ("test_variables_http_local", "test_variables_http_remoto"):
            srv._proyectos.pop(nombre, None)
            p = Rutas.db_proyecto(nombre)
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)
