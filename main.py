import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from frontend.theme_manager import ThemeManager
from frontend.ui.ventana_principal import VentanaPrincipal


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Open APU Studio")
    app.setOrganizationName("OpenAPU")
    app.setFont(QFont("Segoe UI", 10))

    theme = ThemeManager.load_preference()
    ThemeManager.apply(app, theme)

    win = VentanaPrincipal()
    win.show()
    app.processEvents()
    app.setOverrideCursor(Qt.CursorShape.ArrowCursor)
    app.restoreOverrideCursor()
    win.setCursor(Qt.CursorShape.ArrowCursor)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
