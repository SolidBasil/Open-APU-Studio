"""Pytest para backends local — migrado de smoke_api_backends.py."""


def test_backend_activo_es_local(api):
    assert api._backend is api._backend_local


def test_factores_sobrecosto_ida_y_vuelta(api):
    assert api.factores_sobrecosto_obtener() == {}
    factor = api.factores_sobrecosto_guardar({
        "pct_indirectos_campo": 10, "pct_indirectos_oficina": 5,
        "pct_financiamiento": 2, "pct_utilidad": 8,
        "pct_cargos_adicionales": 1,
    })
    assert isinstance(factor, float)
    assert api.factores_sobrecosto_obtener().get("factor_total") == factor
    factor_calc = api.factores_sobrecosto_calcular(
        pct_indirectos_campo=10, pct_indirectos_oficina=5,
        pct_financiamiento=2, pct_utilidad=8, pct_cargos_adicionales=1,
    )
    assert abs(factor_calc - factor) < 1e-9


def test_insumos_vacio_y_rastreo(api):
    assert api.insumos() == []
    assert api.rastrear_insumo(999999) == []
    assert isinstance(api.recalcular_proyecto(), dict)


def test_cerrar_libera_cliente_http(db_tmp):
    from frontend.ventana.api import Api
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    db, tmp = db_tmp
    ds = DataService(db, crear_registry(db), EventBus())
    api = Api(db.conn, tmp, proyecto_id=1, data_service=ds,
              servidor_url="http://127.0.0.1:9")
    assert api._cliente is not None
    api.cerrar()
    assert api._cliente is None
    api.cerrar()  # idempotente, no debe lanzar


def test_cerrar_sin_http_no_hace_nada(api):
    assert api._cliente is None
    api.cerrar()  # no debe lanzar
