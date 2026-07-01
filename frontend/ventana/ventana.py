"""
ventana.py
==========
Ventana principal de Open APU Studio.

Ensambla los mixins de toolbar, paneles y handlers en VentanaPrincipal.
Contiene únicamente el estado de instancia, los métodos de ensamblaje
del layout y la inicialización. Toda la lógica está en los mixins.

Uso:
    from frontend.ventana import VentanaPrincipal
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QStatusBar, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
)

from frontend.temas    import Temas
from frontend.ventana.toolbar  import ToolbarMixin
from frontend.ventana.paneles  import PanelesMixin
from frontend.ventana.handlers import HandlersMixin


# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================

class VentanaPrincipal(ToolbarMixin, PanelesMixin, HandlersMixin, QMainWindow):
    """Ventana principal de Open APU Studio.

    La lógica está distribuida en tres mixins:
      - ToolbarMixin  (frontend/toolbar.py)  — toolbar, temas, barra de búsqueda
      - PanelesMixin  (frontend/paneles.py)  — builders de pestañas de contenido
      - HandlersMixin (frontend/handlers.py) — handlers de eventos y navegación

    Este archivo contiene solo el estado de instancia y el ensamblaje del layout.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Open APU Studio  v0.3")
        self.resize(1400, 800)

        # ── Estado de instancia ───────────────────────────────────────────
        self._tema_modo, self._tema_acento = Temas.cargar_preferencia()
        self._tab_activa = "PROYECTO"                    # pestaña toolbar activa
        self._tab_temp   = None                          # pestaña temporal (click simple)
        self._db         = None                          # Database abierta o None
        self._api        = None                          # Api — se crea al abrir proyecto
        self._arbol_presupuesto = None                   # ref al TablaArbol activo

        self._build_central()
        self._build_statusbar()

    def _build_central(self):
        """Ensambla el layout vertical: tab bar + toolbar + splitter (sidebar | contenido)."""
        wrapper = QWidget()
        layout  = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_tab_bar(layout)
        self._build_toolbar(layout)
        self._switch_tab("PROYECTO")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())

        right        = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        self._build_search_bar(right_layout)
        right_layout.addWidget(self._build_content(), 1)
        splitter.addWidget(right)

        splitter.setCollapsible(0, False)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 8)
        splitter.setSizes([220, 1040])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(wrapper)

    def _build_statusbar(self):
        self._sb = QStatusBar(self)
        self._update_statusbar()
        self.setStatusBar(self._sb)

    def _update_statusbar(self):
        acento = getattr(self, '_tema_acento', 'azul')
        modo   = getattr(self, '_tema_modo', 'oscuro')
        nombre = Temas.nombre_acento(acento)
        self._sb.showMessage(f"{nombre} ({modo})  │  v0.3")
