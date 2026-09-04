"""Pytest para concurrencia del servidor — migrado de smoke_servidor_concurrencia."""
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient

from backend.database.db import Database, Rutas


def _sembrar(nombre):
    db_path = Rutas.db_proyecto(nombre)
    if db_path.exists():
        db_path.unlink()
    db = Database.abrir(db_path)
    cur = db.conn.cursor()
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, activo)
        VALUES (1, 1, 1, 'Insumo de prueba', 'kg', 10, 10, 1)
    """)
    db.conn.commit()
    db.close()
    return db_path


def test_escrituras_concurrentes():
    import server.servidor as srv
    srv._proyectos.clear()
    nombre = "test_concurrencia"
    db_path = _sembrar(nombre)
    tmp_base = tempfile.mkdtemp(prefix="test_servidor_")
    try:
        client = TestClient(srv.app)
        N = 30
        errores = []

        def _actualizar(i):
            resp = client.post(
                f"/proyectos/{nombre}/actualizar",
                json={
                    "entidad": "insumos", "registro_id": 1,
                    "usuario_id": 1, "campos": {"costo_directo": float(i)},
                },
            )
            if resp.status_code != 200:
                return f"request {i}: status {resp.status_code} — {resp.text}"
            return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            for f in as_completed([ex.submit(_actualizar, i) for i in range(N)]):
                err = f.result()
                if err:
                    errores.append(err)
        assert not errores

        resp = client.get(f"/proyectos/{nombre}/insumo/1")
        assert resp.status_code == 200
        assert 0 <= resp.json()["costo_directo"] < N
    finally:
        srv._proyectos.pop(nombre, None)
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


def test_lecturas_escrituras_mezcladas():
    import server.servidor as srv
    srv._proyectos.clear()
    nombre = "test_concurrencia_mixta"
    db_path = _sembrar(nombre)
    tmp_base = tempfile.mkdtemp(prefix="test_servidor_")
    try:
        client = TestClient(srv.app)
        errores = []

        def _mixto(i):
            try:
                if i % 2 == 0:
                    r = client.get(f"/proyectos/{nombre}/insumos")
                else:
                    r = client.post(
                        f"/proyectos/{nombre}/actualizar",
                        json={
                            "entidad": "insumos", "registro_id": 1,
                            "usuario_id": 1, "campos": {"costo_directo": float(i)},
                        },
                    )
                if r.status_code != 200:
                    return f"request {i}: status {r.status_code} — {r.text}"
            except Exception as e:
                return f"request {i}: excepción {type(e).__name__}: {e}"
            return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            for f in as_completed([ex.submit(_mixto, i) for i in range(40)]):
                err = f.result()
                if err:
                    errores.append(err)
        assert not errores
    finally:
        srv._proyectos.pop(nombre, None)
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


def test_carrera_registro_proyecto_nuevo():
    import server.servidor as srv
    srv._proyectos.clear()
    nombre = "test_carrera_registro"
    db_path = Rutas.db_proyecto(nombre)
    if db_path.exists():
        db_path.unlink()
    db = Database.abrir(db_path)
    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Carrera Test')")
    db.conn.commit()
    db.close()
    tmp_base = tempfile.mkdtemp(prefix="test_servidor_carrera_")
    try:
        client = TestClient(srv.app)
        errores = []

        def _pedir_arbol(i):
            r = client.get(f"/proyectos/{nombre}/arbol")
            if r.status_code != 200:
                return f"request {i}: status {r.status_code} — {r.text}"
            return None

        with ThreadPoolExecutor(max_workers=10) as ex:
            for f in as_completed([ex.submit(_pedir_arbol, i) for i in range(20)]):
                err = f.result()
                if err:
                    errores.append(err)
        assert not errores
        assert nombre in srv._proyectos
    finally:
        srv._proyectos.pop(nombre, None)
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)
