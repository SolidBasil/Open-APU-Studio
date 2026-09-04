"""Pytest para pestañas de generadores — migrado de smoke_generador_tabs (offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def win_tabs(qapp, api, db_tmp):
    from PySide6.QtWidgets import QTabWidget, QStackedWidget
    from frontend.ventana.mixins.generador import GeneradorMixin
    from backend.database.repos.generador import GeneradorRepo

    class _FakeWindow(GeneradorMixin):
        def __init__(self, conn, api, tabs):
            self._conn = conn
            self._api = api
            self._tabs = tabs
            self._tabs_generadores = tabs
            self._renglones_stack = QStackedWidget()
            self._db = None

        def _switch_tab(self, *args, **kwargs):
            pass

    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
        VALUES
            (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1',  NULL, 0),
            (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 0, 0),
            (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 0, 0)
    """)
    db.conn.commit()
    win = _FakeWindow(db.conn, api, QTabWidget())
    gen_a = api.generador_crear(nombre="Gen A", concepto_id=2, unidad="m2")
    gen_b = api.generador_crear(nombre="Gen B", concepto_id=3, unidad="m2")
    r1 = api.generador_renglon_guardar(gen_a, eje="1", tramo="A-B", veces=1, largo=10, ancho=2)
    yield win, api, db, gen_a, gen_b, r1


def test_abrir_dos_pestanas_independientes(win_tabs):
    win, api, db, gen_a, gen_b, r1 = win_tabs
    win._abrir_generador_tab(gen_a, "Gen A")
    win._abrir_generador_tab(gen_b, "Gen B")
    assert win._tabs.count() == 2
    tabla_a = win._tabs.widget(0)._tabla_generador
    tabla_b = win._tabs.widget(1)._tabla_generador
    assert tabla_a._generador_id == gen_a
    assert tabla_b._generador_id == gen_b
    assert tabla_a.topLevelItemCount() == 2
    win._abrir_generador_tab(gen_a, "Gen A")
    assert win._tabs.count() == 2


def test_mover_renglon_entre_pestanas(win_tabs):
    from backend.database.repos.generador import GeneradorRepo
    win, api, db, gen_a, gen_b, r1 = win_tabs
    win._abrir_generador_tab(gen_a, "Gen A")
    win._abrir_generador_tab(gen_b, "Gen B")
    tabla_a = win._tabs.widget(0)._tabla_generador
    tabla_b = win._tabs.widget(1)._tabla_generador
    assert win._on_drop_generador([r1], gen_b, None, copiar=False)
    assert GeneradorRepo(db.conn).buscar_renglon(r1)["generador_id"] == gen_b
    assert tabla_a.topLevelItemCount() == 1
    assert tabla_b.topLevelItemCount() == 2
