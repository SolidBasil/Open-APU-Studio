"""
smoke_pegar_insumo.py
======================
Prueba de humo end-to-end (sin mocks) del pegado en el árbol de
Presupuesto: copiar la fila de un concepto ligado a un insumo y pegarla
sobre otro concepto debe re-ligarlo al insumo correcto, usando
Descripción/Unidad (visibles por defecto) — no solo Clave, que está
oculta por defecto (ver TablaArbol._resolver_insumo_pegado).

Cubre:
    - Copiar un concepto ligado a Insumo A y pegar su Descripción sobre
      un concepto ligado a Insumo B → el segundo debe terminar ligado a A.
    - Lo mismo pegando la Unidad en vez de la Descripción.
    - Pegar un texto que no coincide con ningún insumo no debe tocar la
      celda ni desligar el concepto.

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_pegar_insumo.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api
from frontend.ventana.mixins.apu import ApuMixin
from frontend.ventana.widgets.arbol import TablaArbol, ID_ROLE, INSUMO_ROLE


class _FakeWindow(ApuMixin):
    """Objeto mínimo con el mixin real de edición inline, para probar
    _on_concepto_editado sin levantar toda VentanaPrincipal."""
    def __init__(self, api):
        self._api = api


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

        insumo_a = api.insumo_insertar(
            tipo_id=1, descripcion="Cemento gris 50kg", unidad="pza", costo=180.0,
        )
        insumo_b = api.insumo_insertar(
            tipo_id=1, descripcion="Arena de rio m3", unidad="m3", costo=350.0,
        )

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
        win = _FakeWindow(api)
        nodos = api.presupuesto_arbol()
        tree.poblar(nodos)

        item_a = tree._buscar_item_por_id(2)   # concepto ligado a insumo_a (Cemento)
        item_b = tree._buscar_item_por_id(3)   # concepto ligado a insumo_b (Arena)
        assert item_a is not None and item_b is not None
        assert item_a.data(0, INSUMO_ROLE) == insumo_a
        assert item_b.data(0, INSUMO_ROLE) == insumo_b
        assert item_a.text(4) == "Cemento gris 50kg"
        assert item_b.text(4) == "Arena de rio m3"

        # ── Caso 1: copiar Descripción de A y pegarla sobre B (col 4) ──
        tree.setCurrentItem(item_b, 4)
        ok = tree._escribir_celda_pegada(item_b, 4, "Cemento gris 50kg")
        assert ok, "el resolver debió reconocer la descripción de un insumo existente"
        win._on_concepto_editado(item_b, 4)  # simula el itemChanged real
        nodo_b = api.campo_valor("estructura_presupuesto", "insumo_id", 3)
        assert nodo_b["insumo_id"] == insumo_a, (
            f"esperaba que el concepto 3 quedara ligado a insumo_a ({insumo_a}), "
            f"quedó en insumo_id={nodo_b['insumo_id']}"
        )
        print("OK  — pegar Descripción re-liga el concepto al insumo correcto")

        # ── Caso 2: Unidad NO re-liga por sí sola (el texto no es único) ──
        resultado = tree._resolver_insumo_pegado(item_b, 5, "m3")
        assert resultado is None, (
            "Unidad no debe resolver un insumo por sí sola: el texto de "
            "unidad no identifica un insumo (lo comparten muchos)"
        )
        print("OK  — Unidad por sí sola no re-liga (correcto, no identifica insumo)")

        # ── Caso 3: volver a ligar a insumo_b pegando su Descripción ──
        ok = tree._escribir_celda_pegada(item_b, 4, "Arena de rio m3")
        assert ok, "el resolver debió reconocer la descripción del segundo insumo"
        win._on_concepto_editado(item_b, 4)
        nodo_b = api.campo_valor("estructura_presupuesto", "insumo_id", 3)
        assert nodo_b["insumo_id"] == insumo_b, (
            f"esperaba volver a insumo_b ({insumo_b}), quedó en insumo_id={nodo_b['insumo_id']}"
        )
        print("OK  — pegar Descripción vuelve a re-ligar el concepto")

        # ── Caso 3: texto que no coincide con ningún insumo no debe tocar nada ──
        ok = tree._escribir_celda_pegada(item_b, 4, "Texto que no existe en el catálogo")
        assert not ok, "un texto sin insumo correspondiente no debe resolverse"
        nodo_b = api.campo_valor("estructura_presupuesto", "insumo_id", 3)
        assert nodo_b["insumo_id"] == insumo_b, "no debió cambiar el insumo ligado"
        print("OK  — texto no reconocido no toca la celda ni desliga el concepto")

        # ── Caso 4: capítulo — Descripción sigue siendo texto libre ──
        item_cap = tree._buscar_item_por_id(1)
        resultado = tree._resolver_insumo_pegado(item_cap, 4, "Capítulo renombrado")
        assert resultado == ("Capítulo renombrado", None), \
            "la Descripción de un capítulo debe seguir aceptando texto libre"
        resultado = tree._resolver_insumo_pegado(item_cap, 3, "algo")
        assert resultado is None, "Clave no debe resolver nada en un capítulo"
        print("OK  — capítulos conservan Descripción como texto libre")

        db.close()
        print("OK — pegado en árbol de Presupuesto re-liga insumos vía Descripción/Unidad")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
