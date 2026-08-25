"""
smoke_generador_validacion.py
===============================
Prueba de humo de la corrección del Hallazgo 2: "generador_renglones" no
tenía reglas en SchemaRegistry, así que largo/ancho/alto se podían
capturar en negativo y se propagaban sin error hasta el total del
presupuesto. Además, el único camino real de escritura
(DataService.guardar_renglon_generador(), usado por la UI) nunca llamaba
a SchemaRegistry.validate() en absoluto — un problema aparte, del mismo
tipo que los Hallazgos 1 y 5, encontrado al implementar este fix.

Cubre:
    - largo/ancho/alto negativos ahora se rechazan con ValidationError,
      vía el camino real que usa la UI (guardar_renglon_generador)
    - largo/ancho/alto positivos o None (renglón solo con 'veces') siguen
      funcionando igual que antes
    - 'veces' negativo NO se bloquea a propósito (convención de
      deducciones en generadores de obra — ver comentario en
      schema_registry.py) — no es una omisión, es una decisión explícita
    - generadores.nombre/unidad también validan (vía insertar/actualizar
      genérico, que ya llamaba a SchemaRegistry desde antes)

Uso:
    python3 tests/smoke_generador_validacion.py
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

    gen_id = ds.insertar("generadores", proyecto_id=1, nombre="Muros", unidad="m2")
    print(f"OK: generador creado (id={gen_id})")

    # ── largo negativo se rechaza ───────────────────────────────────────
    try:
        ds.guardar_renglon_generador(gen_id, veces=1, largo=-5, ancho=3, alto=2.5)
        raise AssertionError("debía rechazar largo negativo")
    except ValidationError as e:
        print(f"OK: largo negativo rechazado ({e})")

    # ── ancho negativo se rechaza ───────────────────────────────────────
    try:
        ds.guardar_renglon_generador(gen_id, veces=1, largo=5, ancho=-3, alto=2.5)
        raise AssertionError("debía rechazar ancho negativo")
    except ValidationError as e:
        print(f"OK: ancho negativo rechazado ({e})")

    # ── alto negativo se rechaza ────────────────────────────────────────
    try:
        ds.guardar_renglon_generador(gen_id, veces=1, largo=5, ancho=3, alto=-2.5)
        raise AssertionError("debía rechazar alto negativo")
    except ValidationError as e:
        print(f"OK: alto negativo rechazado ({e})")

    # ── Ningún renglón inválido quedó guardado ──────────────────────────
    renglones = cur.execute(
        "SELECT COUNT(*) AS n FROM generador_renglones WHERE generador_id = ?", [gen_id]
    ).fetchone()
    assert renglones["n"] == 0, \
        f"no debía haber quedado ningún renglón inválido guardado, hay {renglones['n']}"
    print("OK: ningún renglón con dimensión negativa quedó persistido")

    # ── Caso válido: dimensiones positivas ──────────────────────────────
    rid = ds.guardar_renglon_generador(gen_id, veces=2, largo=5, ancho=3, alto=2.5)
    fila = cur.execute(
        "SELECT subtotal FROM generador_renglones WHERE id = ?", [rid]
    ).fetchone()
    assert abs(fila["subtotal"] - (2 * 5 * 3 * 2.5)) < 0.001
    print(f"OK: renglón válido (2×5×3×2.5={fila['subtotal']}) se guarda normalmente")

    # ── Caso válido: solo 'veces' (conteo), sin dimensiones ─────────────
    rid2 = ds.guardar_renglon_generador(gen_id, veces=4)
    fila2 = cur.execute(
        "SELECT subtotal, largo, ancho, alto FROM generador_renglones WHERE id = ?", [rid2]
    ).fetchone()
    assert fila2["largo"] is None and fila2["ancho"] is None and fila2["alto"] is None
    assert abs(fila2["subtotal"] - 4.0) < 0.001
    print("OK: renglón solo con 'veces' (sin dimensiones) sigue funcionando")

    # ── 'veces' negativo NO se bloquea (convención de deducciones) ──────
    rid3 = ds.guardar_renglon_generador(gen_id, veces=-1, largo=2, ancho=1, alto=2.1)
    fila3 = cur.execute(
        "SELECT subtotal FROM generador_renglones WHERE id = ?", [rid3]
    ).fetchone()
    assert fila3["subtotal"] < 0, \
        "veces negativo debía permitirse (deducción de puertas/ventanas), dio subtotal no-negativo"
    print(f"OK: 'veces' negativo se sigue permitiendo a propósito (subtotal={fila3['subtotal']})")

    # ── generadores.nombre/unidad ya validaban desde antes (insertar genérico) ──
    try:
        ds.insertar("generadores", proyecto_id=1, nombre=123, unidad="m2")
        raise AssertionError("debía rechazar nombre no-string")
    except ValidationError as e:
        print(f"OK: generadores.nombre sigue validando tipo (vía insertar genérico) ({e})")

    db.close()
    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 2 PASARON")


if __name__ == "__main__":
    main()
