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
