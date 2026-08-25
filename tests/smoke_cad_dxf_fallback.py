"""
smoke_cad_dxf_fallback.py
==========================
Prueba de humo de la corrección del Hallazgo 13 (set_entities() era un
compat shim no-op y GeneradorMixin._cargar_dxf_en_tab lo llamaba en
silencio cuando result.doc era None, dejando el visor vacío sin avisar).

Cubre:
    - Caso normal: parse_dxf() real siempre trae doc -> set_document()
      se usa (nunca cae en la rama vieja).
    - Caso simulado result.doc=None (el único disparador real del bug,
      aunque parse_dxf() de hoy nunca lo produce): antes esto llamaba a
      set_entities() en silencio y el usuario no se enteraba. Ahora debe
      lanzar un error explícito que cae en el manejo de errores existente
      (container._cad_coords_lbl con "DXF no disponible" en modo
      silencioso, para no bloquear el test con un QMessageBox modal).
    - set_entities() sigue existiendo (compat shim) pero ya no tiene
      ningún llamador real en el repo.

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_cad_dxf_fallback.py
"""
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api
from frontend.ventana.mixins.generador import GeneradorMixin
from backend.cad.lector_dxf import DxfParseResult


class _FakeWindow(GeneradorMixin):
    def __init__(self, conn, api):
        self._conn = conn
        self._api = api
        self._tabs = QTabWidget()
        self._db = None


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    try:
        db = Database.abrir(db_path)
        event_bus = EventBus()
        registry = crear_registry(db)
        ds = DataService(db, registry, event_bus)

        cur = db.conn.cursor()
        cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
        cur.execute("""
            INSERT INTO estructura_presupuesto
                (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
            VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 'Concepto A', 0, 0)
        """)
        db.conn.commit()
        api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)
        win = _FakeWindow(db.conn, api)

        gen_a = api.generador_crear(nombre="Gen A", concepto_id=1, unidad="m2")
        win._abrir_generador_tab(gen_a, "Gen A")
        container = win._tabs.widget(0)
        assert container is not None and hasattr(container, "_cad_viewer")

        # ── Caso 1: result.doc=None simulado (el caso que causaba el bug) ──
        entidades_falsas = ["e1", "e2", "e3"]
        capas_falsas = ["capa1"]
        resultado_sin_doc = DxfParseResult(
            entities=entidades_falsas, layers=capas_falsas,
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
            assert container._cad_dxf_path is None, \
                "no debió actualizarse la ruta del DXF si falló la carga"
            texto = container._cad_coords_lbl.text()
            assert "no disponible" in texto.lower(), \
                f"debía mostrar aviso de 'DXF no disponible', mostró: {texto!r}"
        print("OK — result.doc=None ahora produce un error visible (antes: silencio total)")

        # ── Caso 2: parse_dxf real (con un DXF válido mínimo) siempre trae doc ──
        dxf_minimo = (
            "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n10\n"
            "0\nENDSEC\n0\nEOF\n"
        )
        tmp_dxf = tempfile.NamedTemporaryFile(suffix=".dxf", delete=False, mode="w")
        tmp_dxf.write(dxf_minimo)
        tmp_dxf.close()
        try:
            with patch.object(container._cad_viewer, "set_document") as mock_set_doc, \
                 patch.object(container._cad_viewer, "set_entities") as mock_set_ent:
                win._cargar_dxf_en_tab(container, tmp_dxf.name, silencioso=True)
                mock_set_doc.assert_called_once()
                mock_set_ent.assert_not_called()
            assert container._cad_dxf_path == tmp_dxf.name
            print("OK — parse_dxf() real siempre trae doc -> set_document() se usa, nunca set_entities()")
        finally:
            os.unlink(tmp_dxf.name)

        db.close()
        print("\nTODAS LAS PRUEBAS DEL HALLAZGO 13 PASARON")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
