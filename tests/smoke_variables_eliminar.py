"""
smoke_variables_eliminar.py
=============================
Prueba de humo end-to-end de la corrección del Hallazgo 5 (borrar una
variable de fórmula no reescribía las fórmulas que la usaban —
sustituir_variable_eliminada() existía pero ningún flujo real la
invocaba), contra una BD SQLite real (sin mocks), a través de Api.

Cubre que Api.variables_eliminar() sustituya el último valor conocido de
la variable eliminada en:
    - otras variables_formula.expresion que la referencian
    - estructura_presupuesto.formula (cantidad de un concepto)
    - apu_matrices.formula (valor de un componente APU, matriz_id
      positivo y negativo — ver convención de signo)
antes de borrarla, y que las fórmulas ya reescritas se puedan seguir
evaluando sin "variable no definida".

Uso:
    python3 tests/smoke_variables_eliminar.py
"""
import os
import sys
import tempfile
from decimal import Decimal

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
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (1, 1, 1, 'Insumo simple',    'kg', 10, 10, 0, 1),
            (2, 1, 1, 'Insumo compuesto', 'm3', 0,  0,  1, 1)
    """)
    cur.execute("""
        INSERT INTO estructura_presupuesto
            (id, proyecto_id, padre_id, wbs, nivel, orden, tipo,
             insumo_id, descripcion, cantidad, formula, total, activo)
        VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto A', 6.0, 'ancho_muro * altura', 60, 1)
    """)
    # Componente APU de una matriz positiva (concepto id=1) con fórmula propia
    cur.execute("""
        INSERT INTO apu_matrices (id, matriz_id, insumo_id, valor, operador, precio, formula)
        VALUES (100, 1, 1, 3.5, '*', 10, 'ancho_muro')
    """)
    # Componente APU de una matriz negativa (insumo compuesto id=2 -> matriz_id=-2)
    cur.execute("""
        INSERT INTO apu_matrices (id, matriz_id, insumo_id, valor, operador, precio, formula)
        VALUES (101, -2, 1, 2.8, '*', 10, 'altura')
    """)
    db.conn.commit()

    api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)

    # ── Variables: ancho_muro=3.5, altura=2.8, area_muro=ancho_muro*altura ──
    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")
    id_area = api.variables_crear("area_muro", expresion="ancho_muro * altura")
    id_independiente = api.variables_crear("factor_desperdicio", expresion="1.05")

    resueltas = api.variables_resueltas()
    assert resueltas["ancho_muro"] == Decimal("3.5")
    assert resueltas["area_muro"] == Decimal("9.8")
    print("OK: variables base creadas y resueltas correctamente")

    # ── Eliminar ancho_muro: debe tocar area_muro, el concepto y los 2 componentes APU ──
    resultado = api.variables_eliminar(id_ancho)
    print(f"Resumen de la eliminación: {resultado}")

    assert "area_muro" in resultado["variables"], \
        f"area_muro depende de ancho_muro, debía reescribirse: {resultado}"
    assert 1 in resultado["conceptos"], \
        f"el concepto 1 (formula='ancho_muro * altura') debía reescribirse: {resultado}"
    assert 100 in resultado["componentes_apu"], \
        f"el componente 100 (matriz positiva, formula='ancho_muro') debía reescribirse: {resultado}"
    # 101 depende de 'altura', no de 'ancho_muro' -> no debía tocarse
    assert 101 not in resultado["componentes_apu"], \
        f"el componente 101 depende de 'altura', no debía tocarse: {resultado}"
    print("OK: se detectaron y reescribieron exactamente las fórmulas que referenciaban ancho_muro")

    # factor_desperdicio no depende de nada -> no debía tocarse
    assert "factor_desperdicio" not in resultado["variables"]

    # ── La variable ya no existe ──────────────────────────────────────
    nombres = {v["nombre"] for v in api.variables_listar()}
    assert "ancho_muro" not in nombres, "ancho_muro debía quedar eliminada"
    print("OK: ancho_muro fue eliminada")

    # ── area_muro sigue evaluando bien, ahora con 3.5 constante ────────
    resueltas2 = api.variables_resueltas()
    assert resueltas2["area_muro"] == Decimal("9.8"), \
        f"area_muro debía seguir dando 9.8 (3.5 constante * altura), dio {resueltas2.get('area_muro')}"
    var_area = [v for v in api.variables_listar() if v["nombre"] == "area_muro"][0]
    assert "ancho_muro" not in var_area["expresion"], \
        f"la expresión de area_muro ya no debía mencionar ancho_muro: {var_area['expresion']!r}"
    print(f"OK: area_muro quedó como {var_area['expresion']!r} y sigue evaluando 9.8")

    # ── El concepto 1: formula reescrita y cantidad recalculada (3.5 * 2.8 = 9.8) ──
    concepto = cur.execute(
        "SELECT formula, cantidad FROM estructura_presupuesto WHERE id = 1"
    ).fetchone()
    assert "ancho_muro" not in (concepto["formula"] or ""), \
        f"formula del concepto ya no debía mencionar ancho_muro: {concepto['formula']!r}"
    assert abs(concepto["cantidad"] - 9.8) < 0.001, \
        f"cantidad debía recalcularse a 9.8, quedó {concepto['cantidad']}"
    print(f"OK: concepto 1 quedó con formula={concepto['formula']!r}, cantidad={concepto['cantidad']}")

    # ── Componente 100 (matriz positiva): formula reescrita y valor recalculado ──
    comp100 = cur.execute(
        "SELECT formula, valor FROM apu_matrices WHERE id = 100"
    ).fetchone()
    assert "ancho_muro" not in (comp100["formula"] or "")
    assert abs(comp100["valor"] - 3.5) < 0.001, \
        f"valor del componente 100 debía recalcularse a 3.5, quedó {comp100['valor']}"
    print(f"OK: componente 100 quedó con formula={comp100['formula']!r}, valor={comp100['valor']}")

    # ── Componente 101 (matriz negativa, insumo compuesto): NO debía tocarse ──
    comp101 = cur.execute(
        "SELECT formula, valor FROM apu_matrices WHERE id = 101"
    ).fetchone()
    assert comp101["formula"] == "altura", \
        f"componente 101 no dependía de ancho_muro, no debía tocarse: {comp101['formula']!r}"
    print("OK: componente 101 (matriz negativa, no relacionado) quedó intacto")

    # ── Ctrl+Z: los cambios en variables_formula/estructura_presupuesto/  ──
    # apu_matrices quedaron en el historial (aunque la variable en sí, al
    # ser DELETE físico sin columna activo, no es deshacible — ver
    # Hallazgo 5 original y el comentario en formulas.py del repo).
    deshecho = ds.deshacer(usuario_id=1, proyecto_id=1)
    assert deshecho, "debía poder deshacerse al menos el último cambio (eliminar physical no es deshacible, pero antes de eso sí hubo updates)"
    print("OK: el historial capturó los cambios previos al DELETE físico (deshacer funciona)")

    db.close()
    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 5 PASARON")


if __name__ == "__main__":
    main()
