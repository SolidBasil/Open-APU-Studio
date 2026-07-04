# Open APU Studio — AGENTS.md

Actualizado: 2026-07-03 19:45 (hora local)

## Regla .md: fecha de modificación
Todo archivo .md generado debe incluir la fecha y hora de su última modificación
(ISO 8601, hora local) para que sea posible detectar cuándo el contenido está
desactualizado. Ejemplo al inicio o al final:
```
Actualizado: 2026-07-01 14:30 (hora local)
```

## Regla pre-commit
Antes de subir a GitHub: actualizar `docs/` (SCHEMA.md, DOCUMENTACION.md, planes/)
y revisar que comentarios en el código no referencien columnas o tablas eliminadas.
El docstring o comentario que miente es peor que ningún comentario.

## Stack
- Python 3.11+ / PySide6 (Qt6) / SQLite+FTS5 / dbfread (import OPUS) / PyInstaller (dist)
- Targets: Windows (principal) + Linux (nativo desde inicio)

## Arquitectura — regla cardinal
**SQL solo vive en `backend/database/repos/`**. Si SQL aparece en UI o en `core.py`, es error. Capas:
```
frontend/ (PySide6) → frontend/ventana/api.py (fachada) → backend/database/repos/ (SQL) → backend/database/db.py → SQLite (.presup)
```

### Reglas de servicios (ver `docs/ARQUITECTURA_SERVICIOS.md`)
- **Repositorios:** Solo SQL. Sin eventos, sin validación de negocio.
- **Servicios:** Coordinan: validar → transacción → repo → commit → evento. Sin SQL.
- **Eventos:** Se emiten después del COMMIT, no antes. Contienen el registro completo post-update.
- **Transacciones:** Las abre el servicio, no el repositorio. `Database.transaction()` context manager.
- **Validación:** `SchemaRegistry` con Field types en Python. No inspecciona PRAGMA.
- **Extensibilidad:** Agregar una tabla = registrar el repo en `RepositoryRegistry`. No se toca `UpdateService`.

## Estructura actual
```
main.py                          ← Punto de entrada
backend/
  __init__.py                    ← Documentación del paquete
  database/
    db.py                        ← Conexión SQLite + aplicar schema.sql + Config (JSON)
    schema.sql                   ← Esquema completo (single file, no migraciones numeradas)
    core.py                      ← Lógica de negocio: árbol, métricas, recálculo, validación
    repos/                       ← Repositorios (paquete, SQL vive aquí)
      __init__.py                ← Re-exporta todos los repos
      base.py                    ← RepoBase (clase raíz, _update/_insert/_delete genéricos)
      proyecto.py                ← ProyectoRepo, FactoresSobrecostoRepo
      presupuesto.py             ← NodoRepo (capítulos y conceptos del árbol)
      insumos.py                 ← InsumoRepo
      apu.py                     ← ApuMatricesRepo
      recalculo.py               ← RecalculoRepo
      catalogos.py               ← FamiliaRepo, SubfamiliaRepo, NotaRepo
      explosion.py               ← ExplosionRepo
      diagnostico.py             ← DiagnosticoRepo (integridad del catálogo)
    services/                    ← Servicios de aplicación (coordina, no SQL)
      __init__.py
      repository_registry.py     ← RepositoryRegistry (resuelve repo por nombre de entidad)
      data_service.py            ← DataService (actualizar / insertar / eliminar — único servicio de escritura)
    schema_registry.py           ← SchemaRegistry (Field types + reglas de validación)
    event_bus.py                 ← EventBus + eventos semánticos
  importar/
    importar.py                  ← Importador OPUS 2010 (.DBF → SQLite)
    schemas_opus.json            ← Esquemas OPUS por versión
  exportar/
    exportar.py                  ← Exportación a formatos estándar (rota, no mantenida)
    informe_pdf/
      latex.py                   ← Generación de PDF vía LaTeX
      latex/templates/           ← Templates .tex
frontend/
  __init__.py                    ← Documentación del paquete
  temas/
    __init__.py                  ← Exportación del módulo
    temas.py                     ← Temas (modo + acento)
    modo-oscuro.qss              ← Modo oscuro (default)
    modo-claro.qss               ← Modo claro
    acento-azul.qss              ← Acento azul (default, vacío)
    acento-rosa.qss              ← Acento rosa
    acento-cafe.qss              ← Acento café
    acento-verde.qss             ← Acento verde
  ventana/
    __init__.py                  ← Re-exporta VentanaPrincipal
    ventana.py                   ← Ventana principal (ensambla mixins)
    toolbar.py                   ← ToolbarMixin: toolbar, temas, búsqueda
    api.py                       ← Api: fachada UI→backend (sin SQL, sin PySide6)
    paneles.py                   ← PanelesMixin: sidebar, presupuesto, insumos, buscador
    handlers/                    ← Paquete de handlers de eventos
      __init__.py                ← HandlersMixin (navegación, búsqueda, vista, adjuntos)
      gestion_proyectos.py       ← GestionProyectosMixin (abrir/cerrar/copiar/renombrar/eliminar/importar)
      informes.py                ← InformesMixin (generar PDF, compilar, vista previa)
      diag_dialogs.py            ← DiagDialogsMixin (depurar catálogos, hash, info proyecto)
    apu/                         ← Paquete de mixins de APU
      __init__.py                ← Re-exporta ApuMixin, RastreoMixin, ExplosionMixin
      apu.py                     ← ApuMixin (pestañas APU, edición inline, navegación)
      rastreo.py                 ← RastreoMixin (rastreo de insumos, tabla de uso)
      explosion.py               ← ExplosionMixin (explosión de insumos/matrices, sobrecostos)
    widgets/
      __init__.py
      base.py                    ← TreeTableWidget reutilizable (header persistence)
      arbol.py                   ← TablaArbol (árbol jerárquico del presupuesto)
      insumos.py                 ← TablaInsumos (catálogo de insumos)
      dialogs.py                 ← Diálogos reutilizables
      ajustes.py                 ← Diálogo de ajustes
      explosion.py               ← PestañaExplosion, DialogoExplosion
docs/
  SCHEMA.md                      ← Documentación del esquema SQL
  DECISIONES_PENDIENTES.md       ← Decisiones de diseño registradas
  DOCUMENTACION.md               ← Documentación general del proyecto
  ARQUITECTURA_SERVICIOS.md      ← Plan de arquitectura de servicios (EventBus, UpdateService, etc.)
  planes/
    PLAN_INSUMOS.md              ← Plan de transformación de insumos
    PLAN_FSR.md                  ← Plan FSR completo
    PLAN_PRESUPUESTO.md          ← Plan de presupuesto (ID-based)
```

## Decisiones técnicas (de docs/)
- **Formato archivo:** `.presup` = SQLite. Un archivo = un proyecto. (ver `docs/SCHEMA.md`)
- **Pragmas:** `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL` en `backend/db.py`
- **Búsqueda:** FTS5 con `tokenize='unicode61 remove_diacritics 1'`, triggers en `schema.sql`
- **Temas:** Sistema modo × acento: `frontend/temas/temas.py` carga modo-*.qss + acento-*.qss en runtime
- **OPUS import:** `dbfread` con `encoding='cp850'`, sistema de bits para tipos de insumo — `backend/importar.py`
- **Esquema:** Single `schema.sql` aplicado por `db.py`. Si hay cambios futuros: migraciones numeradas en SQL (ver `docs/SCHEMA.md` sección migraciones)
- **Recálculo:** Bottom-up en Python desde `backend/database/repos/presupuesto.py::actualizar_total()` — `capítulos.total = SUM(hijos.total)`, sin bifurcación `importe`/`subtotal`
- **Total:** Columna unificada en `estructura_presupuesto` — reemplaza la antigua dualidad `importe` (GENERATED) + `subtotal`. Para conceptos se calcula como `cantidad × precio` (precio desde insumo o APU); para capítulos es `SUM(hijos.total)`.
- **FSR:** Dos modos: calculado desde `insumos.catfsr → factores_fsr` o manual (`insumos.factor_fsr`). `salario_real = salario_nominal × COALESCE(factor_fsr, 1.0)`
- **Fórmulas:** `simpleeval` vendereado como `backend/formulas.py`. Evaluación recursiva de variables desde `variables_formula`. Aplica en `apu_matrices.formula` y `estructura_presupuesto.formula`.

## MVP vs v1.x
Delimitación exacta en `docs/DECISIONES_PENDIENTES.md` y `docs/SCHEMA.md` sección "Lo que falta".
- MVP: solo lectura, árbol presupuesto, APU, catálogo insumos, importación OPUS
- v1.x: edición, semáforo, notas, historial (Ctrl+Z), frentes, explosión insumos, proveedores

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
- No hay `requirements.txt` — necesita PySide6, dbfread como mínimo
- No hay testing framework definido — decidir pytest u otro
- No hay licencia — decidir cuál
- No hay CI configurado
- **Exportación (`backend/exportar/`):** rota/incompleta tras cambios de schema.
  `exportar.py` se conserva como referencia para cuando se quiera restaurar, pero
  no se invoca desde la UI y no se mantiene activamente.
- **Sobrecostos:** la tabla vieja `sobrecostos` (OPUS I.DBF) fue eliminada.
  Solo existe `factores_sobrecosto` con 5 porcentajes + `factor_total`
  (multiplicador compuesto). `costo_final = costo_directo * COALESCE(factor_total, 1.0)`.
  Ver `backend/database/repos/proyecto.py::FactoresSobrecostoRepo`.

## UI / Diseño
- Layout principal: sidebar (árbol) | contenido (tab + detalle) — ver `frontend/ventana.py`
- Paleta en `frontend/temas/modo-oscuro.qss`
- Estilo botones/inputs/tablas siguiendo el QSS existente (editar `.qss` para cambios globales)
- Tipografía: Segoe UI (Windows), fuente del sistema — `QFont` en `main.py:21`
- Espaciado: escala 4-8-12-16-24-32 px, no valores arbitrarios
- Temas: `frontend/temas/temas.py` carga `frontend/temas/*.qss` según `QSettings`
- Todos los widgets tabla heredan de `TreeTableWidget` en `frontend/ventana/widgets/base.py`

## Referencias
- Esquema DB completo: `docs/SCHEMA.md`
- Decisiones de diseño registradas: `docs/DECISIONES_PENDIENTES.md`
- Plan de transformación de insumos: `docs/planes/PLAN_INSUMOS.md`
- Plan FSR completo: `docs/planes/PLAN_FSR.md`
- Datos de muestra: `CASA EG/` (importar con `backend/importar.py`)
