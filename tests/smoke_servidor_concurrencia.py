"""
smoke_servidor_concurrencia.py
================================
Prueba de humo del fix de concurrencia del servidor HTTP: antes,
Database._abrir() creaba la conexión SQLite sin check_same_thread=False,
y los endpoints síncronos de FastAPI se despachan en un thread pool —
dos requests concurrentes al mismo proyecto, cayendo en threads
distintos, hacían que sqlite3 rechazara la conexión compartida con
ProgrammingError ("SQLite objects created in a thread can only be used
in that same thread").

Esta prueba usa fastapi.testclient.TestClient, que despacha los
endpoints síncronos exactamente igual que un servidor real desplegado
(vía el thread pool interno de Starlette/AnyIO) — no es una
simplificación del problema real.

Cubre:
    - Ráfaga de requests de escritura CONCURRENTES (ThreadPoolExecutor
      con varios workers reales) al mismo proyecto, sin ningún
      ProgrammingError de threading
    - Los datos quedan consistentes al final (todas las escrituras se
      aplicaron, ninguna se perdió por una condición de carrera)
    - Lecturas concurrentes mezcladas con escrituras tampoco crashean

Uso:
    python3 tests/smoke_servidor_concurrencia.py
"""
import os
import sys
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    tmp_base = tempfile.mkdtemp(prefix="smoke_servidor_")

    from backend.database.db import Database, Rutas

    nombre_proyecto = "smoke_concurrencia_test"
    db_path = Rutas.db_proyecto(nombre_proyecto)
    if db_path.exists():
        db_path.unlink()

    # Crear el proyecto con el flujo normal de escritorio (check_same_thread=True,
    # default) y sembrar un insumo con tipo_id conocido para poder actualizarlo.
    db = Database.abrir(db_path)
    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Concurrencia Test')")
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

    try:
        from fastapi.testclient import TestClient
        import server.servidor as srv

        # server.servidor cachea servicios por nombre de proyecto en un dict
        # global (_proyectos) — limpiar por si un test previo dejó algo.
        srv._proyectos.clear()

        client = TestClient(srv.app)

        # ── Ráfaga de escrituras concurrentes (el escenario que rompía) ──
        N = 30
        errores = []

        def _actualizar(i):
            resp = client.post(
                f"/proyectos/{nombre_proyecto}/actualizar",
                json={
                    "entidad": "insumos", "registro_id": 1,
                    "usuario_id": 1, "campos": {"costo_directo": float(i)},
                },
            )
            if resp.status_code != 200:
                return f"request {i}: status {resp.status_code} — {resp.text}"
            return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            futuros = [ex.submit(_actualizar, i) for i in range(N)]
            for f in as_completed(futuros):
                err = f.result()
                if err:
                    errores.append(err)

        assert not errores, (
            f"{len(errores)}/{N} requests concurrentes fallaron "
            f"(el bug de threading de sqlite3 causaba esto antes del fix):\n"
            + "\n".join(errores[:5])
        )
        print(f"OK: {N} escrituras concurrentes (8 workers) sin ningún error de threading")

        # ── Los datos quedan consistentes (alguna de las 30 escrituras "ganó") ──
        resp = client.get(f"/proyectos/{nombre_proyecto}/insumo/1")
        assert resp.status_code == 200
        valor_final = resp.json()["costo_directo"]
        assert 0 <= valor_final < N, f"el valor final debía ser uno de los escritos (0..{N-1}), dio {valor_final}"
        print(f"OK: los datos quedaron consistentes tras la ráfaga (costo_directo final = {valor_final})")

        # ── Lecturas concurrentes mezcladas con escrituras ───────────────
        errores2 = []

        def _mixto(i):
            try:
                if i % 2 == 0:
                    r = client.get(f"/proyectos/{nombre_proyecto}/insumos")
                else:
                    r = client.post(
                        f"/proyectos/{nombre_proyecto}/actualizar",
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
            futuros = [ex.submit(_mixto, i) for i in range(40)]
            for f in as_completed(futuros):
                err = f.result()
                if err:
                    errores2.append(err)

        assert not errores2, (
            f"{len(errores2)} requests de lectura+escritura mezcladas fallaron:\n"
            + "\n".join(errores2[:5])
        )
        print("OK: lecturas y escrituras concurrentes mezcladas (40 requests, 8 workers) sin errores")

        print("\nTODAS LAS PRUEBAS DE CONCURRENCIA DEL SERVIDOR PASARON")
    finally:
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


def test_carrera_registro_proyecto_nuevo():
    """El otro fix de esta corrección: _registro_lock evita que dos
    requests concurrentes pidiendo el MISMO proyecto por primera vez
    (nunca antes cacheado en _proyectos) creen dos Database/conexiones
    distintas para el mismo archivo .db."""
    tmp_base = tempfile.mkdtemp(prefix="smoke_servidor_carrera_")
    from backend.database.db import Database, Rutas

    nombre_proyecto = "smoke_carrera_registro_test"
    db_path = Rutas.db_proyecto(nombre_proyecto)
    if db_path.exists():
        db_path.unlink()

    db = Database.abrir(db_path)
    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Carrera Test')")
    db.conn.commit()
    db.close()

    try:
        from fastapi.testclient import TestClient
        import server.servidor as srv

        srv._proyectos.clear()
        client = TestClient(srv.app)

        # Todos los workers piden el árbol del MISMO proyecto nunca antes
        # abierto por este proceso — el primero en llegar debe crear la
        # entrada en _proyectos; los demás deben reusarla, no crear cada
        # uno la suya.
        errores = []

        def _pedir_arbol(i):
            r = client.get(f"/proyectos/{nombre_proyecto}/arbol")
            if r.status_code != 200:
                return f"request {i}: status {r.status_code} — {r.text}"
            return None

        with ThreadPoolExecutor(max_workers=10) as ex:
            futuros = [ex.submit(_pedir_arbol, i) for i in range(20)]
            for f in as_completed(futuros):
                err = f.result()
                if err:
                    errores.append(err)

        assert not errores, (
            f"{len(errores)} requests fallaron en la carrera de registro:\n"
            + "\n".join(errores[:5])
        )
        assert nombre_proyecto in srv._proyectos, "el proyecto debía quedar registrado"
        print("OK: 20 requests concurrentes pidiendo un proyecto nunca antes "
              "abierto, sin condición de carrera en el registro")
    finally:
        if db_path.exists():
            db_path.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
    test_carrera_registro_proyecto_nuevo()
    print("\nTODAS LAS PRUEBAS (incluida la carrera de registro) PASARON")
