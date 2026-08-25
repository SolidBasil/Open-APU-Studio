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
    QMainWindow, QStatusBar, QWidget, QVBoxLayout, QSplitter, QStackedWidget,
)

from frontend.temas    import Temas
from frontend.ventana.colores import TEXT, TEXT_INVERSO
from frontend.ventana.mixins.toolbar           import ToolbarMixin
from frontend.ventana.mixins.paneles           import PanelesMixin
from frontend.ventana.mixins.navegacion        import HandlersMixin
from frontend.ventana.mixins.gestion_proyectos import GestionProyectosMixin
from frontend.ventana.mixins.informes          import InformesMixin
from frontend.ventana.mixins.diag_dialogs      import DiagDialogsMixin
from frontend.ventana.mixins.apu               import ApuMixin
from frontend.ventana.mixins.rastreo           import RastreoMixin
from frontend.ventana.mixins.explosion         import ExplosionMixin
from frontend.ventana.mixins.generador         import GeneradorMixin


# =============================================================================
# VENTANA PRINCIPAL
# =============================================================================

class VentanaPrincipal(
    ToolbarMixin, PanelesMixin, HandlersMixin,
    GestionProyectosMixin, InformesMixin, DiagDialogsMixin,
    ApuMixin, RastreoMixin, ExplosionMixin, GeneradorMixin,
    QMainWindow,
):
    """Ventana principal de Open APU Studio.

    La lógica está distribuida en mixins:
      - ToolbarMixin          — toolbar, temas, barra de búsqueda
      - PanelesMixin          — sidebar, presupuesto, insumos, buscador
      - HandlersMixin         — navegación, búsqueda, vista, adjuntos
      - GestionProyectosMixin — lifecycle de proyectos
      - InformesMixin         — generación de PDF
      - DiagDialogsMixin      — diagnóstico y utilidades
      - ApuMixin              — pestañas APU y edición
      - RastreoMixin          — rastreo de insumos
      - ExplosionMixin        — explosión de insumos/matrices y sobrecostos
    """

    _TITULO_BASE = "Open APU Studio  v0.3"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self._TITULO_BASE)
        self.resize(1400, 800)

        # ── Estado de instancia ───────────────────────────────────────────
        self._tema_modo, self._tema_acento = Temas.cargar_preferencia()

        # Inicializar conjunto de iconos desde config
        from frontend.ventana.iconos import set_iconos, set_default_tint
        from backend.database.db import Config
        set_iconos(Config.get("iconos", "lucide"))
        set_default_tint(TEXT if self._tema_modo == 'oscuro' else TEXT_INVERSO)

        self._tab_activa = "PROYECTO"                    # pestaña toolbar activa
        self._tab_temp   = None                          # pestaña temporal (click simple)
        self._db         = None                          # Database abierta o None
        self._api        = None                          # Api — se crea al abrir proyecto
        self._data_service = None                        # DataService — se crea al abrir proyecto
        self._registry   = None                          # RepositoryRegistry — se crea al abrir proyecto
        self._event_bus  = None                           # EventBus — se crea al abrir proyecto
        self._arbol_presupuesto = None                   # ref al TablaArbol activo
        self._server_proc = None                          # subprocess del servidor embebido

        self._build_central()
        self._build_statusbar()
        # Teclado-first: Tab/Shift+Tab ciclan entre las 4 zonas (cinta,
        # herramientas, panel, área) sin importar dónde esté el foco —
        # el filtro vive a nivel aplicación (ver toolbar.py::_build_toolbar).

    def closeEvent(self, event):
        from frontend.ventana.widgets.base import TreeTableWidget
        for i in range(self._tabs.count()):
            w = self._tabs.widget(i)
            if w is None:
                continue
            if isinstance(w, TreeTableWidget):
                w._save_header_state()
            for hijo in w.findChildren(TreeTableWidget):
                hijo._save_header_state()
        self._stop_server()
        super().closeEvent(event)

    def _build_central(self):
        """Ensambla el layout vertical: tab bar + toolbar + área central.

        El área central es un QStackedWidget con 2 páginas:
          0 = espacio normal — sidebar | pestañas de contenido (Presupuesto,
              Insumos, APU, informes...) — lo de siempre.
          1 = espacio de Generadores — panel de renglones del generador
              activo | pestañas de generadores abiertos, completamente
              aparte de las pestañas normales. Se activa solo al entrar a
              la cinta GENERADORES (ver _switch_tab en toolbar.py) —
              "Volver al presupuesto" (o clicar cualquier otra pestaña de
              la cinta) regresa a la página 0.
        """
        wrapper = QWidget()
        layout  = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_tab_bar(layout)
        self._build_toolbar(layout)

        self._central_stack = QStackedWidget()

        # ── Página 0: espacio normal ──────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._left_stack = QStackedWidget()
        self._left_stack.addWidget(self._build_left_panel())  # index 0 = sidebar
        splitter.addWidget(self._left_stack)
        self._main_splitter = splitter

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
        self._central_stack.addWidget(splitter)  # índice 0

        # ── Página 1: espacio de Generadores ──────────────────────────
        self._central_stack.addWidget(self._build_espacio_generadores())  # índice 1

        layout.addWidget(self._central_stack, 1)

        self.setCentralWidget(wrapper)
        self._switch_tab("PRINCIPAL")  # ribbon por defecto = pestaña inicial (Presupuesto)

    def _build_statusbar(self):
        self._sb = QStatusBar(self)
        self._update_statusbar()
        self.setStatusBar(self._sb)

    def _update_statusbar(self):
        acento = getattr(self, '_tema_acento', 'azul')
        modo   = getattr(self, '_tema_modo', 'oscuro')
        nombre = Temas.nombre_acento(acento)
        self._sb.showMessage(f"{nombre} ({modo})  |  v0.3")
