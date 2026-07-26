"""
ui_utils.py
===========
Utilidades pequeñas de UI compartidas entre mixins.

cursor_espera(): la app no usa hilos para operaciones lentas (compilar
LaTeX, importar un proyecto legado) — corren directo sobre el hilo
principal, así que mientras duran, Qt no repinta y la ventana se ve
congelada sin ningún aviso. Este helper al menos cambia el cursor a
"reloj de arena" para que quede claro que la app sigue viva y está
trabajando.
"""

from contextlib import contextmanager

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


@contextmanager
def cursor_espera():
    """Cursor de reloj de arena mientras dura el bloque `with`.

    Restaura el cursor normal aunque la operación lance una excepción.
    Para que el usuario vea el cambio ANTES de que arranque la operación
    bloqueante (Qt no repinta hasta que el hilo vuelve al event loop),
    llama a QApplication.processEvents() justo después de mostrar
    cualquier mensaje de status bar y antes de entrar al bloque:

        self._sb.showMessage("Generando PDF…")
        QApplication.processEvents()
        with cursor_espera():
            pdf = compilar_pdf(tex_path)
    """
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()
