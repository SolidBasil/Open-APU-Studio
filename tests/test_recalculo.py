"""Pytest para convergencia de recálculo — migrado de smoke_recalculo_convergencia."""
from backend.database.repos.recalculo import RecalculoRepo


def _ciclo_divergente(db):
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (10, 1, 1, 'Compuesto A', 'lote', 1.0, 1.0, 1, 1),
            (11, 1, 1, 'Compuesto B', 'lote', 1.0, 1.0, 1, 1)
    """)
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio)
        VALUES (-10, 11, 2, '*', 1.0), (-11, 10, 2, '*', 1.0)
    """)
    db.conn.commit()


def test_ciclo_divergente_no_converge(db_tmp):
    db, _ = db_tmp
    _ciclo_divergente(db)
    r = RecalculoRepo(db.conn).recalcular_proyecto(1)
    db.conn.commit()
    assert r["iteraciones_compuestos"] == RecalculoRepo.MAX_ITERACIONES
    assert r["convergio"] is False


def test_caso_normal_converge(db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (20, 1, 1, 'Cemento',            'kg',   10.0, 10.0, 0, 1),
            (21, 1, 1, 'Compuesto simple A', 'lote', 0.0,  0.0,  1, 1)
    """)
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio)
        VALUES (-21, 20, 3, '*', 10.0)
    """)
    db.conn.commit()
    r = RecalculoRepo(db.conn).recalcular_proyecto(1)
    db.conn.commit()
    assert r["convergio"] is True
    assert r["iteraciones_compuestos"] < RecalculoRepo.MAX_ITERACIONES


def test_api_propaga_convergio(api, db_tmp):
    db, _ = db_tmp
    _ciclo_divergente(db)
    r = api.recalcular_proyecto()
    assert "convergio" in r
    assert r["convergio"] is False


def test_totales_exactos_proyecto_pequeno(api, db_tmp):
    """Ambas variantes de matriz (concepto positive y compuesto negative)
    aparecen en los resúmenes con valores exactos: mat 10×2=20, X se
    compone de mat; c1 = 5×X = 100, c2 = 3×mat = 30, cap = 130."""
    db, _ = db_tmp
    id_mat = api.insumo_insertar(tipo_id=1, descripcion="Mat", unidad="kg", costo=10)
    id_x = api.insumo_insertar(
        tipo_id=1, descripcion="X", unidad="lote", costo=0, es_compuesto=1)
    cap = api.agregar_nodo("capitulo", descripcion="Cap")
    c1 = api.agregar_nodo("concepto", padre_id=cap, insumo_id=id_x, cantidad=5)
    c2 = api.agregar_nodo("concepto", padre_id=cap, insumo_id=id_mat, cantidad=3)
    # APUs: X usa 2 de mat; c1 usa 1 de X
    api.apu_agregar_componente(-id_x, id_mat, valor=2)
    api.apu_agregar_componente(c1, id_x, valor=1)
    r = api.recalcular_proyecto()
    assert r["convergio"] is True
    assert api.nodo_total(c1) == 100.0
    assert api.nodo_total(c2) == 30.0
    assert api.nodo_total(cap) == 130.0
    # resumenes: clave negativa (compuesto X) y positiva (concepto c1);
    # el costo_directo del resumen es la suma del APU (no × cantidad)
    from backend.database.repos.recalculo import RecalculoRepo
    res = RecalculoRepo(db.conn).calcular_todos_resumenes(1)
    assert res[-id_x]["costo_directo"] == 20.0
    assert res[-id_x]["materiales"] == 20.0
    assert res[c1]["costo_directo"] == 20.0
    assert res[c1]["materiales"] == 20.0
    assert c2 not in res or res[c2]["costo_directo"] == 0.0
