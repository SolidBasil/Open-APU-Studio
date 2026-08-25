"""
smoke_drag_drop_arbol.py
=========================
Prueba de humo end-to-end del drag and drop del árbol de Presupuesto
(mover/copiar renglones de un capítulo a otro, con posición exacta) —
ver TablaArbol.dropEvent + HandlersMixin._on_drop_arbol (navegacion.py)
+ NodoRepo.mover_bloque/duplicar_bloque (presupuesto.py).

Cubre:
    - Mover un concepto de un capítulo a otro, al final.
    - Mover un concepto a una posición exacta (antes de otro renglón).
    - Rechazar un movimiento que crearía un ciclo (soltar un nodo dentro
      de su propio subárbol).
    - Copiar (Ctrl+drag) un concepto: el original queda intacto y se crea
      uno nuevo en el destino.

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_drag_drop_arbol.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.repos import NodoRepo
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api
from frontend.ventana.mixins.navegacion import HandlersMixin


class _FakeWindow(HandlersMixin):
    """Objeto mínimo con el mixin real de mover/copiar nodos, para
    probar _on_drop_arbol sin levantar toda VentanaPrincipal."""
    def __init__(self, db, ds, api):
        self._db = db
        self._data_service = ds
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
        win = _FakeWindow(db, ds, api)

        # Capítulo 1 (id 1) con conceptos A(2), B(3)
        # Capítulo 2 (id 4) con concepto  C(5)
        cur.execute("""
            INSERT INTO estructura_presupuesto
                (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
            VALUES
                (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1', NULL, 0),
                (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 1, 100),
                (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 1, 200),
                (4, 1, NULL, '2',   0, 2, 'capitulo', 'Capítulo 2', NULL, 0),
                (5, 1, 4,    '2.1', 1, 1, 'concepto', 'Concepto C', 1, 300)
        """)
        db.conn.commit()
        repo = NodoRepo(db.conn)

        # ── Caso 1: rechazar mover un nodo dentro de su propio subárbol ──
        ok = win._on_drop_arbol([1], nuevo_padre_id=2, antes_de_id=None, copiar=False)
        assert not ok, "mover el Capítulo 1 dentro de su propio concepto debe rechazarse"
        fila = repo.buscar(1)
        assert fila["padre_id"] is None, "el capítulo 1 no debió moverse tras el rechazo"
        print("OK  — mover dentro del propio subárbol se rechaza (evita ciclo)")

        # ── Caso 2: mover Concepto A al final de Capítulo 2 ──
        ok = win._on_drop_arbol([2], nuevo_padre_id=4, antes_de_id=None, copiar=False)
        assert ok
        fila_a = repo.buscar(2)
        assert fila_a["padre_id"] == 4, f"esperaba padre_id=4, quedó en {fila_a['padre_id']}"
        hermanos = repo.hermanos_de(4, 1)
        assert hermanos == [5, 2], f"esperaba [5, 2] (A al final), quedó {hermanos}"
        print("OK  — mover un concepto a otro capítulo, al final")

        # ── Caso 3: mover Concepto B a una posición exacta (antes de C) ──
        ok = win._on_drop_arbol([3], nuevo_padre_id=4, antes_de_id=5, copiar=False)
        assert ok
        hermanos = repo.hermanos_de(4, 1)
        assert hermanos == [3, 5, 2], f"esperaba [3, 5, 2] (B antes de C), quedó {hermanos}"
        print("OK  — mover a una posición exacta (antes de otro renglón)")

        # ── Caso 4: copiar (Ctrl+drag) Concepto C hacia Capítulo 1 ──
        ids_antes = set(r["id"] for r in db.conn.execute(
            "SELECT id FROM estructura_presupuesto").fetchall())
        ok = win._on_drop_arbol([5], nuevo_padre_id=1, antes_de_id=None, copiar=True)
        assert ok
        ids_despues = set(r["id"] for r in db.conn.execute(
            "SELECT id FROM estructura_presupuesto").fetchall())
        nuevos = ids_despues - ids_antes
        assert len(nuevos) == 1, f"esperaba exactamente 1 nodo nuevo, hubo {len(nuevos)}"
        nuevo_id = nuevos.pop()
        nueva_fila = repo.buscar(nuevo_id)
        assert nueva_fila["descripcion"] == "Concepto C"
        assert nueva_fila["padre_id"] == 1
        original = repo.buscar(5)
        assert original["padre_id"] == 4, "el original no debió moverse al copiar"
        print("OK  — copiar (Ctrl+drag) crea un nodo nuevo y no toca el original")

        # ── Caso 5: deshacer la copia borra (soft-delete) el nodo nuevo ──
        deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
        assert deshecho, "debía haber algo que deshacer (la copia)"
        fila_nueva = db.conn.execute(
            "SELECT activo FROM estructura_presupuesto WHERE id = ?", [nuevo_id]
        ).fetchone()
        assert fila_nueva["activo"] == 0, "el nodo copiado debió quedar soft-eliminado tras deshacer"
        hermanos_cap1 = repo.hermanos_de(1, 1)
        assert nuevo_id not in hermanos_cap1, "el nodo deshecho no debe aparecer entre los hijos del capítulo 1"
        print("OK  — deshacer (Ctrl+Z) una copia la borra correctamente")

        # ── Caso 6: rehacer la copia la revive ──
        rehecho = ds.rehacer(usuario_id=1, proyecto_id=1)
        assert rehecho, "debía haber algo que rehacer"
        fila_revivida = db.conn.execute(
            "SELECT activo FROM estructura_presupuesto WHERE id = ?", [nuevo_id]
        ).fetchone()
        assert fila_revivida["activo"] == 1, "el nodo copiado debió revivir tras rehacer"
        print("OK  — rehacer (Ctrl+Shift+Z) revive la copia")

        db.close()
        print("OK — drag and drop del árbol de Presupuesto (mover/copiar) funciona correctamente")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
