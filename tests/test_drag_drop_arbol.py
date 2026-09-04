"""Pytest para drag&drop del árbol — migrado de smoke_drag_drop_arbol (offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from backend.database.repos import NodoRepo
from backend.database.services.data_service import DataService
from backend.database.services.repository_registry import crear_registry
from backend.database.event_bus import EventBus
from frontend.ventana.mixins.navegacion import HandlersMixin


class _FakeWindow(HandlersMixin):
    def __init__(self, db, ds, api):
        self._db = db
        self._data_service = ds
        self._api = api


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def win_arbol(qapp, api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
        VALUES
            (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1', NULL, 0),
            (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 1, 100),
            (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 1, 200),
            (4, 1, NULL, '2',   0, 2, 'capitulo', 'Capítulo 2', NULL, 0),
            (5, 1, 4,    '2.1', 1, 1, 'concepto', 'Concepto C', 1, 300)
    """)
    db.conn.commit()
    ds = DataService(db, crear_registry(db), EventBus())
    win = _FakeWindow(db, ds, api)
    yield win, api, db, ds


def test_rechaza_ciclo(win_arbol):
    win, api, db, ds = win_arbol
    repo = NodoRepo(db.conn)
    assert not win._on_drop_arbol([1], nuevo_padre_id=2, antes_de_id=None, copiar=False)
    assert repo.buscar(1)["padre_id"] is None


def test_mover_al_final_y_posicion(win_arbol):
    win, api, db, ds = win_arbol
    repo = NodoRepo(db.conn)
    assert win._on_drop_arbol([2], nuevo_padre_id=4, antes_de_id=None, copiar=False)
    assert repo.buscar(2)["padre_id"] == 4
    assert repo.hermanos_de(4, 1) == [5, 2]
    assert win._on_drop_arbol([3], nuevo_padre_id=4, antes_de_id=5, copiar=False)
    assert repo.hermanos_de(4, 1) == [3, 5, 2]


def test_copiar_deshacer_rehacer(win_arbol):
    win, api, db, ds = win_arbol
    repo = NodoRepo(db.conn)
    ids_antes = {r["id"] for r in db.conn.execute("SELECT id FROM estructura_presupuesto").fetchall()}
    assert win._on_drop_arbol([5], nuevo_padre_id=1, antes_de_id=None, copiar=True)
    nuevos = {r["id"] for r in db.conn.execute("SELECT id FROM estructura_presupuesto").fetchall()} - ids_antes
    assert len(nuevos) == 1
    nuevo_id = nuevos.pop()
    assert repo.buscar(nuevo_id)["descripcion"] == "Concepto C"
    assert repo.buscar(nuevo_id)["padre_id"] == 1
    assert repo.buscar(5)["padre_id"] == 4
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    fila = db.conn.execute(
        "SELECT activo FROM estructura_presupuesto WHERE id = ?", [nuevo_id]).fetchone()
    assert fila["activo"] == 0
    assert nuevo_id not in repo.hermanos_de(1, 1)
    assert ds.rehacer(usuario_id=1, proyecto_id=1)
    fila = db.conn.execute(
        "SELECT activo FROM estructura_presupuesto WHERE id = ?", [nuevo_id]).fetchone()
    assert fila["activo"] == 1
