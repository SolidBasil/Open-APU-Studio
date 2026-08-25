"""
smoke_proyecto_guardar.py
===========================
Prueba de humo de la corrección del hallazgo N1 (encontrado al trabajar
el Hallazgo 1): Api.proyecto_guardar() escribía directo vía ProyectoRepo
sin pasar por DataService — sin validación, sin historial, y sin
comitear por sí solo (dependía de que el caller hiciera commit a mano).
Mismo patrón que tenía indirectos antes del Hallazgo 1.

Cubre:
    - proyecto_guardar() valida contra SchemaRegistry (rechaza
      duracion_obra_dias negativo)
    - proyecto_guardar() captura historial -> deshacible con Ctrl+Z
    - proyecto_guardar() comitea su propia transacción (no depende de un
      commit manual del caller)

Uso:
    python3 tests/smoke_proyecto_guardar.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
from backend.database.exceptions import ValidationError
from frontend.ventana.api import Api

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

    api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)

    # ── Validación: duracion_obra_dias negativo se rechaza ──────────────
    try:
        api.proyecto_guardar({"duracion_obra_dias": -5})
        raise AssertionError("debía rechazar duracion_obra_dias negativo")
    except ValidationError as e:
        print(f"OK: duracion_obra_dias negativo rechazado ({e})")

    fila = cur.execute("SELECT duracion_obra_dias FROM proyectos WHERE id=1").fetchone()
    assert (fila["duracion_obra_dias"] or 0) == 0, "el valor inválido no debía persistirse"
    print("OK: el valor inválido no quedó guardado")

    # ── Guardado normal: sin commit manual, queda persistido igual ──────
    api.proyecto_guardar({"duracion_obra_dias": 45, "cliente_nombre": "Cliente de prueba"})
    # OJO: sin ningún db.conn.commit() manual aquí a propósito — el punto
    # es confirmar que proyecto_guardar() comitea su propia transacción.
    db2 = Database.abrir(db_path)  # conexión nueva: solo ve datos comiteados
    fila2 = db2.conn.execute(
        "SELECT duracion_obra_dias, cliente_nombre FROM proyectos WHERE id=1"
    ).fetchone()
    assert fila2["duracion_obra_dias"] == 45
    assert fila2["cliente_nombre"] == "Cliente de prueba"
    print("OK: proyecto_guardar() comitea su propia transacción (sin commit manual del caller)")
    db2.close()

    # ── Historial: deshacible con Ctrl+Z ─────────────────────────────────
    api.proyecto_guardar({"duracion_obra_dias": 99})
    fila3 = cur.execute("SELECT duracion_obra_dias FROM proyectos WHERE id=1").fetchone()
    assert fila3["duracion_obra_dias"] == 99

    deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho, "debía poder deshacerse el cambio de duracion_obra_dias (antes: sin historial)"
    fila4 = cur.execute("SELECT duracion_obra_dias FROM proyectos WHERE id=1").fetchone()
    assert fila4["duracion_obra_dias"] == 45, \
        f"deshacer debió restaurar 45, quedó {fila4['duracion_obra_dias']}"
    print("OK: proyecto_guardar() pasa por historial — Ctrl+Z funciona")

    db.close()
    print("\nTODAS LAS PRUEBAS DE N1 (proyecto_guardar) PASARON")


if __name__ == "__main__":
    main()
