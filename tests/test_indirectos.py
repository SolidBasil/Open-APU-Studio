"""Pytest para indirectos — migrado de smoke_indirectos (solo local)."""


def test_indirectos_lista_y_plantilla(api):
    """Lista indirectos, carga plantilla, calcula totales."""
    assert len(api.indirectos_lista()) == 0
    # Cargar plantilla campo
    n = api.indirectos_cargar_plantilla("campo")
    assert n == 45
    lista = api.indirectos_lista("campo")
    assert len(lista) == 45
    # Calcular totales (sin insumos/conceptos, devuelve solo duracion_obra_dias)
    totales = api.indirectos_calcular_totales()
    assert "duracion_obra_dias" in totales
    assert "afectados_por_duracion_faltante" in totales
    # Aplicar a sobrecosto (costo directo 0 debe fallar)
    try:
        api.indirectos_aplicar_a_sobrecosto()
        assert False, "debía fallar sin costo directo"
    except ValueError:
        pass