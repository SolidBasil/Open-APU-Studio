"""Pytest para insumos — migrado de smoke_insumos (solo local)."""
from decimal import Decimal


def test_insumos_crud(api):
    # crear
    id1 = api.insumo_insertar(tipo_id=1, descripcion="Cemento", unidad="kg", costo=10)
    assert api.insumo_por_id(id1)["descripcion"] == "Cemento"
    # duplicado por hash
    try:
        api.insumo_insertar(tipo_id=1, descripcion="Cemento", unidad="kg", costo=12)
        assert False, "debía fallar colisión"
    except ValueError:
        pass
    # actualizar descripción
    api.insumo_actualizar_descripcion(id1, "Cemento gris tipo I")
    assert api.insumo_por_id(id1)["descripcion"] == "Cemento gris tipo I"
    # actualizar precio
    api.insumo_actualizar_precio(id1, 20)
    assert api.insumo_por_id(id1)["costo_directo"] == 20
    # actualizar campo genérico
    api.insumo_actualizar_campo(id1, "unidad", "ton")
    assert api.insumo_por_id(id1)["unidad"] == "ton"
    # costo_final se recalcula automáticamente desde costo_directo * factor_fsr
    # no se puede fijar directamente (se recalcula en cascada)
    api.insumo_actualizar_campo(id1, "costo_directo", 30)
    assert api.insumo_por_id(id1)["costo_directo"] == 30
    # eliminar
    api.eliminar_insumo(id1)
    assert api.insumo_por_id(id1) is None