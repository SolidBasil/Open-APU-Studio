import importlib.util
import os
import sys

_module = None


def _get_core():
    global _module
    if _module is not None:
        return _module
    fn = os.path.join(os.path.dirname(__file__), "..", "..",
                      "Conversor de opus", "backend", "core.py")
    fn = os.path.normpath(fn)
    if not os.path.exists(fn):
        raise ImportError(f"Conversor de opus not found at {fn}")
    spec = importlib.util.spec_from_file_location("opus_core", fn)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["opus_core"] = mod
    spec.loader.exec_module(mod)
    _module = mod
    return mod


def build_budget_tree(db_path):
    return _get_core().build_budget_tree(db_path)


def count_nodes(nodes):
    return _get_core().count_nodes(nodes)


def count_concepts(nodes):
    return _get_core().count_concepts(nodes)
