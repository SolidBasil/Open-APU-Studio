# Guía visual — Open APU Studio

Actualizado: 2026-07-08 00:10 (hora local)

Guía rápida de estilo visual para crear ventanas y widgets que se vean
como parte del mismo programa. No cubre arquitectura (ver `GUIA_INTERFAZ.md`)
ni convenciones de código (`GUIA_CODIGO.md`).

---

## 1. Anatomía de la ventana

```
+-----------------------------------------------------------------+
|  [PROYECTO] [INICIO] [INS] [SOBRECOSTOS] [HERRAMIENTAS]    [☰] |  ← tabBar
|-----------------------------------------------------------------|
| [+ Nuevo] [Abrir] [Guardar]  |  [Recalcular] [Auditoría]  [▼] |  ← tbCustom (toolbar)
|-----------------------------------------------------------------|
|  🔍 Buscar...                                              [▼] |  ← searchBar
|-----------------------------------------------------------------|
|  📁 Propuesta      | +---------------------------------------+ |
|    📋 Presupuesto  | | Tab content/widget                    | |  ← QSplitter
|    🔍 Buscar       | |                                       | |     sidebar | content
|    📦 Explosión    | |                                       | |
|  📁 Sobrecostos    | |                                       | |
|    💰 Cálculo      | +---------------------------------------+ |
|-----------------------------------------------------------------|
|  🌸 rosa (oscuro)  │  v0.3                                    |  ← statusBar
+-----------------------------------------------------------------+
```

La ventana es siempre un `QMainWindow` con este stack vertical fijo:
`tabBar → toolbar → searchBar → splitter[sidebar | tabs] → statusBar`.

---

## 2. Paleta de colores (modo oscuro — default)

### 2.1 Fondos

| Uso | Color | Muestra |
|-----|-------|---------|
| Fondo ventana | `#12161D` | ![](https://placehold.co/12x12/12161D/12161D.png) |
| Paneles / cabeceras | `#1B2330` | ![](https://placehold.co/12x12/1B2330/1B2330.png) |
| Toolbar | `#1F2A38` | ![](https://placehold.co/12x12/1F2A38/1F2A38.png) |
| Inputs, tablas | `#12161D` | ![](https://placehold.co/12x12/12161D/12161D.png) |
| Filas alternas | `#19212E` | ![](https://placehold.co/12x12/19212E/19212E.png) |
| Cabeceras tabla | `#203244` | ![](https://placehold.co/12x12/203244/203244.png) |

### 2.2 Texto

| Uso | Color | Muestra |
|-----|-------|---------|
| Principal | `#E8EDF2` | ![](https://placehold.co/12x12/E8EDF2/E8EDF2.png) |
| Secundario | `#B7C0C8` | ![](https://placehold.co/12x12/B7C0C8/B7C0C8.png) |
| Deshabilitado | `#6B7884` | ![](https://placehold.co/12x12/6B7884/6B7884.png) |

### 2.3 Acentos (cambian con el tema)

| Acento | Color | Muestra |
|--------|-------|---------|
| Azul (default) | `#7FAFD6` | ![](https://placehold.co/12x12/7FAFD6/7FAFD6.png) |
| Rosa | `#D48FB7` | ![](https://placehold.co/12x12/D48FB7/D48FB7.png) |
| Café | `#C4A882` | ![](https://placehold.co/12x12/C4A882/C4A882.png) |
| Verde | `#8DB58B` | ![](https://placehold.co/12x12/8DB58B/8DB58B.png) |

El acento se aplica a: selección de tabla, hover de botones, borde de input
en focus, pestaña activa, scrollbar hover, checkbox/radio checked.

### 2.4 Semánticos

| Uso | Color | Muestra |
|-----|-------|---------|
| Success | `#5B8A72` | ![](https://placehold.co/12x12/5B8A72/5B8A72.png) |
| Warning | `#D5B39B` | ![](https://placehold.co/12x12/D5B39B/D5B39B.png) |
| Error | `#A06A6A` | ![](https://placehold.co/12x12/A06A6A/A06A6A.png) |

### 2.5 Partidas (colores de WBS en árbol)

| Tipo | Color | Muestra |
|------|-------|---------|
| Capítulo | `#8B6FB5` | ![](https://placehold.co/12x12/8B6FB5/8B6FB5.png) |
| Subpartida | `#5E9CA0` | ![](https://placehold.co/12x12/5E9CA0/5E9CA0.png) |

---

## 3. Tipografía

- **Familia:** `"Inter", "Segoe UI", "Segoe UI Variable Text", sans-serif`
  (definido globalmente en QSS, no redeclarar)
- **Tablas:** `13px` (`QTreeView`, `QTableView`)
- **Toolbar buttons:** `10px`
- **Tab bar:** `12px` bold
- **Search input:** `13px`
- **Diálogos (títulos):** `15px` bold (`#dlgHeader`)
- **Diálogos (detalle):** `11px` (`#dlgDetail`)
- **Status bar:** `12px`
- **Código grande:** Nunca. No hay monospace en la UI.

No usar `setFont()` en widgets individuales — el QSS global lo define.
Excepción: `_icon()` usa `"Segoe UI Symbol"` para emoji.

---

## 4. Sistema de espaciado

Escala: **4-8-12-16-24-32 px**. No usar valores fuera de esta escala.

| Contexto | Padding/Spacing |
|----------|----------------|
| Contenido de diálogo | `margin: 12px`, `spacing: 8px` |
| Input fields | `padding: 4px 8px` |
| Botones | `padding: 4px 16px` o `6px 16px` |
| Tabla celdas | `padding: 4px 2px`, `min-height: 28px` |
| Sidebar items | `padding: 8px 12px` |
| Toolbar buttons | `padding: 4px 6px` |
| Separadores toolbar | `margin: 4px 6px` |

Regla: `setContentsMargins(0,0,0,0)` + `setSpacing(0)` en layouts de alto
nivel (toolbar, splitter, tab content). El espaciado interno lo da cada
widget vía QSS, no el layout padre.

---

## 5. Componentes

### 5.1 Botones

| Tipo | ObjectName | Estilo |
|------|-----------|--------|
| Primario | `btnPrimario` | Fondo acento, texto blanco, bold implícito |
| Secundario | — | Borde `1px solid #C8C0B4` (claro) / `#2A4158` (oscuro) |
| Cancelar | `dlgCancel` | Fondo gris, borde none |
| Toolbar | `QToolButton` | Transparente, 48x40 min, ícono + texto abajo |

Crear botón primario con:
```python
btn = QPushButton("Texto")
btn.setObjectName("btnPrimario")
```

### 5.2 Tablas (TreeTableWidget)

Toda tabla hereda de `TreeTableWidget` (base.py). No crear `QTreeWidget` o
`QTableView` directamente.

```python
from frontend.ventana.widgets.base import TreeTableWidget

class MiTabla(TreeTableWidget):
    COLUMNAS = ["Col A", "Col B", "Col C"]
    # ...
```

Patrón: columnas en mayúscula inicial, `EDITABLE = frozenset({...})` con
índices de columnas editables, `COLUMNAS_CATALOGO` si se permite
personalización.

### 5.3 Diálogos

Usar `QDialog` con este layout base:

```python
class MiDialogo(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Título")
        self.setMinimumSize(520, 400)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
```

Diálogos con cabecera:
```python
header = QLabel("Título")
header.setObjectName("dlgHeader")
header.setFixedHeight(48)
header.setAlignment(Qt.AlignCenter)
```

Diálogos con tarjeta:
```python
card = QWidget()
card.setObjectName("dlgCard")
```

### 5.4 Sidebar

Estructura fija: `QTreeWidget` con `setHeaderLabel("Explorador")`,
`setIndentation(16)`, `setAnimated(True)`,
`setSelectionMode(SingleSelection)`.

Los items se agregan con emoji + texto, agrupados por categoría:
```python
root = QTreeWidgetItem(["📁 Propuesta"])
hijo = QTreeWidgetItem(["📋 Presupuesto programable"])
```

### 5.5 Etiquetas de detalle

| ObjectName | Uso |
|-----------|-----|
| `dlgInfo` | Texto informativo en diálogos (fondo semitransparente, `#dlgInfo`) |
| `dlgDetail` | Texto pequeño secundario (`11px`, gris) |
| `dlgCardTitle` | Título dentro de tarjeta (`13px` bold) |

---

## 6. Sistema de iconos

Todos los iconos se generan con la función `_icon()` que pinta un carácter
emoji/unicode sobre un pixmap transparente con `Segoe UI Symbol`.

```python
from frontend.ventana.toolbar import _icon  # solo para toolbar
# para otros widgets:
def _emoji_icon(char, size=20):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setPen(QColor("#E8EDF2"))
    p.setFont(QFont("Segoe UI Symbol", size - 6))
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, char)
    p.end()
    return QIcon(pix)
```

Se espera que el target tenga la fuente `Segoe UI Symbol`. En Windows viene
incluida. En Linux puede faltar — ver deuda en `GUIA_INTERFAZ.md §10.4`.

Emojis comunes en la app:

| Concepto | Emoji |
|----------|-------|
| Proyecto / archivo | 📁 |
| Presupuesto | 📋 |
| APU | 🔧 |
| Insumo / material | 🧱 |
| Búsqueda | 🔍 |
| Guardar | 💾 |
| Eliminar | 🗑 |
| Editar | ✏ |
| Copiar | 📄 |
| Importar | 📥 |
| Exportar | 📤 |
| Configuración | ⚙ |
| Información | 🛈 |
| Usuario | 👥 |
| Calculadora | 🧮 |
| PDF | 📄 |
| Adjunto | 📎 |

---

## 7. Checklist para una ventana nueva

- [ ] Hereda de `TreeTableWidget` (tabla) o `QDialog` (diálogo)
- [ ] Usa colores de la paleta (no colores inline excepto acentos)
- [ ] Espaciado en escala 4-8-12-16-24-32
- [ ] Botón primario con `setObjectName("btnPrimario")`
- [ ] Diálogo modal con `setModal(True)` y `setMinimumSize(520, 400)`
- [ ] No redeclara `setFont()` ni `setStyleSheet()` en instancias individuales
- [ ] Iconos con `_emoji_icon()` usando `Segoe UI Symbol`
- [ ] Layouts de alto nivel con margins=0, spacing=0
- [ ] `setAlternatingRowColors(True)` en tablas
- [ ] Columnas definidas como `COLUMNAS = [ ... ]` con mayúscula inicial
- [ ] `ID_ROLE` guardado en `UserRole+1` para navegación por id

---

## 8. Qué NO hacer

- ❌ Colores inline (`setStyleSheet("color: red")`) — rompen el tema
- ❌ `setFont()` en widgets sueltos — el QSS global lo define
- ❌ `QTableWidget` — siempre `TreeTableWidget`
- ❌ Layouts con espacios duros (`setSpacing(5)`, `setContentsMargins(7, ...)`)
- ❌ Inputs sin `setObjectName` para focus styling
- ❌ Botones sin `btnPrimario` / `dlgCancel` cuando corresponde
- ❌ Texto hardcodeado de color que no contrasta con ambos modos

---

## 9. Referencia rápida

| Recurso | Archivo |
|---------|---------|
| Modo oscuro QSS | `frontend/temas/modo-oscuro.qss` |
| Modo claro QSS | `frontend/temas/modo-claro.qss` |
| Acentos | `frontend/temas/acento-{azul,rosa,cafe,verde}.qss` |
| Base tablas | `frontend/ventana/widgets/base.py` |
| Árbol ejemplo | `frontend/ventana/widgets/arbol.py` |
| Insumos ejemplo | `frontend/ventana/widgets/insumos.py` |
| Diálogos ejemplo | `frontend/ventana/widgets/dialogs.py` |
| Sidebar | `frontend/ventana/paneles.py` |
| Toolbar | `frontend/ventana/toolbar.py` |
