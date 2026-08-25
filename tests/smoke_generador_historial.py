"""
smoke_generador_historial.py
==============================
Prueba de humo de la auditoría del hallazgo N6 (métodos custom de
DataService que no pasaban por SchemaRegistry/HistorialRepo). Al revisar
todos los métodos custom relacionados a generadores, se encontraron dos
gaps de historial (no de validación) distintos al del Hallazgo 2:

    - eliminar_renglon_generador(): el único camino que usa la UI para
      borrar un renglón nunca capturaba historial — no era deshacible.
    - reasignar_generador(): cambiar el concepto vinculado a un generador
      tampoco capturaba historial.

mover_renglones_generador() ya capturaba historial correctamente (no
tenía el gap) y se deja como referencia/control en este mismo test.

Uso:
    python3 tests/smoke_generador_historial.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService

import logging
logging.basicConfig(level=logging.WARNING)


def main():
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

    gen_a = ds.insertar("generadores", proyecto_id=1, nombre="Generador A", unidad="m2")
    gen_b = ds.insertar("generadores", proyecto_id=1, nombre="Generador B", unidad="m2")

    # ═══════════════════════════════════════════════════════════════════
    # eliminar_renglon_generador(): debía quedar deshacible
    # ═══════════════════════════════════════════════════════════════════
    renglon_id = ds.guardar_renglon_generador(gen_a, veces=2, largo=3, ancho=2, alto=1)
    fila = cur.execute("SELECT activo FROM generador_renglones WHERE id=?", [renglon_id]).fetchone()
    assert fila["activo"] == 1

    ds.eliminar_renglon_generador(renglon_id, usuario_id=1)
    fila2 = cur.execute("SELECT activo FROM generador_renglones WHERE id=?", [renglon_id]).fetchone()
    assert fila2["activo"] == 0, "el renglón debía quedar soft-eliminado"
    print("OK: eliminar_renglon_generador() soft-eliminó el renglón")

    deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho, "eliminar un renglón de generador debía quedar deshacible (antes: sin historial, imposible)"
    fila3 = cur.execute("SELECT activo FROM generador_renglones WHERE id=?", [renglon_id]).fetchone()
    assert fila3["activo"] == 1, "deshacer debía revivir el renglón"
    print("OK: eliminar_renglon_generador() ahora es deshacible con Ctrl+Z")

    # ═══════════════════════════════════════════════════════════════════
    # reasignar_generador(): debía quedar deshacible
    # ═══════════════════════════════════════════════════════════════════
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 'Concepto 1', 0, 0, 1)
    """)
    db.conn.commit()

    gen_antes = cur.execute("SELECT concepto_id FROM generadores WHERE id=?", [gen_a]).fetchone()
    assert gen_antes["concepto_id"] is None

    ds.reasignar_generador(gen_a, nuevo_concepto_id=1, usuario_id=1)
    gen_despues = cur.execute("SELECT concepto_id FROM generadores WHERE id=?", [gen_a]).fetchone()
    assert gen_despues["concepto_id"] == 1
    print("OK: reasignar_generador() cambió el concepto_id")

    deshecho2 = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho2, "reasignar un generador a otro concepto debía quedar deshacible (antes: sin historial)"
    gen_restaurado = cur.execute("SELECT concepto_id FROM generadores WHERE id=?", [gen_a]).fetchone()
    assert gen_restaurado["concepto_id"] is None, \
        f"deshacer debía restaurar concepto_id=None, quedó {gen_restaurado['concepto_id']}"
    print("OK: reasignar_generador() ahora es deshacible con Ctrl+Z")

    # ═══════════════════════════════════════════════════════════════════
    # mover_renglones_generador(): control — ya funcionaba bien antes
    # ═══════════════════════════════════════════════════════════════════
    renglon2 = ds.guardar_renglon_generador(gen_a, veces=1, largo=5, ancho=1, alto=1)
    ok = ds.mover_renglones_generador([renglon2], gen_b, antes_de_id=None, copiar=False, usuario_id=1)
    assert ok
    fila_movida = cur.execute(
        "SELECT generador_id FROM generador_renglones WHERE id=?", [renglon2]
    ).fetchone()
    assert fila_movida["generador_id"] == gen_b
    deshecho3 = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho3, "mover un renglón entre generadores ya era deshacible (control de regresión)"
    print("OK: mover_renglones_generador() sigue siendo deshacible (control, sin cambios)")

    db.close()
    print("\nTODAS LAS PRUEBAS DE N6 (historial en métodos custom de generadores) PASARON")


if __name__ == "__main__":
    main()
