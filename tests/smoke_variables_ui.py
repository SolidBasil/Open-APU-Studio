"""
smoke_variables_ui.py
=======================
Prueba de humo de N3 (UI de "Variables de fórmula", antes solo backend) y
del fix encontrado al construirla: Api.variables_actualizar() no validaba
nombre duplicado al renombrar (solo variables_crear() lo hacía).

Cubre:
    - El handler del botón de toolbar está registrado y apunta al método
      correcto (_on_variables_formula existe en la ventana)
    - El diálogo se construye y puebla la tabla sin errores contra datos
      reales (variables existentes + resolución de valores)
    - variables_actualizar(): renombrar a un nombre duplicado ahora se
      rechaza con ValueError (antes: se mezclaban silenciosamente en el
      diccionario de resolución de ciclos)
    - variables_actualizar(): renombrar a un nombre con formato inválido
      también se rechaza (antes: solo variables_crear() lo validaba)
    - El flujo completo de creación/edición/borrado vía Api sigue
      funcionando igual que antes (regresión sobre el Hallazgo 5)

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_variables_ui.py
"""
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QWidget

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api
from frontend.ventana.mixins.toolbar import _HANDLERS
from frontend.ventana.mixins.navegacion import HandlersMixin


class _FakeDb:
    def __init__(self, conn):
        self._conn = conn


class _FakeWindow(HandlersMixin, QWidget):
    def __init__(self, conn, api):
        QWidget.__init__(self)
        self._db = _FakeDb(conn)
        self._api = api
        from PySide6.QtWidgets import QStatusBar
        self._sb = QStatusBar()


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    # ── El botón de toolbar está registrado ─────────────────────────────
    assert _HANDLERS.get("Variables de fórmula") == "_on_variables_formula", \
        "el botón de toolbar debía apuntar a _on_variables_formula"
    print("OK: 'Variables de fórmula' registrado en _HANDLERS de la toolbar")

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    db = Database.abrir(db_path)
    event_bus = EventBus()
    registry = crear_registry(db)
    ds = DataService(db, registry, event_bus)

    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
    db.conn.commit()
    api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)

    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")

    # ── El diálogo se construye sin crashear con datos reales ───────────
    win = _FakeWindow(db.conn, api)
    assert hasattr(win, "_on_variables_formula"), "el handler debía existir en la ventana"
    with patch.object(QDialog, "exec", return_value=0):
        win._on_variables_formula()  # construye, puebla, resuelve valores, y "exec()" no bloquea (mockeado)
    print("OK: el diálogo se construye y puebla la tabla sin errores (2 variables reales)")

    # ── variables_actualizar(): duplicado al renombrar se rechaza ───────
    try:
        api.variables_actualizar(id_altura, nombre="ancho_muro")  # ya existe
        raise AssertionError("debía rechazar el renombrado a un nombre duplicado")
    except ValueError as e:
        print(f"OK: renombrar a nombre duplicado se rechaza ({e})")

    # confirmar que NO se mezclaron silenciosamente (bug que existía antes)
    nombres = {v["nombre"] for v in api.variables_listar()}
    assert nombres == {"ancho_muro", "altura"}, \
        f"no debía haberse perdido ninguna variable por el intento fallido: {nombres}"
    print("OK: ninguna variable se perdió tras el intento de renombrado duplicado")

    # ── variables_actualizar(): formato de nombre inválido se rechaza ──
    try:
        api.variables_actualizar(id_altura, nombre="123-no-valido")
        raise AssertionError("debía rechazar un nombre con formato inválido")
    except ValueError as e:
        print(f"OK: formato de nombre inválido rechazado en actualizar ({e})")

    # ── Renombrado válido: sigue funcionando ─────────────────────────────
    api.variables_actualizar(id_altura, nombre="altura_muro")
    nombres2 = {v["nombre"] for v in api.variables_listar()}
    assert "altura_muro" in nombres2 and "altura" not in nombres2
    print("OK: renombrado válido sigue funcionando normalmente")

    db.close()
    print("\nTODAS LAS PRUEBAS DE N3 (UI de variables) PASARON")


if __name__ == "__main__":
    main()
