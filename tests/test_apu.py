"""Pytest para APU — migrado de smoke_apu (solo local)."""
import pytest


def test_apu_crud(api):
    """CRUD de APU: crear matriz, agregar componentes, actualizar, reasignar."""
    # Crear insumos
    mat = api.insumo_insertar(tipo_id=1, descripcion="Material A", unidad="kg", costo=100)
    mo = api.insumo_insertar(tipo_id=2, descripcion="MO A", unidad="h", costo=200)

    # Crear insumo compuesto
    ins_comp = api.insumo_insertar(tipo_id=1, descripcion="Concreto armado", unidad="m3", costo=0, es_compuesto=1)
    matriz_id = -ins_comp

    # Agregar componentes al APU
    c1 = api.apu_agregar_componente(matriz_id, mat, valor=1.5, operador="*")
    c2 = api.apu_agregar_componente(matriz_id, mo, valor=0.5, operador="*")

    # Leer APU
    apu = api.apu(insumo_id=ins_comp)
    assert apu is not None
    assert len(apu["detalle"]) == 2
    assert apu["totales"]["materiales"] > 0

    # Actualizar operador
    api.apu_actualizar_operador(c1, "/")
    apu2 = api.apu(insumo_id=ins_comp)
    # operador "/" significa cantidad = 1 / valor
    assert apu2["detalle"][0]["cantidad"] == pytest.approx(1 / 1.5)

    # Actualizar valor con fórmula
    api.apu_actualizar_valor(c1, 2, formula="2 * 3")
    apu3 = api.apu(insumo_id=ins_comp)
    assert apu3["detalle"][0]["formula"] == "2 * 3"
    assert apu3["detalle"][0]["valor"] == 6

    # Reasignar componente
    api.apu_reasignar_componente(c2, mo)
    api.apu_reasignar_componente(c2, mat)
    apu4 = api.apu(insumo_id=ins_comp)
    assert apu4["detalle"][1]["insumo_id"] == mat

    # Precio componente delega a insumo
    api.apu_actualizar_precio_componente(mat, 150)
    assert api.insumo_por_id(mat)["costo_directo"] == 150