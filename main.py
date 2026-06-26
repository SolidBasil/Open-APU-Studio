"""
main.py
=======
Punto de entrada de Open APU Studio.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from backend.db import Config, Rutas
from frontend.temas import Temas
from frontend.ventana import VentanaPrincipal


def main():
    """Punto de entrada: inicializa QApplication, aplica tema, crea y muestra la ventana principal."""
    app = QApplication(sys.argv)
    app.setApplicationName("Open APU Studio")
    app.setOrganizationName("OpenAPU")
    app.setFont(QFont("Segoe UI", 10))

    # Aplicar tema guardado (default: dark)
    tema = Config.get("tema", "dark")
    Temas.aplicar(app, tema)

    win = VentanaPrincipal()
    win.show()
    app.processEvents()
    app.setOverrideCursor(Qt.CursorShape.ArrowCursor)
    app.restoreOverrideCursor()
    win.setCursor(Qt.CursorShape.ArrowCursor)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
