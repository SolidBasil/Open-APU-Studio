"""Fixtures compartidos para smokes y futuros tests pytest."""
import tempfile
import pathlib
import pytest

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.data_service import DataService
from backend.database.services.repository_registry import crear_registry
from frontend.ventana.api import Api


@pytest.fixture
def db_tmp():
    tmp = tempfile.mktemp(suffix=".db")
    db = Database(tmp)
    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
    cur.execute("INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material') ON CONFLICT DO NOTHING")
    db.conn.commit()
    yield db, tmp
    db.close()
    pathlib.Path(tmp).unlink(missing_ok=True)
    for p in pathlib.Path(tmp).parent.glob(pathlib.Path(tmp).name + "*"):
        try:
            p.unlink()
        except OSError:
            pass


@pytest.fixture
def api(db_tmp):
    db, tmp = db_tmp
    eb = EventBus()
    ds = DataService(db, crear_registry(db), eb)
    return Api(db.conn, tmp, proyecto_id=1, data_service=ds)


def _puerto_libre() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def servidor_http():
    """Levanta server/servidor.py real con uvicorn en hilo (para paridad local-vs-HTTP)."""
    import socket
    import threading
    import time
    uvicorn = pytest.importorskip("uvicorn")
    import server.servidor as srv
    srv._proyectos.clear()
    puerto = _puerto_libre()
    config = uvicorn.Config(srv.app, host="127.0.0.1", port=puerto, log_level="error")
    server_uv = uvicorn.Server(config)
    hilo = threading.Thread(target=server_uv.run, daemon=True)
    hilo.start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("el servidor de prueba no arrancó a tiempo")
    yield f"http://127.0.0.1:{puerto}"
    server_uv.should_exit = True
    hilo.join(timeout=5)
