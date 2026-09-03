"""Pytest para variables de fórmula — migrado de smoke_variables_http (solo local)."""
from decimal import Decimal


def test_variables_crud(api):
    # api fixture viene de conftest (local, sin HTTP)
    assert api.variables_listar() == []
    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")
    id_area = api.variables_crear("area_muro", expresion="ancho_muro * altura")
    assert len(api.variables_listar()) == 3
    resueltas = api.variables_resueltas()
    assert resueltas["ancho_muro"] == Decimal("3.5")
    assert resueltas["area_muro"] == Decimal("9.8")
    # evaluar
    assert api.formula_evaluar("ancho_muro * 2") == Decimal("7.0")
    # actualizar con ciclo debe fallar
    try:
        api.variables_actualizar(id_ancho, expresion="area_muro + 1")
        assert False, "debía fallar por ciclo"
    except ValueError:
        pass
    # eliminar
    api.variables_eliminar(id_ancho)
    assert len(api.variables_listar()) == 2
