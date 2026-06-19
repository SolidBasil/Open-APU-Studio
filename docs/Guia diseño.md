# Guía de Diseño Visual — Open APU Studio

Versión: 0.2
Estado: Adaptada para PySide6/QSS

---

## 1. Objetivo

Establecer un conjunto de reglas visuales y de interacción para **Open APU Studio**. Cada regla incluye su implementación concreta en PySide6 + QSS.

---

## 2. Filosofía de Diseño

**Principios:**
- Productividad, claridad, consistencia, densidad media, rapidez, organización lógica

**Evitar:**
- Animaciones decorativas, minimalismo extremo, espacios vacíos excesivos

**Referencias visuales:**

| Programa | Qué aporta como referencia |
|---|---|
| Excel | Densidad de tabla, formato numérico, pestañas de documentos, toolbar funcional |
| Word | Organización de menús, feedback de estado, tipografía compacta |
| AutoCAD | Panel lateral de propiedades, toolbar con grupos, navegación por capas |
| OPUS 2020 | Árbol de navegación jerárquico, jerarquía de niveles en tabla (capítulo/subpartida/concepto), flujo de presupuestación |
| Neodatas | Densidad de información, manejo de catálogos, estructura de APU |
| VS Code | Sistema de temas intercambiables, layout con sidebar colapsable |
| Fusion 360 | Panel secundario contextual, uso del espacio en apps técnicas |

---

## 3. Paleta de Colores

Se usa la paleta original definida en esta guía. Roles mapeados a QSS:

| Rol | Hex | Uso |
|---|---|---|
| Fondo principal | `#12161D` | `QWidget`, `QMainWindow` background |
| Superficie (panel) | `#1B2330` | `QMenuBar`, `QToolBar`, `QTabBar`, sidebar, statusbar |
| Superficie elevada | `#203244` | `QHeaderView`, `QMenu`, hover items, gridlines |
| Superficie activa | `#2A4158` | `QTreeView` selección, `QPushButton` pressed |
| Navy 700 (selección) | `#37628F` | `QTableView` selection-background-color |
| Navy 600 (focus) | `#5A82AB` | `QLineEdit:focus` border, `QPushButton:hover` border |
| Navy 500 (acento) | `#7FAFD6` | Tabs activos, focus, detail panel headers |
| Texto principal | `#E8EDF2` | `color` global |
| Texto secundario | `#B7C0C8` | `QTabBar` inactivo |
| Texto deshabilitado | `#6B7884` | `QStatusBar`, `QComboBox` arrow |
| Partidas (árbol) | `#8B6FB5` | Nivel 1 del presupuesto |
| Subpartidas | `#5E9CA0` | Nivel 2 del presupuesto |
| Success | `#5B8A72` | Validaciones, confirmaciones |
| Warning | `#D5B39B` | Advertencias |
| Error | `#A06A6A` | Errores, operaciones fallidas |
| Critical | `#7A4D4D` | Estados críticos |
| Info | `#5A82AB` | Mensajes informativos |

**Implementación:** `themes/dark.qss` — archivo QSS intercambiable en runtime sin reiniciar.

---

## 4. Sistema de Colores — Estados Semánticos

Colores reservados para estados del sistema. No usarlos para categorías, módulos o navegación.

| Estado | Hex | Widget QSS |
|---|---|---|
| Success | `#5B8A72` | `color: #5B8A72` en `QLabel` de estado |
| Error | `#A06A6A` | `color: #A06A6A` en validation feedback |
| Warning | `#D5B39B` | `color: #D5B39B` |
| Info | `#5A82AB` | `color: #5A82AB` |

**Restricción:** No usar verde para categorías, rojo para navegación, amarillo para botones normales, azul para éxito.

### Colores para gráficas (chart)

Usar paleta independiente de los semánticos:

| Color | Hex |
|---|---|
| Orange | `#C98A4A` |
| Purple | `#8B6FB5` |
| Cyan | `#5E9CA0` |
| Magenta | `#A56A8A` |
| Amber | `#B89A5A` |
| Teal | `#4F7E78` |

**Restricción:** No usar verde, rojo ni amarillo como colores principales de series de datos.

---

## 5. Tipografía

### Fuente principal

Preferida: **Inter**. Alternativas: `Segoe UI`, fuente del sistema.

En QSS:
```qss
* {
    font-family: "Inter", "Segoe UI", "Segoe UI Variable", sans-serif;
}
```
Si Inter no está instalada, Qt usa `font-family` del sistema. No es necesario embeberla.

### Fuente monoespaciada

Para: código, coordenadas, datos tabulares.
Preferidas: `Cascadia Code`, `Consolas`, `Fira Code`.

En QSS:
```qss
QPlainTextEdit, código técnico {
    font-family: "Cascadia Code", "Consolas", "Fira Code", monospace;
}
```

### Escala tipográfica

| Uso | Tamaño | QSS / Qt |
|---|---|---|
| Título principal | 24 px | `QWidget` header, no en QSS directo |
| Título de sección | 18 px | `font-size: 18px` |
| Subsección | 16 px | `font-size: 16px` |
| Texto normal | 14 px | Tamaño base del tema |
| Texto auxiliar | 12 px | `QStatusBar`, `QLabel` secundario |
| Texto técnico compacto | 11 px | Tablas densas |

En `dark.qss` ya está configurado `font-size: 13px` para tablas y `12px` para statusbar.

---

## 6. Espaciado — Escala Oficial

| Token | Valor | Uso típico en PySide6 |
|---|---|---|
| `--space-1` | 4 px | `setContentsMargins(4,...)`, padding compacto |
| `--space-2` | 8 px | `setSpacing(8)`, padding botones, gap tabs |
| `--space-3` | 12 px | Márgenes de layout estándar |
| `--space-4` | 16 px | `QMainWindow` margin, padding toolbar |
| `--space-5` | 24 px | Separación de secciones |
| `--space-6` | 32 px | Margen externo de diálogos |

**Regla:** No usar valores arbitrarios. 13 px, 19 px, 27 px prohibidos.

### Atajo en layouts

```python
layout = QVBoxLayout()
layout.setContentsMargins(12, 12, 12, 12)  # space-3
layout.setSpacing(8)                        # space-2
```

---

## 7. Bordes

### Radios permitidos

| Tipo | QSS |
|---|---|
| Compacto | `border-radius: 4px` |
| Normal | `border-radius: 6px` |

No se permiten otros radios.

### Filosofía QSS

```qss
/* Preferir diferencias de superficie antes que bordes */
QGroupBox {
    border: none;  /* sin borde, usar background distinto */
}
/* Para tablas: gridline-color en vez de border */
QTableView {
    gridline-color: #203244;
    border: none;
}
```

---

## 8. Sombras

No usar sombras decorativas. Excepciones permitidas (muy sutiles):
- Menús flotantes (nativas de Qt, no requiere QSS)
- Tooltips
- Modales (`QDialog` modal)

```qss
/* Qt renderiza sombras de menú nativas — no forzar */
QMenu {
    /* Qt ya aplica sombra de OS */
}
```

---

## 9. Layout Principal

```
┌──────────────────────────────────────────────┐
│ MenuBar + Toolbar                            │
├─────────┬──────────────────────┬─────────────┤
│         │                      │             │
│Sidebar  │   Contenido          │ Panel       │
│(Tree)   │   (Tabs/Tablas)      │ Secundario  │
│         │                      │             │
├─────────┴──────────────────────┴─────────────┤
│ StatusBar                                     │
└──────────────────────────────────────────────┘
```

### Implementación PySide6

```python
splitter = QSplitter(Qt.Horizontal)
splitter.addWidget(sidebar_tree)          # QTreeView
splitter.addWidget(tab_content)           # QTabWidget
splitter.addWidget(secondary_panel)       # QWidget (ocultable)
```

### Sidebar

- Visible por defecto, colapsable, redimensionable
- Tamaños recomendados: colapsado=48 px, normal=260 px, expandido=340 px
- Implementar con `QTreeView` + `QAbstractItemModel` (solo filas visibles)

### Panel secundario

- Ocultable, redimensionable, dependiente del contexto
- Para: propiedades, desglose APU, ayuda contextual, vista previa

---

### Referencia visual: OPUS 2018 — Menú de Presupuesto

> **Nota:** Esta sección describe la interfaz de OPUS 2018 como referencia de inspiración estructural. Los colores, tipografía y estilos visuales mencionados aquí corresponden a ese software y **no aplican a Open APU Studio**, que sigue su propia paleta y filosofía definidas en esta guía.

OPUS 2018 representa el estándar de software de presupuestación en México y es el contexto que los usuarios objetivo conocen. Analizarlo permite identificar qué patrones conservar, cuáles mejorar y cuáles evitar.

#### Estructura general de OPUS (referencia)

```
┌─────────────────────────────────────┐
│ Barra de título + selector de vista  │
├─────────────────────────────────────┤
│ Ribbon de herramientas (pestañas)    │
├───────────────┬─────────────────────┤
│ Explorador    │ Área principal       │
│ lateral       │ (tabla de datos)     │
│ (árbol)       │                      │
├───────────────┴─────────────────────┤
│ Barra inferior de estado             │
└─────────────────────────────────────┘
```

Este layout es estructuralmente equivalente al de Open APU Studio. La diferencia principal está en la capa visual y en la densidad de controles de la barra superior.

#### Patrones de OPUS a conservar en Open APU Studio

| Patrón | Implementación en Open APU Studio |
|---|---|
| Árbol lateral jerárquico de navegación | `QTreeView` colapsable (Sidebar, sección anterior) |
| Tabla principal como componente central | `QTableView` + `QAbstractItemModel` (ver sección 12) |
| Tres niveles visuales en tabla (capítulo / subcapítulo / concepto) | Colores `#8B6FB5` (partidas) y `#5E9CA0` (subpartidas), fondo principal para conceptos |
| Pestañas de documentos abiertos | `QTabWidget` en área de contenido |
| Barra de estado con contexto | `QStatusBar` con texto auxiliar 12 px |
| Columnas fijas: clave, descripción, unidad, cantidad, P.U., total | Estructura de columnas estándar en `QTableView` |

#### Patrones de OPUS a mejorar

| Problema en OPUS | Solución en Open APU Studio |
|---|---|
| Ribbon sobrecargado con demasiados iconos compitiendo | Toolbar compacta con grupos reducidos; acciones secundarias en menú contextual |
| Jerarquía de tabla depende exclusivamente del color azul | Color + peso tipográfico + sangría (nunca solo color, ver sección 16) |
| Poca separación visual entre filas de conceptos | `gridline-color: #203244` + `alternate-background-color` para mejorar legibilidad |
| Pestañas activas en amarillo (color semántico ocupado) | Pestañas activas con `#7FAFD6` (Navy 500), sin amarillo |
| Sin guía visual para usuarios nuevos | Panel secundario contextual con ayuda y desglose APU |

#### Grupos de acciones del Ribbon de OPUS (referencia de funcionalidad)

Los siguientes grupos de OPUS documentan las acciones que Open APU Studio debe cubrir, independientemente de cómo se organicen en la UI:

- **Editar:** Copiar, Pegar, Seleccionar todo, Agregar, Modificar, Desglosar, Eliminar, Deshacer
- **Buscar:** En catálogos, En vista
- **Desplegar:** Primer nivel, Resumen de agrupadores, Todo, por Nivel
- **Filtrar:** Global, Por columna, Editor
- **Cálculo:** Recalcular, Auditoría

---

## 10. Botones

### Tamaños

| Tipo | Altura | QSS |
|---|---|---|
| Compacto | 28 px | `padding: 2px 8px; font-size: 12px` |
| Normal | 36 px | `padding: 4px 16px; font-size: 14px` |
| Grande | 44 px | `padding: 8px 24px; font-size: 16px` |

### Clasificación

```qss
/* Primario — acción principal */
QPushButton#btnPrimario {
    background-color: #37628F;
    color: #E8EDF2;
    border-radius: 6px;
    padding: 4px 16px;
}

/* Secundario */
QPushButton#btnSecundario {
    background-color: transparent;
    color: #7FAFD6;
    border: 1px solid #37628F;
    border-radius: 6px;
    padding: 4px 16px;
}

/* Peligro */
QPushButton#btnPeligro {
    background-color: #7A4D4D;
    color: #E8EDF2;
    border-radius: 6px;
    padding: 4px 16px;
}
```

---

## 11. Formularios

- Etiquetas consistentes → `QLabel` con `font-size: 14px` y `space-2` de separación
- Validación visible → `QLineEdit` con `border: 1px solid #A06A6A` en error
- Mensajes de error → `QLabel` con `color: #A06A6A`

```qss
QLineEdit {
    background-color: #12161D;
    color: #E8EDF2;
    border: 1px solid #203244;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus {
    border: 1px solid #5A82AB;
}
QLineEdit[error="true"] {
    border: 1px solid #A06A6A;
}
```

---

## 12. Tablas

Componente principal del ecosistema. En PySide6: `QTableView` + `QAbstractItemModel`.

### Requisitos

| Requisito | PySide6 |
|---|---|
| Encabezados fijos | `QHeaderView.setStretchLastSection(False)` |
| Selección visible | `setSelectionBehavior(SelectRows)` + QSS `selection-background-color` |
| Navegación por teclado | Nativo de Qt |
| Scroll eficiente | Nativo de Qt |
| Alto rendimiento | Cargar solo filas visibles vía `QAbstractItemModel` |
| Filas alternas | `setAlternatingRowColors(True)` + QSS `alternate-background-color` |

### Formato numérico

| Tipo | Precisión |
|---|---|
| Precios unitarios | 2 decimales |
| Cantidades | 4 decimales |
| Porcentajes | 1 decimal |
| Factores / rendimiento | 4 decimales |

```python
# Formateo con locale o f-strings
f"${precio:,.2f}"   # P.U.
f"{cantidad:,.4f}"  # Cantidad
f"{factor:.4f}"     # Rendimiento
```

---

## 13. Iconografía

Para este proyecto (simplicidad, MVP): usar **símbolos Unicode** como íconos en botones.

| Acción | Símbolo |
|---|---|
| Nuevo | `+` |
| Abrir | `📂` |
| Guardar | `💾` |
| Editar | `✎` |
| Eliminar | `✕` |
| Buscar | `🔍` |
| Configuración | `⚙` |
| Recalcular | `↻` |

**Restricción:** No mezclar múltiples estilos de iconografía en la misma app.

Si se necesita iconografía más completa en v1.x, usar **Lucide Icons** (SVG con `QIcon`).

---

## 14. Agrupación de Información

- **QGroupBox** sin borde (solo texto + superficie distinta)
- **QSplitter** para paneles
- **QTabWidget** para contenido contextual
- **Cards:** `QFrame` con `background-color: #12161D` + `border-radius: 6px`

Evitar anidaciones excesivas (> 3 niveles).

---

## 15. Animaciones

Filosofía: mejorar comprensión, nunca decorativas.

| Acción | Duración | PySide6 |
|---|---|---|
| Hover | 150 ms | `QPropertyAnimation` o QSS `:hover` |
| Apertura de panel | 200 ms | `QPropertyAnimation` en width |
| Cambio de pestaña | 150–200 ms | Nativo de Qt |
| Toasts | 250 ms | `QTimer` + fade out |

**Prohibido:** rebotes, animaciones largas, efectos exagerados, transiciones innecesarias.

```qss
/* Hover sutil vía QSS (150 ms nativo de Qt) */
QPushButton:hover {
    background-color: #203244;
}
```

---

## 16. Aplicaciones de Ingeniería — Reglas Específicas

- **Unidades siempre visibles** — `QLabel("Carga: 150 kN")`, nunca `QLabel("150")`
- **Precisión consistente** en toda la app (ver sección 12)
- **Datos críticos** jerarquía visual + peso tipográfico + agrupación — nunca solo color

---

## 17. Sistema de Temas

### Arquitectura

El sistema de temas es intercambiable en runtime sin reiniciar la app. Cada tema es un archivo `.qss` independiente ubicado en `themes/`. La app carga el tema guardado en preferencias del usuario al iniciar.

```
themes/
├── dark.qss       # Tema oscuro (definido en esta guía, sección 3)
└── light.qss      # Tema claro (estilo Excel/OPUS, definido abajo)
```

### Implementación PySide6

```python
# theme_manager.py
class ThemeManager:
    THEMES = {
        "dark":  "themes/dark.qss",
        "light": "themes/light.qss",
    }

    @staticmethod
    def apply(app: QApplication, theme_key: str):
        path = ThemeManager.THEMES.get(theme_key)
        if path and os.path.exists(path):
            with open(path, "r") as f:
                app.setStyleSheet(f.read())

    @staticmethod
    def save_preference(theme_key: str):
        settings = QSettings("OpenAPU", "Studio")
        settings.setValue("theme", theme_key)

    @staticmethod
    def load_preference() -> str:
        settings = QSettings("OpenAPU", "Studio")
        return settings.value("theme", defaultValue="dark")
```

### Punto de acceso para el usuario

**Herramientas > Preferencias > Apariencia > Tema**

- Control: `QComboBox` con opciones "Oscuro" / "Claro"
- El cambio aplica inmediatamente sin reiniciar
- La preferencia se guarda automáticamente con `QSettings`

```python
combo_tema.currentTextChanged.connect(lambda t: (
    ThemeManager.apply(app, t),
    ThemeManager.save_preference(t)
))
```

---

### Tema Oscuro (`dark.qss`)

Ya definido en la sección 3. Paleta base `#12161D`. Referencia visual: VS Code, Fusion 360.

---

### Tema Claro (`light.qss`)

Referencia visual: Excel, Word, OPUS 2020, Neodatas. Fondo blanco en área de trabajo, superficies grises claras.

#### Paleta del tema claro

| Rol | Hex | Equivalente en dark |
|---|---|---|
| Fondo principal | `#F5F6F7` | `#12161D` |
| Superficie (panel) | `#E8EAED` | `#1B2330` |
| Superficie elevada | `#D8DCE0` | `#203244` |
| Superficie activa | `#C5CDD6` | `#2A4158` |
| Área de trabajo (tabla) | `#FFFFFF` | `#12161D` |
| Selección tabla | `#CCE0F0` | `#37628F` |
| Acento / focus | `#2A6099` | `#7FAFD6` |
| Texto principal | `#1A1F24` | `#E8EDF2` |
| Texto secundario | `#4A5560` | `#B7C0C8` |
| Texto deshabilitado | `#8A9499` | `#6B7884` |
| Partidas (árbol) | `#6B4F9A` | `#8B6FB5` |
| Subpartidas | `#3E7A7E` | `#5E9CA0` |
| Gridlines tabla | `#D0D5DA` | `#203244` |
| Encabezados tabla | `#E0E4E8` | `#1B2330` |

#### Reglas específicas del tema claro

- El área de trabajo (`QTableView`, `QPlainTextEdit`) usa **siempre fondo `#FFFFFF`**, no el fondo de superficie
- Los encabezados de tabla (`QHeaderView`) usan `#E0E4E8` con borde inferior `1px solid #C0C5CA`
- Las filas alternas en tabla: `#FFFFFF` / `#F5F6F7`
- El sidebar usa `#E8EAED`, no blanco, para diferenciarse del área de trabajo
- Los colores semánticos se oscurecen para mantener contraste sobre fondo claro:

| Estado | Tema oscuro | Tema claro |
|---|---|---|
| Success | `#5B8A72` | `#3D6B55` |
| Warning | `#D5B39B` | `#A07850` |
| Error | `#A06A6A` | `#8B3A3A` |
| Info | `#5A82AB` | `#2A6099` |

#### QSS base del tema claro

```qss
/* light.qss — base */
QWidget, QMainWindow {
    background-color: #F5F6F7;
    color: #1A1F24;
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 14px;
}
QMenuBar, QToolBar, QStatusBar {
    background-color: #E8EAED;
    color: #1A1F24;
}
QTableView {
    background-color: #FFFFFF;
    alternate-background-color: #F5F6F7;
    gridline-color: #D0D5DA;
    border: none;
    selection-background-color: #CCE0F0;
    selection-color: #1A1F24;
}
QHeaderView::section {
    background-color: #E0E4E8;
    color: #1A1F24;
    border: none;
    border-bottom: 1px solid #C0C5CA;
    padding: 4px 8px;
}
QTreeView {
    background-color: #E8EAED;
    alternate-background-color: #E0E4E8;
    selection-background-color: #CCE0F0;
    selection-color: #1A1F24;
    border: none;
}
QLineEdit {
    background-color: #FFFFFF;
    color: #1A1F24;
    border: 1px solid #C0C5CA;
    border-radius: 4px;
    padding: 4px 8px;
}
QLineEdit:focus {
    border: 1px solid #2A6099;
}
QPushButton#btnPrimario {
    background-color: #2A6099;
    color: #FFFFFF;
    border-radius: 6px;
    padding: 4px 16px;
}
QPushButton#btnSecundario {
    background-color: transparent;
    color: #2A6099;
    border: 1px solid #2A6099;
    border-radius: 6px;
    padding: 4px 16px;
}
```

---

### Reglas que aplican a ambos temas

Estas decisiones son independientes del tema y deben respetarse en `dark.qss` y `light.qss`:

- Tipografía, espaciado y radios de borde (secciones 5, 6, 7)
- Colores semánticos solo para estados del sistema, nunca para categorías (sección 4)
- Paleta de gráficas separada de los semánticos (sección 4)
- Formato numérico y precisión de decimales (sección 12)
- Iconografía Unicode / Lucide, sin mezclar estilos (sección 13)
- Animaciones funcionales únicamente (sección 15)

---

## 18. Pendientes para v1.x

- Sistema de pestañas MDI/ dockable
- Sistema de notificaciones (toasts)
- Estándar de gráficas (QtCharts / matplotlib)
- Sistema de atajos de teclado
- Diseño responsive para pantallas pequeñas
- Guía de accesibilidad (WCAG, contraste, focus visible)

---

## 19. Referencias

- Implementación actual: `themes/dark.qss`, `themes/light.qss`
- Paleta oscura: `docs/Guia diseño.md` sección 3
- Paleta clara: `docs/Guia diseño.md` sección 17
- Widget tree: `ui/ventana_principal.py`
- Gestor de temas: `theme_manager.py`