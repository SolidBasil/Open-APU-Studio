# Guía: Generadores de obra (con captura de medidas desde CAD)

## 1. Qué es esto y por qué se hace

Hoy `estructura_presupuesto.cantidad` de un concepto se captura a mano o vía
un campo `formula` (una sola expresión). No hay forma de ver *de dónde salió*
ese número, ni de reutilizar un desglose de medición entre proyectos o
conceptos.

Se agrega el **generador de obra**: un documento de medición (ubicación ×
veces × largo × ancho × alto → subtotal, uno o más renglones) que:

1. Puede existir **solo**, sin estar ligado a ningún concepto — para armar
   cantidades mientras decides dónde van, o para tener el desglose de
   memoria de cálculo aparte del presupuesto.
2. Opcionalmente se liga a un concepto del presupuesto — y en ese caso su
   cantidad total se suma automáticamente a `estructura_presupuesto.cantidad`
   sin necesidad de un botón "aplicar".
3. Sus renglones pueden capturarse a mano, o midiendo directamente sobre un
   plano CAD (DXF) abierto dentro de la app — guardando siempre de dónde
   salió cada medida para poder auditarla o corregirla después.

Esta guía cubre **qué se construye, cómo y por qué**, en el orden en que se
va a implementar. No incluye código — es el documento que se aprueba antes
de escribirlo.

---

## 2. Alcance por fases

| Fase | Contenido | Depende de |
|---|---|---|
| **1** | Modelo de datos, `GeneradorRepo`, sincronización automática con el presupuesto, auditoría vía `historial`, UI de tabla editable a mano (sin CAD) | Nada — es la base |
| **2** | Visor CAD: importar DXF (`ezdxf`), render en pantalla, capas, pan/zoom, calibración de escala | Fase 1 |
| **3** | Herramientas de medición sobre el visor (línea, polígono/área, conteo, punto) con snap obligatorio → crean renglones automáticamente | Fase 2 |
| **4** (futuro, fuera de esta guía) | Exportar generador a PDF; DWG nativo vía ODA File Converter | — |

La Fase 1 es independiente del CAD por completo — se puede construir, probar
y usar (captura manual) sin que exista todavía el visor.

---

## 3. Modelo de datos

### 3.1 `generadores` — entidad independiente

```sql
CREATE TABLE generadores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    concepto_id     INTEGER REFERENCES estructura_presupuesto(id),  -- NULL = suelto
    nombre          TEXT    NOT NULL DEFAULT '',   -- "Excavación cepa perimetral"
    unidad          TEXT,                          -- opcional, informativa (m3, m2, pza...)
    cantidad_total  REAL    NOT NULL DEFAULT 0.0,   -- SUM(renglones activos), Python lo recalcula
    notas           TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

**Por qué `concepto_id` es nullable y no una tabla puente:** la relación es
muchos-generadores-a-un-concepto (varios generadores pueden sumar al mismo
concepto), pero cada generador solo apunta a **un** concepto a la vez. Una
FK nullable directa en `generadores` alcanza; no hace falta tabla puente
porque un generador nunca reparte su cantidad entre dos conceptos distintos.

**Por qué `cantidad_total` es columna real y no `GENERATED`:** sigue la
misma convención ya usada en `estructura_presupuesto.total` — Python la
recalcula bottom-up (aquí no hay árbol, pero sí una suma que depende de
otra tabla, y `GENERATED` de SQLite no puede sumar filas de otra tabla).

### 3.2 `generador_renglones` — cuelga de un generador, no de un concepto

```sql
CREATE TABLE generador_renglones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    generador_id    INTEGER NOT NULL REFERENCES generadores(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL DEFAULT 0,

    ubicacion       TEXT    NOT NULL DEFAULT '',   -- "Eje A-B, nivel 1"
    veces           REAL    NOT NULL DEFAULT 1,
    largo           REAL,
    ancho           REAL,
    alto            REAL,
    subtotal        REAL    NOT NULL DEFAULT 0.0,   -- ver 3.3

    origen          TEXT    NOT NULL DEFAULT 'manual' CHECK(origen IN ('manual', 'cad')),
    cad_archivo_id  INTEGER REFERENCES generador_cad_archivos(id),
    cad_capa        TEXT,
    cad_tipo_medicion TEXT CHECK(cad_tipo_medicion IN
                        ('punto', 'linea', 'polilinea', 'area', 'contador')),
    cad_geometria   TEXT,   -- JSON: [{"x":.., "y":..}, ...] — puntos exactos medidos

    notas           TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

### 3.3 Cómo se calcula `subtotal` (regla única, vale para manual y CAD)

```
subtotal = veces × (largo o 1) × (ancho o 1) × (alto o 1)
```

Los factores ausentes (`NULL`) cuentan como 1 — así un renglón manual típico
(veces × largo × ancho) y un renglón medido en CAD (que a veces solo trae
`largo` ya resuelto, ej. un área) usan la misma fórmula sin casos especiales.
Lo único que cambia según `cad_tipo_medicion` es **qué campo llena** el
visor CAD antes de guardar (ver sección 6).

### 3.4 `generador_cad_archivos` — DXF embebido en la base de datos

```sql
CREATE TABLE generador_cad_archivos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    nombre_archivo  TEXT    NOT NULL,
    contenido       BLOB    NOT NULL,              -- el DXF completo, no una ruta
    unidades        TEXT    NOT NULL DEFAULT 'm',   -- declaradas por $INSUNITS del DXF, o manual
    escala          REAL    NOT NULL DEFAULT 1.0,   -- corrección por calibración (sección 7)
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

**Por qué `BLOB` y no una ruta a disco:** ya decidido — el proyecto entero
es un único archivo `.presup` portable (`docs/SCHEMA.md`, "Formato
archivo"). Si el DXF viviera aparte, el proyecto se rompería en cuanto el
plano se moviera, se borrara, o se abriera el `.presup` en otra máquina.

---

## 4. Sincronización automática con el presupuesto

Regla acordada: **automática**, sin botón "aplicar" (a diferencia del panel
de Catálogo General, que sí es manual/reconciliación).

Flujo, respetando la regla cardinal del proyecto (repos = solo SQL,
servicios = validar → transacción → repo → commit → evento):

1. `GeneradorRepo` inserta/edita/borra el renglón (solo SQL).
2. Dentro de la misma transacción, el servicio:
   a. recalcula `generadores.cantidad_total = SUM(subtotal)` de renglones
      activos de ese generador;
   b. si ese generador tiene `concepto_id` asignado, recalcula
      `estructura_presupuesto.cantidad = SUM(cantidad_total)` de **todos**
      los generadores activos enlazados a ese concepto (no solo el que
      cambió — puede haber varios sumando al mismo concepto);
   c. si la operación fue **reasignar** un generador a otro concepto (o
      desvincularlo), se recalculan **ambos** conceptos: el de origen
      (pierde el aporte) y el de destino (lo gana);
   d. se reutiliza `RecalculoRepo.recalcular_proyecto()` ya existente para
      propagar `total` (cantidad × precio) hacia los capítulos padres.
3. Después del commit se emiten los eventos correspondientes (regla del
   proyecto: eventos solo después de commit exitoso).

---

## 5. Auditoría (quién cambió qué, cuándo)

El proyecto ya tiene un mecanismo genérico para esto: la tabla `historial`,
alimentada automáticamente por `DataService.actualizar()` (captura
`valor_anterior`/`valor_nuevo` antes de cada `UPDATE`, agrupado por
`sesion` para poder deshacer).

**Decisión:** las escrituras de `generadores` y `generador_renglones` pasan
por ese mismo mecanismo — no por llamadas directas al repo por fuera de
`DataService`. Esto da, gratis y consistente con el resto de la app:
- historial de cambios por renglón/generador (para auditar),
- integración con Ctrl+Z / Ctrl+Y cuando esa función esté activa,
- mismo patrón que ya conocen `insumos` y `estructura_presupuesto`.

---

## 6. Trazabilidad del origen físico de una medida CAD

No basta con saber que un renglón "vino de CAD" — hay que poder volver a
encontrar exactamente qué se midió. Por eso cada renglón con `origen='cad'`
guarda:

| Campo | Para qué |
|---|---|
| `cad_archivo_id` | qué plano (de los varios que puede tener el proyecto) |
| `cad_capa` | qué capa del DXF |
| `cad_tipo_medicion` | cómo interpretar la geometría (ver tabla abajo) |
| `cad_geometria` | los puntos exactos (JSON), para resaltar/reeditar la medida sobre el plano después |

| `cad_tipo_medicion` | Qué mide | Campo que llena |
|---|---|---|
| `punto` | marca de referencia sin magnitud propia | `veces` = número de puntos marcados |
| `linea` | distancia entre 2 puntos, o polilínea abierta | `largo` = longitud total |
| `polilinea` | ídem `linea` pero explícitamente multi-segmento | `largo` = suma de segmentos |
| `area` | polígono cerrado | `largo` = área (factor único; `ancho`/`alto` vacíos) |
| `contador` | conteo de símbolos/entidades (ej. puertas) | `veces` = número contado |

Esta tabla es la que decide qué campo llena el visor CAD antes de invocar
el mismo `guardar_renglon_generador()` que usa la captura manual — el
backend no distingue "vino de CAD" salvo para guardar la trazabilidad.

---

## 7. Visor CAD y calibración de escala (Fase 2)

- Lectura de DXF con **`ezdxf`** (pure-Python, no requiere AutoCAD
  instalado). Entidades soportadas inicialmente: `LINE`, `LWPOLYLINE`,
  `CIRCLE`, `ARC` — cubren la gran mayoría de planos arquitectónicos de
  obra civil. `ELLIPSE`/`HATCH` se agregan si hacen falta después.
- **DWG**: se integra el **ODA File Converter** como subproceso externo
  (decisión ya tomada) — convierte DWG→DXF antes de leer con `ezdxf`. Es un
  ejecutable, no una librería Python, así que se empaqueta aparte y se
  invoca desde `backend/cad/`.
- **Render**: `QGraphicsView`/`QGraphicsScene` de PySide6, con pan/zoom y
  un panel de capas (mostrar/ocultar por `cad_capa`), igual patrón visual
  que el resto de paneles de la app (`TreeTableWidget` para el panel de
  capas).
- **Calibración de escala**: muchos DXF no vienen a escala real (a veces en
  mm, a veces con unidades arbitrarias). Se resuelve con el método estándar
  de dos clics: el usuario marca dos puntos sobre una medida conocida del
  plano (ej. un acotado que dice "3.50 m") y captura esa distancia real. La
  app calcula `escala = distancia_real / distancia_en_el_dibujo` y la guarda
  en `generador_cad_archivos.escala`. Todas las medidas posteriores sobre
  ese archivo se corrigen con ese factor.

---

## 8. Herramientas de medición y snap (Fase 3)

- **Snap obligatorio** (decisión ya tomada) a los puntos característicos de
  las entidades DXF: extremos de línea/polilínea, punto medio de segmento,
  intersección entre dos entidades. Tolerancia en unidades de mundo (no en
  píxeles de pantalla, para que no cambie con el zoom). Si dos candidatos
  empatan en distancia, gana el extremo sobre el punto medio.
- **Seguridad en el cálculo de área**: un polígono trazado a mano puede
  autointersectarse (un trazo en forma de "moño"), lo que hace que la
  fórmula de área estándar (shoelace) dé un número silenciosamente
  incorrecto — a veces hasta 0. Antes de guardar un renglón de tipo `area`
  se valida esto; si el polígono es inválido, se avisa en vez de guardar un
  `subtotal` mal calculado sin que el usuario se dé cuenta.
- Al cerrar una medición (línea, polígono, punto o conteo), se abre un
  diálogo para asignar `ubicacion` y confirmar antes de crear el renglón —
  la medida no se guarda "a ciegas".

---

## 9. Backend — archivos nuevos / afectados

```
backend/database/schema.sql                ← tablas nuevas (sección 3), bump de versión
docs/SCHEMA.md                             ← documentar tablas nuevas
backend/database/repos/generador.py        ← GeneradorRepo (SQL puro):
                                               CRUD generadores, CRUD renglones,
                                               CRUD archivos CAD, cálculo de subtotal,
                                               recálculo de cantidad_total y de
                                               estructura_presupuesto.cantidad
backend/database/services/data_service.py  ← guardar_renglon_generador(),
                                               eliminar_renglon_generador(),
                                               reasignar_generador() — cada una
                                               envuelta en transacción + historial + evento
backend/database/event_bus.py              ← evento nuevo GeneradorActualizado
backend/database/services/repository_registry.py ← registrar "generadores" y
                                               "generador_renglones"
backend/cad/                               ← paquete nuevo (Fase 2)
  lector_dxf.py                             ← parse_dxf(bytes) -> entidades normalizadas
  convertidor_dwg.py                        ← wrapper del subproceso ODA File Converter
```

## 10. Frontend — archivos nuevos / afectados

```
frontend/ventana/widgets/generador.py      ← TablaGenerador (hereda TreeTableWidget,
                                               mismo patrón que TablaApuDetalle)
frontend/ventana/generador/                ← paquete nuevo, panel independiente
                                               (lista de generadores del proyecto,
                                               ligados y sueltos, con selector de
                                               concepto opcional)
frontend/ventana/cad/                      ← paquete nuevo (Fase 2/3)
  visor.py                                  ← VisorCadWidget (QGraphicsView), capas,
                                               pan/zoom, calibración
  medicion.py                               ← herramientas de medición + snap
  calibracion.py                            ← diálogo de calibración de dos clics
```

El panel de generadores vive como sección propia (no anidado dentro de la
pestaña de un concepto), justamente porque un generador puede no tener
concepto — coherente con la decisión de mantenerlos separados.

---

## 11. Decisión pendiente de confirmar antes de programar Fase 3

**Auto-quantify por capa**: además de medir entidad por entidad a mano, se
podría ofrecer seleccionar una capa completa del DXF y que la app proponga
automáticamente un renglón agregado (Σ área, Σ longitud, o conteo, según
domine esa capa) para revisar y aceptar — ahorra mucho clic en planos con
muchas entidades repetidas (ej. todos los muros de una capa "MUROS").

¿Entra en el alcance de la Fase 3, o la primera versión es solo medición
entidad-por-entidad y esto se evalúa después como Fase 3b?

---

## 12. Orden de implementación

1. **Fase 1** — schema + `GeneradorRepo` + `DataService` + eventos +
   `TablaGenerador` + panel de generadores. Entregable: generador funcional
   de punta a punta sin CAD, incluida la sincronización automática y la
   auditoría.
2. Confirmar la decisión de la sección 11.
3. **Fase 2** — visor DXF + calibración.
4. **Fase 3** — herramientas de medición + snap → generan renglones.

---

Actualizado: 2026-07-14 (hora local)
