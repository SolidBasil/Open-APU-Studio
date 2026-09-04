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


def test_duracion_faltante_marca_afectados(api, db_tmp):
    """Migrado de smoke_indirectos_duracion (Hallazgo 7)."""
    db, _ = db_tmp
    cur = db.conn.cursor()
    id_residente = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Personal", "concepto": "Residente",
        "periodo_dias": 30, "importe": 15000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    id_flete = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Logística", "concepto": "Flete inicial",
        "periodo_dias": 0, "importe": 5000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 2,
    })
    resultado = api.indirectos_calcular_totales()
    assert resultado["duracion_obra_dias"] == 0.0
    assert id_residente in resultado["afectados_por_duracion_faltante"]
    assert id_flete not in resultado["afectados_por_duracion_faltante"]
    fila = [r for r in api.indirectos_lista("campo") if r["id"] == id_residente][0]
    assert float(fila["total"]) == 0.0

    api.proyecto_guardar({"duracion_obra_dias": 30})
    resultado2 = api.indirectos_calcular_totales()
    assert resultado2["duracion_obra_dias"] == 30.0
    assert resultado2["afectados_por_duracion_faltante"] == []
    fila2 = [r for r in api.indirectos_lista("campo") if r["id"] == id_residente][0]
    assert abs(float(fila2["total"]) - 15000.0) < 0.01


def test_aplicar_propaga_aviso_duracion(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    id_residente = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Personal", "concepto": "Residente",
        "periodo_dias": 30, "importe": 15000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, activo)
        VALUES (1, 1, 1, 'Cemento', 'kg', 200, 200, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo,
             insumo_id, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto', 1000, 200000, 1)
    """)
    db.conn.commit()
    resultado3 = api.indirectos_aplicar_a_sobrecosto()
    assert resultado3["duracion_obra_dias"] == 0.0
    assert id_residente in resultado3["afectados_por_duracion_faltante"]