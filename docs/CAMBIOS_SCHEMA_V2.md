# Cambios al esquema — Versión 2

Documento que consolida todas las decisiones de rediseño del schema
antes de implementarlas. Una vez aprobado, se aplican todos de una sola pasada.

---

## 1. Tablas que se eliminan

| Tabla | Razón |
|---|---|
| `roles` | App monousuario — nunca se activa |
| `tipos_herramienta` | Nunca se llena, ningún código la usa |
| `tipos_equipo` | Ídem |
| `tipos_material` | Ídem |
| `estados_nodo` | Se colapsa a columna en `estructura_presupuesto` |

---

## 2. Tablas que se simplifican

### `usuarios`
Se elimina la columna `rol_id` y su FK a `roles`.
Queda solo `id`, `nombre`, `email`, `activo`, `creado_en`, `ultimo_acceso`.

### `insumos`
Se eliminan las columnas:
- `tipo_herramienta_id` (FK a tipos_herramienta eliminada)
- `tipo_equipo_id` (FK a tipos_equipo eliminada)
- `tipo_material_id` (FK a tipos_material eliminada)

Se agrega una columna:
- `tipo_trabajo TEXT CHECK(tipo_trabajo IN ('subcontrato','acarreo','destajo'))` — solo aplica cuando `tipo_id = 128`, NULL en el resto

---

## 3. Tablas que se renombran

| Nombre actual | Nombre nuevo | Razón |
|---|---|---|
| `nodos` | `estructura_presupuesto` | Describe exactamente el contenido |
| `apu_nodos` | `apu_auxiliares` | Son insumos compuestos con APU propio |
| `apu_detalle` | `apu_componentes` | Cada fila es un componente del APU |
| `apu_totales` | `apu_resumen` | Es el resumen por tipo de costo |
| `pie_precios` | `sobrecostos` | Término más usado en obra |
| `proyecto_config` | `configuracion_proyecto` | Más claro al leerlo |

Sin cambio: `insumos`, `proyectos`, `auxiliares`, `notas`, `historial`, `proveedores`

---

## 4. Cambio en estados del nodo

**Se elimina** la tabla `estados_nodo` y su JOIN en todas las queries.

**Se agrega** la columna `estado` en `estructura_presupuesto`:
```sql
estado INTEGER NOT NULL DEFAULT 0
```

| Valor | Significado | Color (frontend) |
|---|---|---|
| 0 | Sin revisar | `#808080` gris |
| 1 | En revisión | `#F5A623` ámbar |
| 2 | Verificado | `#4CAF7D` verde |
| 3 | Cuestionado | `#E05252` rojo |

El frontend mapea el entero al color — sin JOIN, sin tabla auxiliar.

---

## 5. Catálogo de tipos de insumo actualizado

La tabla `tipos_insumo` se amplía con dos tipos nuevos para fletes y trabajos.
Los ids siguen el sistema de bits de OPUS:

| id | clave | nombre |
|---|---|---|
| 1 | `material` | Material |
| 2 | `mano_obra` | Mano de obra |
| 4 | `herramienta` | Herramienta |
| 8 | `equipo` | Equipo |
| 16 | `auxiliar` | Auxiliar |
| 32 | `concepto` | Concepto compuesto |
| 64 | `flete` | Flete |
| 128 | `trabajo` | Trabajo |

---

## 6. Familias y subfamilias — dos tablas separadas

Se reemplaza la tabla `familias` (árbol con `padre_id`) por dos tablas independientes,
reflejando cómo OPUS los trata como dos campos distintos en la captura:

```sql
CREATE TABLE familias (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL,
    activo  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE subfamilias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    familia_id  INTEGER NOT NULL REFERENCES familias(id),
    nombre      TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);
```

En `insumos`, las columnas cambian de:
```sql
familia_id  INTEGER REFERENCES familias(id)
```
a:
```sql
familia_id     INTEGER REFERENCES familias(id),
subfamilia_id  INTEGER REFERENCES subfamilias(id)
```

---

## 7. Tablas que se conservan sin cambio

| Tabla | Razón |
|---|---|
| `usuarios` | Se simplifica (ver punto 2) pero se conserva |
| `tipos_insumo` | Se amplía (ver punto 5) |
| `insumos` | Se ajusta (ver punto 2) |
| `proyectos` | Sin cambios |
| `configuracion_proyecto` | Solo renombre |
| `sobrecostos` | Solo renombre |
| `estructura_presupuesto` | Renombre + cambio de estado |
| `apu_auxiliares` | Solo renombre |
| `apu_componentes` | Solo renombre |
| `apu_resumen` | Solo renombre |
| `auxiliares` | Sin cambios |
| `proveedores` | Sin cambios |
| `familias` | Rediseño (ver punto 6) |
| `subfamilias` | Nueva (ver punto 6) |
| `notas` | Sin cambios |
| `historial` | Sin cambios — base para Ctrl+Z colaborativo |

---

## 8. Archivos afectados por los cambios

| Archivo | Cambios necesarios |
|---|---|
| `backend/schema.sql` | Todos los cambios del schema |
| `backend/core.py` | Quitar JOINs con `estados_nodo`, renombres de tablas, `estado` en lugar de `estado_nombre/color` |
| `backend/repos.py` | Renombres, quitar refs a tablas eliminadas, agregar `ApuNodoRepo` → `ApuAuxiliarRepo`, `SubfamiliaRepo` |
| `backend/importar.py` | Renombres de tablas, `_tipo_id()` actualizado con bits 64 y 128 |
| `frontend/ventana.py` | `ApuNodoRepo` → `ApuAuxiliarRepo` |

---

## 9. Lo que NO cambia en esta versión

- `historial` — se conserva vacía, se implementa con el Ctrl+Z colaborativo
- La lógica de importación WBS — sin cambios
- Los archivos de frontend de widgets — sin cambios
- Los archivos QSS de temas — sin cambios

---

*Pendiente de aprobación antes de implementar*
