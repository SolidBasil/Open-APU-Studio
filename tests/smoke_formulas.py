"""
smoke_formulas.py
==================
Prueba de humo del motor de fórmulas/variables (backend/motor/formulas.py).

Uso:
    python3 tests/smoke_formulas.py
"""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.formulas import (
    ErrorFormula, evaluar_formula, nombres_referenciados, resolver_variables,
    FUNCIONES_PERMITIDAS, sustituir_variable_eliminada,
)


def main():
    # ── nombres_referenciados ────────────────────────────────────────
    assert nombres_referenciados("ancho_muro * altura + 2*pi") == {
        "ancho_muro", "altura", "pi",
    }
    assert nombres_referenciados("2*3.1416*1.5") == set()
    try:
        nombres_referenciados("2 +* 3")
        assert False, "debía fallar con sintaxis inválida"
    except ErrorFormula:
        pass

    # ── resolver_variables: caso simple ─────────────────────────────
    resueltas = resolver_variables({"a": "2", "b": "a * 3"})
    assert resueltas == {"a": Decimal(2), "b": Decimal(6)}, resueltas
    assert all(isinstance(v, Decimal) for v in resueltas.values())

    # ── resolver_variables: recursivo de varios niveles ─────────────
    resueltas = resolver_variables({
        "ancho_muro": "3.5",
        "altura":     "2.8",
        "area_muro":  "ancho_muro * altura",
        "perimetro":  "2 * (ancho_muro + altura)",
    })
    assert resueltas["area_muro"] == Decimal("9.80"), resueltas
    assert resueltas["perimetro"] == Decimal("12.6"), resueltas

    # ── resolver_variables: ciclo detectado ──────────────────────────
    try:
        resolver_variables({"x": "y + 1", "y": "x - 1"})
        assert False, "debía detectar el ciclo x<->y"
    except ErrorFormula as e:
        assert "iclo" in str(e), str(e)

    # ── resolver_variables: variable indefinida ──────────────────────
    try:
        resolver_variables({"a": "b * 2"})
        assert False, "debía fallar: b no está definida"
    except ErrorFormula:
        pass

    # ── evaluar_formula: aritmética simple, sin variables ─────────────
    assert evaluar_formula("2*3.1416*1.5") == Decimal("9.4248")
    assert evaluar_formula("(10+5)/2 + 3**2") == Decimal("16.5")

    # ── evaluar_formula: notación ^ como potencia ────────────────────
    assert evaluar_formula("2^3") == Decimal(8)

    # ── evaluar_formula: contra variables ya resueltas ────────────────
    contexto = resolver_variables({"ancho_muro": "3.5", "altura": "2.8"})
    assert evaluar_formula("ancho_muro * altura", contexto) == Decimal("9.80")

    # ── Decimal puro: 0.1 + 0.2 sin error binario ───────────────────
    assert evaluar_formula("0.1 + 0.2") == Decimal("0.3")

    # ── evaluar_formula: seguridad — no debe poder ejecutar código ────
    for peligrosa in ('__import__("os").system("echo hacked")',
                       'open("/etc/passwd").read()'):
        try:
            evaluar_formula(peligrosa)
            assert False, f"debía bloquear: {peligrosa}"
        except ErrorFormula:
            pass

    # ── evaluar_formula: variable no definida da error legible ───────
    try:
        evaluar_formula("variable_que_no_existe * 2")
        assert False, "debía fallar: variable indefinida"
    except ErrorFormula as e:
        assert "variable_que_no_existe" in str(e), str(e)

    # ── Whitelist: funciones permitidas ──────────────────────────────
    assert evaluar_formula("sqrt(9)") == Decimal(3)
    assert evaluar_formula("abs(-5)") == Decimal(5)
    assert evaluar_formula("min(3, 7)") == Decimal(3)
    assert evaluar_formula("max(3, 7)") == Decimal(7)
    assert evaluar_formula("round(3.14159, 2)") == Decimal("3.14")

    # ── Whitelist: funciones prohibidas ──────────────────────────────
    try:
        evaluar_formula("factorial(5)")
        assert False, "debía bloquear factorial"
    except ErrorFormula:
        pass

    try:
        evaluar_formula("exp(1)")
        assert False, "debía bloquear exp"
    except ErrorFormula:
        pass

    try:
        evaluar_formula("log(10)")
        assert False, "debía bloquear log"
    except ErrorFormula:
        pass

    # ── sustituir_variable_eliminada ──────────────────────────────────
    resultado = sustituir_variable_eliminada("ancho_muro * altura", "ancho_muro", Decimal(5))
    assert "ancho_muro" not in resultado, resultado
    assert "altura" in resultado, resultado

    # No debe reemplazar coincidencias parciales
    resultado2 = sustituir_variable_eliminada("ancho * ancho_muro", "ancho", Decimal(3))
    assert "ancho_muro" in resultado2, resultado2

    # Variable que no aparece → fórmula intacta
    resultado3 = sustituir_variable_eliminada("altura * 2", "ancho_muro", Decimal(5))
    assert "ancho_muro" not in resultado3, resultado3

    print("OK — smoke_formulas: todos los casos pasaron")


if __name__ == "__main__":
    main()
