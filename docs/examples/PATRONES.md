# Ejemplos completos de patrones de interfaz

> Este archivo contiene implementaciones completas de los patrones descritos
> en `docs/GUIA_INTERFAZ.md`. Los ejemplos aquí son ilustrativos, no
> necesariamente iguales al código en producción.
>
> Actualizado: 2026-07-07 22:43 (hora local)

---

## 7.1 Tabla nueva

Ejemplo mínimo de un widget tabular que hereda de `TreeTableWidget`.

```python
from frontend.ventana.widgets.base import TreeTableWidget, ColumnaDef
from PySide6.QtCore import Qt

COLUMNAS = ["Clave", "Descripción", "Valor"]
EDITABLE = frozenset({1, 2})

COLUMNAS_CATALOGO = [
    ColumnaDef(0, "Clave",       "Identificación"),
    ColumnaDef(1, "Descripción", "Identificación"),
    ColumnaDef(2, "Valor",       "Cálculo"),
]

class MiTabla(TreeTableWidget):
    _HEADER_KEY = "mi_tabla_header"
    _CATALOGO_KEY = "mi_tabla_favoritas"
    COLUMNAS_CATALOGO = COLUMNAS_CATALOGO

    def __init__(self, parent=None):
        super().__init__(COLUMNAS, EDITABLE, flat=True, parent=parent)
        from PySide6.QtWidgets import QHeaderView
        self.set_column_modes({
            c: (QHeaderView.ResizeMode.Interactive, w)
            for c, w in enumerate([90, 250, 100])
        })
        for col in COLUMNAS_CATALOGO:
            self.setColumnHidden(col.idx, not col.visible_default)
        self._search_cols = {1}
        self._restore_header_state()
        self._api = None
        self._event_bus = None

    def poblar(self, items):
        self.clear()
        for item in items:
            row = self.add_row([
                item.get("clave", ""),
                item.get("desc", ""),
                item.get("valor", 0),
            ])
            row.setData(0, Qt.ItemDataRole.UserRole, item.get("id"))

    def conectar_eventos(self, event_bus, api):
        self._api = api
        self._event_bus = event_bus

    def desconectar_eventos(self):
        self._event_bus = None
```

### Claves del patrón

1. `COLUMNAS`, `EDITABLE` y `COLUMNAS_CATALOGO` son variables de módulo
   (no de instancia) para que sean visibles en la definición de la clase.
2. `_HEADER_KEY` debe ser único por tipo de tabla. Sin key, el usuario
   pierde su configuración de columnas al cerrar la app.
3. `_restore_header_state()` se llama al final de `__init__`.
4. `poblar()` siempre empieza con `self.clear()` y usa `add_row()`.
5. Los ids se guardan con `setData(…, UserRole, id)` para recuperarlos
   después sin parsear texto visible.

---

## 7.2 Diálogo

Estructura completa de un diálogo modal (ej: `DialogoAjustes`).

```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QWidget
)
from PySide6.QtCore import Qt

class DialogoBase(QDialog):
    """Clase base para diálogos — una vez que exista."""
    # ... pendiente (ver deuda técnica en GUIA_INTERFAZ.md sección 10.1)

class DialogoEjemplo(QDialog):
    """Ejemplo de diálogo con estructura estándar manual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ejemplo")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # Header
        header = QLabel("Título del diálogo")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(48)
        ly.addWidget(header)

        # Separador
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFixedHeight(1)
        ly.addWidget(sep1)

        # Contenido
        body = QWidget()
        body_ly = QVBoxLayout(body)
        body_ly.setContentsMargins(16, 16, 16, 16)
        # ... agregar campos aquí
        ly.addWidget(body, 1)

        # Separador
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFixedHeight(1)
        ly.addWidget(sep2)

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(16, 8, 16, 8)
        footer.addStretch()
        btn_ok = QPushButton("Aceptar")
        btn_cancel = QPushButton("Cancelar")
        footer.addWidget(btn_ok)
        footer.addWidget(btn_cancel)
        ly.addLayout(footer)

        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
```

---

## 7.3 Builder en PanelesMixin

Ejemplo completo de builder con importaciones diferidas.

```python
# Dentro de PanelesMixin (frontend/ventana/paneles.py):

def _build_mi_modulo(self):
    from frontend.ventana.widgets.mi_widget import MiWidget
    if not self._db:
        return self._build_placeholder("📦 Mi módulo")
    w = MiWidget()
    if self._api:
        datos = self._api.mis_datos()
        w.poblar(datos)
    w.conectar_eventos(self._event_bus, self._api)
    return w
```

Registro en el router de sidebar:

```python
# Dentro de _open_sidebar_tab (PanelesMixin):
if title == "📦 Mi módulo":
    content = self._build_mi_modulo()
```

### Notas

- La importación del widget es diferida (dentro del método, no al inicio
  del archivo) para evitar dependencias circulares.
- El builder siempre verifica `self._db` primero. Sin proyecto abierto,
  devuelve placeholder.
- `conectar_eventos()` se llama después de `poblar()` para evitar que un
  evento llegue antes de que haya datos.

---

## 7.4 Suscripción al EventBus

Ejemplo completo con suscripción a múltiples eventos y limpieza explícita.

```python
from backend.database.event_bus import (
    InsumoActualizado,
    ProyectoRecalculado,
    NodoActualizado,
)

class MiWidget(TreeTableWidget):
    # ... __init__ y poblar ...

    def conectar_eventos(self, event_bus, api):
        self._api = api
        self._event_bus = event_bus
        event_bus.suscribir(InsumoActualizado, self._on_insumo_actualizado)
        event_bus.suscribir(ProyectoRecalculado, self._on_proyecto_recalculado)
        event_bus.suscribir(NodoActualizado, self._on_nodo_actualizado)

    def desconectar_eventos(self):
        bus = getattr(self, '_event_bus', None)
        if bus is None:
            return
        bus.desuscribir(InsumoActualizado, self._on_insumo_actualizado)
        bus.desuscribir(ProyectoRecalculado, self._on_proyecto_recalculado)
        bus.desuscribir(NodoActualizado, self._on_nodo_actualizado)
        self._event_bus = None

    def _on_insumo_actualizado(self, evento):
        if not self.isVisible():
            return
        # refrescar solo la fila afectada, no todo el widget
        idx = self._find_row_by_id(evento.datos.get("id"))
        if idx is not None:
            self._update_row(idx, evento.datos)

    def _on_proyecto_recalculado(self, evento):
        # recargar todo porque el cambio pudo afectar muchas filas
        if self._api:
            self.poblar(self._api.mis_datos())

    def _on_nodo_actualizado(self, evento):
        pass  # solo relevantes cuando el widget muestra nodos
```

### Reglas

1. `desconectar_eventos()` es **obligatorio**. Sin él, el widget retenido
   por la closure del callback crashea al recibir el próximo evento.
2. Usar `getattr(self, '_event_bus', None)` en lugar de acceder directamente
   a `self._event_bus` para que el método no falle si se llama antes de
   `conectar_eventos()`.
3. Los handlers verifican `self.isVisible()` como optimización, pero
   igual deben ser seguros de llamar aunque el widget esté oculto.
4. La actualización in-place (refrescar solo la fila afectada) es preferible
   a `poblar()` completo, pero no siempre es posible.

---

## 7.5 Actualización reactiva

Contraste entre el flujo correcto y el incorrecto.

### Incorrecto

```python
# En un mixin:
def _on_editar_celda(self, row, col, valor):
    self._api.actualizar_insumo(id, {"precio": valor})
    self._tabla_insumos.poblar(self._api.obtener_insumos())  # ❌ acoplamiento directo
```

### Correcto

```python
def _on_editar_celda(self, row, col, valor):
    self._api.actualizar_insumo(id, {"precio": valor})
    # El EventBus se encarga de notificar a todos los widgets suscritos.
    # El mixin no toca ningún widget.
    # Si necesita diferir el refresco por señal Qt anidada:
    # from PySide6.QtCore import QTimer
    # QTimer.singleShot(0, lambda: ...)
```

---

Actualizado: 2026-07-07 22:43 (hora local)
