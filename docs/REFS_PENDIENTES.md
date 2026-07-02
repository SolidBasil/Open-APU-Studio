# Referencias a columnas eliminadas — pendientes de actualizar

Generado: 2026-07-01

## `apu_matrices.rendimiento` → eliminada

| Archivo | Línea | Código |
|---------|-------|--------|
| `backend/database/core.py` | 212 | `ad.rendimiento,` |
| `backend/database/repos/apu.py` | 32 | `rendimiento,` (INSERT columnas) |
| `backend/database/repos/apu.py` | 38 | `datos.get("rendimiento", 0)` |
| `backend/exportar/exportar.py` | 675 | `comp.get('rendimiento')` |
| `backend/exportar/exportar.py` | 685 | `'RENDTO': rendto,` |
| `backend/exportar/exportar.py` | 784 | `comp.get('rendimiento')` |

## `apu_matrices.cantidad` → reemplazada por `valor` + `operador`

### SQL: `ac.cantidad` → `CASE WHEN operador='*' THEN valor ELSE 1.0/valor END`
### SQL: `ac.cantidad * ac.precio` → `CASE WHEN operador='*' THEN valor*precio ELSE precio/valor END`

| Archivo | Línea | Código |
|---------|-------|--------|
| `backend/database/core.py` | 213 | `ad.cantidad,` |
| `backend/database/core.py` | 215 | `ad.cantidad * ad.precio AS importe` |
| `backend/database/repos/apu.py` | 33 | `cantidad,` (INSERT columnas) |
| `backend/database/repos/apu.py` | 39 | `datos.get("cantidad", 0)` (INSERT vals) |
| `backend/database/repos/apu.py` | 84 | `SUM(ac.cantidad * ac.precio)` |
| `backend/database/repos/apu.py` | 98–107 | 10× `ac.cantidad*ac.precio` / `ac.cantidad` en CASE por tipo |
| `backend/database/repos/explosion.py` | 252 | `SUM(am.cantidad * ep.cantidad)` |
| `backend/database/repos/explosion.py` | 253 | `SUM(am.cantidad * ep.cantidad) * i.costo_final` |
| `backend/database/repos/explosion.py` | 280–281 | `SUM(am.cantidad * am.precio * ep.cantidad)` (×2) |
| `backend/database/repos/insumos.py` | 80 | `SUM(ac.cantidad * ac.precio)` |
| `backend/database/repos/insumos.py` | 90 | `am.cantidad,` |
| `backend/database/repos/insumos.py` | 92 | `am.cantidad * am.precio AS importe` |
| `backend/database/repos/recalculo.py` | 116 | `SUM(ac.cantidad * ac.precio)` |
| `backend/database/repos/recalculo.py` | 134–143 | 10× `ac.cantidad` / `ac.cantidad*ac.precio` en CASE por tipo |

### Python: `comp.get('cantidad')` → lógica `valor/operador`

| Archivo | Línea | Código |
|---------|-------|--------|
| `backend/database/repos/explosion.py` | 142 | `p["cantidad"]` |
| `backend/database/repos/explosion.py` | 153 | `p["cantidad"]` |
| `backend/database/repos/explosion.py` | 184 | `p["cantidad"]` |
| `backend/database/repos/explosion.py` | 186 | `p["cantidad"]` |
| `backend/exportar/exportar.py` | 674 | `comp.get('cantidad')` |
| `backend/exportar/exportar.py` | 677 | `importe = cantidad * precio` |
| `backend/exportar/exportar.py` | 685 | `'RENDTO': rendto,` |
| `backend/exportar/exportar.py` | 785 | `comp.get('cantidad')` |
| `backend/exportar/exportar.py` | 787–799 | `'CANTIDAD': cantidad,` y `'MONTO': cantidad * precio` |
| `backend/exportar/exportar.py` | 813 | `comp.get('cantidad')` |
| `frontend/ventana/api.py` | 141 | `r.get("cantidad", 0)` — desde `get_apu()` que devuelve `ad.cantidad` |
| `frontend/ventana/api.py` | 143 | `r.get("importe", 0)` — desde `get_apu()` que devuelve `ad.cantidad*precio` |
| `frontend/ventana/paneles.py` | 207 | `r['cantidad']` — desde `get_apu()` detalle |
| `frontend/ventana/paneles.py` | 753 | `comp.get("importe", 0)` y `comp.get("cantidad", 0)` — desde `por_matriz()` |
| `frontend/ventana/paneles.py` | 759 | `comp['cantidad']` — desde `por_matriz()` |

## `insumos` — columnas faltantes en INSERTs/manejos

| Archivo | Línea | Problema |
|---------|-------|----------|
| `repos/insumos.py` | 108–115 | `actualizar_precio()` no setea `costo_directo` (solo `costo_mn` y `costo_final`) |
| `repos/insumos.py` | 163–169 | `insertar()` no incluye `costo_directo`, `catfsr`, `factor_fsr`, `fsr_minimo` |

## Columnas sin implementar en código (existen en schema.sql, 0 refs en Python)

| Columna / Tabla | Uso previsto | Estado |
|-----------------|--------------|--------|
| `insumos.catfsr` | Categoría FSR | Sin código |
| `insumos.factor_fsr` | Factor manual FSR | Sin código |
| `insumos.fsr_minimo` | Flag salario mínimo FSR | Sin código |
| `factores_sobrecosto` (tabla) | % indirectos, financiamiento, utilidad, cargos | Sin código |
| `factores_fsr` (tabla) | Tabla FSR por categoría | Sin código |
| `variables_formula` (tabla) | Variables para fórmulas | Sin código |
| `apu_matrices.operador` | `'*'` o `'/'` | Solo INSERT fijo `'*'` en importar.py |
| `apu_matrices.valor` | Valor del componente | Solo importado desde OPUS |
| `apu_matrices.importe` (REAL) | Importe calculado | Nunca se escribe — solo alias en SELECT |

## Documentación desactualizada

| Archivo | Línea | Contenido viejo |
|---------|-------|-----------------|
| `docs/DOCUMENTACION.md` | 485 | `costo_mn, costo_me, costo_base, costo_final,` — `costo_base` ya no existe |
| `docs/DOCUMENTACION.md` | 492 | `activo, es_basico,` — `es_basico` ya no existe |
| `docs/DOCUMENTACION.md` | 503 | `rendimiento, cantidad, precio,` — `rendimiento`, `cantidad` ya no existen |
| `docs/SCHEMA.md` | 244 | `am.rendimiento, am.cantidad, am.precio, am.importe` — ejemplo desactualizado |
| `docs/planes/completo/PLAN_EXPORTACION.md` | 176 | Mapeo `BASICO → es_basico` |
| `docs/planes/completo/PLAN_EXPORTACION.md` | 228–229 | `NOELE → rendimiento`, `RENDTO → rendimiento` |
| `docs/planes/completo/PLAN_EXPORTACION.md` | 322 | Referencia a `es_basico=1` |
| `docs/planes/completo/PLAN_EXPORTACION.md` | 753 | Filtrar insumos donde `es_basico=1` |

## Verificaciones: `estructura_presupuesto`

| Archivo | Línea | Referencia | Columna | ¿Existe? |
|---------|-------|------------|---------|----------|
| `backend/database/core.py` | 142 | `n.cantidad` | `estructura_presupuesto.cantidad` | ✔️ |
| `backend/database/core.py` | 143 | `n.total` | `estructura_presupuesto.total` | ✔️ |
| `frontend/ventana/widgets/arbol.py` | 165 | `n.get("cantidad")` | `estructura_presupuesto.cantidad` | ✔️ |
| `frontend/ventana/widgets/arbol.py` | 166 | `n.get("precio_unitario")` | alias `i.costo_final` en `core.py:141` | ✔️ |
| `frontend/ventana/paneles.py` | 545 | `c.get("cantidad", 0)` | desde NodoRepo (`ep.cantidad`) | ✔️ |
| `backend/exportar/informe_pdf/latex.py` | 156 | `hijo.get("cantidad")` | desde árbol (`ep.cantidad`) | ✔️ |
| `backend/exportar/exportar.py` | 591 | `nodo.get('total')` | `estructura_presupuesto.total` | ✔️ |
| `backend/exportar/exportar.py` | 595 | `cantidad * pu` | `nodo.get('cantidad')` + `nodo.get('precio_unitario')` | ✔️ |
| `ep.importe` en toda la base | — | **0 ocurrencias** | GENERATED COLUMN eliminada en v4 | ✔️ |

## Columnas ya verificadas como limpias

- `insumos.costo_base`: 0 refs ✔️
- `insumos.marca`: 0 refs ✔️
- `insumos.pais_origen`: 0 refs ✔️
- `insumos.es_basico`: 0 refs ✔️
- `exportar.py: 'BASICO'`: campo DBF (formato OPUS), no columna SQL ✔️
- `schemas_opus.json: 'BASICO'`: esquema DBF, no columna SQL ✔️

## Frontend — verificaciones adicionales

| Archivo | Línea | Acceso | Resultado |
|---------|-------|--------|-----------|
| `handlers.py` | 282 | `result['apu_matrices']` — contador desde import() | ✔️ |
| `handlers.py` | 665, 677, 740 | `EXISTS (SELECT 1 FROM apu_matrices ...)` | ✔️ solo filtra, no lee columnas |
| `handlers.py` | 994 | `COUNT(*) FROM apu_matrices` | ✔️ |
| `handlers.py` | 1038 | `self._api.presupuesto_arbol()` | ✔️ no toca apu_matrices |
| `api.py` | 162–170 | `insumo_ids_con_apu()` solo lee `apu_matrices.insumo_id` | ✔️ |
| `api.py` | 176–177 | `JOIN apu_matrices` solo filtra por `am.matriz_id` | ✔️ |
| `paneles.py` | 104, 466, 515, 520, 582, 657 | Llamadas API indirectas | ✔️ |
| `widgets/explosion.py` | 11 | Comentario `am.importe` — ahora REAL en schema, no GENERATED | ✔️ (cosmético) |
| `widgets/dialogs.py` | — | Sin accesos directos a apu_matrices | ✔️ |
| `widgets/insumos.py` | — | Solo lee `costo_final`, `costo_mn`, `costo_me` — existen | ✔️ |
| `toolbar.py` | — | Sin accesos directos a apu_matrices o insumos viejos | ✔️ |

## Regla de importación OPUS → `apu_matrices.valor` / `apu_matrices.operador`

| Tipo insumo | Campo OPU S | `valor` | `operador` | Efecto |
|-------------|-------------|---------|------------|--------|
| MO (tipo_id=2) | `RENDTO` | `RENDTO` | `'/'` | `importe = precio / rendto` |
| Resto | `CANTIDAD` | `CANTIDAD` | `'*'` | `importe = cantidad × precio` |

**Por qué MO usa división:**
En OPUS la fórmula de MO es `importe = (CANTIDAD / RENDTO) × PRECIO`. Pero `CANTIDAD` casi siempre es 1.0 (una hora, un día), y `RENDTO` es el rendimiento real (ej: 10 m²/día). Con `operador='/'` y `valor=RENDTO` se obtiene `importe = PRECIO / RENDTO`, que es matemáticamente idéntico. El resto de tipos usan `CANTIDAD × PRECIO` directamente.

**Implicaciones en exportación a OPUS:**
- Si `operador='*'`: emitir `CANTIDAD=valor, RENDTO=1.0`
- Si `operador='/'`: emitir `CANTIDAD=1.0, RENDTO=valor`
- En ambos casos el DBF resultante es compatible con OPUS.

## Notas

- `sobrecostos` (tabla vieja, OPUS I.DBF) y `factores_sobrecosto` (tabla nueva, cascada) **coexisten**.
- `importar.py` INSERT de insumos ya incluye `costo_directo` — OK. Faltan `catfsr`, `factor_fsr`, `fsr_minimo` (tienen DEFAULT/NULL, no rompen).
- Todas las refs a `estructura_presupuesto.cantidad` son válidas — la columna sigue en schema.
- Para la cascada de sobrecosto: `costo_final` se usará como resultado final. `costo_directo` = CD base antes de aplicar %.
