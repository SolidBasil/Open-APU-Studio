"""Pytest de regresión: detener() despierta al hilo WS aunque esté en backoff."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_detener_despierta_backoff(qapp):
    from frontend.ventana.ws_client import WebSocketClient
    # Puerto cerrado: el cliente entra en backoff exponencial (hasta 30s).
    # Se esperan ~8s para que el backoff supere los 5s del wait: con el
    # código viejo (sleep monolítico) detener() tardaría 8-16s y el
    # wait(5000) expirararía; con sleep interrumpible termina al instante.
    c = WebSocketClient("http://127.0.0.1:9", "inexistente")
    c.start()
    time.sleep(8)
    assert c.isRunning(), "el hilo debía seguir vivo en backoff"
    t0 = time.monotonic()
    c.detener()
    terminado = c.wait(5000)
    dt = time.monotonic() - t0
    assert terminado, "el hilo debió terminar tras detener()"
    assert dt < 4.0, f"detener() tardó {dt:.1f}s (antes: hasta 30s en backoff)"
