"""
smoke_generador_tabs.py
========================
Prueba de humo de la capa de UI para abrir generadores en pestañas
independientes y arrastrar renglones entre ellas (ver
GeneradorMixin._abrir_generador_tab/_on_drop_generador en
mixins/generador.py, y TablaGenerador.dropEvent en widgets/generador.py).

La lógica de negocio (mover/copiar/deshacer) ya se prueba a fondo en
smoke_generador_dragdrop.py contra DataService directamente; este test
cubre la capa encima: que abrir dos pestañas cree dos TablaGenerador
independientes, y que _on_drop_generador de verdad mueva un renglón de
la tabla de una pestaña a la de la otra y refresque ambas.

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_generador_tabs.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTabWidget

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.repos.generador import GeneradorRepo
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api
from frontend.ventana.mixins.generador import GeneradorMixin


class _FakeWindow(GeneradorMixin):
    """Objeto mínimo con el mixin real de Generadores + un QTabWidget
    real, para probar abrir pestañas y arrastrar entre ellas."""
    def __init__(self, conn, api):
        self._conn = conn
        self._api = api
        self._tabs = QTabWidget()
        self._gen_seleccionado = None
        self._gen_nombre_base = ""


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
        db.conn.commit()
        api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)
        win = _FakeWindow(db.conn, api)

        cur.execute("""
            INSERT INTO estructura_presupuesto
                (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
            VALUES
                (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1',  NULL, 0),
                (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 0, 0),
                (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 0, 0)
        """)
        db.conn.commit()

        gen_a = api.generador_crear(nombre="Gen A", concepto_id=2, unidad="m2")
        gen_b = api.generador_crear(nombre="Gen B", concepto_id=3, unidad="m2")
        r1 = api.generador_renglon_guardar(gen_a, eje="1", tramo="A-B", veces=1, largo=10, ancho=2)

        # ── Caso 1: abrir dos pestañas independientes ──
        win._abrir_generador_tab(gen_a, "Gen A")
        win._abrir_generador_tab(gen_b, "Gen B")
        assert win._tabs.count() == 2, f"esperaba 2 pestañas, hay {win._tabs.count()}"
        tabla_a = win._tabs.widget(0)._tabla_generador
        tabla_b = win._tabs.widget(1)._tabla_generador
        assert tabla_a._generador_id == gen_a
        assert tabla_b._generador_id == gen_b
        assert tabla_a.topLevelItemCount() == 2  # r1 + fila vacía placeholder
        print("OK  — abrir dos generadores en pestañas independientes")

        # reabrir la misma pestaña no debe duplicarla, solo enfocarla
        win._abrir_generador_tab(gen_a, "Gen A")
        assert win._tabs.count() == 2, "reabrir un generador ya abierto no debe crear otra pestaña"
        print("OK  — reabrir un generador ya abierto enfoca la pestaña existente, no la duplica")

        # ── Caso 2: mover r1 de la pestaña de Gen A a la de Gen B ──
        ok = win._on_drop_generador([r1], gen_b, None, copiar=False)
        assert ok
        repo = GeneradorRepo(db.conn)
        assert repo.buscar_renglon(r1)["generador_id"] == gen_b
        # las dos tablas de pestañas deben haberse refrescado solas
        assert tabla_a.topLevelItemCount() == 1, "Gen A debía quedar solo con la fila vacía"
        assert tabla_b.topLevelItemCount() == 2, "Gen B debía ganar el renglón movido + su fila vacía"
        print("OK  — mover un renglón entre pestañas refresca ambas tablas visibles")

        db.close()
        print("OK — pestañas de Generadores y drag and drop entre ellas funcionan correctamente")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
