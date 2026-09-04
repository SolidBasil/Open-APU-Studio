"""Pytest para fallback DXF — migrado de smoke_cad_dxf_fallback (Hallazgo 13)."""
import os
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from frontend.ventana.mixins.generador import GeneradorMixin
from backend.cad.lector_dxf import DxfParseResult


class _FakeWindow(GeneradorMixin):
    def __init__(self, conn, api, tabs):
        from PySide6.QtWidgets import QStackedWidget
        self._conn = conn
        self._api = api
        self._tabs = tabs
        self._db = None
        self._tabs_generadores = tabs
        self._renglones_stack = QStackedWidget()

    def _switch_tab(self, *args, **kwargs):
        pass


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture()
def win_cad(qapp, api, db_tmp):
    from PySide6.QtWidgets import QTabWidget
    db, _ = db_tmp
    cur = db.conn.cursor()
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 'Concepto A', 0, 0)
    """)
    db.conn.commit()
    win = _FakeWindow(db.conn, api, QTabWidget())
    gen_a = api.generador_crear(nombre="Gen A", concepto_id=1, unidad="m2")
    win._abrir_generador_tab(gen_a, "Gen A")
    container = win._tabs.widget(0)
    assert container is not None and hasattr(container, "_cad_viewer")
    yield win, container
    # sin teardown especial: db_tmp lo limpia el fixture


def test_doc_none_error_visible(win_cad):
    win, container = win_cad
    resultado_sin_doc = DxfParseResult(
        entities=["e1", "e2", "e3"], layers=["capa1"],
        extents_min={"x": 0, "y": 0}, extents_max={"x": 1, "y": 1},
        units="m", doc=None,
    )
    with patch("backend.cad.lector_dxf.parse_dxf", return_value=resultado_sin_doc), \
         patch.object(container._cad_viewer, "set_document") as mock_set_doc, \
         patch.object(container._cad_viewer, "set_entities") as mock_set_ent:
        container._cad_dxf_path = None
        win._cargar_dxf_en_tab(container, "falso.dxf", silencioso=True)
        mock_set_doc.assert_not_called()
        mock_set_ent.assert_not_called()
        assert container._cad_dxf_path is None
        assert "no disponible" in container._cad_coords_lbl.text().lower()


def test_parse_real_usa_set_document(win_cad, tmp_path):
    win, container = win_cad
    dxf_minimo = (
        "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n10\n"
        "0\nENDSEC\n0\nEOF\n"
    )
    ruta = tmp_path / "minimo.dxf"
    ruta.write_text(dxf_minimo)
    with patch.object(container._cad_viewer, "set_document") as mock_set_doc, \
         patch.object(container._cad_viewer, "set_entities") as mock_set_ent:
        win._cargar_dxf_en_tab(container, str(ruta), silencioso=True)
        mock_set_doc.assert_called_once()
        mock_set_ent.assert_not_called()
    assert container._cad_dxf_path == str(ruta)
