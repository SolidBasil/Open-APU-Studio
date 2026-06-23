"""
temas.py
========
Gestión de temas visuales de la aplicación.
Los archivos .qss viven en frontend/temas/

Uso:
    from frontend.temas import Temas

    tema = Temas.cargar_preferencia()
    Temas.aplicar(app, tema)
"""

from pathlib import Path
from PySide6.QtWidgets import QApplication

from backend.db import Config


class Temas:
    OPCIONES = {
        "dark":   "dark.qss",
        "light":  "light.qss",
        "hybrid": "hybrid.qss",
        "rosa":   "rosa.qss",
        "cafe":   "cafe.qss",
        "verde":  "verde.qss",
    }
    NOMBRES = {
        "dark":   "Oscuro",
        "light":  "Claro",
        "hybrid": "Híbrido",
        "rosa":   "Rosa",
        "cafe":   "Café",
        "verde":  "Verde",
    }

    @staticmethod
    def aplicar(app: QApplication, clave: str):
        ruta = Path(__file__).parent / "temas" / Temas.OPCIONES.get(clave, "dark.qss")
        if ruta.exists():
            app.setStyleSheet(ruta.read_text(encoding="utf-8"))

    @staticmethod
    def guardar_preferencia(clave: str):
        Config.set("tema", clave)

    @staticmethod
    def cargar_preferencia() -> str:
        return Config.get("tema", "dark")

    @staticmethod
    def nombre(clave: str) -> str:
        return Temas.NOMBRES.get(clave, clave)
