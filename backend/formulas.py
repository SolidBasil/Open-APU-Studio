"""
formulas.py
===========
Motor de evaluación de fórmulas y resolución de variables nombradas por
proyecto. Ver docs/planes/PLAN_FORMULAS_VARIABLES.md para la guía completa.

Usa Decimal en toda la aritmética (no float) para evitar errores de
redondeo binario en valores de presupuesto.

Dependencias:
    - simpleeval (PyPI) — evaluación segura de expresiones
    - graphlib (stdlib) — orden topológico y detección de ciclos
    - ast (stdlib) — extraer nombres de variable de una expresión
"""

from __future__ import annotations

import ast
import graphlib
import math
from decimal import Decimal

from simpleeval import EvalWithCompoundTypes, NameNotDefined, InvalidExpression


class ErrorFormula(Exception):
    """Error al parsear/resolver/evaluar una fórmula o variable.
    El mensaje ya viene listo para mostrar al usuario."""


def _envolver_math(fn):
    """Envuelve una función de math (que solo acepta float) para que
    acepte Decimal y devuelva Decimal. La pérdida de precisión es
    inherente a las funciones trascendentales."""
    def envoltura(x):
        return Decimal(str(fn(float(x))))
    return envoltura


FUNCIONES_PERMITIDAS = {
    "sqrt": _envolver_math(math.sqrt),
    "sin":  _envolver_math(math.sin),
    "cos":  _envolver_math(math.cos),
    "tan":  _envolver_math(math.tan),
    "pi":   lambda: Decimal(str(math.pi)),
    "abs":  abs,
    "min":  min,
    "max":  max,
    "round": lambda n, *a: round(n, *(int(x) for x in a)),
}

_CONSTANTES = {}


class EvalDecimal(EvalWithCompoundTypes):
    """Variante de simpleeval donde todo literal numérico se evalúa como
    Decimal en vez de float. Esto evita TypeError al mezclar literales
    con variables Decimal y elimina el error de redondeo binario.

    Decimal(str(valor)) en vez de Decimal(valor): Decimal(0.1) a
    partir del float ya construido arrastra el error binario;
    Decimal(str(0.1)) produce exactamente Decimal('0.1')."""

    def _eval_constant(self, node):
        valor = node.value
        if isinstance(valor, float):
            return Decimal(str(valor))
        if isinstance(valor, int):
            return Decimal(valor)
        return valor


def _normalizar(expr: str) -> str:
    """Ajustes de sintaxis 'estilo calculadora' antes de parsear."""
    return expr.strip().replace("^", "**")


def nombres_referenciados(expr: str) -> set[str]:
    """Nombres de variable que aparecen en una expresión.

    Usa el parser de Python (ast) para leer la estructura — no evalúa
    nada aquí. Sirve para armar el grafo de dependencias.
    """
    try:
        arbol = ast.parse(_normalizar(expr), mode="eval")
    except SyntaxError as e:
        raise ErrorFormula(f"Sintaxis inválida: {e}")
    return {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}


def resolver_variables(variables: dict[str, str]) -> dict[str, Decimal]:
    """Resuelve un conjunto de variables (nombre -> expresión) en orden
    de dependencias. Devuelve {nombre: valor Decimal}.

    Lanza ErrorFormula si hay ciclo o nombre indefinido.
    No persiste el resultado — se recalcula en memoria cada vez.
    """
    grafo = {
        nombre: nombres_referenciados(expr) & variables.keys()
        for nombre, expr in variables.items()
    }
    try:
        orden = list(graphlib.TopologicalSorter(grafo).static_order())
    except graphlib.CycleError as e:
        ciclo = " → ".join(e.args[1])
        raise ErrorFormula(f"Ciclo entre variables: {ciclo}")

    resueltas: dict[str, Decimal] = {}
    for nombre in orden:
        expr = variables.get(nombre)
        if expr is None:
            continue
        ev = EvalDecimal(names=resueltas, functions=FUNCIONES_PERMITIDAS)
        try:
            resueltas[nombre] = ev.eval(_normalizar(expr))
        except NameNotDefined as e:
            raise ErrorFormula(f"'{nombre}': variable no definida ({e})")
        except (InvalidExpression, TypeError, ValueError, ZeroDivisionError, SyntaxError) as e:
            raise ErrorFormula(f"'{nombre}': {e}")
    return resueltas


def _mensaje_error(e: Exception) -> str:
    """Traduce excepciones de simpleeval/Decimal a mensajes legibles."""
    msg = str(e)
    m = msg.lower()
    if "division" in m and "zero" in m:
        return "División entre cero"
    if "domain" in m and "math" in m:
        return "Operación matemática no válida (ej. raíz de negativo)"
    if "was never closed" in m:
        return "Falta cerrar un paréntesis"
    if "unmatched" in m and ")" in m:
        return "Paréntesis de más o mal colocado"
    if "is not callable" in m:
        return "Ese nombre no es una función (no lleva paréntesis)"
    if "invalid syntax" in m:
        return "Sintaxis inválida en la expresión"
    if "not defined" in m:
        return f"Variable no definida: {e}"
    return msg


def evaluar_formula(expr: str, variables_resueltas: dict[str, Decimal] | None = None) -> Decimal:
    """Evalúa la expresión de una celda (Cant/Valor) contra las variables
    ya resueltas del proyecto. Devuelve Decimal."""
    nombres = dict(variables_resueltas or {})
    nombres.update(_CONSTANTES)  # pi, e, etc. — sobreescribibles por variables del proyecto
    ev = EvalDecimal(names=nombres, functions=FUNCIONES_PERMITIDAS)
    try:
        return ev.eval(_normalizar(expr))
    except NameNotDefined as e:
        raise ErrorFormula(f"Variable no definida: {e}")
    except (InvalidExpression, TypeError, ValueError, ZeroDivisionError, ArithmeticError, SyntaxError) as e:
        msg = _mensaje_error(e)
        raise ErrorFormula(msg)


class _SustitutorNombre(ast.NodeTransformer):
    """Reemplaza en el AST cada ocurrencia de un nombre por una constante."""

    def __init__(self, nombre: str, valor: Decimal):
        self.nombre = nombre
        self.valor = valor

    def visit_Name(self, nodo):
        if nodo.id == self.nombre:
            return ast.copy_location(ast.Constant(value=float(self.valor)), nodo)
        return nodo


def sustituir_variable_eliminada(formula: str, nombre: str, ultimo_valor: Decimal) -> str:
    """Reemplaza cada aparición de `nombre` como variable (ast.Name) por
    su último valor resuelto, reconstruyendo la expresión desde el AST.

    A diferencia de un replace() de texto, esto no rompe coincidencias
    parciales como 'ancho' dentro de 'ancho_muro'. Ver §4.7 de la guía.
    """
    arbol = ast.parse(_normalizar(formula), mode="eval")
    arbol_nuevo = _SustitutorNombre(nombre, ultimo_valor).visit(arbol)
    ast.fix_missing_locations(arbol_nuevo)
    return ast.unparse(arbol_nuevo)
