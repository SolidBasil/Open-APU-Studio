"""Pytest para coordenadas negativas — migrado de smoke_coordenadas_negativas (N7)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make(widget_type: str, value):
    from PySide6.QtWidgets import QDoubleSpinBox
    w = QDoubleSpinBox()
    if widget_type == "spin_float":
        w.setDecimals(2)
        w.setRange(0, 999999)
    elif widget_type == "spin_coord":
        w.setDecimals(6)
        w.setRange(-180, 180)
    w.setValue(float(value) if value else 0)
    return w


def test_spin_coord_conserva_negativos(qapp):
    w_lon = _make("spin_coord", -99.1332)
    assert abs(w_lon.value() - (-99.1332)) < 1e-4
    w_lat = _make("spin_coord", 19.4326)
    assert abs(w_lat.value() - 19.4326) < 1e-4
    assert _make("spin_coord", -99.1332).value() != 0.0


def test_spin_float_sigue_recortando(qapp):
    assert _make("spin_float", -5.0).value() == 0.0


def test_proyecto_guardar_longitud_negativa(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    api.proyecto_guardar({"obra_latitud": 19.4326, "obra_longitud": -99.1332})
    fila = cur.execute(
        "SELECT obra_latitud, obra_longitud FROM proyectos WHERE id=1").fetchone()
    assert abs(fila["obra_longitud"] - (-99.1332)) < 1e-4
