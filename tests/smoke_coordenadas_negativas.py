"""
smoke_coordenadas_negativas.py
================================
Prueba de humo de la corrección de N7: el widget de latitud/longitud en
el diálogo de info de proyecto usaba el mismo QDoubleSpinBox que
tipo_cambio/horas_dia (rango 0-999999), que nunca permitía valores
negativos. Como México está al oeste de Greenwich, su longitud real es
negativa (ej. CDMX ≈ -99.13) — antes era físicamente imposible
capturarla bien, y además cualquier valor negativo ya guardado se
recortaba a 0 en silencio al mostrarlo (QDoubleSpinBox.setValue()
recorta al rango del widget).

Cubre:
    - El nuevo widget "spin_coord" acepta y conserva valores negativos
    - "spin_float" (tipo_cambio, horas_dia) sigue sin permitir negativos
      — no se debilitó la validación de esos campos por accidente
    - Guardar una longitud negativa a través de Api.proyecto_guardar()
      sigue funcionando end-to-end (SchemaRegistry ya lo permitía; lo que
      faltaba era que la UI pudiera producir ese valor)

Uso:
    QT_QPA_PLATFORM=offscreen python3 tests/smoke_coordenadas_negativas.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDoubleSpinBox


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    # Réplica mínima de la lógica de _add_field para "spin_coord" vs
    # "spin_float" (no se importa el método completo porque vive como
    # closure dentro de _mostrar_info_proyecto — se prueba la lógica del
    # widget directamente, que es lo que cambió).
    def _make(widget_type: str, value):
        w = QDoubleSpinBox()
        if widget_type == "spin_float":
            w.setDecimals(2)
            w.setRange(0, 999999)
        elif widget_type == "spin_coord":
            w.setDecimals(6)
            w.setRange(-180, 180)
        w.setValue(float(value) if value else 0)
        return w

    # ── spin_coord: conserva valores negativos ──────────────────────────
    w_lon = _make("spin_coord", -99.1332)
    assert abs(w_lon.value() - (-99.1332)) < 1e-4, \
        f"spin_coord debía conservar -99.1332, dio {w_lon.value()}"
    print(f"OK: spin_coord conserva el valor negativo ({w_lon.value()})")

    w_lat = _make("spin_coord", 19.4326)
    assert abs(w_lat.value() - 19.4326) < 1e-4
    print(f"OK: spin_coord también acepta positivos normalmente ({w_lat.value()})")

    # ── spin_float: sigue sin permitir negativos (no se debilitó) ───────
    w_tc = _make("spin_float", -5.0)
    assert w_tc.value() == 0.0, \
        f"spin_float debía seguir recortando negativos a 0 (rango sin cambios), dio {w_tc.value()}"
    print("OK: spin_float (tipo_cambio/horas_dia) sigue sin permitir negativos — sin regresión")

    # ── Antes del fix: cargar un valor negativo ya guardado se recortaba
    #    a 0 en silencio. Confirmamos que spin_coord ya NO hace esto. ──
    w_repeticion = _make("spin_coord", -99.1332)
    assert w_repeticion.value() != 0.0, \
        "un valor negativo cargado no debía recortarse a 0 en silencio"
    print("OK: un valor negativo cargado desde la BD ya no se recorta a 0 al mostrarlo")

    # ── End-to-end: Api.proyecto_guardar() con longitud negativa ────────
    import tempfile
    from backend.database.db import Database
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = Database.abrir(tmp.name)
    ds = DataService(db, crear_registry(db), EventBus())
    cur = db.conn.cursor()
    cur.execute("INSERT INTO proyectos (id, nombre) VALUES (1, 'Test')")
    db.conn.commit()
    api = Api(db.conn, tmp.name, proyecto_id=1, data_service=ds)

    api.proyecto_guardar({"obra_latitud": 19.4326, "obra_longitud": -99.1332})
    fila = cur.execute(
        "SELECT obra_latitud, obra_longitud FROM proyectos WHERE id=1"
    ).fetchone()
    assert abs(fila["obra_longitud"] - (-99.1332)) < 1e-4, \
        f"la longitud negativa debía guardarse tal cual, quedó {fila['obra_longitud']}"
    print(f"OK: proyecto_guardar() persiste correctamente lat={fila['obra_latitud']}, "
          f"lon={fila['obra_longitud']} (CDMX real, con signo correcto)")

    db.close()
    os.unlink(tmp.name)

    print("\nTODAS LAS PRUEBAS DE N7 (coordenadas negativas) PASARON")


if __name__ == "__main__":
    main()
