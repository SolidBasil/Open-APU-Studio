"""Verifica que api.py sea dispatcher puro y sin SQL (regla cardinal)."""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))


def test_api_sin_sql():
    api = pathlib.Path("frontend/ventana/api.py").read_text()
    assert "SELECT " not in api, "api.py no debe tener SQL"


def test_api_sin_ramas_por_metodo():
    api = pathlib.Path("frontend/ventana/api.py").read_text()
    per_method = len(re.findall(r"\n    if self\._use_http:", api))
    assert per_method == 0, f"api.py aún tiene {per_method} ramas por método"


def test_toque_backend_70():
    from frontend.ventana.api_backends import ToqueApiBackend

    n = len([m for m in dir(ToqueApiBackend) if not m.startswith("_")])
    assert n == 70, f"esperado 70, got {n}"


def test_api_cliente_transporte():
    from frontend.ventana.api_cliente import ApiCliente

    pub = [m for m in dir(ApiCliente) if not m.startswith("_")]
    assert len(pub) == 7, f"esperado 7, got {len(pub)}: {pub}"
