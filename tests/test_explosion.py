"""Pytest para explosión de insumos — migrado de smoke_explosion (solo local)."""
import pytest


def test_explotar(api):
    """Prueba la explosión de insumos."""
    # Crear estructura básica
    cap = api.agregar_nodo("capitulo", descripcion="Cap1")
    ins = api.insumo_insertar(tipo_id=1, descripcion="Material", unidad="kg", costo=10)
    conc = api.agregar_nodo("concepto", padre_id=cap, insumo_id=api.insumo_insertar(tipo_id=1, descripcion="Compuesto", unidad="m3", costo=0, es_compuesto=1), cantidad=2)

    # El insumo compuesto tiene APU
    ins_comp = api.insumo_insertar(tipo_id=1, descripcion="Mezcla", unidad="m3", costo=0, es_compuesto=1)
    api.apu_agregar_componente(-ins_comp, api.insumo_insertar(tipo_id=1, descripcion="SubMat", unidad="kg", costo=5), valor=1.5)

    # Reasignar concepto al compuesto
    api.concepto_reasignar_insumo(conc, ins_comp)

    # Explotar
    filas, total = api.explotar([conc], nivel="basico", tipos_ids=[1])
    assert len(filas) > 0
    assert total > 0
    assert any(f["tipo_id"] == 1 for f in filas)
    assert sum(f["total"] for f in filas) == pytest.approx(total)

    # Primer nivel
    filas2, total2 = api.explotar([conc], nivel="primer_nivel", tipos_ids=[1])
    assert len(filas2) >= 0