# Open Structural Studio

Aplicación de escritorio para ingeniería estructural que combina **presupuestos/costos** (evolucionada de Open APU Studio) con **análisis estructural** (usando motor OpenSeesPy).

## Arquitectura General

```
Open Structural Studio/
├── main_test_opensees.py          # ← TEMPORAL: ventana de prueba del motor estructural
├── backend/
│   ├── database/                  # Base de datos SQLite (presupuestos)
│   │   ├── db.py                  # Rutas, config, helper Database
│   │   ├── core.py                # Lógica de negocio pura
│   │   ├── schema.sql             # Schema completo SQLite
│   │   └── repos/                 # Repositorios por dominio
│   │       ├── base.py            # RepoBase con helpers SQLite
│   │       ├── proyecto.py        # ProyectoRepo
│   │       ├── presupuesto.py     # NodoRepo (árbol presupuestal)
│   │       ├── insumos.py         # InsumoRepo (elementos de costo)
│   │       ├── apu.py             # ApuMatricesRepo
│   │       ├── explosion.py       # ExplosionRepo (3 niveles)
│   │       ├── recalculo.py       # RecalculoRepo
│   │       └── catalogos.py       # FamiliaRepo, SubfamiliaRepo
│   ├── motor/
│   │   └── opensees_repo.py       # Wrapper OpenSeesPy (Nodo/Elemento)
│   ├── importar/                  # Importación OPUS 2010
│   └── exportar/                  # Exportación DBF + PDF/LaTeX
├── frontend/
│   ├── temas/                     # Sistema de temas QSS
│   │   ├── temas.py               # Temas (modo + acento)
│   │   ├── modo-oscuro.qss        # Tema oscuro
│   │   ├── modo-claro.qss         # Tema claro
│   │   └── acento-*.qss           # 4 acentos (azul/rosa/café/verde)
│   └── ventana/
│       ├── ventana.py             # VentanaPrincipal (ventana principal APU)
│       ├── toolbar.py             # ToolbarMixin (ribbon presupuestos)
│       ├── toolbar_estructural.py # ToolbarEstructuralMixin (ribbon estructural)
│       ├── paneles.py             # PanelesMixin
│       ├── handlers.py            # HandlersMixin
│       ├── api.py                 # Api (fachada de servicios)
│       └── widgets/
│           ├── base.py            # TreeTableWidget (widget base)
│           ├── viewport3d.py      # Viewport3D (PyVistaQt)
│           ├── sidebar_estructura.py  # SidebarEstructura
│           └── ...                # Widgets especializados
└── docs/
    └── analisis-toolbar.md        # Inventario de botones
```

## Cómo Correr

```bash
pip install PySide6 openseespy pyvista pyvistaqt
python main_test_opensees.py
```

## Componentes Principales

### 1. Motor OpenSeesPy (`backend/motor/opensees_repo.py`)

Encapsula el dominio OpenSees en memoria.

```python
repo = OpenSeesRepo()
repo.construir_modelo_ejemplo(niveles=3, bahias_x=2, bahias_y=2)
repo.analizar()

nodos = repo.obtener_nodos()      # List[Nodo]
elementos = repo.obtener_elementos()  # List[Elemento]
```

**Dataclasses:**
- `Nodo`: tag, x, y, z, restringido, dx/dy/dz, rx/ry/rz, rx_reac/ry_reac/rz_reac
- `Elemento`: tag, tipo, nodo_i, nodo_j, axial, corte_y, corte_z, momento_y, momento_z

**⚠️ TEMPORAL:** El modelo de ejemplo es fijo (3 niveles, 2 bahías). Los parámetros `_niveles` y `_bahias` en `main_test_opensees.py` son valores hardcodeados.

### 2. Viewport 3D (`frontend/ventana/widgets/viewport3d.py`)

Widget PyVistaQt embebido en Qt para visualización 3D.

**Métodos públicos:**
| Método | Descripción |
|--------|-------------|
| `limpiar()` | Limpia la escena |
| `mostrar_modelo(nodos, elementos)` | Geometría no-deformada |
| `mostrar_deformada(nodos, elementos, escala)` | Forma deformada escalada |
| `mostrar_fuerza(nodos, elementos, campo, color)` | Diagrama de fuerza interna |

**Campos disponibles para `mostrar_fuerza()`:**
- `momento_y`, `momento_z` (flector)
- `corte_y`, `corte_z` (cortante)
- `axial`

**Colores por tipo de fuerza:**
- Momento: Verde `#6FCF97`
- Cortante: Púrpura `#BB6BD9`
- Axial: Naranja `#E8825A`

### 3. Sidebar Estructural (`frontend/ventana/widgets/sidebar_estructura.py`)

Panel izquierdo de dos niveles estilo RAM Elements.

**Categorías:** Nudos / Miembros / Placas / Área / Gen

**⚠️ TEMPORAL:** Las tablas se llenan con datos del motor en `_refrescar_tablas()`, pero la mayoría de sub-pestañas son esqueleto vacío (36 filas en blanco). Solo "Coordenadas", "Restricciones", "Conectividad" y "Cargas sobre miembros" tienen datos reales.

### 4. Toolbar Estructural (`frontend/ventana/toolbar_estructural.py`)

Ribbon toolbar con 5 pestañas: INICIO / MODELADO / ANÁLISIS / PROCESO / SALIDA.

**Iconos:** Usa `Segoe Fluent Icons` (Windows 11) con fallback a `Segoe MDL2 Assets` → `Segoe UI Symbol`.

**Diccionario `_I`:** Mapeo de nombres a codepoints PUA.

**Config `_TOOLBAR_CFG`:** Estructura de botones por pestaña.

**⚠️ TEMPORAL:** Muchos botones muestran "(pendiente)" y están grisados. Solo unos pocos están conectados.

### 5. Botones Conectados

| Botón | Pestaña | Handler | Acción |
|-------|---------|---------|--------|
| Analizar modelo | PROCESO | `_on_analizar()` | Corre OpenSees + muestra momento Y |
| Ver en pantalla | SALIDA | `_on_pantalla_completa()` | Fullscreen |
| Figura deformada | ANÁLISIS | `_on_ver_deformada()` | Muestra deformada |
| Momento Y | ANÁLISIS | `_on_ver_momento_y()` | Diagrama momento Y |
| Momento Z | ANÁLISIS | `_on_ver_momento_z()` | Diagrama momento Z |
| Cortante Y | ANÁLISIS | `_on_ver_corte_y()` | Diagrama cortante Y |
| Cortante Z | ANÁLISIS | `_on_ver_corte_z()` | Diagrama cortante Z |
| Axial | ANÁLISIS | `_on_ver_axial()` | Diagrama axial |

### 6. Sistema de Temas

**2 modos × 4 acentos = 8 combinaciones:**
- Modo: oscuro / claro
- Acento: azul / rosa / café / verde

**Archivos QSS:** `modo-oscuro.qss`, `modo-claro.qss`, `acento-*.qss`

**Persistencia:** `Temas.cargar_preferencia()` / `Temas.guardar_preferencia()`

## Código Temporal / Marcar para Futuro

| Archivo | Qué es temporal |
|---------|-----------------|
| `main_test_opensees.py` | Ventana de prueba, no es la ventana final |
| `_niveles`, `_bahias` | Parámetros hardcodeados del modelo |
| `_escala_deformada = 80` | Escala fija, debería ser configurable |
| `_refrescar_tablas()` | Llenado manual, falta conexión bidireccional |
| 36 filas vacías en tablas | Placeholder temporal |
| `_poblar_menu_pendiente()` | Menús desplegables con "(próximamente)" |
| Botones grisados "(pendiente)" | No conectados aún |
| Secciones/Materiales fijos en motor | No leídos del sidebar |
| Picking en viewport | No implementado (selección 3D → tabla) |
| Exportar a DXF | No implementado |
| Guardar vista 3D | No implementado |

## Diagrama de Flujo del Análisis

```
1. Construir modelo
   repo.construir_modelo_ejemplo()
   ↓
2. Visualizar geometría
   viewport.mostrar_modelo(nodos, elementos)
   ↓
3. Analizar
   repo.analizar()  →  OpenSees resuelve
   ↓
4. Ver resultados
   viewport.mostrar_fuerza(campo="momento_y")
   viewport.mostrar_deformada(escala=80)
```

## Dependencias

- **PySide6** — Qt para Python
- **openseespy** — Motor de elementos finitos
- **pyvista** / **pyvistaqt** — Visualización 3D (VTK)
- **numpy** — Cálculos numéricos

## Notas Técnicas

### Font de Iconos
Los iconos usan `Segoe Fluent Icons` (PUA Unicode) con fallback automático:
1. `Segoe Fluent Icons` (Windows 11)
2. `Segoe MDL2 Assets` (Windows 10)
3. `Segoe UI Symbol` (fallback final)

### Bug Intel Fortran
En Windows, `opensees.pyd` puede crashear con Ctrl+C fantasma. Solución:
```python
os.environ["FOR_DISABLE_CONSOLE_CTRL_HANDLER"] = "1"
```

### Escalado de Diagramas
`mostrar_fuerza()` calcula escala automática basada en el valor máximo. Factor: `1.5 / max_valores`.
