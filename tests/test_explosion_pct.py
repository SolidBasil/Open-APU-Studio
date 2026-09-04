"""Pytest para (%)CONCEPTO — migrado de smoke_explosion_pct_concepto (Hallazgo 4)."""
import sqlite3

import pytest

from backend.database.repos.explosion import ExplosionRepo, _parse_unidad_pct, _PCT_TIPO_DESTINO


def test_pct_concepto_resuelve_subcontrato():
    es_pct, sufijo, tipo_destino = _parse_unidad_pct("(%)CONCEPTO")
    assert es_pct is True
    assert sufijo == "CONCEPTO"
    assert tipo_destino == 32
    _, _, tipo_subc = _parse_unidad_pct("(%)SUBC")
    assert tipo_destino == tipo_subc


@pytest.mark.parametrize("unidad,esperado", [
    ("(%)MO", 2), ("(%)MA", 1), ("(%)MAT", 1),
    ("(%)EQ", 8), ("(%)AUX", 16), ("(%)SUBC", 32), ("(%)FL", 64), ("(%)TR", 128),
])
def test_sufijos_preexistentes_sin_cambios(unidad, esperado):
    _, _, td = _parse_unidad_pct(unidad)
    assert td == esperado


def test_unidad_no_porcentual():
    es_pct, sufijo, tipo_destino = _parse_unidad_pct("m2")
    assert es_pct is False and sufijo is None and tipo_destino is None


def test_postprocesar_bucket_correcto():
    repo = ExplosionRepo(sqlite3.connect(":memory:"))
    filas = [
        {"tipo_id": 32, "tipo_orden": 1, "total": 1000.0, "unidad": "lote"},
        {"tipo_id": 2,  "tipo_orden": 2, "total": 500.0,  "unidad": "jornal"},
        {"tipo_id": 16, "tipo_orden": 3, "total": 100.0,  "unidad": "(%)CONCEPTO"},
    ]
    resultado, total_global = repo._postprocesar(filas, tipos_set={2, 16, 32})
    fila_pct = [f for f in resultado if f["unidad"] == "(%)CONCEPTO"][0]
    assert fila_pct["pct_sufijo"] == "CONCEPTO"
    assert abs(fila_pct["pct_base"] - (100.0 / 1000.0)) < 1e-9
