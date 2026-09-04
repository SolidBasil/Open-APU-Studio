"""Pytest para backends local — migrado de smoke_api_backends.py."""
from backend.database.services.data_service import DataService
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus


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
