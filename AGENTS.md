# Open APU Studio — AGENTS.md

## Stack
- Python 3.11+ / PySide6 (Qt6) / SQLite+FTS5 / LaTeX (PDF) / PyInstaller (dist)
- Targets: Windows (principal) + Linux (nativo desde inicio)

## Arquitectura — regla cardinal
**SQL solo vive en `backend/db/repos/`**. Si SQL aparece en UI o servicios, es error. Capas:
```
frontend/ui (PySide6) → backend/servicios (lógica) → backend/db/repos (SQL) → SQLite (.presup)
```

## Estructura actual
```
main.py
backend/
  __init__.py
  db/
    conexion.py
    migraciones/     ← archivos .sql numerados, tabla schema_version
    repos/           ← base.py, insumos.py, conceptos.py, partidas.py, apu.py
  servicios/         ← importador_opus.py
  opus/              ← proxy a Conversor de opus/backend/core.py
frontend/
  __init__.py
  ui/
    ventana_principal.py
    modelos/
    widgets/
  themes/            ← dark.qss, light.qss
  theme_manager.py   ← ThemeManager con QSettings
Conversor de opus/   ← standalone, importado vía backend/opus/
```

## Decisiones técnicas (de docs/vision_producto.md)
- Formato archivo: `.presup` = SQLite. Un archivo = un proyecto.
- Pragmas siempre activos: `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL`
- Búsqueda: FTS5 con `tokenize='unicode61 remove_diacritics 1'`, triggers automáticos
- Temas: QSS intercambiables en runtime, paleta en docs/Guia diseño.md
- OPUS import: `dbfread` con `encoding='cp850'`, sistema de bits para tipos de insumo
- Migraciones: `.sql` numerados, aplicados en orden al abrir proyecto
- Recálculo en cascada: insumo → apu_componentes → apu_resumen → conceptos → totales (SUM en query)
- Totales de partida/presupuesto no se almacenan — se calculan con SUM()

## MVP vs v1.x
Delimitación exacta en `docs/vision_producto.md` sección "Funciones y características".
- MVP: gestión proyectos, catálogo conceptos, APU, catálogo insumos, presupuesto, reportes básicos
- v1.x: frentes, explosión de insumos, actualización precios, búsqueda global, catálogos reutilizables

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
- No hay `.gitignore`
- No hay CI configurado

## UI / Diseño
- Layout principal: `docs/Guia diseño.md` sección 9 (sidebar | contenido | panel detalle)
- Paleta en `themes/dark.qss`, roles y semántica en `docs/Guia diseño.md` sección 3
- Estilo botones/inputs/tablas: `docs/Guia diseño.md` secciones 10-12
- Tipografía: Inter (sistema), escala en `docs/Guia diseño.md` sección 5
- Espaciado: escala 4-8-12-16-24-32 px, no valores arbitrarios
- Temas: `frontend/theme_manager.py` carga `frontend/themes/*.qss` según QSettings

## Referencias
- Visión completa del producto: `docs/vision_producto.md`
- Guía de diseño visual (PySide6/QSS): `docs/Guia diseño.md`
- Compatibilidad OPUS: `docs/compatibilidad_opus.md`
- Formato archivos OPUS: `docs/GUIA_FORMATOS-OPUS.md`
- Datos de muestra: `CASA EG/`
