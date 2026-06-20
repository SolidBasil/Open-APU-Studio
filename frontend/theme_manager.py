import os
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


class ThemeManager:
    THEMES = {
        "dark": "themes/dark.qss",
        "light": "themes/light.qss",
        "hybrid": "themes/hybrid.qss",
    }

    @staticmethod
    def apply(app: QApplication, theme_key: str):
        path = Path(__file__).parent / ThemeManager.THEMES.get(theme_key, "themes/dark.qss")
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())

    @staticmethod
    def save_preference(theme_key: str):
        settings = QSettings("OpenAPU", "Studio")
        settings.setValue("theme", theme_key)

    @staticmethod
    def load_preference() -> str:
        settings = QSettings("OpenAPU", "Studio")
        return settings.value("theme", defaultValue="dark")
