"""
smoke_insertar_historial.py
=============================
Prueba de humo end-to-end de la corrección del Hallazgo 3
(DataService.insertar() no capturaba historial de creación — ninguna fila
creada desde el genérico era deshacible con Ctrl+Z), contra una BD SQLite
real (sin mocks).

Cubre:
    - insertar() ahora captura CAMPO_CREADO -> deshacer() la soft-elimina
      (o la borra físicamente si la tabla no soporta 'activo')
    - rehacer() revive correctamente las filas de tablas con soft-delete
    - _TABLAS_CON_SOFT_DELETE ahora incluye TODAS las tablas con columna
      'activo' usadas por DataService (antes solo tenía 2 de 7 — insumos,
      familias, subfamilias, indirectos y generadores faltaban, lo que
      hubiera hecho un DELETE físico irreversible al deshacer una
      creación en esas tablas, con redo silenciosamente roto)
    - una tabla sin 'activo' (variables_formula) sigue con DELETE físico
      al deshacer, sin redo posible — comportamiento correcto, no una
      regresión

Uso:
    python3 tests/smoke_insertar_historial.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import Database
from backend.database.event_bus import EventBus
from backend.database.services.repository_registry import crear_registry
from backend.database.services.data_service import DataService, _TABLAS_CON_SOFT_DELETE

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
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    db.conn.commit()

    # ── _TABLAS_CON_SOFT_DELETE completo ──────────────────────────────
    esperado = {
        "estructura_presupuesto", "generador_renglones",
        "insumos", "familias", "subfamilias", "indirectos", "generadores",
    }
    faltantes = esperado - _TABLAS_CON_SOFT_DELETE
    assert not faltantes, f"faltan en _TABLAS_CON_SOFT_DELETE: {faltantes}"
    print(f"OK: _TABLAS_CON_SOFT_DELETE completo ({len(_TABLAS_CON_SOFT_DELETE)} tablas)")

    # ── Caso 1: insertar() en tabla CON soft-delete (insumos) ─────────
    iid = ds.insertar(
        "insumos", proyecto_id=1, tipo_id=1, descripcion="Insumo de prueba",
        unidad="pza", costo_directo=100, costo_final=100, activo=1,
    )
    fila = cur.execute("SELECT activo FROM insumos WHERE id = ?", [iid]).fetchone()
    assert fila["activo"] == 1
    print("OK: insertar() creó el insumo")

    deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho, "debía poder deshacerse la creación del insumo (antes: sin historial, imposible)"
    fila = cur.execute("SELECT activo FROM insumos WHERE id = ?", [iid]).fetchone()
    assert fila is not None, "la fila debía seguir existiendo (soft-delete, no DELETE físico)"
    assert fila["activo"] == 0, f"debía quedar activo=0 tras deshacer, quedó {fila['activo']}"
    print("OK: deshacer() la soft-eliminó (activo=0), no la borró físicamente")

    rehecho = ds.rehacer(usuario_id=1, proyecto_id=1)
    assert rehecho, "debía poder rehacerse"
    fila = cur.execute("SELECT activo FROM insumos WHERE id = ?", [iid]).fetchone()
    assert fila["activo"] == 1, f"debía revivir con activo=1 tras rehacer, quedó {fila['activo']}"
    print("OK: rehacer() revivió el insumo (activo=1) — antes de este fix esto era imposible")

    # ── Caso 2: insertar() en tabla SIN soft-delete (variables_formula) ──
    vid = ds.insertar("variables_formula", proyecto_id=1, nombre="var_test", expresion="1")
    existe = cur.execute("SELECT id FROM variables_formula WHERE id = ?", [vid]).fetchone()
    assert existe is not None
    print("OK: insertar() creó la variable")

    deshecho2 = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho2, "debía poder deshacerse (con DELETE físico, sin activo)"
    existe = cur.execute("SELECT id FROM variables_formula WHERE id = ?", [vid]).fetchone()
    assert existe is None, "sin columna 'activo', deshacer debe borrar físicamente"
    print("OK: deshacer() en tabla sin 'activo' hizo DELETE físico (comportamiento correcto)")

    rehecho2 = ds.rehacer(usuario_id=1, proyecto_id=1)
    assert rehecho2, "la sesión debía marcarse como rehecha aunque no reviva nada"
    existe = cur.execute("SELECT id FROM variables_formula WHERE id = ?", [vid]).fetchone()
    assert existe is None, "no hay forma de revivir un DELETE físico — comportamiento esperado, no una regresión"
    print("OK: rehacer() no revive DELETE físico (esperado, documentado, no es una regresión)")

    # ── Caso 3: familias/subfamilias/generadores/indirectos también capturan creación ──
    for entidad, campos in [
        ("familias", {"nombre": "Familia test", "activo": 1}),
        ("indirectos", {
            "proyecto_id": 1, "tipo": "campo", "categoria": "X",
            "concepto": "Y", "periodo_dias": 1, "importe": 1,
            "pct_participacion": 100, "total": 0, "activo": 1,
        }),
    ]:
        rid = ds.insertar(entidad, **campos)
        d = ds.deshacer(usuario_id=1, proyecto_id=1)
        assert d, f"debía poder deshacerse la creación en {entidad}"
        fila = cur.execute(f"SELECT activo FROM {entidad} WHERE id = ?", [rid]).fetchone()
        assert fila is not None and fila["activo"] == 0, \
            f"{entidad}: debía quedar soft-eliminada tras deshacer, {dict(fila) if fila else None}"
        r = ds.rehacer(usuario_id=1, proyecto_id=1)
        assert r
        fila = cur.execute(f"SELECT activo FROM {entidad} WHERE id = ?", [rid]).fetchone()
        assert fila["activo"] == 1, f"{entidad}: debía revivir tras rehacer"
        print(f"OK: {entidad} — creación deshacible y rehacible correctamente")

    db.close()
    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 3 PASARON")


if __name__ == "__main__":
    main()
