# Open APU Studio — AGENTS.md

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
  db.py                          ← Conexión SQLite + aplicar schema.sql + Config (QSettings)
  schema.sql                     ← Esquema completo (single file, no migraciones numeradas)
  repos.py                       ← Todos los repositorios (insumos, nodos, conceptos, apu, búsqueda)
  core.py                        ← Lógica de negocio: árbol, métricas, recálculo, validación
  importar.py                    ← Importador OPUS 2010 (.DBF → SQLite)
frontend/
  __init__.py                    ← Documentación del paquete
  ventana.py                     ← Ventana principal con QTabWidget
  temas.py                       ← Temas (carga QSS según QSettings)
  widgets/
    base.py                      ← TreeTableWidget reutilizable
    arbol.py                     ← Tabla jerárquica del presupuesto
    insumos.py                   ← Tabla plana de catálogo de insumos
  temas/
    dark.qss                     ← Tema oscuro (default)
    light.qss                    ← Tema claro
    hybrid.qss                   ← Tema híbrido
docs/
  SCHEMA.md                      ← Documentación del esquema SQL
  DECISIONES_PENDIENTES.md       ← Decisiones de diseño registradas
  GUIA_IMPLEMENTACION.md         ← Guía de integración del importador
  Manual opus M1.pdf             ← Manual de referencia OPUS
```

## Decisiones técnicas (de docs/)
- **Formato archivo:** `.presup` = SQLite. Un archivo = un proyecto. (ver `docs/SCHEMA.md`)
- **Pragmas:** `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL` en `backend/db.py`
- **Búsqueda:** FTS5 con `tokenize='unicode61 remove_diacritics 1'`, triggers en `schema.sql`
- **Temas:** QSS intercambiables en runtime via `frontend/temas.py`, paleta en `themes/dark.qss`
- **OPUS import:** `dbfread` con `encoding='cp850'`, sistema de bits para tipos de insumo — `backend/importar.py`
- **Esquema:** Single `schema.sql` aplicado por `db.py`. Si hay cambios futuros: migraciones numeradas en SQL (ver `docs/SCHEMA.md` sección migraciones)
- **Recálculo:** Bottom-up en Python desde `backend/core.py::recalcular_subtotales()` — no se almacenan totales de partida/presupuesto, se calculan con SUM()
- **Importe:** Columna `GENERATED ALWAYS AS (cantidad * precio) STORED` en SQLite

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

## Ausencias conocidas (el agente no debe perder tiempo buscándolas)
- No hay `requirements.txt` — necesita PySide6, dbfread como mínimo
- No hay testing framework definido — decidir pytest u otro
- No hay licencia — decidir cuál
- No hay CI configurado

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
- Datos de muestra: `CASA EG/` (importar con `backend/importar.py`)
