"""Pytest para insumos — migrado de smoke_insumos (solo local)."""


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

def test_insumos_con_matrices_equivale_filtro_viejo(api):
    id_simple = api.insumo_insertar(tipo_id=1, descripcion="Simple X", unidad="kg", costo=5)
    id_comp = api.insumo_insertar(
        tipo_id=1, descripcion="Compuesto X", unidad="m3", costo=0, es_compuesto=1)
    nuevo = api.insumos_con_matrices()
    ids_nuevo = {i["id"] for i in nuevo}
    assert id_comp in ids_nuevo
    assert id_simple not in ids_nuevo
    # misma semántica que el patrón viejo (fetch + filtro Python)
    ids_viejo = api.insumo_ids_con_apu()
    esperado = [i for i in api.insumos() if i.get("id") in ids_viejo]
    assert [i["id"] for i in nuevo] == [i["id"] for i in esperado]
    # con filtro de tipo inexistente no trae nada en ambos
    assert api.insumos_con_matrices("no_existe") == []
