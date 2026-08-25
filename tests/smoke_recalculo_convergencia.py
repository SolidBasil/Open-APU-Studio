"""
smoke_recalculo_convergencia.py
=================================
Prueba de humo de la corrección del Hallazgo 8: RecalculoRepo.recalcular_proyecto()
devolvía "iteraciones_compuestos" pero nada lo comparaba contra
MAX_ITERACIONES=15 en ningún lado — ni siquiera la única pantalla que lo
mostraba (diag_dialogs.py) distinguía "convergió justo en la última
iteración" de "se cortó en el límite sin estabilizarse".

Cubre:
    - Un ciclo real de insumos compuestos (A usa B, B usa A, con
      crecimiento exponencial 2x cada vuelta) fuerza exactamente
      MAX_ITERACIONES sin converger -> "convergio": False
    - Un caso normal (sin ciclos) converge antes del límite ->
      "convergio": True
    - Api.recalcular_proyecto() propaga "convergio" hasta la capa que
      usa la UI (antes: la UI no tenía forma de saberlo)

Uso:
    python3 tests/smoke_recalculo_convergencia.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.db import Database
from backend.database.repos.recalculo import RecalculoRepo


def _setup_proyecto(cur, pid=1):
    cur.execute(f"INSERT INTO proyectos (id, nombre) VALUES ({pid}, 'Test')")
    cur.execute("""
        INSERT INTO tipos_insumo (id, clave, nombre) VALUES (1, 'MAT', 'Material')
        ON CONFLICT(id) DO NOTHING
    """)


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    db = Database.abrir(db_path)
    cur = db.conn.cursor()

    # ═══════════════════════════════════════════════════════════════════
    # Caso 1: ciclo real A↔B con crecimiento exponencial -> NO converge
    # ═══════════════════════════════════════════════════════════════════
    _setup_proyecto(cur, pid=1)
    cur.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (10, 1, 1, 'Compuesto A', 'lote', 1.0, 1.0, 1, 1),
            (11, 1, 1, 'Compuesto B', 'lote', 1.0, 1.0, 1, 1)
    """)
    # A (matriz_id=-10) usa B con valor=2 ; B (matriz_id=-11) usa A con valor=2
    # -> cada vuelta duplica el costo, nunca se estabiliza (diverge).
    cur.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio)
        VALUES (-10, 11, 2, '*', 1.0), (-11, 10, 2, '*', 1.0)
    """)
    db.conn.commit()

    resultado_ciclo = RecalculoRepo(db.conn).recalcular_proyecto(1)
    db.conn.commit()
    assert resultado_ciclo["iteraciones_compuestos"] == RecalculoRepo.MAX_ITERACIONES, \
        f"un ciclo divergente debía agotar las {RecalculoRepo.MAX_ITERACIONES} iteraciones, hizo {resultado_ciclo['iteraciones_compuestos']}"
    assert resultado_ciclo["convergio"] is False, \
        f"un ciclo divergente NO debía marcarse como convergido: {resultado_ciclo}"
    print(f"OK: ciclo A↔B divergente detectado correctamente como NO convergido "
          f"({resultado_ciclo['iteraciones_compuestos']} iteraciones)")

    # ═══════════════════════════════════════════════════════════════════
    # Caso 2: sin ciclos -> converge bien antes del límite
    # ═══════════════════════════════════════════════════════════════════
    tmp2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp2.close()
    db2 = Database.abrir(tmp2.name)
    cur2 = db2.conn.cursor()
    _setup_proyecto(cur2, pid=1)
    cur2.execute("""
        INSERT INTO insumos (id, proyecto_id, tipo_id, descripcion, unidad,
                              costo_directo, costo_final, es_compuesto, activo)
        VALUES
            (20, 1, 1, 'Cemento',            'kg',   10.0, 10.0, 0, 1),
            (21, 1, 1, 'Compuesto simple A', 'lote', 0.0,  0.0,  1, 1)
    """)
    # A (matriz_id=-21) usa un insumo simple (no compuesto) -> se estabiliza
    # en 1 sola iteración, ningún ciclo.
    cur2.execute("""
        INSERT INTO apu_matrices (matriz_id, insumo_id, valor, operador, precio)
        VALUES (-21, 20, 3, '*', 10.0)
    """)
    db2.conn.commit()

    resultado_normal = RecalculoRepo(db2.conn).recalcular_proyecto(1)
    db2.conn.commit()
    assert resultado_normal["convergio"] is True, \
        f"un caso sin ciclos debía converger, dio: {resultado_normal}"
    assert resultado_normal["iteraciones_compuestos"] < RecalculoRepo.MAX_ITERACIONES, \
        f"debía converger antes del límite, hizo {resultado_normal['iteraciones_compuestos']}"
    print(f"OK: caso normal (sin ciclos) converge en "
          f"{resultado_normal['iteraciones_compuestos']} iteración(es), 'convergio': True")
    db2.close()
    os.unlink(tmp2.name)

    # ═══════════════════════════════════════════════════════════════════
    # Caso 3: Api.recalcular_proyecto() propaga 'convergio' hasta la UI
    # ═══════════════════════════════════════════════════════════════════
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from backend.database.event_bus import EventBus
    from backend.database.services.repository_registry import crear_registry
    from backend.database.services.data_service import DataService
    from frontend.ventana.api import Api

    event_bus = EventBus()
    registry = crear_registry(db)
    ds = DataService(db, registry, event_bus)
    api = Api(db.conn, db_path, proyecto_id=1, data_service=ds)
    resultado_api = api.recalcular_proyecto()
    assert "convergio" in resultado_api, \
        f"Api.recalcular_proyecto() debía propagar 'convergio': {resultado_api}"
    assert resultado_api["convergio"] is False  # sigue el mismo ciclo A↔B del caso 1
    print(f"OK: Api.recalcular_proyecto() propaga 'convergio' hasta la capa de la UI: {resultado_api['convergio']}")

    db.close()
    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 8 PASARON")


if __name__ == "__main__":
    main()
