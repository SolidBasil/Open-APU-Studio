# Open APU Studio — AGENTS.md

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
**SQL solo vive en `backend/repos.py`**. Si SQL aparece en UI o en `core.py`, es error. Capas:
```
frontend/ (PySide6) → backend/core.py (lógica) → backend/repos.py (SQL) → backend/db.py → SQLite (.presup)
```

## Estructura actual
```
main.py                          ← Punto de entrada
backend/
  __init__.py                    ← Documentación del paquete
  database/
    db.py                        ← Conexión SQLite + aplicar schema.sql + Config (JSON)
    schema.sql                   ← Esquema completo (single file, no migraciones numeradas)
    repos.py                     ← Todos los repositorios (insumos, nodos, conceptos, apu, búsqueda)
    core.py                      ← Lógica de negocio: árbol, métricas, recálculo, validación
  importar/
    importar.py                  ← Importador OPUS 2010 (.DBF → SQLite)
    schemas_opus.json            ← Esquemas OPUS por versión
  exportar/
    exportar.py                  ← Exportación a formatos estándar
    exportar_plantillas.py       ← Plantillas de exportación
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
    ventana.py                   ← Ventana principal con QTabWidget (mixin host)
    toolbar.py                   ← Toolbar, temas, búsqueda
    paneles.py                   ← Paneles de contenido
    api.py                       ← Api de backend para UI
    handlers.py                  ← Handlers de eventos y navegación
    widgets/
      base.py                    ← TreeTableWidget reutilizable
      arbol.py                   ← Tabla jerárquica del presupuesto
      insumos.py                 ← Tabla plana de catálogo de insumos
      dialogs.py                 ← Diálogos reutilizables
      ajustes.py                 ← Diálogo de ajustes
      explosion.py               ← Explosión de insumos
docs/
  SCHEMA.md                      ← Documentación del esquema SQL
  DECISIONES_PENDIENTES.md       ← Decisiones de diseño registradas
  GUIA_IMPLEMENTACION.md         ← Guía de integración del importador
  DOCUMENTACION.md               ← Documentación general del proyecto
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
- **Recálculo:** Bottom-up en Python desde `backend/repos.py::actualizar_total()` — `capítulos.total = SUM(hijos.total)`, sin bifurcación `importe`/`subtotal`
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
- Paleta en `frontend/temas/dark.qss`
- Estilo botones/inputs/tablas siguiendo el QSS existente (editar `.qss` para cambios globales)
- Tipografía: Segoe UI (Windows), fuente del sistema — `QFont` en `main.py:21`
- Espaciado: escala 4-8-12-16-24-32 px, no valores arbitrarios
- Temas: `frontend/temas.py` carga `frontend/temas/*.qss` según `QSettings`
- Todos los widgets tabla heredan de `TreeTableWidget` en `frontend/widgets/base.py`

## Referencias
- Esquema DB completo: `docs/SCHEMA.md`
- Decisiones de diseño registradas: `docs/DECISIONES_PENDIENTES.md`
- Guía de implementación del importador: `docs/GUIA_IMPLEMENTACION.md`
- Plan de transformación de insumos: `docs/planes/PLAN_INSUMOS.md`
- Plan FSR completo: `docs/planes/PLAN_FSR.md`
- Datos de muestra: `CASA EG/` (importar con `backend/importar.py`)
