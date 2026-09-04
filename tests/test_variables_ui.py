"""Pytest para UI de variables — migrado de smoke_variables_ui (N3, offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_boton_toolbar_registrado(qapp):
    from frontend.ventana.mixins.toolbar import _HANDLERS
    assert _HANDLERS.get("Variables de fórmula") == "_on_variables_formula"


def test_dialogo_construye_con_datos(qapp, api, db_tmp):
    from unittest.mock import patch
    from PySide6.QtWidgets import QDialog, QWidget, QStatusBar
    from frontend.ventana.mixins.navegacion import HandlersMixin

    db, _ = db_tmp

    class _FakeDb:
        def __init__(self, conn):
            self._conn = conn

    class _FakeWindow(HandlersMixin, QWidget):
        def __init__(self, conn, api):
            QWidget.__init__(self)
            self._db = _FakeDb(conn)
            self._api = api
            self._sb = QStatusBar()

    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")

    win = _FakeWindow(db.conn, api)
    assert hasattr(win, "_on_variables_formula")
    with patch.object(QDialog, "exec", return_value=0):
        win._on_variables_formula()

    with pytest.raises(ValueError):
        api.variables_actualizar(id_altura, nombre="ancho_muro")
    assert {v["nombre"] for v in api.variables_listar()} == {"ancho_muro", "altura"}

    with pytest.raises(ValueError):
        api.variables_actualizar(id_altura, nombre="123-no-valido")

    api.variables_actualizar(id_altura, nombre="altura_muro")
    nombres2 = {v["nombre"] for v in api.variables_listar()}
    assert "altura_muro" in nombres2 and "altura" not in nombres2
