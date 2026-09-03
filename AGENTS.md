# Open APU Studio — AGENTS.md

Actualizado: 2026-08-31 04:55 (hora local)
## Regla DE DESARROLLO
no conservar codigo viejo o migraciones de bases de datos con codigo antiguo si no funciona se rehace no se conserva nada antiguo
## Regla: NO subir a GitHub sin pedido expreso
Nunca hacer git push (ni commit) a menos que el usuario lo pida explícitamente.
Primero hacer los cambios, compilar/verificar, y esperar confirmación del usuario.
## Regla .md: fecha de modificación
Todo archivo .md generado debe incluir la fecha y hora de su última modificación
(ISO 8601, hora local) para que sea posible detectar cuándo el contenido está
desactualizado. Ejemplo al inicio o al final:
```
Actualizado: 2026-07-01 14:30 (hora local)
```

## Regla pre-commit
Antes de subir a GitHub: actualizar `docs/` (SCHEMA.md, DOCUMENTACION.md, planes/,
ARQUITECTURA_SERVICIOS.md, GUIA_CODIGO.md, GUIA_INTERFAZ.md, GUIA_VISUAL.md,
GUIA_GENERADOR_OBRA.md, DUPLICACION_Y_DEUDA.md) y revisar que comentarios en el
código no referencien columnas o tablas eliminadas.
El docstring o comentario que miente es peor que ningún comentario.

## Regla de testing
No subir a GitHub sin que el usuario pruebe primero. Esperar confirmación del usuario
antes de hacer push.

## Stack
- Python 3.11+ / PySide6 (Qt6) / SQLite+FTS5 / dbfread (import OPUS)
- simpleeval (fórmulas) / ezdxf (lector CAD) / reportlab + openpyxl (exportación)
- FastAPI + uvicorn + httpx + websockets (servidor multiusuario embebido)
- PyInstaller (dist)
- Targets: Windows (principal) + Linux (nativo desde inicio)
- Dependencias declaradas en `requirements.txt`

## Arquitectura — regla cardinal
**SQL solo vive en `backend/database/repos/`**. Si SQL aparece en UI, en `core.py`,
en `api_backends.py` o en `server/`, es error. Capas:

```
frontend/ (PySide6) → frontend/ventana/api.py (fachada) → backend/database/repos/ (SQL) → backend/database/db.py → SQLite (.db)
                                          └── HTTP (multiusuario) → server/servidor.py (FastAPI) → repos
```

### Local vs HTTP (multiusuario)
`frontend/ventana/api.py` es la fachada única para los widgets. Internamente
selecciona dos backends (ver `api_backends.py`):
- `_BackendLocal` — usa el `DataService` + repos en el mismo proceso.
- `_BackendHTTP` — habla con `server/servidor.py` vía `api_cliente.py` (httpx) y
  `ws_client.py` (WebSocket, invalidación de undo entre sesiones).
- La migración a HTTP está **en progreso**: coexisten métodos que delegan en
  `_BackendHTTP` con otros que usan el patrón `if self._use_http:` método por método.
  El protocolo normativo para terminarla (reglas R1-R9, contrato `ToqueApiBackend`,
  fases y definición de terminado) está en `docs/ARQUITECTURA_SERVICIOS.md`.
- En modo servidor, `server/servidor.py` es el ÚNICO proceso que toca el `.db`.

### Reglas de servicios (ver `docs/ARQUITECTURA_SERVICIOS.md`)
- **Repositorios:** Solo SQL. Sin eventos, sin validación de negocio.
- **Servicios:** Coordinan: validar → transacción → repo → commit → evento. Sin SQL.
- **Eventos:** Se emiten después del COMMIT, no antes. Contienen el registro completo post-update.
- **Transacciones:** Las abre el servicio, no el repositorio. `DataService.transaccion()` context manager.
- **Validación:** `SchemaRegistry` con Field types en Python. No inspecciona PRAGMA.
- **Extensibilidad:** Agregar una tabla = registrar el repo en `RepositoryRegistry`. No se toca `UpdateService`.

## Estructura actual
```
main.py                          ← Punto de entrada (QApplication, tema, ventana)
requirements.txt                 ← Dependencias (PySide6, dbfread, simpleeval, ezdxf, reportlab…)
backend/
  __init__.py                    ← Documentación del paquete
  formulas.py                    ← simpleeval vendereado: evaluar_formula, resolver_variables, ErrorFormula
  cad/
    __init__.py
    lector_dxf.py                ← Parseo DXF con ezdxf → DxfEntity/DxfLayer/DxfParseResult (colores ACI/TrueColor)
  database/
    db.py                        ← Conexión SQLite + aplicar schema.sql + Rutas (datos_usuario/) + Config (config.json)
    schema.sql                   ← Esquema completo (single file, no migraciones numeradas)
    core.py                      ← Lógica de negocio: árbol, métricas, recálculo, validación
    exceptions.py                ← ValidationError, DataServiceError, RepositoryError
    schema_registry.py           ← SchemaRegistry (Field types: FloatField, IntField, StringField, BoolField)
    event_bus.py                 ← EventBus + eventos semánticos (InsumoActualizado, ProyectoRecalculado, GeneradorActualizado…)
    repos/                       ← Repositorios (paquete, SQL vive aquí)
      __init__.py                ← Re-exporta todos los repos (NodoRepo, InsumoRepo, ApuMatricesRepo, …)
      base.py                    ← RepoBase (clase raíz, _update/_insert/_delete genéricos)
      proyecto.py                ← ProyectoRepo, FactoresSobrecostoRepo
      presupuesto.py             ← NodoRepo (capítulos y conceptos), ESTADO_COLOR/ESTADO_NOMBRE, actualizar_total()
      insumos.py                 ← InsumoRepo
      apu.py                     ← ApuMatricesRepo (componentes, matrices)
      recalculo.py               ← RecalculoRepo (recalcula totales bottom-up)
      catalogos.py               ← FamiliaRepo, SubfamiliaRepo, NotaRepo
      explosion.py               ← ExplosionRepo (explosión de insumos/matrices, porcentajes)
      diagnostico.py             ← DiagnosticoRepo (integridad del catálogo)
      formulas.py                ← VariableFormulaRepo (variables y fórmulas)
      generador.py               ← GeneradorRepo, GeneradorRenglonRepo (generadores de obra)
      historial.py               ← HistorialRepo (versiones / undo en el servidor)
      indirectos.py              ← IndirectoRepo (indirectos, plantillas, duración)
    services/                    ← Servicios de aplicación (coordina, no SQL)
      __init__.py
      repository_registry.py     ← RepositoryRegistry + crear_registry() (resuelve repo por nombre de entidad)
      data_service.py            ← DataService (transaccion/actualizar/insertar/eliminar/emitir — vía de escritura)
  importar/
    importar.py                  ← Importador OPUS 2010 (.DBF → SQLite, dbfread, cp850)
    schemas_opus.json            ← Esquemas OPUS por versión
  exportar/
    exportar_generadores_excel.py← Exportación a Excel de generadores (openpyxl, usada desde la UI)
    informe_pdf/
      latex.py                   ← Generación de PDF vía pdflatex (2 pasadas, requiere LaTeX instalado)
      latex/templates/presupuesto.tex ← Template .tex (se copia a datos_usuario/templates/)
server/
  __init__.py
  servidor.py                    ← Servidor FastAPI + WebSocket embebido; ÚNICO proceso que toca el .db en modo red
frontend/
  __init__.py                    ← Documentación del paquete
  temas/
    __init__.py                  ← Exportación del módulo
    temas.py                     ← Temas (modo + acento); persiste en config.json vía Config
    modo-oscuro.qss              ← Modo oscuro (default)
    modo-claro.qss               ← Modo claro
    acento-azul.qss              ← Acento azul (default, vacío)
    acento-rosa.qss              ← Acento rosa
    acento-cafe.qss              ← Acento café
    acento-verde.qss             ← Acento verde
  ventana/
    __init__.py                  ← Re-exporta VentanaPrincipal
    ventana.py                   ← Ventana principal (ensambla mixins)
    colores.py                   ← Paleta de colores (constantes RGB)
    iconos.py                    ← Registry de iconos SVG (lucide monocolor + icons8 color, tint, DPR)
    tipos_insumo.py              ← Tipos de insumo + ICONO_SVG
    ui_utils.py                  ← Utilidades de UI (estilos, helpers)
    api.py                       ← Api: fachada UI→backend (sin SQL, sin PySide6); despacha a _BackendLocal/_BackendHTTP
    api_backends.py              ← _BackendLocal / _BackendHTTP (migración local→HTTP en progreso)
    api_cliente.py               ← ApiCliente (cliente httpx al servidor)
    ws_client.py                 ← WebSocketClient (QThread; invalidación de undo entre sesiones)
    cad/                         ← Visor CAD / medición / cuantificación
      visor.py                   ← VisorCadWidget (QGraphicsView), CadTool
      medicion.py                ← Medición de distancias/áreas (Pt2)
      ortho.py                   ← Modo ortho
      auto_quantify.py           ← Cuantificación automática por capa (LayerQuantity)
      undo_stack.py              ← Undo de anotaciones (UndoState)
      exportar_excel.py          ← Exportación de renglones a Excel
      exportar_pdf.py            ← Exportación a PDF
    mixins/                      ← Paquete de mixins de la ventana (handlers de UI)
      __init__.py
      navegacion.py              ← HandlersMixin (navegación, búsqueda, paleta, vista; _PaletaComandos)
      toolbar.py                 ← ToolbarMixin (toolbar, temas, búsqueda)
      paneles.py                 ← PanelesMixin (sidebar, presupuesto, insumos; _ExploradorTree)
      gestion_proyectos.py       ← GestionProyectosMixin (abrir/cerrar/copiar/renombrar/eliminar/importar)
      informes.py                ← InformesMixin (generar PDF, compilar, vista previa)
      diag_dialogs.py            ← DiagDialogsMixin (depurar catálogos, hash, info proyecto)
      apu.py                     ← ApuMixin (pestañas APU, edición inline, navegación)
      rastreo.py                 ← RastreoMixin (rastreo de insumos, tabla de uso)
      explosion.py               ← ExplosionMixin (explosión de insumos/matrices, sobrecostos)
      generador.py               ← GeneradorMixin (generadores de obra, renglones, drag & drop)
    widgets/
      __init__.py
      base.py                    ← TreeTableWidget reutilizable, TabWidgetCerrable, ColumnaDef, _Delegate
      arbol.py                   ← TablaArbol (árbol jerárquico del presupuesto)
      insumos.py                 ← TablaInsumos (catálogo de insumos)
      apu.py                     ← TablaApuDetalle
      explosion.py               ← PestañaExplosion, DialogoExplosion, TablaExplosion
      generador.py               ← TablaGenerador
      filtros.py                 ← FilterDialog (filtros por columna)
      dialogs.py                 ← Diálogos reutilizables (ProjectDialog, InsumoDialog, EditarPrecioDialog…)
      ajustes.py                 ← DialogoAjustes
      ayuda.py                   ← DialogoAyuda
      config_impresion.py        ← DialogoConfigImpresion
      presupuesto_popup.py       ← PresupuestoPopup
assets/
  icons/                         ← Iconos Lucide (monocolor, recolorables por tint)
  icons8/                        ← Iconos Icons8 Color (116 SVGs mapeados, plano sin tint; mapeo en iconos.py)
  favicon.ico
datos_usuario/                   ← Datos de usuario (gitignored: proyectos/, reportes/, config.json)
  proyectos/*.db                 ← Un archivo .db = un proyecto
  reportes/                      ← PDF/TeX generados
  templates/                     ← Templates .tex del usuario (sobre Bundled)
  config.json                    ← Configuración (tema modo/acento, estado)
docs/
  SCHEMA.md                      ← Documentación del esquema SQL
  DECISIONES_PENDIENTES.md       ← Decisiones de diseño registradas
  DOCUMENTACION.md               ← Documentación general del proyecto
  ARQUITECTURA_SERVICIOS.md      ← Plan de arquitectura de servicios (EventBus, DataService, etc.)
  GUIA_VISUAL.md                 ← Guía de estilo visual para ventanas (colores, espaciado, componentes)
  GUIA_CODIGO.md                 ← Convenciones de código y decisiones de diseño
  GUIA_INTERFAZ.md               ← Guía de interfaz de usuario
  GUIA_GENERADOR_OBRA.md         ← Guía del módulo de generadores de obra
  DUPLICACION_Y_DEUDA.md         ← Deuda técnica y duplicación detectada
  PLAN_REPARACION.md             ← Auditoría y plan de reparación contra GUIA_INTERFAZ.md
  planes/
    PLAN_INSUMOS.md              ← Plan de transformación de insumos
    PLAN_FSR.md                  ← Plan FSR completo
    PLAN_PRESUPUESTO.md          ← Plan de presupuesto (ID-based)
    PLAN_FORMULAS_VARIABLES.md   ← Plan de fórmulas y variables
    PLAN_MULTIUSUARIO.md         ← Plan multiusuario (servidor HTTP/WebSocket)
tests/
  smoke_*.py                     ← Probar scripts de humo (sin framework; sin pytest aún)
```

## Decisiones técnicas (de docs/)
- **Formato archivo:** `.db` = SQLite. Un archivo = un proyecto. (ver `docs/SCHEMA.md`; la extensión `.presup` está deprecada)
- **Pragmas:** `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL` en `backend/database/db.py`
- **Búsqueda:** FTS5 con `tokenize='unicode61 remove_diacritics 1'`, triggers en `schema.sql`
- **Temas:** Sistema modo × acento: `frontend/temas/temas.py` carga modo-*.qss + acento-*.qss en runtime. Persistencia en `config.json` vía `backend/database/db.py::Config`. En `datos_usuario/`
- **Iconos:** Dos conjuntos SVG — `assets/icons/` (Lucide, tint) y `assets/icons8/` (color plano). Registry en `frontend/ventana/iconos.py`, activable con `set_iconos()`
- **OPUS import:** `dbfread` con `encoding='cp850'`, sistema de bits para tipos de insumo — `backend/importar/importar.py`
- **CAD:** `backend/cad/lector_dxf.py` (ezdxf) parsea el DXF; `frontend/ventana/cad/visor.py` lo visualiza y mide; `auto_quantify.py` cuantifica por capa
- **Esquema:** Single `schema.sql` aplicado por `db.py`. Si hay cambios futuros: migraciones numeradas en SQL (ver `docs/SCHEMA.md` sección migraciones)
- **Recálculo:** Bottom-up en Python desde `backend/database/repos/presupuesto.py::actualizar_total()` — `capítulos.total = SUM(hijos.total)`, sin bifurcación `importe`/`subtotal`
- **Total:** Columna unificada en `estructura_presupuesto` — reemplaza la antigua dualidad `importe` (GENERATED) + `subtotal`. Para conceptos se calcula como `cantidad × precio` (precio desde insumo o APU); para capítulos es `SUM(hijos.total)`.
- **FSR:** Manual via `insumos.factor_fsr`. `costo_directo` = base sin FSR. Fórmula: `costo_final = costo_directo × factor_fsr × factor_total`.
- **Fórmulas:** `simpleeval` vendereado como `backend/formulas.py`. Evaluación recursiva de variables desde `backend/database/repos/formulas.py::VariableFormulaRepo`. Aplica en `apu_matrices.formula` y `estructura_presupuesto.formula`.

## MVP vs v1.x
Delimitación exacta en `docs/DECISIONES_PENDIENTES.md` y `docs/SCHEMA.md` sección "Lo que falta".
- MVP: solo lectura, árbol presupuesto, APU, catálogo insumos, importación OPUS
- v1.x: edición, semáforo, notas, historial (Ctrl+Z), frentes, explosión insumos, proveedores
- Ya implementado de v1.x: edición, semáforo, notas, historial, explosión, generadores de obra
  (con visor CAD), indirectos, variables/fórmulas y multiusuario vía servidor HTTP/WebSocket.

## Paleta de colores (dark theme default)
- Fondo: `#12161D` / Panel: `#1B2330` / Cabeceras tabla: `#203244`
- Filas alternas: `#12161D` / `#19212E`
- Acento: `#7FAFD6` / Texto principal: `#E8EDF2` / Texto secundario: `#B7C0C8`
- Partidas: `#8B6FB5` / Subpartidas: `#5E9CA0`
- Semánticos: Success `#5B8A72`, Warning `#D5B39B`, Error `#A06A6A`

## Temas: Modo × Acento
- **2 modos:** `oscuro` / `claro` (fondos, texto, estructura general)
- **4 acentos:** `azul` / `rosa` / `cafe` / `verde` (toolbar, selección, tabs, botones)
- Combinación: `modo-{modo}.qss` + `acento-{acento}.qss` en runtime
- Persistencia: `tema_modo` + `tema_acento` en `config.json`
- Migración automática desde configs legacy con clave única `tema`

## Regla beta: sin migraciones
El proyecto está en beta. **Cualquier cambio en schema.sql rompe proyectos anteriores.**
No se escriben migraciones en `db.py`. Si se agrega una columna, se edita `schema.sql` directamente
y los proyectos viejos se consideran incompatibles (el usuario crea uno nuevo o eventualmente
se añade una herramienta de migración manual). Esto libera al agente de mantener compatibilidad
hacia atrás durante el desarrollo temprano.

## Ausencias conocidas (el agente no debe perder tiempo buscándolas)
- No hay testing framework definido — los `tests/smoke_*.py` son scripts de humo sueltos; decidir pytest u otro
- No hay licencia — decidir cuál
- No hay CI configurado
- **Multiusuario (`server/`, `api_backends.py`, `api_cliente.py`):** migración local→HTTP en progreso;
  coexiste el patrón delegado con `if self._use_http:` método por método en `api.py`. No desdoblar más lógica;
  terminar de moverla a `_BackendLocal`/`_BackendHTTP`.
- **Sobrecostos:** la tabla vieja `sobrecostos` (OPUS I.DBF) fue eliminada.
  Solo existe `factores_sobrecosto` con 5 porcentajes + `factor_total`
  (multiplicador compuesto). `costo_final = costo_directo * COALESCE(factor_total, 1.0)`.
  Ver `backend/database/repos/proyecto.py::FactoresSobrecostoRepo`.
- **Informe PDF:** requiere `pdflatex` instalado en PATH (genera `.tex` en `datos_usuario/reportes/` y compila).

## UI / Diseño
- Layout principal: sidebar (árbol) | contenido (tab + detalle) — ver `frontend/ventana/ventana.py`
- Paleta en `frontend/temas/modo-oscuro.qss`
- Estilo botones/inputs/tablas siguiendo el QSS existente (editar `.qss` para cambios globales)
- Tipografía: Segoe UI (Windows), fuente del sistema — `QFont` en `main.py:29`
- Espaciado: escala 4-8-12-16-24-32 px, no valores arbitrarios
- Temas: `frontend/temas/temas.py` carga `frontend/temas/*.qss` según `config.json`
- Iconos: dos conjuntos SVG con fallback vectorial — `frontend/ventana/iconos.py`
- Todos los widgets tabla heredan de `TreeTableWidget` en `frontend/ventana/widgets/base.py`

## Referencias
- Esquema DB completo: `docs/SCHEMA.md`
- Decisiones de diseño registradas: `docs/DECISIONES_PENDIENTES.md`
- Plan de transformación de insumos: `docs/planes/PLAN_INSUMOS.md`
- Plan FSR completo: `docs/planes/PLAN_FSR.md`
- Plan multiusuario: `docs/planes/PLAN_MULTIUSUARIO.md`
- Plan fórmulas y variables: `docs/planes/PLAN_FORMULAS_VARIABLES.md`
- Guía del módulo de generadores: `docs/GUIA_GENERADOR_OBRA.md`
- Datos de muestra: proyectos `.db` en `datos_usuario/proyectos/` (importar OPUS con `backend/importar/importar.py`)