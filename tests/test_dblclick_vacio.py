"""Pytest de regresión: doble clic en zona vacía no debe crashear.

Qt pasa item=None a los slots de itemDoubleClicked/itemClicked cuando el
clic cae fuera de cualquier fila. Antes, 6 handlers llamaban item.data()
o item.childCount() sin guarda → AttributeError (reportado corriendo
main.py y dando doble clic en el vacío del APU).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_apu_mixin_dblclick_vacio():
    from frontend.ventana.mixins.apu import ApuMixin

    class W(ApuMixin):
        pass

    W()._on_item_dblclick(None, 7)  # no debe lanzar


def test_rastreo_dblclick_vacio():
    from frontend.ventana.mixins.rastreo import RastreoMixin

    class W(RastreoMixin):
        pass

    W()._abrir_matriz_desde_rastreo(None)  # no debe lanzar


def test_sidebar_clicks_vacio():
    from frontend.ventana.mixins.navegacion import HandlersMixin

    class W(HandlersMixin):
        pass

    w = W()
    w._on_sidebar_click(None, 0)  # no debe lanzar
    w._on_sidebar_double_click(None, 0)  # no debe lanzar


def test_rastreo_menu_icon_no_nameerror():
    """Regresión: `_on_rastrear_context_menu`/`PestañaExplosion._on_context_menu`
    usaban `_menu_icon` sin importarlo -> NameError al abrir el menú contextual.
    Fix 2026-09-04: explosion.py lo importa a nivel módulo; rastreo.py lo
    importa dentro del método (local) para no alterar el grafo de imports
    (tiraba la carrera de teardown Qt de test_filtro_local.py:52)."""
    import inspect
    import frontend.ventana.widgets.explosion as explosion_mod
    from frontend.ventana.widgets.base import _menu_icon
    from frontend.ventana.mixins.rastreo import RastreoMixin

    assert explosion_mod._menu_icon is _menu_icon
    src = inspect.getsource(RastreoMixin._on_rastrear_context_menu)
    assert "_menu_icon" in src
    assert "from frontend.ventana.widgets.base import _menu_icon" in src


def test_tabla_apu_dblclick_vacio(qapp):
    from frontend.ventana.widgets.apu import TablaApuDetalle
    t = TablaApuDetalle(1, "x")
    t._on_item_dblclick(None, 2)  # no debe lanzar
