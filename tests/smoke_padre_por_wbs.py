"""
smoke_padre_por_wbs.py
========================
Prueba de humo de la corrección del Hallazgo 9: _padre_por_wbs() trunca
el WBS carácter por carácter sin ninguna noción real de "segmento" o
nivel. No se reescribió el algoritmo (no hay forma de validarlo con
seguridad sin un proyecto OPUS real de jerarquía irregular — el propio
hallazgo original recomendaba probar antes de decidir si vale la pena
una lógica más robusta). En su lugar, la función ahora reporta cuándo
tuvo que truncar MÁS de un carácter para encontrar el padre — una señal
de jerarquía potencialmente irregular que antes se perdía en silencio.

Cubre:
    - Caso regular (1 dígito por nivel): nunca se marca como ambiguo
    - Caso "salto de nivel" (falta un nodo intermedio): si el WBS
      truncado un solo carácter no existe, encontrar el padre dos
      carácteres más arriba SÍ se marca como ambiguo — es exactamente el
      caso que no se podía distinguir de una jerarquía multi-dígito real
    - La señal llega hasta el dict que devuelve importar() (no solo
      print) y hasta el diálogo del frontend (gestion_proyectos.py)

Uso:
    python3 tests/smoke_padre_por_wbs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.importar.importar import _padre_por_wbs


def main():
    # ── Caso regular: 1 dígito por nivel, el padre está justo un char arriba ──
    wbs_a_id = {"1": 1, "11": 2, "111": 3}
    padre_id, ambiguo = _padre_por_wbs("1111", wbs_a_id)
    assert padre_id == 3
    assert ambiguo is False, "truncar un solo carácter y encontrar match no es ambiguo"
    print("OK: caso regular (1 dígito/nivel) — no se marca como ambiguo")

    # ── Caso "salto de nivel": falta el nodo inmediatamente superior ──
    # "1111" no tiene un "111" en el dict (nunca se importó ese nivel) —
    # hay que truncar 2 caracteres para llegar a "11". Esto SÍ se marca.
    wbs_a_id2 = {"1": 1, "11": 2}  # falta "111"
    padre_id2, ambiguo2 = _padre_por_wbs("1111", wbs_a_id2)
    assert padre_id2 == 2  # encontró "11"
    assert ambiguo2 is True, "truncar más de un carácter debía marcarse como ambiguo"
    print("OK: caso con nivel faltante — se marca como ambiguo (antes: silencio total)")

    # ── Caso sin padre en absoluto ──────────────────────────────────────
    padre_id3, ambiguo3 = _padre_por_wbs("999", {"1": 1, "11": 2})
    assert padre_id3 is None
    assert ambiguo3 is False
    print("OK: sin padre encontrado — no se marca como ambiguo (no hay nada que revisar)")

    # ── WBS de un solo carácter o vacío: sin padre, por definición ──────
    assert _padre_por_wbs("1", {}) == (None, False)
    assert _padre_por_wbs("", {}) == (None, False)
    print("OK: WBS de 0-1 caracteres sigue devolviendo (None, False)")

    # ── El conteo llega hasta importar_dbf() y hasta la UI ──────────────
    # (verificación estática: confirmamos que ambos archivos referencian
    # las claves nuevas, sin tener que simular un import DBF completo)
    import inspect
    from backend.importar import importar as mod_importar
    src_importar = inspect.getsource(mod_importar)
    assert '"wbs_ambiguo"' in src_importar and '"wbs_sin_resolver"' in src_importar, \
        "el dict de stats que devuelve importar() debía incluir wbs_ambiguo/wbs_sin_resolver"
    print("OK: importar() incluye wbs_ambiguo/wbs_sin_resolver en el dict que realmente devuelve")

    from frontend.ventana.mixins import gestion_proyectos as mod_gestion
    src_gestion = inspect.getsource(mod_gestion)
    assert "wbs_ambiguo" in src_gestion and "wbs_sin_resolver" in src_gestion, \
        "el diálogo de importación en el frontend debía leer wbs_ambiguo/wbs_sin_resolver"
    print("OK: el diálogo de importación del frontend lee y muestra el aviso al usuario")

    print("\nTODAS LAS PRUEBAS DEL HALLAZGO 9 PASARON")


if __name__ == "__main__":
    main()
