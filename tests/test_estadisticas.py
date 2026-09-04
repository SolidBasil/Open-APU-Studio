"""Pytest para 1.4: DiagnosticoRepo.estadisticas() cableado al diálogo
de información del proyecto (conteos del General tab)."""
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from backend.database.db import Database, Rutas
from backend.database.repos.diagnostico import DiagnosticoRepo


def test_estadisticas_conteos_correctos(api, db_tmp):
    db, _ = db_tmp
    api.insumo_insertar(tipo_id=1, descripcion="Mat", unidad="kg", costo=10)
    cap = api.agregar_nodo("capitulo", descripcion="Cap")
    api.agregar_nodo("concepto", padre_id=cap, insumo_id=1, cantidad=1, descripcion="C1")
    est = DiagnosticoRepo(db.conn).estadisticas(1)
    assert est["n_insumos"] == 1
    assert est["n_nodos"] == 2
    assert est["n_conceptos"] == 1
    assert est["n_matrices"] == 0


def test_api_estadisticas_local_equivale_repo(api):
    est_api = api.estadisticas_proyecto()
    assert set(est_api) == {"n_nodos", "n_conceptos", "n_insumos", "n_matrices"}
    assert est_api["n_nodos"] >= 0


def test_estadisticas_por_http():
    import server.servidor as srv
    srv._proyectos.clear()
    nombre = "test_estadisticas"
    db_path = Rutas.db_proyecto(nombre)
    if db_path.exists():
        db_path.unlink()
    db = Database.abrir(db_path)
    db.conn.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    db.conn.commit()
    db.close()
    try:
        client = TestClient(srv.app)
        r = client.get(f"/proyectos/{nombre}/estadisticas")
        assert r.status_code == 200
        est = r.json()
        assert set(est) == {"n_nodos", "n_conceptos", "n_insumos", "n_matrices"}
    finally:
        srv._proyectos.pop(nombre, None)
        if db_path.exists():
            db_path.unlink()