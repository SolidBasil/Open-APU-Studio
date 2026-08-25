"""
smoke_generador_dragdrop.py
============================
Prueba de humo end-to-end del mover/copiar renglones de Generadores
entre pestañas (DataService.mover_renglones_generador) — cubre:
    - Reordenar renglones dentro del mismo generador.
    - Mover un renglón a OTRO generador (recalcula cantidad_total y la
      cantidad del concepto en ambos lados).
    - Deshacer ese movimiento.
    - Copiar (Ctrl+drag) un renglón a otro generador; deshacer la copia
      (generador_renglones sí tiene soft-delete, a diferencia de
      apu_matrices, así que aquí SÍ se puede rehacer).

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_generador_dragdrop.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.repos.generador import GeneradorRepo
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from frontend.ventana.api import Api


def main():
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
        r2 = api.generador_renglon_guardar(gen_a, eje="2", tramo="B-C", veces=1, largo=5, ancho=2)
        r3 = api.generador_renglon_guardar(gen_b, eje="1", tramo="X-Y", veces=1, largo=4, ancho=3)

        repo = GeneradorRepo(db.conn)

        cant_a = api.concepto_cantidad(2)
        cant_b = api.concepto_cantidad(3)
        assert cant_a == 30.0, f"esperaba 30.0 (10*2 + 5*2), quedó {cant_a}"
        assert cant_b == 12.0, f"esperaba 12.0 (4*3), quedó {cant_b}"
        print("OK  — cantidades iniciales de los conceptos correctas")

        # ── Caso 1: reordenar dentro del mismo generador ──
        ok = api.generador_mover_renglones([r2], gen_a, r1, copiar=False)
        assert ok
        assert repo.hermanos_de(gen_a) == [r2, r1], f"esperaba [r2, r1], quedó {repo.hermanos_de(gen_a)}"
        print("OK  — reordenar renglones dentro del mismo generador")

        # ── Caso 2: mover un renglón de Gen A a Gen B (entre pestañas) ──
        ok = api.generador_mover_renglones([r1], gen_b, None, copiar=False)
        assert ok
        assert repo.buscar_renglon(r1)["generador_id"] == gen_b
        cant_a = api.concepto_cantidad(2)
        cant_b = api.concepto_cantidad(3)
        assert cant_a == 10.0, f"Concepto A debía quedar en 10.0 (solo r2: 5*2), quedó {cant_a}"
        assert cant_b == 32.0, f"Concepto B debía subir a 32.0 (12 + 20), quedó {cant_b}"
        print("OK  — mover un renglón a otro generador recalcula ambos conceptos")

        # deshacer el movimiento
        deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
        assert deshecho
        assert repo.buscar_renglon(r1)["generador_id"] == gen_a, "deshacer debió regresar r1 a gen_a"
        cant_a = api.concepto_cantidad(2)
        cant_b = api.concepto_cantidad(3)
        assert cant_a == 30.0, f"Concepto A debía volver a 30.0, quedó {cant_a}"
        assert cant_b == 12.0, f"Concepto B debía volver a 12.0, quedó {cant_b}"
        print("OK  — deshacer un movimiento entre generadores recalcula ambos conceptos de vuelta")

        # ── Caso 3: copiar (Ctrl+drag) un renglón a otro generador ──
        ids_antes = set(r["id"] for r in db.conn.execute("SELECT id FROM generador_renglones").fetchall())
        ok = api.generador_mover_renglones([r3], gen_a, None, copiar=True)
        assert ok
        ids_despues = set(r["id"] for r in db.conn.execute("SELECT id FROM generador_renglones").fetchall())
        nuevos = ids_despues - ids_antes
        assert len(nuevos) == 1
        nuevo_id = nuevos.pop()
        nueva_fila = repo.buscar_renglon(nuevo_id)
        assert nueva_fila["generador_id"] == gen_a
        assert nueva_fila["tramo"] == "X-Y"
        original = repo.buscar_renglon(r3)
        assert original["generador_id"] == gen_b, "el original no debió moverse al copiar"
        cant_a = api.concepto_cantidad(2)
        assert cant_a == 42.0, f"Concepto A debía subir a 42.0 (30 + 12), quedó {cant_a}"
        print("OK  — copiar un renglón a otro generador, sin tocar el original")

        # deshacer la copia — SÍ tiene soft-delete, a diferencia de apu_matrices
        deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
        assert deshecho
        fila_borrada = db.conn.execute(
            "SELECT activo FROM generador_renglones WHERE id = ?", [nuevo_id]
        ).fetchone()
        assert fila_borrada["activo"] == 0, "el renglón copiado debió quedar soft-eliminado"
        cant_a = api.concepto_cantidad(2)
        assert cant_a == 30.0, f"Concepto A debía volver a 30.0 tras deshacer la copia, quedó {cant_a}"
        print("OK  — deshacer una copia en Generadores la soft-elimina y recalcula")

        # ── Caso 4: rehacer la copia la revive ──
        rehecho = ds.rehacer(usuario_id=1, proyecto_id=1)
        assert rehecho
        fila_revivida = db.conn.execute(
            "SELECT activo FROM generador_renglones WHERE id = ?", [nuevo_id]
        ).fetchone()
        assert fila_revivida["activo"] == 1
        cant_a = api.concepto_cantidad(2)
        assert cant_a == 42.0, f"Concepto A debía volver a 42.0 tras rehacer, quedó {cant_a}"
        print("OK  — rehacer revive la copia y recalcula de nuevo")

        db.close()
        print("OK — mover/copiar renglones entre generadores funciona correctamente")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
