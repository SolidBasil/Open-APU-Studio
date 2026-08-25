"""
smoke_api_backends.py
======================
Prueba funcional de humo contra una BD SQLite real (no mocks) para las
secciones de Api ya migradas al patrón de backends (ver
frontend/ventana/api_backends.py y docs/DUPLICACION_Y_DEUDA.md):
FACTORES DE SOBRECOSTO e INSUMOS.

El proyecto no tenía suite de tests — esto es un punto de partida
mínimo (sin pytest ni otras dependencias) para verificar que una
migración de Api no cambió el comportamiento en modo local. Al migrar
una sección nueva, agregar su caso aquí antes de dar la sección por
cerrada.

Uso:
    python3 tests/smoke_api_backends.py

No cubre el modo HTTP (requiere levantar server/servidor.py aparte).
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

        assert api._backend is api._backend_local, \
            "sin servidor_url, el backend activo debe ser el local"

        r1 = api.factores_sobrecosto_obtener()
        assert r1 == {}, f"esperaba dict vacío antes de guardar, llegó {r1!r}"

        factor = api.factores_sobrecosto_guardar({
            "pct_indirectos_campo": 10, "pct_indirectos_oficina": 5,
            "pct_financiamiento": 2, "pct_utilidad": 8,
            "pct_cargos_adicionales": 1,
        })
        assert isinstance(factor, float)

        r2 = api.factores_sobrecosto_obtener()
        assert r2.get("factor_total") == factor, \
            "el factor guardado debe coincidir con el que devuelve obtener()"

        factor_calc = api.factores_sobrecosto_calcular(
            pct_indirectos_campo=10, pct_indirectos_oficina=5,
            pct_financiamiento=2, pct_utilidad=8, pct_cargos_adicionales=1,
        )
        assert abs(factor_calc - factor) < 1e-9, \
            "calcular() sin persistir debe coincidir con guardar()"

        # ── INSUMOS ──────────────────────────────────────────────────
        vacio = api.insumos()
        assert vacio == [], "insumos() en proyecto vacío debe ser lista vacía"

        usos = api.rastrear_insumo(999999)
        assert usos == [], "rastrear_insumo() de un id inexistente debe ser lista vacía"

        resultado = api.recalcular_proyecto()
        assert isinstance(resultado, dict), "recalcular_proyecto() debe devolver un dict"

        db.close()
        print("OK — FACTORES DE SOBRECOSTO + INSUMOS vía Api._backend")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    main()
