"""
smoke_apu_pegar_dragdrop.py
============================
Prueba de humo end-to-end de las dos features llevadas al desglose de
APU (TablaApuDetalle):
    1. Pegar Clave/Descripción re-liga un componente a otro insumo
       (mismo mecanismo que Presupuesto — ver
       TablaApuDetalle._resolver_insumo_pegado).
    2. Drag and drop: reordenar componentes dentro de la misma matriz,
       y mover/copiar un componente a OTRA matriz (otra pestaña de APU
       abierta) — ver ApuMixin._on_drop_apu.

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_apu_pegar_dragdrop.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.repos import ApuMatricesRepo
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api
from frontend.ventana.mixins.apu import ApuMixin
from frontend.ventana.widgets.apu import TablaApuDetalle


class _FakeWindow(ApuMixin):
    """Objeto mínimo con el mixin real de drag and drop de APU."""
    def __init__(self, conn, ds, api):
        self._conn = conn
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
        win = _FakeWindow(db.conn, ds, api)

        insumo_a = api.insumo_insertar(tipo_id=1, descripcion="Cemento gris 50kg", unidad="pza", costo=180.0)
        insumo_b = api.insumo_insertar(tipo_id=1, descripcion="Arena de rio m3", unidad="m3", costo=350.0)
        insumo_c = api.insumo_insertar(tipo_id=2, descripcion="Peon albañil jornal", unidad="jor", costo=400.0)

        # Capítulo 1 con dos conceptos — cada uno es su propia "matriz" de APU
        cur.execute("""
            INSERT INTO estructura_presupuesto
                (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total)
            VALUES
                (1, 1, NULL, '1',   0, 1, 'capitulo', 'Capítulo 1',  NULL, 0),
                (2, 1, 1,    '1.1', 1, 1, 'concepto', 'Concepto A', 1, 0),
                (3, 1, 1,    '1.2', 1, 2, 'concepto', 'Concepto B', 1, 0)
        """)
        db.conn.commit()

        matriz_a, matriz_b = 2, 3
        comp1 = api.apu_agregar_componente(matriz_a, insumo_a)  # Cemento en matriz A
        comp2 = api.apu_agregar_componente(matriz_a, insumo_b)  # Arena en matriz A
        comp3 = api.apu_agregar_componente(matriz_b, insumo_c)  # Peon en matriz B

        repo = ApuMatricesRepo(db.conn)

        tabla_a = TablaApuDetalle(matriz_a, "Concepto A")
        tabla_a._api = api
        tabla_a.poblar(api.apu(nodo_id=matriz_a))
        tabla_b = TablaApuDetalle(matriz_b, "Concepto B")
        tabla_b._api = api
        tabla_b.poblar(api.apu(nodo_id=matriz_b))

        def _item_de(tabla, comp_id):
            for i in range(tabla.topLevelItemCount()):
                it = tabla.topLevelItem(i)
                if it.data(5, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole) == comp_id:
                    return it
            return None

        # ── Caso 1: pegar Descripción re-liga el componente a otro insumo ──
        item_comp1 = _item_de(tabla_a, comp1)
        assert item_comp1 is not None
        ok = tabla_a._escribir_celda_pegada(item_comp1, 2, "Arena de rio m3")
        assert ok, "el resolver debió reconocer la descripción de un insumo existente"
        tabla_a._on_item_editado(item_comp1, 2)
        fila = repo.buscar(comp1)
        assert fila["insumo_id"] == insumo_b, f"esperaba insumo_b ({insumo_b}), quedó {fila['insumo_id']}"
        print("OK  — pegar Descripción re-liga el componente al insumo correcto")

        # texto no reconocido no debe tocar nada
        ok = tabla_a._escribir_celda_pegada(item_comp1, 2, "Texto que no existe")
        assert not ok
        fila = repo.buscar(comp1)
        assert fila["insumo_id"] == insumo_b, "no debió cambiar tras un texto no reconocido"
        print("OK  — texto no reconocido no toca la celda")

        # ── Caso 2: reordenar dentro de la misma matriz ──
        ok = win._on_drop_apu([comp2], matriz_a, comp1, copiar=False)
        assert ok
        assert repo.hermanos_de(matriz_a) == [comp2, comp1], \
            f"esperaba [comp2, comp1] tras reordenar, quedó {repo.hermanos_de(matriz_a)}"
        print("OK  — reordenar componentes dentro de la misma matriz")

        # ── Caso 3: mover un componente de matriz_a a matriz_b ──
        ok = win._on_drop_apu([comp1], matriz_b, None, copiar=False)
        assert ok
        assert repo.buscar(comp1)["matriz_id"] == matriz_b
        assert comp1 not in repo.hermanos_de(matriz_a)
        assert comp1 in repo.hermanos_de(matriz_b)
        print("OK  — mover un componente a otra matriz (otra pestaña de APU)")

        # deshacer el movimiento debe regresarlo a matriz_a
        deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
        assert deshecho
        assert repo.buscar(comp1)["matriz_id"] == matriz_a, "deshacer debió regresar el componente a matriz_a"
        print("OK  — deshacer un movimiento entre matrices funciona")

        # ── Caso 4: copiar (Ctrl+drag) un componente a otra matriz ──
        ids_antes = set(r["id"] for r in db.conn.execute("SELECT id FROM apu_matrices").fetchall())
        ok = win._on_drop_apu([comp3], matriz_a, None, copiar=True)
        assert ok
        ids_despues = set(r["id"] for r in db.conn.execute("SELECT id FROM apu_matrices").fetchall())
        nuevos = ids_despues - ids_antes
        assert len(nuevos) == 1
        nuevo_id = nuevos.pop()
        nueva_fila = repo.buscar(nuevo_id)
        assert nueva_fila["matriz_id"] == matriz_a
        assert nueva_fila["insumo_id"] == insumo_c
        original = repo.buscar(comp3)
        assert original["matriz_id"] == matriz_b, "el original no debió moverse al copiar"
        print("OK  — copiar (Ctrl+drag) un componente a otra matriz, sin tocar el original")

        # deshacer la copia: apu_matrices no tiene soft-delete → DELETE físico
        deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
        assert deshecho
        fila_borrada = db.conn.execute(
            "SELECT COUNT(*) AS n FROM apu_matrices WHERE id = ?", [nuevo_id]
        ).fetchone()
        assert fila_borrada["n"] == 0, "el componente copiado debió borrarse de verdad tras deshacer"
        print("OK  — deshacer una copia en APU la borra (sin soft-delete disponible aquí)")

        db.close()
        print("OK — pegado + drag and drop en APU funcionan correctamente")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
