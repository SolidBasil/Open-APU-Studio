# Open APU Studio

Aplicación de escritorio para elaborar y analizar presupuestos de construcción
con **Análisis de Precios Unitarios (APU)**. Alternativa libre para constructoras
e ingenieros pequeños que no necesitan (o no pueden costear) licencias de OPUS
o Neodata.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Qt](https://img.shields.io/badge/Qt-PySide6-green)
![Plataforma](https://img.shields.io/badge/Windows%20%7C%20Linux-soportado-orange)

## Características

- **Presupuesto jerárquico** — capítulos y conceptos con drag & drop, selección
  múltiple, edición in-line estilo Excel y estados de revisión (semáforo).
- **Catálogo de insumos** — materiales, mano de obra, herramientas, equipos y
  fletes, con familias/subfamilias, deduplicación por hash y precios.
- **APU** — desglose de conceptos con matrices, sub-APUs, insumos compuestos,
  fórmulas (`simpleeval`) y recálculo bottom-up del total de obra.
- **Explosión de insumos** — insumos y matrices por concepto, porcentajes de
  participación y factores de sobrecosto (indirectos, financiero, etc.).
- **Generadores de obra** — renglones por concepto con **visor CAD (DXF)**
  integrado: medición de distancias/áreas y cuantificación automática a celdas.
- **Importación OPUS 2010** — proyectos y catálogos desde archivos DBF (cp850).
- **Informes** — presupuesto y explosión a LaTeX/PDF, exportación a Excel.
- **Multiusuario ligero** — servidor embebido (HTTP/WebSocket) para trabajar
  en red con invalidación de undo entre sesiones.
- **Temas** — modo oscuro/claro × 4 acentos, y dos conjuntos de iconos SVG.

## Formato de proyecto

Un proyecto = un archivo SQLite (`.db`) en `datos_usuario/proyectos/`.
Esquema documentado en [`docs/SCHEMA.md`](docs/SCHEMA.md).

## Instalación

Requiere Python 3.11+.

```bash
pip install -r requirements.txt
python main.py
```

## Estructura

```
main.py                  ← punto de entrada
backend/
  database/              ← SQLite, schema.sql, repos (SQL solo aquí), servicios
  importar/              ← importador OPUS 2010 (.DBF)
  exportar/              ← informes LaTeX/PDF
  cad/                   ← lector DXF para generadores
frontend/
  ventana/               ← ventana principal, mixins, widgets, iconos SVG
  temas/                 ← temas QSS (modo × acento)
server/                  ← servidor embebido multiusuario
docs/                    ← documentación completa (arquitectura, schema, guías)
tests/                   ← pruebas de humo (QT_QPA_PLATFORM=offscreen)
datos_usuario/           ← proyectos y preferencias (no versionado)
```

## Arquitectura

Regla cardinal: **SQL solo vive en `backend/database/repos/`**.
La UI habla con la fachada `Api` → servicios → repos → SQLite.
Eventos semánticos (`ProyectoRecalculado`, `InsumoActualizado`…) se emiten
después del commit. Detalles en [`docs/DOCUMENTACION.md`](docs/DOCUMENTACION.md)
y [`docs/GUIA_CODIGO.md`](docs/GUIA_CODIGO.md).

## Pruebas de humo

```bash
QT_QPA_PLATFORM=offscreen python3 tests/smoke_drag_drop_arbol.py
```

## Estado

Beta — el esquema puede cambiar entre versiones sin migraciones
(los proyectos viejos se consideran incompatibles; ver `docs/SCHEMA.md`).

## Licencia

Sin definir aún.
