"""Pytest para pegado en árbol — migrado de smoke_pegar_insumo (offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

Qt = pytest.importorskip("PySide6.QtCore").Qt

from frontend.ventana.mixins.apu import ApuMixin
from frontend.ventana.widgets.arbol import TablaArbol, INSUMO_ROLE


class _FakeWindow(ApuMixin):
    def __init__(self, api):
        self._api = api


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _montar(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    insumo_a = api.insumo_insertar(
        tipo_id=1, descripcion="Cemento gris 50kg", unidad="pza", costo=180.0)
    insumo_b = api.insumo_insertar(
        tipo_id=1, descripcion="Arena de rio m3", unidad="m3", costo=350.0)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, insumo_id, descripcion, cantidad, total)
        VALUES
            (1, 1, NULL, '1',   0, 0, 'capitulo', NULL, 'Capítulo 1', NULL, 0),
            (2, 1, 1,    '1.1', 1, 0, 'concepto', ?,    '', 1, 180),
            (3, 1, 1,    '1.2', 1, 1, 'concepto', ?,    '', 1, 350)
    """, [insumo_a, insumo_b])
    db.conn.commit()
    tree = TablaArbol()
    tree._api = api
    tree.poblar(api.presupuesto_arbol())
    return tree, _FakeWindow(api), insumo_a, insumo_b


def test_pegar_descripcion_religa(qapp, api, db_tmp):
    tree, win, insumo_a, insumo_b = _montar(api, db_tmp)
    item_b = tree._buscar_item_por_id(3)
    assert item_b.data(0, INSUMO_ROLE) == insumo_b
    tree.setCurrentItem(item_b, 4)
    assert tree._escribir_celda_pegada(item_b, 4, "Cemento gris 50kg")
    win._on_concepto_editado(item_b, 4)
    assert api.campo_valor("estructura_presupuesto", "insumo_id", 3)["insumo_id"] == insumo_a


def test_unidad_sola_no_religa(qapp, api, db_tmp):
    tree, win, insumo_a, insumo_b = _montar(api, db_tmp)
    item_b = tree._buscar_item_por_id(3)
    assert tree._resolver_insumo_pegado(item_b, 5, "m3") is None


def test_texto_desconocido_no_toca(qapp, api, db_tmp):
    tree, win, insumo_a, insumo_b = _montar(api, db_tmp)
    item_b = tree._buscar_item_por_id(3)
    assert not tree._escribir_celda_pegada(item_b, 4, "Texto que no existe en el catálogo")
    assert api.campo_valor("estructura_presupuesto", "insumo_id", 3)["insumo_id"] == insumo_b


def test_capitulo_texto_libre(qapp, api, db_tmp):
    tree, win, insumo_a, insumo_b = _montar(api, db_tmp)
    item_cap = tree._buscar_item_por_id(1)
    assert tree._resolver_insumo_pegado(item_cap, 4, "Capítulo renombrado") == ("Capítulo renombrado", None)
    assert tree._resolver_insumo_pegado(item_cap, 3, "algo") is None
