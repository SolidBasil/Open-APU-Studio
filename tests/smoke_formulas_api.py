"""
smoke_formulas_api.py
======================
Prueba de humo end-to-end del CRUD de variables_formula y la resolución
de fórmulas contra una BD SQLite real (sin mocks), a través de Api.

Cubre:
    - CRUD de variables_formula vía Api (variables_crear/actualizar/eliminar)
    - Resolución recursiva de variables vía Api.variables_resueltas()
    - Api.formula_evaluar() contra esas variables
    - Validación de nombre duplicado, ciclos y sintaxis inválida

Uso:
    python3 tests/smoke_formulas_api.py
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

# silenciar logging
import logging
logging.basicConfig(level=logging.WARNING)


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

        # ── Variables: CRUD básico ───────────────────────────────────
        assert api.variables_listar() == [], "proyecto nuevo no debe tener variables"

        api.variables_crear("ancho_muro", expresion="3.5")
        id_altura = api.variables_crear("altura", expresion="2.8")
        id_area = api.variables_crear("area_muro", expresion="ancho_muro * altura")

        listado = api.variables_listar()
        assert len(listado) == 3, f"esperaba 3 variables, hay {len(listado)}"
        nombres = {v["nombre"] for v in listado}
        assert nombres == {"ancho_muro", "altura", "area_muro"}, nombres

        # ── Nombre duplicado → ValueError legible ────────────────────
        try:
            api.variables_crear("ancho_muro", expresion="1")
            assert False, "debía rechazar el nombre duplicado"
        except ValueError as e:
            assert "ancho_muro" in str(e), str(e)

        # ── Nombre inválido como identificador → ValueError ────────────
        try:
            api.variables_crear("2ancho", expresion="1")
            assert False, "debía rechazar un nombre que no es identificador válido"
        except ValueError:
            pass

        # ── Resolución recursiva vía Api, siempre en Decimal ──────────
        resueltas = api.variables_resueltas()
        assert resueltas["area_muro"] == Decimal("9.80"), resueltas
        assert all(isinstance(v, Decimal) for v in resueltas.values())

        # ── formula_evaluar() contra esas variables ──────────────────
        assert api.formula_evaluar("area_muro * 2") == Decimal("19.60")

        # ── formula_evaluar() con fórmula inválida → ValueError legible ──
        try:
            api.formula_evaluar("area_muro * variable_fantasma")
            assert False, "debía fallar: variable_fantasma no existe"
        except ValueError as e:
            assert "variable_fantasma" in str(e), str(e)

        # ── Actualizar una variable y verificar que el cambio se propaga ──
        api.variables_actualizar(id_altura, expresion="3.0")
        resueltas = api.variables_resueltas()
        assert resueltas["area_muro"] == Decimal("10.5"), resueltas

        # ── Actualizar con una expresión que crea un ciclo → rechazada ──
        try:
            api.variables_actualizar(id_altura, expresion="area_muro / ancho_muro")
            assert False, "debía rechazar el ciclo altura<->area_muro"
        except ValueError as e:
            assert "iclo" in str(e), str(e)
        # altura debe seguir en 3.0 (el ciclo no se guardó)
        assert api.variables_resueltas()["altura"] == Decimal("3.0")

        # ── Ciclo en variables nuevas → se detecta en resolución ───────
        id_x = api.variables_crear("x_test", expresion="y_test + 1")
        id_y = api.variables_crear("y_test", expresion="x_test - 1")
        try:
            api.variables_resueltas()
            assert False, "debía detectar el ciclo x_test<->y_test"
        except ValueError as e:
            assert "iclo" in str(e), str(e)
        api.variables_eliminar(id_x)
        api.variables_eliminar(id_y)

        # ── Eliminar variable ──────────────────────────────────────────
        api.variables_eliminar(id_area)
        assert len(api.variables_listar()) == 2

        # ── Persistir fórmula en concepto ──────────────────────────────
        cur.execute("INSERT INTO estructura_presupuesto "
                    "(proyecto_id, wbs, nivel, orden, tipo, descripcion, cantidad) "
                    "VALUES (1, '1', 0, 1, 'concepto', 'Prueba fórmula', 0)")
        db.conn.commit()
        cap_id = cur.lastrowid

        api.concepto_actualizar_cantidad(cap_id, cantidad=0, formula="ancho_muro * 2")
        fila = db.conn.execute(
            "SELECT cantidad, formula FROM estructura_presupuesto WHERE id = ?",
            [cap_id],
        ).fetchone()
        assert fila["cantidad"] == 7.0, f"esperaba 7.0, obtuve {fila['cantidad']}"
        assert fila["formula"] == "ancho_muro * 2", fila["formula"]

        # fórmula con número simple
        api.concepto_actualizar_cantidad(cap_id, cantidad=0, formula="15")
        fila = db.conn.execute(
            "SELECT cantidad, formula FROM estructura_presupuesto WHERE id = ?",
            [cap_id],
        ).fetchone()
        assert fila["cantidad"] == 15.0, f"esperaba 15.0, obtuve {fila['cantidad']}"

        # fórmula inválida → ValueError, no se guarda
        try:
            api.concepto_actualizar_cantidad(cap_id, cantidad=0, formula="no_existe * 2")
            assert False, "debía fallar: variable no_existe no definida"
        except ValueError:
            pass

        print("OK — smoke_formulas_api: todos los casos pasaron")
    finally:
        try:
            db.close()
        except Exception:
            pass
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
