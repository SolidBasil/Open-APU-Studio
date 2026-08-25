"""
ayuda.py
========
Diálogo de ayuda: lista todos los atajos de teclado de la app, agrupados
por tema. Se abre con F1 o desde VISTA > Ayuda > Atajos de teclado.

La sección "Acciones de la cinta" se arma leyendo _ATAJOS directamente de
toolbar.py en vez de tener la lista copiada a mano aquí — así, si mañana
se agrega o cambia un atajo de cinta, este diálogo lo refleja solo, sin
que alguien tenga que acordarse de actualizar dos lugares (el mismo
problema de duplicación que ya se resolvió en otros puntos de la app).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea, QFrame,
)

from frontend.ventana.colores import TEXT, TEXT_SEC, MUTED, ACCENT, SEL_BG


# Grupos estables que no dependen de ningún dict del código (se arman a
# mano porque describen conceptos, no una lista de botones que cambie
# seguido). El grupo "Acciones de la cinta" se agrega aparte, generado
# desde _ATAJOS — ver _build_seccion_cinta().
_GRUPOS_FIJOS = [
    ("Navegar sin mouse (4 zonas)", [
        ("Tab", "Salta a la siguiente zona: cinta → herramientas → panel → área → cinta"),
        ("Shift+Tab", "Salta a la zona anterior"),
        ("Flechas", "Se mueve dentro de la zona activa (entre botones, "
                     "filas del árbol, filas de la tabla)"),
        ("Enter / Espacio", "Activa el botón o la pestaña de cinta con foco"),
    ]),
    ("General", [
        ("Ctrl+F  /  /", "Foco en el buscador del proyecto"),
        ("Ctrl+Shift+L", "Foco en el panel izquierdo (Explorador)"),
        ("Ctrl+P", "Paleta de comandos"),
        ("Ctrl+Tab", "Siguiente pestaña de contenido abierta"),
        ("Ctrl+Shift+Tab", "Pestaña de contenido anterior"),
        ("Ctrl+W", "Cerrar la pestaña de contenido activa"),
        ("Alt+1 … Alt+7", "Ir directo a una pestaña de la cinta "
                           "(PROYECTO, INICIO, INFORMES, VISTA, PRINCIPAL, "
                           "HERRAMIENTAS, GENERADORES)"),
        ("F1", "Esta ayuda"),
    ]),
    ("Edición en árboles y tablas", [
        ("Ctrl+Z", "Deshacer"),
        ("Ctrl+Y  /  Ctrl+Shift+Z", "Rehacer"),
        ("Insert  /  Ctrl+Insert", "Agregar fila / agregar agrupador"),
        ("Delete", "Eliminar la selección"),
        ("F2", "Renombrar / editar la celda"),
        ("F5", "Refrescar"),
        ("Alt+Flechas", "Mover el nodo seleccionado (subir/bajar/izquierda/derecha)"),
        ("Ctrl+C  /  Ctrl+X  /  Ctrl+V", "Copiar / cortar / pegar"),
        ("Ctrl+A", "Seleccionar todo"),
    ]),
]


def _fila(tecla: str, descripcion: str) -> QWidget:
    """Una fila: badge de tecla a la izquierda + descripción a la derecha."""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 3, 0, 3)
    row.setSpacing(12)

    badge = QLabel(tecla)
    badge.setMinimumWidth(150)
    badge.setStyleSheet(
        f"color: {ACCENT}; background-color: {SEL_BG}; "
        f"border-radius: 4px; padding: 3px 8px; font-weight: bold; "
        f"font-family: Consolas, monospace; font-size: 11px;"
    )
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

    desc = QLabel(descripcion)
    desc.setWordWrap(True)
    desc.setStyleSheet(f"color: {TEXT};")
    row.addWidget(desc, 1)

    return w


def _seccion(titulo: str, filas: list[tuple[str, str]]) -> QWidget:
    """Un bloque: título de sección + sus filas tecla/descripción."""
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 14)
    lay.setSpacing(2)

    lbl_titulo = QLabel(titulo)
    lbl_titulo.setStyleSheet(
        f"color: {ACCENT}; font-weight: bold; font-size: 13px; "
        f"padding-bottom: 4px;"
    )
    lay.addWidget(lbl_titulo)

    linea = QFrame()
    linea.setFrameShape(QFrame.Shape.HLine)
    linea.setStyleSheet(f"background-color: {MUTED}; max-height: 1px;")
    lay.addWidget(linea)

    for tecla, desc in filas:
        lay.addWidget(_fila(tecla, desc))

    return w


def _build_seccion_cinta() -> QWidget:
    """Sección "Acciones de la cinta", generada desde _ATAJOS (toolbar.py)
    en vez de copiada a mano — se mantiene sola al día."""
    from frontend.ventana.mixins.toolbar import _ATAJOS
    filas = [(seq, f'Acción "{tip}" de la cinta') for tip, seq in _ATAJOS.items()]
    return _seccion("Acciones de la cinta (además de las de arriba)", filas)


class DialogoAyuda(QDialog):
    """Ventana de ayuda con todos los atajos de teclado, agrupados por tema."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atajos de teclado")
        self.setMinimumSize(560, 620)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        titulo = QLabel("Atajos de teclado")
        titulo.setStyleSheet(
            f"color: {TEXT}; font-size: 17px; font-weight: bold; padding: 16px 20px 4px 20px;"
        )
        layout.addWidget(titulo)

        subtitulo = QLabel(
            "El programa está pensado para usarse solo con teclado. "
            "Tab y las flechas mueven el foco; el resto son atajos directos."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"color: {TEXT_SEC}; padding: 0 20px 14px 20px;")
        layout.addWidget(subtitulo)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        contenido = QWidget()
        cl = QVBoxLayout(contenido)
        cl.setContentsMargins(20, 0, 20, 8)
        cl.setSpacing(6)

        for titulo_grupo, filas in _GRUPOS_FIJOS:
            cl.addWidget(_seccion(titulo_grupo, filas))
        cl.addWidget(_build_seccion_cinta())
        cl.addStretch()

        scroll.setWidget(contenido)
        layout.addWidget(scroll, 1)

        footer = QFrame()
        footer.setObjectName("dlgAjustesFooter")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 10, 16, 10)
        fl.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setDefault(True)
        btn_cerrar.clicked.connect(self.accept)
        fl.addWidget(btn_cerrar)
        layout.addWidget(footer)
