"""
ws_client.py
============
Cliente WebSocket para recibir eventos en tiempo real del servidor.

SRV-05: se conecta al endpoint WS del servidor y re-emite los eventos
recibidos en el EventBus local del frontend. Los widgets ya están
suscritos ahí — no necesitan cambios.

Se ejecuta en un QThread daemon. Si el WebSocket se cae, reconecta
automáticamente con backoff exponencial (1s → 2s → 4s → máx 30s).
"""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class WebSocketClient(QThread):
    """Cliente WS que re-emite eventos en el EventBus local.

    Se instancia por proyecto abierto y se detiene al cerrarlo.
    """

    evento_recibido = Signal(str, dict)  # (nombre_evento, data)

    def __init__(self, base_url: str, nombre_proyecto: str, parent=None):
        super().__init__(parent)
        self._url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self._nombre = nombre_proyecto
        self._stop = False

    def run(self):
        import websockets.sync.client as wsc

        ws_url = f"{self._url}/proyectos/{self._nombre}/ws"
        backoff = 1.0

        while not self._stop:
            try:
                with wsc.connect(ws_url, open_timeout=5, close_timeout=3) as ws:
                    backoff = 1.0
                    while not self._stop:
                        try:
                            raw = ws.recv(timeout=5)
                        except TimeoutError:
                            continue
                        try:
                            msg = json.loads(raw)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        evento = msg.get("evento", "")
                        data = msg.get("data", {})
                        self.evento_recibido.emit(evento, data)
            except Exception as e:
                if self._stop:
                    break
                log.debug("WS desconectado: %s — reconectando en %.0fs", e, backoff)
                self._dormir_interrumpible(backoff)
                backoff = min(backoff * 2, 30.0)

    def _dormir_interrumpible(self, segundos: float) -> None:
        """Sleep en tramos cortos para que detener() despierte rápido.

        Sin esto, un detener() durante el backoff (hasta 30s) dejaba el
        hilo vivo emitiendo señales a una ventana ya cerrada u otro
        proyecto (zombi), y al salir de la app Qt advertía por destruir
        un QThread en ejecución.
        """
        import time as _time
        fin = _time.monotonic() + segundos
        while not self._stop and _time.monotonic() < fin:
            _time.sleep(min(0.2, fin - _time.monotonic()))

    def detener(self):
        self._stop = True
