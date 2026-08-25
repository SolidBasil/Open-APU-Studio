# actualizado: 2026-08-24 12:00 (hora local)

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout

from frontend.ventana.iconos import icono


class PresupuestoPopup(QDialog):
    """Popup con el árbol del presupuesto, misma lógica que la pestaña principal.

    Al cerrarse se desconecta del EventBus para evitar fugas de callbacks.
    Las señales itemChanged / itemDoubleClicked / rastrear_insumo / desglozar_nodo
    se conectan a los mismos handlers de VentanaPrincipal que usa la pestaña fija.
    """

    def __init__(self, api, event_bus, parent=None):
        super().__init__(parent)
        self._api = api
        self._tree = None

        self.setWindowTitle("Presupuesto")
        self.setWindowIcon(icono("clipboard", 24))
        self.setMinimumSize(800, 500)
        self.resize(1000, 650)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tree = self._build_tree(api, event_bus)
        self._tree = tree
        if tree:
            layout.addWidget(tree)

    def _build_tree(self, api, event_bus):
        from frontend.ventana.widgets.arbol import TablaArbol
        tree = TablaArbol()
        try:
            nodos = api.presupuesto_arbol()
            tree.poblar(nodos)
        except Exception as e:
            print(f"Error cargando presupuesto en popup: {e}")
            return None

        parent = self.parent()
        tree.conectar_handlers(parent)
        if event_bus and api:
            tree.conectar_eventos(event_bus, api)

        return tree

    def closeEvent(self, event):
        if self._tree:
            try:
                self._tree.desconectar_eventos()
            except RuntimeError:
                pass
        super().closeEvent(event)
