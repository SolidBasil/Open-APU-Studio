# Esquema de base de datos — Open APU Studio

Versión del esquema: **1** (`001_inicial.sql`)

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
  proyectos           Metadatos completos: concursante, cliente, licitación, financiero
  proyecto_config     Parámetros técnicos de cálculo (horas/día, decimales, etc.)
  pie_precios         Renglones de sobrecostos/indirectos por proyecto

BLOQUE 5 — Árbol del presupuesto
  nodos               Capítulos y conceptos con jerarquía por PRE_WBS

BLOQUE 6 — Insumos
  insumos             Catálogo maestro: materiales, MO, herramienta, equipo, auxiliares

BLOQUE 7 — APU
  apu_detalle         Desglose de insumos por concepto (ligado por nodo_id, no por clave)
  apu_totales         Subtotales APU por tipo (actualizados por Python)
  auxiliares          Insumos compuestos intermedios

BLOQUE 8 — Colaboración
  notas               Comentarios por nodo, con autor y estado (abierta/resuelta)
  historial           Auditoría genérica de cambios (tabla + registro_id + campo)

BLOQUE 9 — Control de esquema
  schema_version      Registro de migraciones aplicadas
```

---

## Decisiones de diseño importantes

### 1. `nodos` — jerarquía por `wbs`, no por `padre_id` solo

El campo `padre_id` existe para queries directas (hijos de un nodo), pero la
**fuente de verdad jerárquica es `wbs`**. Durante la importación desde OPUS,
el árbol se reconstruye truncando `PRE_WBS` de derecha a izquierda hasta
encontrar un nodo activo con ese código exacto.

Razón: el 79% de los nodos en la base OPUS están marcados como borrados
lógicamente, lo que rompe las cadenas de `PRE_IDPAD`. Ver `GUIA_ONBOARDING.md`
sección 6 para el detalle completo del bug y la solución.

```sql
-- Hijos directos de un nodo
SELECT * FROM nodos WHERE padre_id = ? AND activo = 1 ORDER BY orden;

-- Todos los descendientes (CTE recursiva)
WITH RECURSIVE sub AS (
    SELECT * FROM nodos WHERE id = ?
    UNION ALL
    SELECT n.* FROM nodos n JOIN sub s ON n.padre_id = s.id WHERE n.activo = 1
)
SELECT * FROM sub;

-- Ruta completa (breadcrumb) de un nodo
WITH RECURSIVE ruta AS (
    SELECT * FROM nodos WHERE id = ?
    UNION ALL
    SELECT n.* FROM nodos n JOIN ruta r ON n.id = r.padre_id
)
SELECT * FROM ruta ORDER BY nivel;
```

### 2. `importe` como columna computada `GENERATED ALWAYS`

En `nodos` y `apu_detalle`, el importe (`cantidad × precio`) es una columna
computada — SQLite la actualiza automáticamente al cambiar `cantidad` o
`precio_unitario`. No se puede olvidar actualizarla.

`subtotal` en `nodos` **no** es computada porque requiere sumar hijos, lo que
SQLite no permite en columnas generadas. Python lo recalcula así:

```python
def recalcular_subtotales(con, nodo_id):
    """Recalcula subtotal bottom-up desde nodo_id hasta la raíz."""
    cur = con.cursor()
    # Subir por el árbol actualizando cada padre
    while nodo_id is not None:
        cur.execute("""
            UPDATE nodos SET
                subtotal = (
                    SELECT COALESCE(SUM(COALESCE(importe, subtotal, 0)), 0)
                    FROM nodos WHERE padre_id = ? AND activo = 1
                ),
                modificado_en = datetime('now')
            WHERE id = ?
        """, (nodo_id, nodo_id))
        row = cur.execute("SELECT padre_id FROM nodos WHERE id = ?", (nodo_id,)).fetchone()
        nodo_id = row[0] if row else None
    con.commit()
```

### 3. `apu_detalle` ligado por `nodo_id`, no por clave texto

En OPUS la relación APU↔concepto se hacía por `NOMBRE` (texto). Aquí es por
`nodo_id` (entero con FK). Ventajas: joins más rápidos, integridad garantizada
por la FK, `ON DELETE CASCADE` elimina el APU si se borra el concepto.

### 4. `historial` genérico

Una sola tabla para auditar cualquier cambio en cualquier tabla. Python genera
un UUID de sesión por operación para agrupar cambios relacionados:

```python
import uuid
sesion = str(uuid.uuid4())
# Todos los INSERT en historial de una misma operación usan este sesion
```

### 5. Borrado lógico (`activo = 1`)

Ninguna tabla borra físicamente registros — usan `activo = 0`. Esto permite
deshacer eliminaciones y mantener el historial íntegro. **Toda query de negocio
debe filtrar `WHERE activo = 1`**, excepto las de auditoría/historial.

---

## Datos semilla (ya insertados al crear la DB)

| Tabla | Registros |
|---|---|
| `roles` | admin, editor, revisor, lector |
| `usuarios` | 1 usuario local (admin) |
| `tipos_insumo` | material, mano_obra, herramienta, equipo, auxiliar, concepto |
| `tipos_herramienta` | estándar, herramienta_mano, equipo_seguridad |
| `tipos_equipo` | costo_horario, renta_horaria, compuesto |
| `tipos_material` | consumo, instalación permanente |
| `estados_nodo` | sin_revisar (#808080), en_revision (#F5A623), verificado (#4CAF7D), cuestionado (#E05252) |
| `schema_version` | versión 1 |

---

## Lo que falta implementar (pendiente en la app)

> El esquema ya soporta todo esto — solo falta la lógica en Python/PyQt.

| Feature | Tablas involucradas | Prioridad |
|---|---|---|
| Login / selección de usuario | `usuarios`, `roles` | Media |
| Mostrar semáforo en árbol PyQt | `estados_nodo`, `nodos.estado_id` | Alta |
| Panel de notas por nodo | `notas` | Media |
| Ctrl+Z (deshacer) | `historial` | Media |
| Gestión de proveedores | `proveedores` | Baja |
| Familias/subfamilias de insumos | `familias` | Baja |
| Pie de precios editable | `pie_precios` | Alta |
| Multi-moneda | `proyectos.costo_mn/me` | Baja |
| Roles y permisos en UI | `roles`, `usuarios.rol_id` | Futura |
| Trabajo en red / sync | Requiere diseño adicional | Futura |

---

## Migraciones futuras

Agregar un archivo `002_nombre.sql` en `backend/db/migraciones/`.
`DatabaseManager` lo detecta y aplica automáticamente al abrir la DB.

Ejemplo de migración para agregar una columna:

```sql
-- 002_agregar_campo_x.sql
ALTER TABLE nodos ADD COLUMN campo_nuevo TEXT;
INSERT INTO schema_version (version, descripcion)
VALUES (2, 'Agrega campo_nuevo a nodos');
```

**Regla:** nunca modificar `001_inicial.sql` después de que esté en producción.
Todos los cambios van en migraciones numeradas.

---

## Queries frecuentes de referencia

```sql
-- Presupuesto completo de un proyecto ordenado por WBS
SELECT
    n.id, n.wbs, n.nivel, n.tipo, n.clave,
    n.descripcion, n.unidad, n.cantidad,
    n.precio_unitario, n.importe, n.subtotal,
    e.nombre AS estado, e.color AS estado_color
FROM nodos n
JOIN estados_nodo e ON e.id = n.estado_id
WHERE n.proyecto_id = ? AND n.activo = 1
ORDER BY n.wbs;

-- APU completo de un concepto
SELECT
    ad.orden, i.clave, i.descripcion, i.unidad,
    ti.nombre AS tipo,
    ad.rendimiento, ad.cantidad, ad.precio, ad.importe
FROM apu_detalle ad
JOIN insumos i  ON i.id = ad.insumo_id
JOIN tipos_insumo ti ON ti.id = i.tipo_id
WHERE ad.nodo_id = ?
ORDER BY ad.orden;

-- Insumos por tipo con total de uso en el proyecto
SELECT
    ti.nombre AS tipo,
    i.clave, i.descripcion, i.unidad, i.costo_final,
    COUNT(ad.id) AS usos_en_apu,
    SUM(ad.importe) AS importe_total
FROM insumos i
JOIN tipos_insumo ti ON ti.id = i.tipo_id
LEFT JOIN apu_detalle ad ON ad.insumo_id = i.id
WHERE i.proyecto_id = ? AND i.activo = 1
GROUP BY i.id
ORDER BY ti.orden, i.clave;

-- Historial de cambios de un nodo
SELECT
    h.cambiado_en, u.nombre AS usuario,
    h.campo, h.valor_anterior, h.valor_nuevo
FROM historial h
JOIN usuarios u ON u.id = h.usuario_id
WHERE h.tabla = 'nodos' AND h.registro_id = ?
ORDER BY h.cambiado_en DESC;

-- Nodos cuestionados o sin revisar (para revisión de calidad)
SELECT n.wbs, n.descripcion, e.nombre AS estado, e.color,
       u.nombre AS modificado_por, n.modificado_en
FROM nodos n
JOIN estados_nodo e ON e.id = n.estado_id
LEFT JOIN usuarios u ON u.id = n.modificado_por
WHERE n.proyecto_id = ?
  AND n.estado_id IN (SELECT id FROM estados_nodo WHERE clave IN ('sin_revisar','cuestionado'))
  AND n.activo = 1
ORDER BY n.wbs;
```
