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
