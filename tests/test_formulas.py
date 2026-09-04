"""Pytest para el motor de fórmulas — migrado de smoke_formulas.py."""
import pytest
from decimal import Decimal

from backend.formulas import (
    ErrorFormula, evaluar_formula, nombres_referenciados, resolver_variables,
    sustituir_variable_eliminada,
)


def test_nombres_referenciados():
    assert nombres_referenciados("ancho_muro * altura + 2*pi") == {
        "ancho_muro", "altura", "pi",
    }
    assert nombres_referenciados("2*3.1416*1.5") == set()
    with pytest.raises(ErrorFormula):
        nombres_referenciados("2 +* 3")


def test_resolver_variables():
    resueltas = resolver_variables({"a": "2", "b": "a * 3"})
    assert resueltas == {"a": Decimal(2), "b": Decimal(6)}
    assert all(isinstance(v, Decimal) for v in resueltas.values())
    resueltas = resolver_variables({
        "ancho_muro": "3.5",
        "altura":     "2.8",
        "area_muro":  "ancho_muro * altura",
        "perimetro":  "2 * (ancho_muro + altura)",
    })
    assert resueltas["area_muro"] == Decimal("9.80")
    assert resueltas["perimetro"] == Decimal("12.6")


def test_resolver_ciclo_e_indefinida():
    with pytest.raises(ErrorFormula, match="iclo"):
        resolver_variables({"x": "y + 1", "y": "x - 1"})
    with pytest.raises(ErrorFormula):
        resolver_variables({"a": "b * 2"})


def test_evaluar_aritmetica():
    assert evaluar_formula("2*3.1416*1.5") == Decimal("9.4248")
    assert evaluar_formula("(10+5)/2 + 3**2") == Decimal("16.5")
    assert evaluar_formula("2^3") == Decimal(8)
    assert evaluar_formula("0.1 + 0.2") == Decimal("0.3")
    contexto = resolver_variables({"ancho_muro": "3.5", "altura": "2.8"})
    assert evaluar_formula("ancho_muro * altura", contexto) == Decimal("9.80")


def test_evaluar_seguridad():
    for peligrosa in ('__import__("os").system("echo hacked")',
                       'open("/etc/passwd").read()'):
        with pytest.raises(ErrorFormula):
            evaluar_formula(peligrosa)
    with pytest.raises(ErrorFormula, match="variable_que_no_existe"):
        evaluar_formula("variable_que_no_existe * 2")


def test_whitelist_funciones():
    assert evaluar_formula("sqrt(9)") == Decimal(3)
    assert evaluar_formula("abs(-5)") == Decimal(5)
    assert evaluar_formula("min(3, 7)") == Decimal(3)
    assert evaluar_formula("max(3, 7)") == Decimal(7)
    assert evaluar_formula("round(3.14159, 2)") == Decimal("3.14")
    for prohibida in ("factorial(5)", "exp(1)", "log(10)"):
        with pytest.raises(ErrorFormula):
            evaluar_formula(prohibida)


def test_sustituir_variable_eliminada():
    resultado = sustituir_variable_eliminada("ancho_muro * altura", "ancho_muro", Decimal(5))
    assert "ancho_muro" not in resultado
    assert "altura" in resultado
    resultado2 = sustituir_variable_eliminada("ancho * ancho_muro", "ancho", Decimal(3))
    assert "ancho_muro" in resultado2
    resultado3 = sustituir_variable_eliminada("altura * 2", "ancho_muro", Decimal(5))
    assert "ancho_muro" not in resultado3
