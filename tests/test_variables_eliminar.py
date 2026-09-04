"""Pytest para eliminar variables con sustitución — migrado de smoke_variables_eliminar."""
from decimal import Decimal


def _montar(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (1, 1, 1, 'Insumo simple',    'kg', 10, 10, 0, 1),
            (2, 1, 1, 'Insumo compuesto', 'm3', 0,  0,  1, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo,
             insumo_id, descripcion, cantidad, formula, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto A', 6.0, 'ancho_muro * altura', 60, 1)
    """)
    cur.execute("""
        INSERT INTO apu_matrices (id, matriz_id, insumo_id, valor, operador, precio, formula)
        VALUES (100, 1, 1, 3.5, '*', 10, 'ancho_muro')
    """)
    cur.execute("""
        INSERT INTO apu_matrices (id, matriz_id, insumo_id, valor, operador, precio, formula)
        VALUES (101, -2, 1, 2.8, '*', 10, 'altura')
    """)
    db.conn.commit()
    return cur


def test_variables_eliminar_sustituye(api, db_tmp):
    cur = _montar(api, db_tmp)
    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    api.variables_crear("altura", expresion="2.8")
    api.variables_crear("area_muro", expresion="ancho_muro * altura")
    api.variables_crear("factor_desperdicio", expresion="1.05")
    assert api.variables_resueltas()["area_muro"] == Decimal("9.8")

    resultado = api.variables_eliminar(id_ancho)
    assert "area_muro" in resultado["variables"]
    assert 1 in resultado["conceptos"]
    assert 100 in resultado["componentes_apu"]
    assert 101 not in resultado["componentes_apu"]
    assert "factor_desperdicio" not in resultado["variables"]

    nombres = {v["nombre"] for v in api.variables_listar()}
    assert "ancho_muro" not in nombres

    resueltas2 = api.variables_resueltas()
    assert resueltas2["area_muro"] == Decimal("9.8")
    var_area = [v for v in api.variables_listar() if v["nombre"] == "area_muro"][0]
    assert "ancho_muro" not in var_area["expresion"]

    concepto = cur.execute(
        "SELECT formula, cantidad FROM estructura_presupuesto WHERE id = 1").fetchone()
    assert "ancho_muro" not in (concepto["formula"] or "")
    assert abs(concepto["cantidad"] - 9.8) < 0.001

    comp100 = cur.execute(
        "SELECT formula, valor FROM apu_matrices WHERE id = 100").fetchone()
    assert "ancho_muro" not in (comp100["formula"] or "")
    assert abs(comp100["valor"] - 3.5) < 0.001

    comp101 = cur.execute(
        "SELECT formula, valor FROM apu_matrices WHERE id = 101").fetchone()
    assert comp101["formula"] == "altura"


def test_variables_eliminar_deshace_previos(api, db_tmp):
    from backend.database.services.data_service import DataService
    from backend.database.services.repository_registry import crear_registry
    from backend.database.event_bus import EventBus

    _montar(api, db_tmp)
    db, _ = db_tmp
    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    api.variables_crear("altura", expresion="2.8")
    api.variables_eliminar(id_ancho)
    ds = DataService(db, crear_registry(db), EventBus())
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
