"""
smoke_variables_http.py
=========================
Prueba de humo de la migración de "variables de fórmula" (el único
módulo sin ningún soporte HTTP hasta ahora) a la API HTTP. Sin este
módulo, concepto_actualizar_cantidad()/apu_actualizar_valor() con
fórmula (que dependen de variables_resueltas()) tampoco funcionaban vía
HTTP — se detectó exactamente así, al correr smoke_apu_http.py y
smoke_presupuesto_http.py después de este refactor.

Uso:
    python3 tests/smoke_variables_http.py
"""
import os
import sys
import time
import socket
import shutil
import tempfile
import threading
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _crear_proyecto(nombre, db, cur):
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES (1, '{nombre}')")
    db.conn.commit()


def _ejercitar_variables(api) -> dict:
    id_ancho = api.variables_crear("ancho_muro", expresion="3.5")
    id_altura = api.variables_crear("altura", expresion="2.8")
    id_area = api.variables_crear("area_muro", expresion="ancho_muro * altura")
    id_independiente = api.variables_crear("factor_desperdicio", expresion="1.05")

    lista = api.variables_listar()
    assert {v["nombre"] for v in lista} == {"ancho_muro", "altura", "area_muro", "factor_desperdicio"}

    resueltas = api.variables_resueltas()
    assert isinstance(resueltas["area_muro"], Decimal)
    assert resueltas["area_muro"] == Decimal("9.8")

    valor_formula = api.formula_evaluar("ancho_muro * 2")
    assert isinstance(valor_formula, Decimal)
    assert valor_formula == Decimal("7.0")

    try:
        api.variables_crear("ancho_muro", expresion="1")
        raise AssertionError("debía rechazar nombre duplicado")
    except ValueError:
        pass
    assert len(api.variables_listar()) == 4

    try:
        api.variables_actualizar(id_independiente, nombre="ancho_muro")
        raise AssertionError("debía rechazar renombrado a duplicado")
    except ValueError:
        pass

    # Renombrar una variable de la que NADA depende — a diferencia de
    # "altura" (usada por area_muro), esto sí debe poder renombrarse sin
    # romper otras fórmulas (renombrar no reescribe dependientes, solo
    # eliminar lo hace — ver Hallazgo 5; intentar renombrar "altura" aquí
    # debe rechazarse, y de hecho se rechaza, correctamente).
    try:
        api.variables_actualizar(id_altura, nombre="altura_muro")
        raise AssertionError("renombrar una variable de la que depende otra fórmula debía rechazarse")
    except ValueError:
        pass

    api.variables_actualizar(id_independiente, nombre="desperdicio_muro")
    nombres = {v["nombre"] for v in api.variables_listar()}
    assert "desperdicio_muro" in nombres and "factor_desperdicio" not in nombres

    resultado = api.variables_eliminar(id_ancho)
    assert "area_muro" in resultado["variables"]
    resueltas2 = api.variables_resueltas()
    assert resueltas2["area_muro"] == Decimal("9.8")

    return {
        "n_variables_final": len(api.variables_listar()),
        "area_muro_resuelta": str(resueltas2["area_muro"]),
        "valor_formula": str(valor_formula),
    }


def main():
    tmp_base = tempfile.mkdtemp(prefix="smoke_variables_http_")
    from backend.database.db import Database, Rutas
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    nombre_a = "smoke_variables_http_local"
    path_a = Rutas.db_proyecto(nombre_a)
    if path_a.exists():
        path_a.unlink()
    db_a = Database.abrir(path_a)
    _crear_proyecto(nombre_a, db_a, db_a.conn.cursor())
    ds_a = DataService(db_a, crear_registry(db_a), EventBus())
    api_local = Api(db_a.conn, path_a, proyecto_id=1, data_service=ds_a)

    resultado_local = _ejercitar_variables(api_local)
    print(f"OK (local): {resultado_local}")
    db_a.close()

    nombre_b = "smoke_variables_http_remoto"
    path_b = Rutas.db_proyecto(nombre_b)
    if path_b.exists():
        path_b.unlink()
    db_b = Database.abrir(path_b)
    _crear_proyecto(nombre_b, db_b, db_b.conn.cursor())
    db_b.close()

    import uvicorn
    import server.servidor as srv
    srv._proyectos.clear()

    puerto = _puerto_libre()
    config = uvicorn.Config(srv.app, host="127.0.0.1", port=puerto, log_level="error")
    server_uv = uvicorn.Server(config)
    hilo = threading.Thread(target=server_uv.run, daemon=True)
    hilo.start()
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("el servidor de prueba no arrancó a tiempo")

    try:
        db_placeholder = Database.abrir(path_a)
        ds_placeholder = DataService(db_placeholder, crear_registry(db_placeholder), EventBus())
        api_http = Api(
            db_placeholder.conn, path_b, proyecto_id=1, data_service=ds_placeholder,
            servidor_url=f"http://127.0.0.1:{puerto}",
        )
        assert api_http._use_http is True

        resultado_http = _ejercitar_variables(api_http)
        print(f"OK (HTTP):  {resultado_http}")

        assert resultado_local == resultado_http, (
            f"el modo HTTP debía dar exactamente el mismo resultado que local:\n"
            f"  local: {resultado_local}\n"
            f"  http:  {resultado_http}"
        )
        print("OK: paridad exacta entre backend local y HTTP para variables de fórmula")
        print("OK: Decimal se preserva correctamente a través de la red (via string, no float)")

        # ── Dependencia cruzada: concepto_actualizar_cantidad con fórmula vía HTTP ──
        import sqlite3
        conn_directa = sqlite3.connect(str(path_b))
        conn_directa.execute("""
            INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
            ON CONFLICT(id) DO NOTHING
        """)
        conn_directa.execute("""
            INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                                  costo_directo, costo_final, activo)
            VALUES (1, 1, 1, 'Cemento', 'kg', 10, 10, 1)
        """)
        conn_directa.execute("""
            INSERT INTO estructura_presupuesto
                (id, proyecto_id, padre_id, wbs, nivel, orden, tipo, insumo_id,
                 descripcion, cantidad, total, activo)
            VALUES (1, 1, NULL, '1', 0, 1, 'concepto', 1, 'Concepto', 0, 0, 1)
        """)
        conn_directa.commit()
        conn_directa.close()

        api_http.concepto_actualizar_cantidad(1, cantidad=0, formula="altura * 2")
        total = api_http.nodo_total(1)
        assert abs(total - (5.6 * 10)) < 0.01, total
        print(f"OK: concepto_actualizar_cantidad() con fórmula que referencia una "
              f"variable ahora funciona vía HTTP (total={total})")

        db_placeholder.close()

        print("\nTODAS LAS PRUEBAS DE LA MIGRACIÓN HTTP DE VARIABLES PASARON")
    finally:
        server_uv.should_exit = True
        hilo.join(timeout=5)
        for p in (path_a, path_b):
            if p.exists():
                p.unlink()
        shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
