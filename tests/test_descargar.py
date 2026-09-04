"""Pytest para descarga de proyecto en servidor (evicción de _proyectos)."""
import shutil
import sqlite3

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from backend.database.db import Database, Rutas


def _sembrar(nombre):
    db_path = Rutas.db_proyecto(nombre)
    if db_path.exists():
        db_path.unlink()
    db = Database.abrir(db_path)
    db.conn.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    db.conn.commit()
    db.close()
    return db_path


def test_descargar_libera_entrada():
    import server.servidor as srv
    srv._proyectos.clear()
    nombre = "test_descargar"
    db_path = _sembrar(nombre)
    tmp_base = None
    import tempfile
    tmp_base = tempfile.mkdtemp(prefix="test_descargar_")
    try:
        client = TestClient(srv.app)
        assert client.get(f"/proyectos/{nombre}/arbol").status_code == 200
        assert nombre in srv._proyectos

        r = client.post(f"/proyectos/{nombre}/descargar")
        assert r.status_code == 200
        assert r.json() == {"ok": True, "estaba_cargado": True}
        assert nombre not in srv._proyectos

        # idempotente: segunda vez no falla
        r2 = client.post(f"/proyectos/{nombre}/descargar")
        assert r2.json() == {"ok": True, "estaba_cargado": False}

        # el proyecto sigue sirviendo (recarga bajo demanda)
        assert client.get(f"/proyectos/{nombre}/arbol").status_code == 200
        assert nombre in srv._proyectos
    finally:
        srv._proyectos.pop(nombre, None)
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


def test_descargar_libera_lock_archivo():
    import server.servidor as srv
    srv._proyectos.clear()
    nombre = "test_descargar_lock"
    db_path = _sembrar(nombre)
    try:
        client = TestClient(srv.app)
        assert client.get(f"/proyectos/{nombre}/arbol").status_code == 200
        client.post(f"/proyectos/{nombre}/descargar")
        # escritura directa debe funcionar (antes: database is locked)
        conn = sqlite3.connect(str(db_path), timeout=10)
        conn.execute("UPDATE proyectos SET nombre = 'X' WHERE id = 1")
        conn.commit()
        assert conn.execute("SELECT nombre FROM proyectos WHERE id = 1").fetchone()[0] == "X"
        conn.close()
    finally:
        srv._proyectos.pop(nombre, None)
        if db_path.exists():
            db_path.unlink()
