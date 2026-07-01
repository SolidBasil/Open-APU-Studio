"""
main.py
=======
Punto de entrada de Open APU Studio.
"""

import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

# Windows: required for the taskbar icon to show our .ico instead of python.exe's icon
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("openapu.studio.1")

from backend.database.db import Config, Rutas
from frontend.temas import Temas
from frontend.ventana import VentanaPrincipal


def main():
    """Punto de entrada: inicializa QApplication, aplica tema, crea y muestra la ventana principal."""
    app = QApplication(sys.argv)
    app.setApplicationName("Open APU Studio")
    app.setOrganizationName("OpenAPU")
    app.setWindowIcon(QIcon("assets/favicon.ico"))
    app.setFont(QFont("Segoe UI", 10))

    # Aplicar tema guardado (default: oscuro + azul)
    modo, acento = Temas.cargar_preferencia()
    Temas.aplicar(app, modo, acento)

    win = VentanaPrincipal()
    win.show()
    app.processEvents()
    app.setOverrideCursor(Qt.CursorShape.ArrowCursor)
    app.restoreOverrideCursor()
    win.setCursor(Qt.CursorShape.ArrowCursor)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
