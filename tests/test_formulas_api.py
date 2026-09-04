"""Pytest para CRUD de variables vía Api — migrado de smoke_formulas_api."""
import pytest
from decimal import Decimal


def test_variables_crud_basico(api):
    assert api.variables_listar() == []
    api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")
    api.variables_crear("area_muro", expresion="ancho_muro * altura")
    assert {v["nombre"] for v in api.variables_listar()} == {"ancho_muro", "altura", "area_muro"}
    with pytest.raises(ValueError, match="ancho_muro"):
        api.variables_crear("ancho_muro", expresion="1")
    with pytest.raises(ValueError):
        api.variables_crear("2ancho", expresion="1")
    assert id_altura is not None


def test_resolucion_y_evaluar(api):
    api.variables_crear("ancho_muro", expresion="3.5")
    api.variables_crear("altura", expresion="2.8")
    api.variables_crear("area_muro", expresion="ancho_muro * altura")
    resueltas = api.variables_resueltas()
    assert resueltas["area_muro"] == Decimal("9.80")
    assert all(isinstance(v, Decimal) for v in resueltas.values())
    assert api.formula_evaluar("area_muro * 2") == Decimal("19.60")
    with pytest.raises(ValueError, match="variable_fantasma"):
        api.formula_evaluar("area_muro * variable_fantasma")


def test_actualizar_propaga_y_rechaza_ciclo(api):
    api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")
    api.variables_crear("area_muro", expresion="ancho_muro * altura")
    api.variables_actualizar(id_altura, expresion="3.0")
    assert api.variables_resueltas()["area_muro"] == Decimal("10.5")
    with pytest.raises(ValueError, match="iclo"):
        api.variables_actualizar(id_altura, expresion="area_muro / ancho_muro")
    assert api.variables_resueltas()["altura"] == Decimal("3.0")


def test_ciclo_en_nuevas_y_eliminar(api):
    id_x = api.variables_crear("x_test", expresion="y_test + 1")
    id_y = api.variables_crear("y_test", expresion="x_test - 1")
    with pytest.raises(ValueError, match="iclo"):
        api.variables_resueltas()
    api.variables_eliminar(id_x)
    api.variables_eliminar(id_y)
    api.variables_crear("ancho_muro", expresion="3.5")
    api.variables_crear("altura", expresion="2.8")
    id_area = api.variables_crear("area_muro", expresion="ancho_muro * altura")
    api.variables_eliminar(id_area)
    assert len(api.variables_listar()) == 2


def test_formula_persiste_en_concepto(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    api.variables_crear("ancho_muro", expresion="3.5")
    cur.execute("INSERT INTO estructura_presupuesto "
                "(proyecto_id, wbs, nivel, orden, tipo, descripcion, cantidad) "
                "VALUES (1, '1', 0, 1, 'concepto', 'Prueba fórmula', 0)")
    db.conn.commit()
    cap_id = cur.lastrowid
    api.concepto_actualizar_cantidad(cap_id, cantidad=0, formula="ancho_muro * 2")
    fila = db.conn.execute(
        "SELECT cantidad, formula FROM estructura_presupuesto WHERE id = ?",
        [cap_id]).fetchone()
    assert fila["cantidad"] == 7.0
    assert fila["formula"] == "ancho_muro * 2"
    api.concepto_actualizar_cantidad(cap_id, cantidad=0, formula="15")
    fila = db.conn.execute(
        "SELECT cantidad, formula FROM estructura_presupuesto WHERE id = ?",
        [cap_id]).fetchone()
    assert fila["cantidad"] == 15.0
    with pytest.raises(ValueError):
        api.concepto_actualizar_cantidad(cap_id, cantidad=0, formula="no_existe * 2")
