"""Pytest de regresión (GUIA_DEUDA_TECNICA.md 4.2): al repoblarse por
ProyectoRecalculado, cada tabla reaplica el filtro de búsqueda sobre
SÍ MISMA vía filter_rows() — nunca trepando a window()._on_search(),
que filtraría la pestaña activa (posiblemente otra tabla).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _FakeInput:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


def _con_datos(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
        VALUES
            (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1', NULL, 0),
            (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 1, 100)
    """)
    db.conn.commit()


def test_arbol_filtra_sobre_si_mismo(qapp, api, db_tmp):
    from frontend.ventana.widgets.arbol import TablaArbol
    _con_datos(api, db_tmp)
    tree = TablaArbol()
    tree._api = api
    tree.poblar(api.presupuesto_arbol())
    llamadas = []
    tree._search_input = _FakeInput("ZZZ-sin-coincidencia")
    tree._on_search = lambda texto: llamadas.append(texto)
    tree._on_proyecto_recalculado(object())
    qapp.processEvents()
    qapp.processEvents()
    assert llamadas == [], "no debe trepar a window()._on_search"
    assert tree.topLevelItem(0).isHidden(), "el filtro debe aplicarse sobre esta tabla"


def test_insumos_filtra_sobre_si_mismo(qapp, api, db_tmp):
    from frontend.ventana.widgets.insumos import TablaInsumos
    _con_datos(api, db_tmp)
    tabla = TablaInsumos()
    tabla._api = api
    tabla.poblar(api.insumos(), set())
    llamadas = []
    tabla._search_input = _FakeInput("ZZZ-sin-coincidencia")
    tabla._on_search = lambda texto: llamadas.append(texto)
    tabla._on_proyecto_recalculado(object())
    qapp.processEvents()
    qapp.processEvents()
    assert llamadas == [], "no debe trepar a window()._on_search"
    assert tabla.topLevelItem(0).isHidden(), "el filtro debe aplicarse sobre esta tabla"
