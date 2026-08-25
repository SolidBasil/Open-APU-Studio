"""
temas.py
========
Gestión de temas visuales: modo (oscuro/claro) + acento (azul/rosa/café/verde).
"""

from pathlib import Path
from PySide6.QtWidgets import QApplication
from backend.database.db import Config


class Temas:
    MODOS = {
        "oscuro": "modo-oscuro.qss",
        "claro":  "modo-claro.qss",
    }
    ACENTOS = {
        "azul":  "acento-azul.qss",
        "rosa":  "acento-rosa.qss",
        "cafe":  "acento-cafe.qss",
        "verde": "acento-verde.qss",
    }
    NOMBRES_ACENTO = {
        "azul":  "Azul",
        "rosa":  "Rosa",
        "cafe":  "Café",
        "verde": "Verde",
    }

    _MODO_DEFECTO    = "oscuro"
    _ACENTO_DEFECTO  = "azul"
    _LEGACY_MAP = {
        "dark":   ("oscuro", "azul"),
        "light":  ("claro",  "azul"),
        "hybrid": ("oscuro", "azul"),
        "rosa":   ("oscuro", "rosa"),
        "cafe":   ("oscuro", "cafe"),
        "verde":  ("oscuro", "verde"),
        "nativo": ("oscuro", "azul"),
    }

    @staticmethod
    def aplicar(app: QApplication, modo: str | None = None, acento: str | None = None):
        modo   = modo   or Temas._MODO_DEFECTO
        acento = acento or Temas._ACENTO_DEFECTO
        modo_file   = Path(__file__).parent / Temas.MODOS.get(modo,   Temas.MODOS[Temas._MODO_DEFECTO])
        acento_file = Path(__file__).parent / Temas.ACENTOS.get(acento, Temas.ACENTOS[Temas._ACENTO_DEFECTO])
        qss = ""
        if modo_file.exists():
            qss += modo_file.read_text(encoding="utf-8")
        if acento_file.exists():
            qss += "\n" + acento_file.read_text(encoding="utf-8")
        app.setStyleSheet(qss)

    @staticmethod
    def guardar_preferencia(modo: str | None = None, acento: str | None = None):
        if modo:
            Config.set("tema_modo", modo)
        if acento:
            Config.set("tema_acento", acento)

    @staticmethod
    def cargar_preferencia():
        modo   = Config.get("tema_modo")
        acento = Config.get("tema_acento")
        if modo and acento:
            return modo, acento
        legacy = Config.get("tema")
        if legacy in Temas._LEGACY_MAP:
            m, a = Temas._LEGACY_MAP[legacy]
            Config.set("tema_modo", m)
            Config.set("tema_acento", a)
            Config.set("tema", None)
            return m, a
        return Temas._MODO_DEFECTO, Temas._ACENTO_DEFECTO

    @staticmethod
    def nombre_acento(clave: str) -> str:
        return Temas.NOMBRES_ACENTO.get(clave, clave)
