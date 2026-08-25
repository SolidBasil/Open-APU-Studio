"""
smoke_indirectos_api.py
========================
Prueba de humo end-to-end de la corrección del Hallazgo 1 (indirectos
fuera de DataService + sin conexión a factores_sobrecosto), contra una
BD SQLite real (sin mocks), a través de Api.

Cubre:
    - IndirectoRepo registrado en crear_registry() (antes: KeyError)
    - CRUD de indirectos vía Api pasa por DataService: evento emitido,
      historial capturado en actualizar()/eliminar() (Ctrl+Z)
    - insertar() ya no deja proyecto_id NULL en filas agregadas a mano
    - IndirectoRepo.costo_directo_total() agrega cantidad × costo_directo
    - Api.indirectos_aplicar_a_sobrecosto() calcula %CI, lo persiste en
      factores_sobrecosto y dispara el recálculo en cascada
    - Api.indirectos_aplicar_a_sobrecosto() lanza ValueError si el costo
      directo del proyecto es 0

Uso:
    python3 tests/smoke_indirectos_api.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import Database
from backend.database.event_bus import EventBus, IndirectoActualizado
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

    # ── Registro en crear_registry() ─────────────────────────────────
    assert registry.obtener("indirectos") is not None, \
        "IndirectoRepo debe estar registrado en crear_registry()"
    print("OK: IndirectoRepo registrado en crear_registry()")

    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
    db.conn.commit()

    api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)

    # ── Evento emitido ────────────────────────────────────────────────
    eventos = []
    event_bus.suscribir(IndirectoActualizado, lambda e: eventos.append(e))

    # ── insertar() sin proyecto_id explícito ──────────────────────────
    rid = api.indirectos_insertar({
        "tipo": "campo", "categoria": "Personal", "concepto": "Residente",
        "periodo_dias": 30, "importe": 15000, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    fila = [r for r in api.indirectos_lista("campo") if r["id"] == rid]
    assert fila, "el indirecto insertado sin proyecto_id explícito debe listarse igual (bug corregido)"
    assert fila[0]["proyecto_id"] == 1, f"proyecto_id debe inyectarse solo, quedó {fila[0]['proyecto_id']}"
    print("OK: indirectos_insertar() inyecta proyecto_id y el registro se lista bien")

    # ── actualizar() captura historial (Ctrl+Z) ───────────────────────
    api.indirectos_guardar(rid, {"importe": 20000})
    deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho, "debe poder deshacerse el cambio de importe (antes: sin historial)"
    fila = [r for r in api.indirectos_lista("campo") if r["id"] == rid][0]
    assert float(fila["importe"]) == 15000.0, f"deshacer debió restaurar 15000, quedó {fila['importe']}"
    print("OK: indirectos_guardar() pasa por historial — Ctrl+Z funciona")

    rehecho = ds.rehacer(usuario_id=1, proyecto_id=1)
    assert rehecho  # deja importe=20000 para el resto de la prueba

    assert len(eventos) >= 2, f"se esperaban >=2 IndirectoActualizado (insert + update), hubo {len(eventos)}"
    print(f"OK: EventBus recibió {len(eventos)} evento(s) de indirectos tras insert+update")

    # ── eliminar() también captura historial ──────────────────────────
    rid2 = api.indirectos_insertar({
        "tipo": "oficina", "categoria": "Dirección", "concepto": "Temporal",
        "periodo_dias": 0, "importe": 500, "pct_participacion": 100,
        "total": 0.0, "activo": 1, "orden": 1,
    })
    api.indirectos_eliminar(rid2)
    assert rid2 not in [r["id"] for r in api.indirectos_lista("oficina")]
    deshecho2 = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho2, "debe poder deshacerse el eliminar (soft-delete con historial)"
    assert rid2 in [r["id"] for r in api.indirectos_lista("oficina")]
    api.indirectos_eliminar(rid2)  # lo dejamos eliminado para el resto de la prueba
    print("OK: indirectos_eliminar() pasa por historial — deshacer funciona")

    # ── costo_directo_total() == 0 → ValueError en aplicar_a_sobrecosto ──
    try:
        api.indirectos_aplicar_a_sobrecosto()
        raise AssertionError("debía lanzar ValueError con costo directo 0")
    except ValueError as e:
        print(f"OK: ValueError esperado con costo directo 0 ({e})")

    # ── Presupuesto mínimo con costo directo real ─────────────────────
    # 1000 unidades * costo_directo 200 = 200,000 de costo directo total.
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_mn, costo_directo, costo_final, activo)
        VALUES (1, 1, 1, 'Cemento', 'kg', 200, 200, 200, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo,
             insumo_id, descripcion, cantidad, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto de prueba', 1000, 200000, 1)
    """)
    db.conn.commit()

    from backend.database.repos import IndirectoRepo
    costo_directo = IndirectoRepo(db.conn).costo_directo_total(1)
    assert costo_directo == 200000.0, f"esperaba 200000 (1000 * 200), dio {costo_directo}"
    print(f"OK: costo_directo_total() = {costo_directo}")

    # duracion_obra_dias = 30, periodo_dias del indirecto de campo = 30
    # -> total_campo = 20000 * (30/30) * (100/100) = 20000
    api.proyecto_guardar({"duracion_obra_dias": 30})
    db.conn.commit()

    resultado = api.indirectos_aplicar_a_sobrecosto()
    assert abs(resultado["total_indirectos_campo"] - 20000.0) < 0.01, resultado
    assert abs(resultado["total_indirectos_oficina"] - 0.0) < 0.01, resultado
    # %CI campo = 20000 / 200000 * 100 = 10%
    assert abs(resultado["pct_indirectos_campo"] - 10.0) < 0.01, resultado
    assert abs(resultado["pct_indirectos_oficina"] - 0.0) < 0.01, resultado
    print(f"OK: indirectos_aplicar_a_sobrecosto() -> {resultado}")

    factores = api.factores_sobrecosto_obtener()
    assert abs(float(factores["pct_indirectos_campo"]) - 10.0) < 0.01, factores
    print("OK: factores_sobrecosto quedó con el %CI calculado desde indirectos")

    # el presupuesto debió recalcularse en cascada: total del concepto ahora
    # incluye el factor de sobrecosto (>= costo directo * 1.10)
    concepto = cur.execute(
        "SELECT total FROM estructura_presupuesto WHERE id = 1"
    ).fetchone()
    assert concepto["total"] > 200000.0, \
        f"el recálculo en cascada debió subir el total del concepto, quedó {concepto['total']}"
    print(f"OK: recálculo en cascada aplicado — total del concepto ahora es {concepto['total']:.2f}")

    # ── Consistencia (encontrado en revisión final): cargar_plantilla ──
    # también debe quedar deshacible, igual que indirectos_insertar() —
    # antes usaba repo.insert() directo, sin pasar por DataService.
    antes = len(api.indirectos_lista("oficina"))
    insertados = api.indirectos_cargar_plantilla("oficina")
    assert insertados > 0, "la plantilla de oficina debía insertar al menos un renglón"
    despues = len(api.indirectos_lista("oficina"))
    assert despues == antes + insertados
    deshecho_plantilla = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho_plantilla, \
        "cargar_plantilla() debía quedar deshacible con Ctrl+Z (antes: repo.insert() directo, sin historial)"
    print(f"OK: indirectos_cargar_plantilla() ({insertados} renglones) queda deshacible con Ctrl+Z")

    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 1 PASARON")


if __name__ == "__main__":
    main()
