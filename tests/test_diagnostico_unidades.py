"""Pytest para deduplicación 5.3: mapa único de unidades en DiagnosticoRepo."""
from backend.database.repos.diagnostico import _ALIASES, _unidades_mapa


def test_aliases_esperados():
    assert _ALIASES["m2"] == "m²"
    assert _ALIASES["m3"] == "m³"
    assert _ALIASES["lt"] == "L"
    assert _ALIASES["hor"] == "hr"


def test_mapa_incluye_alias_y_estandar(db_tmp):
    mapa = _unidades_mapa()
    assert mapa["m2"] == "m²"
    assert mapa["jgo"] == "juego"
    for u, std in (("kg", "kg"), ("m3", "m³")):
        assert mapa.get(u) == std or u in mapa


def test_metodos_usan_mapa_compartido(api, db_tmp):
    from backend.database.repos.diagnostico import DiagnosticoRepo
    db, _ = db_tmp
    repo = DiagnosticoRepo(db.conn)
    # con catálogo vacío no hay filas en ninguna de las dos
    assert repo.unidades_no_estandar(1) == []
    assert repo.unidades_case(1) == []
    api.insumo_insertar(tipo_id=1, descripcion="X", unidad="M2", costo=1)
    case = repo.unidades_case(1)
    assert any(r["unidad"] == "M2" for r in case)
    no_est = repo.unidades_no_estandar(1)
    assert not any(r["unidad"] == "M2" for r in no_est)
