"""Pytest para _padre_por_wbs — migrado de smoke_padre_por_wbs (Hallazgo 9)."""
from backend.importar.importar import _padre_por_wbs


def test_caso_regular_no_ambiguo():
    wbs_a_id = {"1": 1, "11": 2, "111": 3}
    padre_id, ambiguo = _padre_por_wbs("1111", wbs_a_id)
    assert padre_id == 3
    assert ambiguo is False


def test_salto_nivel_marca_ambiguo():
    wbs_a_id2 = {"1": 1, "11": 2}  # falta "111"
    padre_id2, ambiguo2 = _padre_por_wbs("1111", wbs_a_id2)
    assert padre_id2 == 2
    assert ambiguo2 is True


def test_sin_padre():
    padre_id3, ambiguo3 = _padre_por_wbs("999", {"1": 1, "11": 2})
    assert padre_id3 is None
    assert ambiguo3 is False
    assert _padre_por_wbs("1", {}) == (None, False)
    assert _padre_por_wbs("", {}) == (None, False)


def test_stats_llegan_a_importar_y_ui():
    import inspect
    from backend.importar import importar as mod_importar
    src_importar = inspect.getsource(mod_importar)
    assert '"wbs_ambiguo"' in src_importar and '"wbs_sin_resolver"' in src_importar
    from frontend.ventana.mixins import gestion_proyectos as mod_gestion
    src_gestion = inspect.getsource(mod_gestion)
    assert "wbs_ambiguo" in src_gestion and "wbs_sin_resolver" in src_gestion
