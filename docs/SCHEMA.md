# Esquema de base de datos — Open APU Studio

Versión del esquema: **3** (`schema.sql` — v2+v3 migradas automáticamente en `db.py`)

Este documento explica el diseño de la base de datos SQLite, las decisiones
de arquitectura y qué falta implementar en versiones futuras.

---

## Convenciones generales

| Convención | Valor |
|---|---|
| Llaves primarias | `INTEGER PRIMARY KEY AUTOINCREMENT` |
| Fechas | `TEXT` en ISO 8601: `'YYYY-MM-DD HH:MM:SS'` |
| Booleanos | `INTEGER` — `0` = falso, `1` = verdadero |
| Soft-delete | Columna `activo INTEGER NOT NULL DEFAULT 1` |
| Auditoría | Toda tabla editable tiene `creado_por`, `creado_en`, `modificado_por`, `modificado_en` |
| Importes calculados | Columnas `GENERATED ALWAYS AS (...) STORED` — SQLite las mantiene automáticamente |
| Subtotales de árbol | **No** son columnas computadas — Python los recalcula bottom-up al editar |

---

## Mapa de tablas por bloque

```
BLOQUE 1 — Identidad
  roles               Catálogo de roles: admin / editor / revisor / lector
  usuarios            Personas que usan la app (local o colaborativo)

BLOQUE 2 — Catálogos del sistema (semilla fija)
  tipos_insumo        Material / Mano de obra / Herramienta / Equipo / Auxiliar / Concepto
  tipos_herramienta   Estándar / Herramienta de mano / Equipo de seguridad
  tipos_equipo        Costo horario / Renta horaria / Compuesto
  tipos_material      De consumo / De instalación permanente
  estados_nodo        Semáforo: Sin revisar / En revisión / Verificado / Cuestionado

BLOQUE 3 — Catálogos del proyecto (editables)
  familias            Árbol de familias/subfamilias de insumos (self-join)
  proveedores         Proveedores de materiales y recursos

BLOQUE 4 — Proyecto
  proyectos               Metadatos completos: concursante, cliente, licitación, financiero
  configuracion_proyecto  Parámetros técnicos de cálculo (horas/día, decimales, etc.)
  sobrecostos             Renglones de sobrecostos/indirectos por proyecto

BLOQUE 5 — Árbol del presupuesto
  estructura_presupuesto  Capítulos y conceptos con jerarquía por WBS

BLOQUE 6 — Insumos
  insumos                 Catálogo maestro: materiales, MO, herramienta, equipo, auxiliares
                          (campo es_compuesto=1 identifica insumos con APU propio)

BLOQUE 7 — APU
  apu_matrices            Desglose de insumos por matriz (concepto o insumo compuesto),
                          con matriz_id único
  apu_resumen_totales     Subtotales APU por tipo (actualizados por Python)
                          (antiguos auxiliares se almacenan en insumos con es_compuesto=1)

BLOQUE 8 — Colaboración
  notas               Comentarios por nodo, con autor y estado (abierta/resuelta)
  historial           Auditoría genérica de cambios (tabla + registro_id + campo)

BLOQUE 9 — Control de esquema
  schema_version      Registro de migraciones aplicadas
```

---

## Decisiones de diseño importantes

### 1. `estructura_presupuesto` — jerarquía por `wbs`, no por `padre_id` ni `PRE_IDPAD`

El campo `padre_id` existe para queries directas (hijos de un nodo), pero la
**fuente de verdad jerárquica es `wbs`**. Durante la importación desde OPUS,
el árbol se reconstruye truncando `PRE_WBS` de derecha a izquierda hasta
encontrar un nodo activo con ese código exacto.

Los valores `PRE_IDPAD` del archivo `*1.DBF` pertenecen a un sistema de
numeración diferente y **no** son referencias válidas a `PRE_ID`. Usarlos
directamente produce padres incorrectos cuando coinciden por azar con un
`PRE_ID` existente. Por esta razón la importación ignora `PRE_IDPAD` y siempre
resuelve padres por truncamiento de WBS.

```sql
-- Hijos directos de un nodo
SELECT * FROM estructura_presupuesto WHERE padre_id = ? AND activo = 1 ORDER BY orden;

-- Todos los descendientes (CTE recursiva)
WITH RECURSIVE sub AS (
    SELECT * FROM estructura_presupuesto WHERE id = ?
    UNION ALL
    SELECT n.* FROM estructura_presupuesto n JOIN sub s ON n.padre_id = s.id WHERE n.activo = 1
)
SELECT * FROM sub;

-- Ruta completa (breadcrumb) de un nodo
WITH RECURSIVE ruta AS (
    SELECT * FROM estructura_presupuesto WHERE id = ?
    UNION ALL
    SELECT n.* FROM estructura_presupuesto n JOIN ruta r ON n.id = r.padre_id
)
SELECT * FROM ruta ORDER BY nivel;
```

### 2. `total` columna unificada de valor monetario

En `estructura_presupuesto` el campo `total` reemplaza la antigua dualidad
`importe` (GENERATED) + `subtotal` (calculado en Python). Ahora:
- **conceptos**: `total = cantidad × precio` — el precio se resuelve desde
  `insumos.costo_final` o `apu_matrices` vía `insumo_id`
- **capítulos**: `total = SUM(hijos.total)` — calculado bottom-up en Python

La UI ya no bifurca por tipo — lee `total` directamente.

Python lo recalcula así:

```python
def actualizar_total(nodo_id):
    cur = con.cursor()
    while nodo_id is not None:
        cur.execute("""
            UPDATE estructura_presupuesto SET
                total = (
                    SELECT COALESCE(SUM(COALESCE(total, 0)), 0)
                    FROM estructura_presupuesto WHERE padre_id = ? AND activo = 1
                ),
                modificado_en = datetime('now')
            WHERE id = ?
        """, (nodo_id, nodo_id))
        nodo_id = cur.execute("SELECT padre_id FROM estructura_presupuesto WHERE id = ?", (nodo_id,)).fetchone()
        nodo_id = nodo_id[0] if nodo_id else None
    con.commit()
```

### 3. `apu_matrices` ligado por `matriz_id`, no por clave texto

En OPUS la relación APU↔concepto se hacía por `NOMBRE` (texto). Aquí es por
`matriz_id` (entero). Un mismo id puede referenciar un nodo del árbol
(estructura_presupuesto) o un insumo compuesto (insumos con es_compuesto=1).
El contexto de la llamada sabe cuál es — no se necesita columna discriminadora.

Ventajas: joins más rápidos, sin duplicación de columnas (concepto_id /
insumo_compuesto_id como en v1), consultas unificadas.

### 4. `historial` genérico

Una sola tabla para auditar cualquier cambio en cualquier tabla.
`sesion` (UUID) agrupa cambios de una misma operación.

### 5. Familias y subfamilias — lookup en queries de insumos

Las familias se importan desde el campo `ELE_GRUPO` o `ELE_FAM` del archivo `*P.DBF`.
Subfamilias desde `ELE_SFAM` (ausente en muchos proyectos).

```sql
-- Insumos con familia y subfamilia
SELECT i.*, f.nombre AS familia_nombre, sf.nombre AS subfamilia_nombre
FROM insumos i
LEFT JOIN familias f    ON f.id  = i.familia_id
LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id
WHERE i.proyecto_id = ? AND i.activo = 1;
```

`InsumoRepo` incluye estos JOINs en todos sus métodos (`todos`, `por_tipo`,
`buscar`, `buscar_por_clave`, `buscar_texto`).

---

### 6. Borrado lógico (`activo = 1`)

Ninguna tabla borra físicamente registros — usan `activo = 0`. Esto permite
deshacer eliminaciones y mantener el historial íntegro. **Toda query de negocio
debe filtrar `WHERE activo = 1`**, excepto las de auditoría/historial.

---

## Datos semilla (ya insertados al crear la DB)

| Tabla | Registros |
|---|---|
| `usuarios` | 1 usuario local |
| `tipos_insumo` | material, mano_obra, herramienta, equipo, auxiliar, concepto, flete, trabajo |
| `schema_version` | versión 3 |

---

## Lo que falta implementar (pendiente en la app)

> El esquema ya soporta todo esto — solo falta la lógica en Python/PyQt.

| Feature | Tablas involucradas | Prioridad |
|---|---|---|
| Login / selección de usuario | `usuarios` | Media |
| Panel de notas por nodo | `notas` | Media |
| Ctrl+Z (deshacer) | `historial` | Media |
| Gestión de proveedores | `proveedores` | Baja |
| Sobrecostos editable | `sobrecostos` | Alta |
| Multi-moneda | `proyectos.costo_mn/me` | Baja |
| Trabajo en red / sync | Requiere diseño adicional | Futura |

---

## Migraciones aplicadas

Las migraciones se gestionan en `backend/db.py` (no hay carpeta de migraciones separada).
El schema completo vive en `backend/schema.sql`. Las migraciones v2→v3 se aplican
automáticamente vía `ALTER TABLE` en `Database._aplicar_schema()`.

| Versión | Cambios clave |
|---|---|
| 1 | Esquema inicial con `nodos`, `apu_detalle`, `estados_nodo`, roles |
| 2 | Renombres (`nodos`→`estructura_presupuesto`, etc.), eliminar tablas no usadas (roles, estados_nodo, tipos_* extra), agregar subfamilias, tipo trabajo/flete, estado como entero |
| 3 | `concepto_id` + `insumo_compuesto_id` → `matriz_id` único, `es_compuesto` por presencia en `*F.DBF` |

**Regla:** nunca modificar `schema.sql` en formas que rompan migraciones existentes.
Todos los cambios futuros van como migraciones en `db.py`.

---

## Queries frecuentes de referencia

```sql
-- Presupuesto completo de un proyecto ordenado por WBS
SELECT
    n.id, n.wbs, n.nivel, n.tipo, n.insumo_id,
    COALESCE(i.descripcion, n.descripcion) AS descripcion,
    n.cantidad, n.total,
    CASE n.estado
        WHEN 0 THEN 'Sin revisar'
        WHEN 1 THEN 'En revisión'
        WHEN 2 THEN 'Verificado'
        WHEN 3 THEN 'Cuestionado'
    END AS estado_nombre
FROM estructura_presupuesto n
LEFT JOIN insumos i ON i.id = n.insumo_id
WHERE n.proyecto_id = ? AND n.activo = 1
ORDER BY n.wbs;

-- APU completo de un concepto o insumo compuesto
SELECT
    am.orden, i.clave, i.descripcion, i.unidad,
    ti.nombre AS tipo,
    am.rendimiento, am.cantidad, am.precio, am.importe
FROM apu_matrices am
JOIN insumos i  ON i.id = am.insumo_id
JOIN tipos_insumo ti ON ti.id = i.tipo_id
WHERE am.matriz_id = ?
ORDER BY am.orden;

-- Insumos por tipo con total de uso en el proyecto
SELECT
    ti.nombre AS tipo,
    i.clave, i.descripcion, i.unidad, i.costo_final,
    COUNT(am.id) AS usos_en_apu,
    SUM(am.importe) AS importe_total
FROM insumos i
JOIN tipos_insumo ti ON ti.id = i.tipo_id
LEFT JOIN apu_matrices am ON am.insumo_id = i.id
WHERE i.proyecto_id = ? AND i.activo = 1
GROUP BY i.id
ORDER BY ti.orden, i.clave;

-- Historial de cambios de un nodo
SELECT
    h.cambiado_en, u.nombre AS usuario,
    h.campo, h.valor_anterior, h.valor_nuevo
FROM historial h
JOIN usuarios u ON u.id = h.usuario_id
WHERE h.tabla = 'estructura_presupuesto' AND h.registro_id = ?
ORDER BY h.cambiado_en DESC;

-- Nodos cuestionados o sin revisar
SELECT n.wbs, n.descripcion, n.estado,
       u.nombre AS modificado_por, n.modificado_en
FROM estructura_presupuesto n
LEFT JOIN usuarios u ON u.id = n.modificado_por
WHERE n.proyecto_id = ?
  AND n.estado IN (0, 3)
  AND n.activo = 1
ORDER BY n.wbs;
```
