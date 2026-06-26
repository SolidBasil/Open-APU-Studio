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


# ── Gestor de temas visuales ──────────────────────────────────────

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

    # ── Aplicar un tema por clave ─────────────────────────────────

    @staticmethod
    def aplicar(app: QApplication, clave: str):
        """Carga y aplica el archivo .qss del tema. No hace nada si el archivo no existe."""
        ruta = Path(__file__).parent / "temas" / Temas.OPCIONES.get(clave, "dark.qss")
        if ruta.exists():
            app.setStyleSheet(ruta.read_text(encoding="utf-8"))

    # ── Persistir preferencia ─────────────────────────────────────

    @staticmethod
    def guardar_preferencia(clave: str):
        """Persiste la clave del tema seleccionado en config.json."""
        Config.set("tema", clave)

    # ── Recuperar preferencia guardada ────────────────────────────

    @staticmethod
    def cargar_preferencia() -> str:
        """Devuelve la clave del tema guardado en config.json; 'dark' por defecto."""
        return Config.get("tema", "dark")

    # ── Obtener nombre legible de un tema ─────────────────────────

    @staticmethod
    def nombre(clave: str) -> str:
        """Devuelve el nombre legible (para UI) de una clave de tema."""
        return Temas.NOMBRES.get(clave, clave)
