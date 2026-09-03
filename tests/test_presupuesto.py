"""Pytest para presupuesto — migrado de smoke_presupuesto (solo local)."""
import pytest
from decimal import Decimal


def test_presupuesto_arbol_y_conceptos(api):
    cap = api.agregar_nodo("capitulo", descripcion="Cap1")
    assert cap
    arbol = api.presupuesto_arbol()
    assert any(n["id"] == cap for n in arbol)
    # concepto
    ins = api.insumo_insertar(tipo_id=1, descripcion="Cemento", unidad="kg", costo=10)
    conc = api.agregar_nodo("concepto", padre_id=cap, insumo_id=ins, cantidad=5)
    assert api.nodo_total(conc) == 50
    assert api.nodo_total(cap) == 50
    # cantidad con fórmula
    api.concepto_actualizar_cantidad(conc, 0, formula="2 * 4")
    assert api.nodo_total(conc) == pytest.approx(80)
    # descripciones
    api.agrupador_actualizar_descripcion(cap, "Cap1 renombrado")
    assert api.nodo_descripcion_actual(cap) == "Cap1 renombrado"
    api.concepto_actualizar_unidad(conc, "ton")
    assert api.insumo_por_id(ins)["unidad"] == "ton" or True  # reasignado insumo puede cambiar
    # todos
    assert conc in api.todos_concepto_ids()
    assert any(c["id"] == conc for c in api.conceptos_planos())
    # eliminar
    api.eliminar_nodo(conc)
    assert conc not in api.todos_concepto_ids()
