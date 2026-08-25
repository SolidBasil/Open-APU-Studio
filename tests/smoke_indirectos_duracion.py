"""
smoke_indirectos_duracion.py
==============================
Prueba de humo de la corrección del Hallazgo 7:
IndirectoRepo.calcular_totales() convertía duracion_obra_dias=NULL en 0,
así que un indirecto con periodo_dias > 0 daba total=0 en silencio, sin
ningún aviso de que faltaba capturar la duración de obra del proyecto.

Cubre:
    - calcular_totales() ahora detecta y reporta qué indirectos quedaron
      en total=0 por falta de duración de obra
    - con duración capturada, esos mismos indirectos calculan bien y ya
      no aparecen en la lista de afectados
    - un indirecto con periodo_dias=0 (no depende de la duración) nunca
      se marca como afectado, aunque la duración esté en 0
    - Api.indirectos_aplicar_a_sobrecosto() propaga el mismo aviso

Uso:
    python3 tests/smoke_indirectos_duracion.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService
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
    # duracion_obra_dias se deja en su default (0/NULL) a propósito.
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
    db.conn.commit()

    api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)

    # Indirecto que SÍ depende de la duración (periodo_dias > 0)
    id_residente = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Personal", "concepto": "Residente",
        "periodo_dias": 30, "importe": 15000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    # Indirecto que NO depende de la duración (periodo_dias = 0, ej. flete único)
    id_flete = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Logística", "concepto": "Flete inicial",
        "periodo_dias": 0, "importe": 5000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 2,
    })

    # ── Sin duración de obra capturada: 'Residente' debe quedar marcado ──
    resultado = api.indirectos_calcular_totales()
    assert resultado["duracion_obra_dias"] == 0.0
    assert id_residente in resultado["afectados_por_duracion_faltante"], \
        f"'Residente' (periodo_dias=30) debía marcarse como afectado: {resultado}"
    assert id_flete not in resultado["afectados_por_duracion_faltante"], \
        f"'Flete' (periodo_dias=0) NO depende de la duración, no debía marcarse: {resultado}"
    print(f"OK: sin duración capturada, se detectó el indirecto afectado: {resultado}")

    fila_residente = [r for r in api.indirectos_lista("campo") if r["id"] == id_residente][0]
    assert float(fila_residente["total"]) == 0.0, \
        f"el total silencioso sigue siendo 0 (comportamiento numérico sin cambios), dio {fila_residente['total']}"
    print("OK: el total numérico sigue siendo 0 (no se inventa un valor), pero ahora se avisa")

    # ── Con duración capturada: ya no debe aparecer como afectado ────────
    api.proyecto_guardar({"duracion_obra_dias": 30})
    db.conn.commit()
    resultado2 = api.indirectos_calcular_totales()
    assert resultado2["duracion_obra_dias"] == 30.0
    assert resultado2["afectados_por_duracion_faltante"] == [], \
        f"con duración capturada no debía haber afectados: {resultado2}"
    fila_residente2 = [r for r in api.indirectos_lista("campo") if r["id"] == id_residente][0]
    assert abs(float(fila_residente2["total"]) - 15000.0) < 0.01, \
        f"con duración=periodo=30, total debía ser 15000, dio {fila_residente2['total']}"
    print(f"OK: con duración capturada, el total se calcula bien y ya no hay afectados: {resultado2}")

    # ── indirectos_aplicar_a_sobrecosto() propaga el mismo aviso ─────────
    api.proyecto_guardar({"duracion_obra_dias": 0})  # la volvemos a quitar
    db.conn.commit()
    # Necesitamos algo de costo directo para que aplicar_a_sobrecosto no falle antes de llegar al aviso
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, activo)
        VALUES (1, 1, 1, 'Cemento', 'kg', 200, 200, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo,
             insumo_id, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto', 1000, 200000, 1)
    """)
    db.conn.commit()

    resultado3 = api.indirectos_aplicar_a_sobrecosto()
    assert resultado3["duracion_obra_dias"] == 0.0
    assert id_residente in resultado3["afectados_por_duracion_faltante"], \
        f"indirectos_aplicar_a_sobrecosto() debía propagar el aviso: {resultado3}"
    print(f"OK: indirectos_aplicar_a_sobrecosto() propaga el aviso de duración faltante: "
          f"afectados={resultado3['afectados_por_duracion_faltante']}")

    db.close()
    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 7 PASARON")


if __name__ == "__main__":
    main()
