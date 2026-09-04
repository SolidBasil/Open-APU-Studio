"""Pytest para proyecto_guardar — migrado de smoke_proyecto_guardar (solo local)."""
import pytest

from backend.database.exceptions import ValidationError


def test_proyecto_guardar_valida(api, db_tmp):
    db, _ = db_tmp
    cur = db.conn.cursor()
    with pytest.raises(ValidationError):
        api.proyecto_guardar({"duracion_obra_dias": -5})
    fila = cur.execute("SELECT duracion_obra_dias FROM proyectos WHERE id=1").fetchone()
    assert (fila["duracion_obra_dias"] or 0) == 0


def test_proyecto_guardar_persiste_y_deshace(api, db_tmp):
    from backend.database.services.data_service import DataService
    from backend.database.services.repository_registry import crear_registry
    from backend.database.event_bus import EventBus
    from backend.database.db import Database

    db, db_path = db_tmp
    cur = db.conn.cursor()
    api.proyecto_guardar({"duracion_obra_dias": 45, "cliente_nombre": "Cliente"})
    # visible en conexión nueva = comiteado
    db2 = Database.abrir(db_path)
    fila2 = db2.conn.execute(
        "SELECT duracion_obra_dias, cliente_nombre FROM proyectos WHERE id=1").fetchone()
    assert fila2["duracion_obra_dias"] == 45
    assert fila2["cliente_nombre"] == "Cliente"
    db2.close()
    # historial: deshacible
    api.proyecto_guardar({"duracion_obra_dias": 99})
    ds = DataService(db, crear_registry(db), EventBus())
    assert ds.deshacer(usuario_id=1, proyecto_id=1)
    fila4 = cur.execute("SELECT duracion_obra_dias FROM proyectos WHERE id=1").fetchone()
    assert fila4["duracion_obra_dias"] == 45
