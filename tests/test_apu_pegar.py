"""Pytest para pegado/drag&drop en APU — migrado de smoke_apu_pegar_dragdrop (offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtCore import Qt

from backend.database.repos import ApuMatricesRepo
from frontend.ventana.mixins.apu import ApuMixin
from frontend.ventana.widgets.apu import TablaApuDetalle


class _FakeWindow(ApuMixin):
    def __init__(self, conn, ds, api):
        self._conn = conn
        self._data_service = ds
        self._api = api


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def montaje(qapp, api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    insumo_a = api.insumo_insertar(
        tipo_id=1, descripcion="Cemento gris 50kg", unidad="pza", costo=180.0)
    insumo_b = api.insumo_insertar(
        tipo_id=1, descripcion="Arena de rio m3", unidad="m3", costo=350.0)
    insumo_c = api.insumo_insertar(
        tipo_id=2, descripcion="Peon albañil jornal", unidad="jor", costo=400.0)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
        VALUES
            (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1',  NULL, 0),
            (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 1, 0),
            (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 1, 0)
    """)
    db.conn.commit()
    matriz_a, matriz_b = 2, 3
    comp1 = api.apu_agregar_componente(matriz_a, insumo_a)
    comp2 = api.apu_agregar_componente(matriz_a, insumo_b)
    comp3 = api.apu_agregar_componente(matriz_b, insumo_c)
    repo = ApuMatricesRepo(db.conn)
    tabla_a = TablaApuDetalle(matriz_a, "Concepto A")
    tabla_a._api = api
    tabla_a.poblar(api.apu(nodo_id=matriz_a))
    tabla_b = TablaApuDetalle(matriz_b, "Concepto B")
    tabla_b._api = api
    tabla_b.poblar(api.apu(nodo_id=matriz_b))
    from backend.database.services.data_service import DataService
    from backend.database.services.repository_registry import crear_registry
    from backend.database.event_bus import EventBus
    ds = DataService(db, crear_registry(db), EventBus())
    win = _FakeWindow(db.conn, ds, api)
    return {
        "db": db, "api": api, "ds": ds, "win": win, "repo": repo,
        "tabla_a": tabla_a, "tabla_b": tabla_b,
        "matriz_a": matriz_a, "matriz_b": matriz_b,
        "comp1": comp1, "comp2": comp2, "comp3": comp3,
        "insumo_a": insumo_a, "insumo_b": insumo_b, "insumo_c": insumo_c,
    }


def _item_de(tabla, comp_id):
    for i in range(tabla.topLevelItemCount()):
        it = tabla.topLevelItem(i)
        if it.data(5, Qt.ItemDataRole.UserRole) == comp_id:
            return it
    return None


def test_pegar_descripcion_religa(montaje):
    m = montaje
    item_comp1 = _item_de(m["tabla_a"], m["comp1"])
    assert item_comp1 is not None
    assert m["tabla_a"]._escribir_celda_pegada(item_comp1, 2, "Arena de rio m3")
    m["tabla_a"]._on_item_editado(item_comp1, 2)
    assert m["repo"].buscar(m["comp1"])["insumo_id"] == m["insumo_b"]
    assert not m["tabla_a"]._escribir_celda_pegada(item_comp1, 2, "Texto que no existe")
    assert m["repo"].buscar(m["comp1"])["insumo_id"] == m["insumo_b"]


def test_reordenar_misma_matriz(montaje):
    m = montaje
    assert m["win"]._on_drop_apu([m["comp2"]], m["matriz_a"], m["comp1"], copiar=False)
    assert m["repo"].hermanos_de(m["matriz_a"]) == [m["comp2"], m["comp1"]]


def test_mover_entre_matrices_y_deshacer(montaje):
    m = montaje
    assert m["win"]._on_drop_apu([m["comp1"]], m["matriz_b"], None, copiar=False)
    assert m["repo"].buscar(m["comp1"])["matriz_id"] == m["matriz_b"]
    assert m["comp1"] not in m["repo"].hermanos_de(m["matriz_a"])
    assert m["comp1"] in m["repo"].hermanos_de(m["matriz_b"])
    assert m["ds"].deshacer(usuario_id=1, proyecto_id=1)
    assert m["repo"].buscar(m["comp1"])["matriz_id"] == m["matriz_a"]


def test_copiar_y_deshacer_borra(montaje):
    m = montaje
    db = m["db"]
    ids_antes = {r["id"] for r in db.conn.execute("SELECT id FROM apu_matrices").fetchall()}
    assert m["win"]._on_drop_apu([m["comp3"]], m["matriz_a"], None, copiar=True)
    nuevos = {r["id"] for r in db.conn.execute("SELECT id FROM apu_matrices").fetchall()} - ids_antes
    assert len(nuevos) == 1
    nuevo_id = nuevos.pop()
    assert m["repo"].buscar(nuevo_id)["matriz_id"] == m["matriz_a"]
    assert m["repo"].buscar(nuevo_id)["insumo_id"] == m["insumo_c"]
    assert m["repo"].buscar(m["comp3"])["matriz_id"] == m["matriz_b"]
    assert m["ds"].deshacer(usuario_id=1, proyecto_id=1)
    fila = db.conn.execute(
        "SELECT COUNT(*) AS n FROM apu_matrices WHERE id = ?", [nuevo_id]).fetchone()
    assert fila["n"] == 0
