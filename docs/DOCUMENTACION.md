# Open APU Studio — Documentación completa

Actualizado: 2026-08-31 04:55 (hora local)

---

## 1. Visión general

Aplicación de escritorio para visualización y análisis de presupuestos de construcción
con Análisis de Precios Unitarios (APU),cons operte para importar desde OPUS 2010 (formato DBF).

**Stack:**
- Python 3.11+ / PySide6 (Qt6)
- SQLite + FTS5 (full-text search con `unicode61 remove_diacritics`)
- dbfread (importación OPUS, encoding cp850)
- PyInstaller (distribución futura)

**Público:** Ingenieros civiles, arquitectos, contratistas pequeños.
No se busca remplazar opus si no ser una alternativa para constructoras pequeñas que no tienen para comprar las licencias de opus o neodata.

**Targets:** Windows (principal), Linux (nativo desde el diseño), mac(posible implementacion futura).

---

## 2. Arquitectura

### Regla cardinal

**SQL solo vive en `backend/database/repos/`.** Si aparece SQL en UI o en
`backend/core.py`, es error de diseño.

### Arquitectura de servicios (ver `ARQUITECTURA_SERVICIOS.md`)

El plan completo de migración a servicios (`UpdateService`, `EventBus`,
`SchemaRegistry`) está documentado en `docs/ARQUITECTURA_SERVICIOS.md`.
Este documento describe las 5 fases, las reglas arquitectónicas, y el
checklist de revisión.

### Patrón de herencia (mixins)

```python
class VentanaPrincipal(ToolbarMixin, PanelesMixin, HandlersMixin, QMainWindow):
```

Cada mixin aporta un grupo de métodos. `self` es siempre la instancia de
`VentanaPrincipal`. Atributos compartidos (ej. `self._db`, `self._tabs`,
`self._api`, `self._tab_activa`) se definen en `VentanaPrincipal.__init__`.

### Fachada Api (frontend/api.py)

Puente entre frontend y backend. Nunca importa PySide6, nunca escribe SQL.
Siempre devuelve tipos Python estándar (dict, list, str, int, float, None).

```python
api = Api(conn, db_path, proyecto_id=1)
arbol   = api.presupuesto_arbol()
apu     = api.apu(clave="0202002")
filas,t = api.explotar(concepto_ids=[5,23], nivel="basico", tipos_ids=[1,2,4])
```

---

## 3. Estructura del proyecto

```
Open APU Studio/
├── main.py                          ← Entry point (QApplication, tema, ventana)
├── requirements.txt
├── backend/
│   ├── __init__.py
│   ├── formulas.py                  ← simpleeval vendereado
│   ├── cad/lector_dxf.py            ← Parseo DXF (ezdxf)
│   ├── database/
│   │   ├── db.py                    ← SQLite + schema + Rutas/Config
│   │   ├── schema.sql               ← Single file, sin migraciones
│   │   ├── core.py                  ← Lógica de negocio (árbol, métricas)
│   │   ├── event_bus.py             ← EventBus + eventos semánticos
│   │   ├── schema_registry.py       ← SchemaRegistry (Field types)
│   │   ├── repos/                   ← SQL vive aquí
│   │   │   ├── base.py, proyecto.py, presupuesto.py, insumos.py, apu.py,
│   │   │   │   recalculo.py, catalogos.py, explosion.py, diagnostico.py,
│   │   │   │   formulas.py, generador.py, historial.py, indirectos.py
│   │   │   └── __init__.py
│   │   └── services/                ← DataService, RepositoryRegistry
│   ├── importar/importar.py         ← OPUS 2010 (.DBF → SQLite)
│   └── exportar/
│       ├── exportar_generadores_excel.py
│       └── informe_pdf/latex.py     ← pdflatex (2 pasadas)
├── server/servidor.py               ← FastAPI + WebSocket (único que toca .db en red)
├── frontend/
│   ├── temas/                       ← modo×acento (QSS) + Config
│   └── ventana/
│       ├── ventana.py               ← VentanaPrincipal (mixins)
│       ├── api.py                   ← Fachada (dispatcher a _BackendLocal/_BackendHTTP)
│       ├── api_backends.py          ← ToqueApiBackend Protocol (66 métodos)
│       ├── api_cliente.py           ← ApiCliente (transporte httpx, 7 métodos)
│       ├── ws_client.py             ← WebSocketClient (QThread)
│       ├── colores.py, iconos.py, tipos_insumo.py, ui_utils.py
│       ├── cad/                     ← VisorCadWidget, medición, cuantificación
│       ├── mixins/                  ← 9 mixins (navegacion, toolbar, paneles, gestion_proyectos, informes, diag_dialogs, apu, rastreo, explosion, generador)
│       └── widgets/                 ← TreeTableWidget, TablaArbol, TablaInsumos, TablaApuDetalle, PestañaExplosion, TablaGenerador, FilterDialog, dialogs, ajustes, ayuda, config_impresion, presupuesto_popup
├── assets/
│   ├── icons/                       ← Lucide (monocolor, tint)
│   ├── icons8/                      ← Icons8 Color (116 SVGs, mapeo en iconos.py)
│   └── favicon.ico
├── datos_usuario/                   ← gitignored: proyectos/*.db, reportes/, config.json
└── docs/
    ├── SCHEMA.md, DECISIONES_PENDIENTES.md, DOCUMENTACION.md
    ├── ARQUITECTURA_SERVICIOS.md    ← Protocolo local↔HTTP (R1-R9, Fases 0-5)
    ├── GUIA_*.md, DUPLICACION_Y_DEUDA.md, PLAN_REPARACION.md
    └── planes/                      ← PLAN_INSUMOS, PLAN_FSR, PLAN_MULTIUSUARIO, PLAN_FORMULAS_VARIABLES, PLAN_PRESUPUESTO
```

Open APU Studio/
│
├── main.py                      ← 44 L — Entry point
│
├── assets/
│   └── favicon.ico              ← Icono de la aplicación
│
├── backend/                     ← Capa de datos y negocio
│   ├── __init__.py              ← Docstring del paquete
│   ├── db.py                    ← Conexión SQLite + Config
│   ├── schema.sql               ← Esquema SQL completo
│   ├── core.py                  ← Lógica de negocio pura
│   ├── database/
│   │   └── repos/               ← Repositorios CRUD (paquete)
│   │       ├── __init__.py      ← Re-exporta todos los repos
│   │       ├── base.py          ← RepoBase (actualizar_campo genérico)
│   │       ├── proyecto.py      ← ProyectoRepo, FactoresSobrecostoRepo
│   │       ├── presupuesto.py   ← NodoRepo
│   │       ├── insumos.py       ← InsumoRepo
│   │       ├── apu.py           ← ApuMatricesRepo
│   │       ├── recalculo.py     ← RecalculoRepo
│   │       ├── catalogos.py     ← FamiliaRepo, SubfamiliaRepo, NotaRepo
│   │       ├── explosion.py     ← ExplosionRepo
│   │       └── diagnostico.py   ← DiagnosticoRepo
│   ├── importar/
│   │   ├── importar.py          ← Importador OPUS 2010
│   │   └── schemas_opus.json    ← Esquemas OPUS por versión
│   └── exportar/
│       ├── exportar.py          ← Exportación (rota, no mantenida)
│       └── informe_pdf/
│           ├── latex.py         ← Generación de PDF vía LaTeX
│           └── latex/templates/ ← Templates .tex
│
├── frontend/                    ← Capa de presentación (PySide6)
│   ├── __init__.py              ← Docstring del paquete
│   ├── ventana.py               ← Ventana principal (ensambla mixins)
│   ├── toolbar.py               ← ToolbarMixin
│   ├── paneles.py               ← PanelesMixin (sidebar, presupuesto, insumos)
│   ├── api.py                   ← Api de backend para UI
│   ├── temas/                   ← Gestor de temas QSS
│   │   ├── __init__.py
│   │   ├── temas.py             ← 68 L — Gestor de temas
│   │   ├── modo-oscuro.qss
│   │   ├── modo-claro.qss
│   │   ├── acento-azul.qss
│   │   ├── acento-rosa.qss
│   │   ├── acento-cafe.qss
│   │   └── acento-verde.qss
│   └── ventana/
│       ├── __init__.py
│       ├── ventana.py           ← Ventana principal (layout + estado)
│       ├── toolbar.py           ← Toolbar, temas, búsqueda
│       ├── paneles.py           ← PanelesMixin
│       ├── api.py               ← Api (fachada frontend→backend)
│       ├── handlers/            ← Paquete de handlers
│       │   ├── __init__.py      ← HandlersMixin (navegación, búsqueda)
│       │   ├── gestion_proyectos.py ← GestionProyectosMixin
│       │   ├── informes.py      ← InformesMixin
│       │   └── diag_dialogs.py  ← DiagDialogsMixin
│       ├── apu/                 ← Paquete de mixins APU
│       │   ├── __init__.py      ← Re-exporta ApuMixin, RastreoMixin, ExplosionMixin
│       │   ├── apu.py           ← ApuMixin
│       │   ├── rastreo.py       ← RastreoMixin
│       │   └── explosion.py     ← ExplosionMixin
│       └── widgets/
│           ├── __init__.py
│           ├── base.py          ← TreeTableWidget (tabla genérica)
│           ├── arbol.py         ← Tabla jerárquica del presupuesto
│           ├── insumos.py       ← Catálogo plano de insumos
│           ├── explosion.py     ← Explosión de insumos
│           ├── dialogs.py       ← Diálogos modales
│           └── ajustes.py       ← Configuración de decimales
│
└── docs/
    ├── SCHEMA.md                ← Documentación del esquema (legacy)
    ├── DECISIONES_PENDIENTES.md ← Decisiones de diseño (legacy)
    ├── GUIA_IMPLEMENTACION.md   ← Guía de integración (legacy)
    ├── CAMBIOS_SCHEMA_V2.md     ← Migración v2→v3 (legacy)
    └── DOCUMENTACION.md         ← ← Este archivo
```

---

## 4. Backend

### 4.1 `backend/db.py` — Conexión y configuración

**Database** (singleton):
- Una sola conexión SQLite activa a la vez.
- Aplica `schema.sql` automáticamente en DB nueva.
- Pragmas: `foreign_keys = ON`, `journal_mode = WAL`.

```python
db = Database.abrir(ruta_db)
conn = db.conn
Database.cerrar()
```

**Config** (persistencia JSON):
- Archivo: `config.json` en la carpeta de datos del usuario.
- Valores: `tema`, `ultimo_proyecto`, `arbol_header_state`.

```python
Config.get("tema", "dark")
Config.set("ultimo_proyecto", "D60JALISCOT")
```

**Rutas** (carpeta de datos del usuario):

| OS | Ruta |
|---|---|
| Windows | `C:/Users/<user>/AppData/Local/Open APU Studio/` |
| Linux | `~/.local/share/Open APU Studio/` |
| macOS | `~/Library/Application Support/Open APU Studio/` |

```
├── config.json
├── proyectos/      ← archivos .db
└── logs/           ← logs de importación y errores
```

Usa `platformdirs` si está instalado; fallback a `datos_usuario/` junto al ejecutable.

### 4.2 `backend/schema.sql` — Esquema de base de datos

Bloques (ver sección 6 para detalle de cada tabla):

1. **Usuarios** — monousuario, tabla preparada para colaboración futura.
2. **Catálogos del sistema** — `tipos_insumo` (8 tipos, sistema de bits).
3. **Catálogos del proyecto** — `familias`, `subfamilias`, `proveedores`.
4. **Proyecto** — `proyectos`, `configuracion_proyecto`, `sobrecostos`.
5. **Árbol del presupuesto** — `estructura_presupuesto` (jerarquía por WBS).
6. **Insumos** — `insumos` (catálogo maestro con `es_compuesto`).
7. **APU** — `apu_matrices`, `apu_resumen_totales`.
8. **Colaboración** — `notas`, `historial`.
9. **Control de esquema** — `schema_version`.

### 4.3 `backend/database/repos/` — Repositorios

**`RepoBase`** — clase base con helpers genéricos:

```python
class RepoBase:
    def _uno(self, sql, params)      → dict | None
    def _lista(self, sql, params)    → list[dict]
    def _ejecutar(self, sql, params) → lastrowid
    def _muchos(self, sql, seq)      → None
    def _actualizar_campo(self, tabla, id_col, id_val, campo, valor, tipo, conn)
```

**Repositorios concretos:**

| Archivo | Clase(s) | Tabla(s) | Métodos clave |
|---|---|---|---|
| `presupuesto.py` | `NodoRepo` | `estructura_presupuesto` | `todos()`, `hijos()`, `buscar_por_clave()`, `buscar_texto()`, `actualizar_total()`, `actualizar_descripcion_agrupador()`, `ids_por_tipo()` |
| `insumos.py` | `InsumoRepo` | `insumos` + `familias` + `subfamilias` | `todos()`, `por_tipo()`, `buscar_por_clave()`, `donde_se_usa()`, `actualizar_campo()`, `ids_con_apu()` |
| `apu.py` | `ApuMatricesRepo` | `apu_matrices` | `por_matriz()`, `por_insumos()`, `actualizar_campo()` |
| `recalculo.py` | `RecalculoRepo` | `apu_resumen_totales` | `calcular()`, `recalcular()` |
| `proyecto.py` | `ProyectoRepo`, `FactoresSobrecostoRepo` | `proyectos`, `configuracion_proyecto`, `factores_sobrecosto` | `todos()`, `config()`, `por_proyecto()`, `guardar()` |
| `catalogos.py` | `FamiliaRepo`, `SubfamiliaRepo`, `NotaRepo` | `familias`, `subfamilias`, `notas` | `todas()`, `por_familia()`, `por_concepto()`, `agregar()` |
| `explosion.py` | `ExplosionRepo` | Múltiples tablas | `calcular()` (3 niveles de explosión) |
| `diagnostico.py` | `DiagnosticoRepo` | Múltiples tablas | `insumos_hash_desactualizado()`, `aplicar_hash()`, `estadisticas()`, `conceptos_sin_familia()`, `insumos_duplicados()` |

### 4.4 `backend/core.py` — Lógica de negocio

Funciones puras que reciben `db_path` y devuelven estructuras Python.

```python
build_budget_tree(db_path, proyecto_id=1)     → list[dict]  # árbol jerárquico
get_apu(db_path, concepto_id)                  → dict        # APU + totales
get_proyecto(db_path, proyecto_id=1)           → dict | None
validar(db_path, proyecto_id=1)                → dict        # reporte de integridad

# Métricas
count_nodes(nodes)         → int
count_concepts(nodes)      → int
total_obra(nodes)          → float
flatten(nodes)             → list[dict]
```

**`build_budget_tree`**: Lee `estructura_presupuesto` ordenado por WBS, construye
árbol en memoria usando `padre_id`. No necesita SQL recursivo porque el ORDER BY WBS
garantiza que los padres se procesen antes que los hijos.

**`get_apu`**: Lee `apu_matrices` JOIN `insumos` JOIN `tipos_insumo` para un
`matriz_id`. También lee `apu_resumen_totales`.

### 4.5 `backend/importar.py` — Importador OPUS 2010

Lee archivos `.DBF` de una carpeta OPUS y los convierte a SQLite.

**Archivos DBF que procesa:**

| Archivo | Contenido |
|---|---|
| `*1.DBF` | Estructura del presupuesto (capítulos + conceptos) |
| `*P.DBF` | Catálogo de insumos (materiales, MO, herramienta, equipo, etc.) |
| `*F.DBF` | Componentes APU (desglose de cada concepto) |
| `*R.DBF` | Resumen de precios unitarios |
| `*G.DBF` | Grupos de insumos (familias/subfamilias) |

**Algoritmo WBS truncation:**
- El árbol se reconstruye truncando `PRE_WBS` de derecha a izquierda hasta encontrar
  un nodo activo con ese código exacto.
- `PRE_IDPAD` se ignora (pertenece a otro sistema de numeración y produce padres incorrectos).

**Sistema de bits (PREFIJO):**
`tipo_id` en `tipos_insumo` sigue el sistema de bits de OPUS:

| Bit | ID | Tipo |
|---|---|---|
| 1 | 1 | Material |
| 2 | 2 | Mano de obra |
| 4 | 4 | Herramienta |
| 8 | 8 | Equipo |
| 16 | 16 | Auxiliar |
| 32 | 32 | Concepto compuesto |
| 64 | 64 | Flete |
| 128 | 128 | Trabajo |

**Insumos compuestos:**
- `es_compuesto = 1` si el insumo aparece como matriz padre en `*F.DBF` o tiene el bit 32.
- Sus componentes se almacenan en `apu_matrices` (no hay tabla `apu_auxiliares` separada).

---

## 5. Frontend

### 5.1 `frontend/ventana.py` — VentanaPrincipal

Estado de instancia:

```python
self._tema              # str — tema visual activo
self._tab_activa        # str — pestaña toolbar activa ("PROYECTO", "INICIO", ...)
self._tab_temp          # QWidget | None — pestaña temporal (click simple en sidebar)
self._db                # Database | None — proyecto abierto
self._api               # Api | None — fachada de servicios
self._arbol_presupuesto # TablaArbol | None — referencia al árbol activo
```

Layout:

```
┌─────────────────────────────────────────────────┐
│ [PROYECTO] [INICIO] [INFORMES] [VISTA] [PR...]  │ ← Tab bar
├─────────────────────────────────────────────────┤
│ Icon+text groups per tab                         │ ← Toolbar (QStackedWidget)
├─────────────────────────────────────────────────┤
│ 🔍 Buscar en el proyecto…                       │ ← Search bar
├──────────────────┬──────────────────────────────┤
│  Sidebar         │  QTabWidget                   │
│  (explorador)    │  ┌─────────────────────────┐  │
│                  │  │ Presupuesto │ APU │ ...  │  │
│                  │  └─────────────────────────┘  │
├──────────────────┴──────────────────────────────┤
│ Tema: Oscuro  │  v0.3                           │ ← Status bar
└─────────────────────────────────────────────────┘
```

### 5.2 `frontend/toolbar.py` — ToolbarMixin

**Tab bar:** Botones conmutables para 6 pestañas: PROYECTO, INICIO, INFORMES,
VISTA, PRINCIPAL, HERRAMIENTAS.

**Toolbar:** `QStackedWidget` con una página por pestaña. Cada página se construye
bajo demanda (lazy) desde `_TOOLBAR_CFG`. Grupos de botones con:

- **Botones grandes** (ToolButtonTextUnderIcon): icono 40×40 + texto corto.
- **Botones apilados** (ToolButtonTextBesideIcon): pares icono+texto en columna.
- **Grupos mixtos**: combinan ambos estilos.

**Barra de búsqueda:** `QLineEdit` con:
- Filtro en tiempo real (`textChanged` → `filter_rows`).
- Menú contextual (clic derecho) para seleccionar columnas de búsqueda.
- Placeholder "🔍 Buscar en el proyecto…".

**Temas:** Botones para 6 temas (dark, light, hybrid, rosa, cafe, verde).
Selección persiste en `config.json`.

**Iconos:** Todos los iconos son caracteres Unicode pintados sobre QPixmap
transparente — sin dependencia de archivos de imagen.

### 5.3 `frontend/ventana/paneles.py` — PanelesMixin

**Sidebar:** `QTreeWidget` con secciones:
- 📋 **Presupuesto programable** → árbol del presupuesto
- 📐 **Conceptos** → tabla plana de conceptos
- 📦 **Explosión de insumos** → diálogo + tabla de resultados
- 💰 **Cálculo de indirectos** → placeholder (en desarrollo)
- 📚 **Insumos** → catálogo por tipo (Todos, Materiales, MO, Herramienta, etc.)
- 🧮 **Matrices** → insumos compuestos con APU

**Pestañas de contenido:**
Cada builder crea un widget que se inserta en el `QTabWidget` central.
Click simple → pestaña temporal (reemplazable). Doble click → pestaña permanente.

### 5.4 `frontend/ventana/mixins/` — HandlersMixin (navegacion) + 8 mixins

| Archivo | Clase | Función |
|---|---|---|
| `__init__.py` | `HandlersMixin` | Navegación, búsqueda, vista, adjuntos |
| `gestion_proyectos.py` | `GestionProyectosMixin` | Abrir/cerrar/copiar/renombrar/eliminar/importar proyecto |
| `informes.py` | `InformesMixin` | Generar PDF, compilar, vista previa |
| `diag_dialogs.py` | `DiagDialogsMixin` | Depurar catálogos, hash, info proyecto |

### 5.5 `frontend/ventana/apu/` — Paquete de mixins APU

| Archivo | Clase | Función |
|---|---|---|
| `__init__.py` | — | Re-exporta `ApuMixin`, `RastreoMixin`, `ExplosionMixin` |
| `apu.py` | `ApuMixin` | Pestañas APU, edición inline, navegación |
| `rastreo.py` | `RastreoMixin` | Rastreo de insumos, tabla de uso |
| `explosion.py` | `ExplosionMixin` | Explosión de insumos/matrices, sobrecostos |

### 5.6 `frontend/ventana/api.py` — Api (fachada)

```python
class Api:
    # Presupuesto
    presupuesto_arbol()              → list[dict]
    todos_concepto_ids()             → list[int]
    conceptos_planos()               → list[dict]
    nodo_total(nodo_id)              → float | None
    nodoActualizarCampo(nodo_id, campo, valor, tipo)  → bool

    # APU
    apu(clave)                       → dict | None
    insumo_es_compuesto(clave)       → bool
    claves_con_apu()                 → set[str]
    apu_actualizar_campo(clave, campo, valor, tipo)    → bool

    # Insumos
    insumos(tipo_clave=None)         → list[dict]
    insumos_con_matrices(...)        → list[dict]
    insumo_por_clave(clave)          → dict | None
    rastrear_insumo(insumo_id)       → list[dict]

    # Explosión
    explotar(concepto_ids, nivel, tipos_ids) → tuple[list[dict], float]
    resumen_tipos_explosion(tipos_ids)       → str

    # Sobrecostos
    factores_sobrecosto_por_proyecto()       → dict
    factores_sobrecosto_guardar(...)         → bool

    # Proyectos
    proyectos_disponibles()          → list[str]
    abrir_carpeta_proyectos()        → None
```

### 5.6 Widgets

**`TreeTableWidget`** (`base.py`):
- Tabla genérica con cabecera, checkboxes, selección múltiple.
- Soporta modo árbol (`QTreeWidget`) y plano (lista simple).
- Búsqueda multi-columna client-side (`filter_rows()`).
- Menú contextual de cabecera (ocultar/mostrar columnas).
- Persistencia de estado del header (anchos, visibilidad) en `config.json`.
- Columnas de profundidad con líneas conectoras (estilo explorador de archivos).

**`TablaArbol`** (`arbol.py`):
- Árbol jerárquico del presupuesto con colores por nivel.
- 13 columnas: Nivel, Clave, Descripción, Unid, Cant, P.U., Total,
  Desc. Corta, Tipo, Estado, Notas, Creado, Modificado.
- Colores por nivel (0→púrpura, 1→azul, 2→teal, 3→beige, 4→verde, 5+→vino).
- Capítulos en negritas con color. Conceptos editables (cantidad, precio, clave, desc).
- WBS visual calculado: `"1.1.3"` en lugar de WBS crudo.

**`TablaInsumos`** (`insumos.py`):
- Tabla plana con íconos por tipo de insumo.
- Columnas: Tipo, Clave, Descripción, Unidad, Costo final, Familia.
- Doble clic → abre APU del insumo compuesto.

**`TablaExplosion`** (`explosion.py`):
- Resultados de explosión con agrupación por tipo.
- Columnas: Tipo, Clave, Descripción, Unidad, Cantidad, P.U., Total, %.
- Subtotales por tipo destacados con color.
- Fila de TOTAL GENERAL al final.
- Menú contextual: "🔍 Rastrear uso".
- Doble clic → abre APU del insumo.

**`DialogoExplosion`** (`explosion.py`):
- Diálogo modal de selección: método de cálculo (básico/compuesto/primer nivel)
  + checkboxes de tipos de insumo a incluir.

---

## 6. Esquema de base de datos (detallado)

### Convenciones

| Convención | Valor |
|---|---|
| Llaves primarias | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| Fechas | `TEXT` en ISO 8601: `'YYYY-MM-DD HH:MM:SS'` |
| Booleanos | `INTEGER` — `0` = falso, `1` = verdadero |
| Soft-delete | `activo INTEGER NOT NULL DEFAULT 1` |
| Auditoría | `creado_por`, `creado_en`, `modificado_por`, `modificado_en` |
| Importes calculados | `GENERATED ALWAYS AS (...) STORED` |
| Subtotales de árbol | No son computados — Python los recalcula bottom-up |
| Monousuario | `usuario_id=1` por defecto (preparado para multi) |

### Bloques

#### Bloque 1 — Usuarios

```sql
usuarios (id, nombre, email, activo, creado_en, ultimo_acceso)
```

Semilla: 1 usuario local. Sin tabla `roles` (eliminada en v2).

#### Bloque 2 — Catálogos del sistema

```sql
tipos_insumo (id, clave, nombre, orden)
-- 1=material, 2=mano_obra, 4=herramienta, 8=equipo,
-- 16=auxiliar, 32=concepto, 64=flete, 128=trabajo
```

Nota: las tablas `tipos_herramienta`, `tipos_equipo`, `tipos_material` y
`estados_nodo` fueron eliminadas en la migración v2.

#### Bloque 3 — Catálogos del proyecto

```sql
familias     (id, nombre, activo)
subfamilias  (id, familia_id, nombre, activo)
proveedores  (id, nombre, contacto, telefono, email, notas, activo, creado_en)
```

#### Bloque 4 — Proyecto

```sql
proyectos               (id, nombre, ..., total_obra, activo, ...)
configuracion_proyecto  (proyecto_id, horas_dia, decimales_costo, decimales_cantidad, ...)
sobrecostos             (id, proyecto_id, orden, variable, descripcion, formula,
                         porcentaje_mn, porcentaje_me, tipo, ...)
```

#### Bloque 5 — Árbol del presupuesto

```sql
estructura_presupuesto (
    id, proyecto_id, padre_id,
    wbs, nivel, orden,          -- jerarquía
    tipo,                        -- 'capitulo' | 'concepto'
    insumo_id,                   -- REFERENCES insumos(id) — solo conceptos
    descripcion,
    cantidad,
    formula,                     -- expresión opcional para cantidad
    total,                       -- unificado: conceptos=cant×precio, capítulos=SUM(hijos)
    estado INTEGER,              -- 0=sin revisar, 1=en revisión, 2=verificado, 3=cuestionado
    notas_rapidas,
    activo, creado_por, creado_en, modificado_por, modificado_en
)
```

La fuente de verdad jerárquica es `wbs` (no `padre_id`). Durante la importación,
el árbol se reconstruye truncando WBS de derecha a izquierda.

#### Bloque 6 — Insumos

```sql
insumos (
    id, proyecto_id,
    clave, clave_usuario, tipo_id, es_compuesto,
    descripcion, descripcion_corta, unidad,
    familia_id, subfamilia_id, proveedor_id,
    costo_mn, costo_me, costo_base, costo_final,
    salario_nominal, salario_real,
    marca, pais_origen,
    tipo_trabajo,                    -- solo para tipo_id=128
    fecha_precio, indice_inegi, peso_kg,
    formula_costo_mn, formula_costo_me,
    indice_1..6,
    activo, es_basico,
    creado_por, creado_en, modificado_por, modificado_en,
    UNIQUE(proyecto_id, clave)
)
```

#### Bloque 7 — APU

```sql
apu_matrices (
    id, matriz_id, insumo_id,
    rendimiento, cantidad, precio,
    importe GENERATED ALWAYS AS (ROUND(cantidad * precio, 6)) STORED,
    formula, orden,
    creado_por, creado_en, modificado_por, modificado_en
)
-- matriz_id unificado (v3): referencia a concepto (id>0) o insumo compuesto (id<0)

apu_resumen_totales (
    id, matriz_id,
    materiales, mano_obra, herramienta, equipo,
    auxiliares, subcontratos, fletes, trabajos,
    costo_directo, indirectos_pct, financiamiento_pct,
    utilidad_pct, cargo_adicional_pct, precio_venta,
    modificado_en
)
```

Nota: `apu_auxiliares` fue eliminada. Los insumos compuestos se identifican
con `es_compuesto=1` en la tabla `insumos`.

#### Bloque 8 — Colaboración

```sql
notas      (id, concepto_id, usuario_id, texto, resuelta, creado_en, modificado_en)
historial  (id, sesion, tabla, registro_id, campo,
            valor_anterior, valor_nuevo, usuario_id, cambiado_en)
```

#### Bloque 9 — Schema version

```sql
schema_version (version, aplicado_en, descripcion)
-- v1: inicial, v2: renombres+limpieza, v3: matriz_id unificado
```

### Datos semilla

| Tabla | Registros |
|---|---|
| `usuarios` | 1 usuario local |
| `tipos_insumo` | 8 tipos (material, mano_obra, ..., trabajo) |
| `schema_version` | versión 3 |

### Queries frecuentes

```sql
-- Presupuesto completo ordenado por WBS
SELECT n.id, n.wbs, n.nivel, n.tipo, n.insumo_id,
       COALESCE(i.descripcion, n.descripcion) AS descripcion,
       n.cantidad, n.total,
       CASE n.estado WHEN 0 THEN 'Sin revisar' WHEN 1 THEN 'En revisión'
                     WHEN 2 THEN 'Verificado' WHEN 3 THEN 'Cuestionado'
       END AS estado_nombre
FROM estructura_presupuesto n
LEFT JOIN insumos i ON i.id = n.insumo_id
WHERE n.proyecto_id = ? AND n.activo = 1
ORDER BY n.wbs;

-- APU completo de un concepto o insumo compuesto
SELECT am.*, i.clave AS insumo_clave, i.descripcion AS insumo_descripcion,
       i.unidad AS insumo_unidad, t.clave AS tipo_clave, t.nombre AS tipo_nombre
FROM apu_matrices am
JOIN insumos i      ON i.id = am.insumo_id
JOIN tipos_insumo t ON t.id = i.tipo_id
WHERE am.matriz_id = ?
ORDER BY am.orden;
```

---

## 7. Decisiones de diseño (consolidadas)

### BD-01 — Un archivo .db por proyecto ✓
Cada proyecto es un archivo SQLite independiente. Se pueden compartir enviando
el archivo. Un error en un proyecto no afecta a los demás.

### BD-02 — Carpeta de datos del usuario ✓
Usa `platformdirs` para obtener la carpeta estándar del SO. Contiene
`config.json`, `proyectos/` y `logs/`.

### IMP-01 — Reimportación ⏳
Actualmente: borrar DB + reimportar. Merge inteligente pendiente.

### IMP-02 — Exportación a OPUS ⏳
Fuera del alcance actual. Requiere `dbfwrite` y generación de `.FPT`.

### FE-01 — Solo lectura hasta pulir lectura ✓
El frontend prioriza la visualización. Edición limitada a celdas del árbol
(clave, descripción, unidad, cantidad, precio).

### FE-02 — Ctrl+Z con interfaz migrable ✓
`HistorialMemoria` en el MVP. `HistorialDB` cuando llegue multi-usuario.
Toda la app usa la interfaz `Historial`, nunca la implementación directa.

### FE-03 — Búsqueda multi-columna ✓
Implementada con menú contextual en la barra de búsqueda.
Cada widget define sus columnas por defecto (`_search_cols`).

### FE-04 — Notas inline ⏳
Panel inline dentro de la fila del nodo. Pendiente hasta que el frontend
esté en modo edición (depende de FE-01).

### COL-01/02/03 — Colaboración ⏳
Login local, sincronización por archivo compartido, semáforo de confiabilidad.
La infraestructura de DB está lista; la lógica de UI pendiente.

### DIS-01 — PyInstaller ⏳
Pendiente hasta tener el lector de datos 100% funcional.
Considerar Nuitka como alternativa.

---

## 8. Explosión de insumos (en detalle)

### Niveles

| Nivel | Método | Filtro | Sigue conceptos intermedios |
|---|---|---|---|
| `basico` | bottom-up recursivo | `es_compuesto=0` | ✅ sí |
| `compuesto` | bottom-up recursivo | `es_compuesto=1` | ✅ sí |
| `primer_nivel` | SQL directo (agregado) | Sin filtro | ❌ no (solo 1 nivel) |

### Algoritmo bottom-up (básico y compuesto)

1. Carga todos los conceptos del presupuesto con sus cantidades (`budget_cant`).
2. Carga todos los insumos del proyecto (`insumos_map`).
3. Construye mapping `concepto_id → insumo_id` (por clave compartida).
4. Construye índice reverso `insumo_id → [matrices padre]` desde `apu_matrices`.
5. Para cada insumo que cumple el filtro (`es_compuesto` según nivel):
   - Busca sus padres en el índice reverso.
   - Para cada padre, calcula el multiplicador bottom-up (`_calc_mult`):
     - Si el padre es un concepto en el presupuesto: devuelve su cantidad.
     - Si es un concepto intermedio: busca su insumo y sigue recursivamente
       hacia arriba.
     - Si es un compuesto (matriz_id negativo): busca sus padres y sigue.
   - Acumula `cantidad × multiplicador`.
6. Post-procesa: filtra por tipos, calcula % global y % MO para herramienta.

### Herramienta

La columna PU para herramienta muestra el porcentaje sobre MO.

- **Básico/Compuesto:** `pct_mo = total / total_mo_global` (calculado en
  `_postprocesar` a partir de todos los items MO del resultado).
- **Primer nivel:** `pct_mo = total / SUM(am.precio * ep.cantidad)` (calculado
  en SQL desde el MO subtotal de los mismos APU donde aparece la herramienta).

El `setdefault` en `_postprocesar` asegura que si `pct_mo` ya viene calculado
desde SQL (primer nivel), se conserva; si no (básico/compuesto), se calcula
desde `total / total_mo`.

### Tipos de insumo (IDs)

| ID | Nombre | Bit |
|---|---|---|
| 1 | Material | 1 |
| 2 | Mano de obra | 2 |
| 4 | Herramienta | 4 |
| 8 | Equipo | 8 |
| 16 | Auxiliar | 16 |
| 32 | Concepto compuesto | 32 |
| 64 | Flete | 64 |
| 128 | Trabajo | 128 |

---

## 9. Setup de desarrollo

### Dependencias

```bash
pip install PySide6 dbfread platformdirs
```

- `PySide6` — obligatorio (Qt6 bindings).
- `dbfread` — solo para importación OPUS (opcional si solo se abren .db existentes).
- `platformdirs` — opcional (fallback a carpeta local).

### Ejecución

```bash
python main.py
```

### Importación de proyecto de muestra

Desde la app: toolbar PROYECTO → Importar OPUS → seleccionar carpeta con archivos DBF.

O desde Python:
```python
from backend.importar import importar
resultado = importar(r"carpeta_opus", "ruta_salida.db", nombre_proyecto="Mi Obra")
print(resultado)
# → {proyecto_id: 1, nodos: 172, insumos: 330, apu_matrices: 686, ...}
```

### Números de referencia (proyecto D60JALISCOT)

| Métrica | Esperado |
|---|---|
| Nodos totales | 172 |
| Nodos tipo concepto | 148 |
| Nodos tipo capítulo | 24 |
| Insumos | 330 |
| Insumos compuestos | 120 |
| APU matrices | 686 |
| APU resumen totales | 148 |
| Sobrecostos | 2 |

---

## 10. MVP vs v1.x

### Implementado (MVP)

| Funcionalidad | Estado |
|---|---|
| Importación OPUS (DBF → SQLite) | ✅ |
| Árbol jerárquico del presupuesto | ✅ |
| Vista APU de concepto/insumo | ✅ |
| Drill-down (doble clic → APU) | ✅ |
| Catálogo de insumos por tipo | ✅ |
| Explosión de insumos (3 niveles) | ✅ |
| Rastreo de insumo (dónde se usa) | ✅ |
| Búsqueda multi-columna | ✅ |
| 6 temas visuales QSS | ✅ |
| Persistencia de estado (header, tema) | ✅ |
| Barra de estado con tema y versión | ✅ |

### Pendiente (v1.x)

| Funcionalidad | Prioridad |
|---|---|
| Edición completa | Alta |
| Semáforo de confiabilidad (estado visual) | Alta |
| Sobrecostos editable | Alta |
| Ctrl+Z (deshacer/rehacer) | Media |
| Notas por nodo | Media |
| Login / selección de usuario | Media |
| Gestión de proveedores | Baja |
| Multi-moneda | Baja |
| Exportación a Excel/PDF | Baja |
| Exportación a OPUS | Baja |
| Empaquetado PyInstaller/Nuitka | Media |
| Testing framework | Media |
| Colaboración en red | Futura |

---

## Historial de migraciones de esquema

| Versión | Cambios clave |
|---|---|
| 1 | Esquema inicial con `nodos`, `apu_detalle`, `estados_nodo`, roles |
| 2 | Renombres (`nodos`→`estructura_presupuesto`, etc.), eliminar tablas no usadas, estado como entero, familias/subfamilias separadas |
| 3 | `concepto_id`+`insumo_compuesto_id`→`matriz_id` único, `es_compuesto` por presencia en `*F.DBF` |

No hay sistema de migraciones automáticas. El esquema se aplica en `schema.sql` directamente.
No modificar `schema.sql` en formas que rompan proyectos existentes durante la beta.

---

*Documento generado a partir del código fuente. Los docs legacy (`SCHEMA.md`,
`DECISIONES_PENDIENTES.md`, `GUIA_IMPLEMENTACION.md`, `CAMBIOS_SCHEMA_V2.md`)
se mantienen por referencia histórica.*
