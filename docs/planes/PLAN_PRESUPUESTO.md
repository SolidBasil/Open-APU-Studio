# Plan: mejora de la tabla de presupuestos, unificación de columnas `importe`/`subtotal` → `total`
#       y limpieza de columnas duplicadas de insumos en el árbol

## 1. Motivación

### 1.1 Dualidad `importe` / `subtotal`

`estructura_presupuesto` tiene dos columnas para almacenar el valor monetario
de cada nodo, cada una con semántica distinta:

| Columna | Tipo | Semántica | Poblado por |
|---------|------|-----------|-------------|
| `importe` | `REAL GENERATED ALWAYS... STORED` | `cantidad × precio_unitario` para conceptos hoja | SQLite (GENERATED) |
| `subtotal` | `REAL NOT NULL DEFAULT 0.0` | Suma acumulada de hijos para capítulos | Python (recalcular_subtotales) |

Esto genera **10 workarounds** en 7 archivos (ver §5) que constantemente
preguntan `if tipo == "concepto"` para decidir qué columna leer o escribir.
La lógica de recálculo del mismo CASE existe **3 veces** (core.py, repos.py,
importar.py) — cualquier cambio debe replicarse en los tres sitios.

### 1.2 Columnas duplicadas de insumos

El árbol del presupuesto también almacena copia local de datos que ya existen
en `insumos`: `descripcion_corta`, `unidad`, `precio_unitario`. Si se edita
el insumo pero no el árbol (o viceversa), se descordinan.

Con el cambio, `estructura_presupuesto` solo almacena datos **propios del
árbol**: jerarquía, `insumo_id` (vínculo a `insumos.id`), `descripcion` (para
agrupadores), `cantidad` y `total`. Todo lo demás se resuelve via `JOIN` a
`insumos` o `apu_matrices`.

---

## 2. Schema

### 2.1 Resumen

| Columna actual | Acción |
|----------------|--------|
| `importe` (GENERATED) | ❌ Eliminar |
| `subtotal` | ❌ Eliminar |
| `descripcion_corta` | ❌ Eliminar |
| `unidad` | ❌ Eliminar |
| `precio_unitario` | ❌ Eliminar |
| `clave` | ❌ Eliminar (reemplazado por `insumo_id`) |
| *(nueva)* `insumo_id` | ➕ `INTEGER REFERENCES insumos(id)` — vínculo directo al insumo |
| *(nueva)* `total` | ➕ `REAL NOT NULL DEFAULT 0.0` |
| *(nueva)* `formula` | ➕ `TEXT` — expresión para calcular `cantidad` |

### 2.2 Nuevo DDL de `estructura_presupuesto`

```sql
CREATE TABLE IF NOT EXISTS estructura_presupuesto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id),
    padre_id        INTEGER REFERENCES estructura_presupuesto(id),
    wbs             TEXT    NOT NULL,
    nivel           INTEGER NOT NULL,
    orden           INTEGER NOT NULL DEFAULT 0,
    tipo            TEXT    NOT NULL DEFAULT 'capitulo'
                    CHECK(tipo IN ('capitulo', 'concepto')),

    -- insumo_id: vínculo directo al insumo (solo conceptos)
    insumo_id       INTEGER REFERENCES insumos(id),
    -- descripcion: para agrupadores es el nombre del capítulo;
    --              para conceptos se sobreescribe con insumos.descripcion via JOIN
    descripcion     TEXT    NOT NULL DEFAULT '',

    -- Medición (solo conceptos hoja)
    cantidad        REAL,                         -- valor fijo O resultado de formula
    formula         TEXT,                          -- 🆕 expresion opcional para cantidad

    -- Única columna de valor: para conceptos = cantidad × precio (desde APU o insumo),
    --                          para capítulos = suma de hijos
    total           REAL    NOT NULL DEFAULT 0.0,

    -- Semáforo, notas, auditoría
    estado          INTEGER NOT NULL DEFAULT 0,
    notas_rapidas   TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)
);
```

### 2.3 Lo que NO cambia

- `apu_resumen_totales` — no se toca

---

## 3. Modelo de precio

### 3.1 Por tipo de insumo

| Tipo de insumo | Precio unitario | Cálculo del `total` en el árbol |
|---|---|---|
| **Básico** (sin APU) | `insumos.costo_final` | `cantidad × costo_final` |
| **Compuesto** (con APU) | `SUM(apu_matrices.cant × apu_matrices.precio)` | `cantidad × (costo_unitario_del_APU)` |
| **Agrupador** (capítulo) | — | `SUM(hijos.total)` |

### 3.2 Algoritmo de `actualizar_total()`

```
actualizar_total(concepto_id):
  └─ para cada nodo afectado (bottom-up desde el editado hasta la raíz):

     └─ SI el nodo tiene formula:
            └─ cantidad = resolver(ep.formula, desde variables_formula)
            └─ UPDATE estructura_presupuesto SET cantidad = ? WHERE id = ?

     SI el nodo es 'concepto':
       └─ buscar el insumo vinculado (ep.insumo_id → insumos.id)
         ├─ SI el insumo es compuesto (es_compuesto = 1):
         │    └─ total = cantidad × (SELECT SUM(cant * precio)
         │                            FROM apu_matrices
         │                            WHERE matriz_id = insumo_id)
         └─ SI NO (básico):
                └─ total = cantidad × insumos.costo_final

     SI el nodo es 'capitulo':
       └─ total = SUM(hijos.total)

     UPDATE estructura_presupuesto SET total = ? WHERE id = ?
     subir al padre y repetir
```

### 3.3 No se necesita `precio_unitario` en `estructura_presupuesto`

El precio siempre se resuelve desde:
- `insumos.costo_final` para insumos básicos
- `apu_matrices` (costo total del APU) para insumos compuestos

---

## 4. Contrato del nuevo dict de árbol

`build_budget_tree()` devolverá por nodo:

```python
{
    "id":               int,
    "padre_id":         int | None,
    "wbs":              str,
    "nivel":            int,
    "tipo":             str,          # "capitulo" | "concepto"
    "insumo_id":        int | None,   # solo conceptos
    "descripcion":      str,          # conceptos: COALESCE(i.descripcion, n.descripcion)
                                      # capitulos: n.descripcion
    "cantidad":         float | None,
    "total":            float,        # unificado
    "notas_rapidas":    str | None,
    "modificado_en":    str | None,
    "creado_en":        str | None,
    "estado":           int,
    "hijos":            list[dict],
}
```

**5 campos eliminados** del dict anterior: `descripcion_corta`, `unidad`,
`precio_unitario`, `importe`, `subtotal`.

### 4.1 SQL de `build_budget_tree()`

```sql
SELECT
    n.id, n.padre_id, n.wbs, n.nivel, n.tipo, n.insumo_id,
    CASE WHEN n.tipo = 'concepto'
         THEN COALESCE(i.descripcion, n.descripcion)
         ELSE n.descripcion
    END AS descripcion,
    n.cantidad, n.total,
    n.notas_rapidas, n.modificado_en, n.creado_en, n.estado
FROM estructura_presupuesto n
LEFT JOIN insumos i ON i.id = n.insumo_id
WHERE n.proyecto_id = ? AND n.activo = 1
ORDER BY n.wbs
```

---

## 5. Catálogo de workarounds a eliminar

### 5.1 El CASE en tres versiones → se vuelve `SUM(total)`

Cada vez que hay que sumar hijos de un capítulo, el código pregunta el tipo
de cada hijo para decidir qué columna usar:

```sql
-- ANTES (en core.py:346, importar.py:739, repos.py:283)
CASE WHEN tipo = 'concepto'
     THEN COALESCE(importe, 0)
     ELSE COALESCE(subtotal, 0)
END

-- DESPUÉS
COALESCE(total, 0)
```

**Archivos:** `backend/core.py`, `backend/importar.py`, `backend/repos.py`

### 5.2 UI: bifurcación por tipo en cada fila → campo directo

```python
# ANTES (arbol.py:140)
_fmt(n.get("importe") if n.get("tipo") == "concepto" else n.get("subtotal"))

# DESPUÉS
_fmt(n.get("total"))
```

**Archivo:** `frontend/widgets/arbol.py`

### 5.3 total_obra(): fallback cadena → campo directo

```python
# ANTES (core.py:265)
sum(n.get("subtotal") or n.get("importe") or 0 for n in nodes)

# DESPUÉS
sum(n.get("total", 0) for n in nodes)
```

**Archivo:** `backend/core.py`

### 5.4 Exportar OPUS: bifurcación por tipo → campo directo

```python
# ANTES (exportar.py:588-596)
pre_pre = subtotal if es_capitulo else pu
pre_vol = 1.0     if es_capitulo else cantidad
pre_imp = 0.0     if es_capitulo else (cantidad * pu)

# DESPUÉS — el campo OPUS PRE_PRE recibe total para capitulos,
# y precio_unitario viene de insumos para conceptos via JOIN
```

```python
# ANTES (exportar.py:640) — fallback incorrecto
cd = float(nodo.get('subtotal') or (float(nodo.get('cantidad') or 0) * pu))

# DESPUÉS
cd = float(nodo.get('total') or 0)
```

**Archivo:** `backend/exportar.py`

### 5.5 LaTeX: guard defensivo → campo directo

```python
# ANTES (latex.py:258-259)
if "subtotal" in partida and partida["subtotal"]:
    lines.append(rf"\SubtotalPartida{{{partida['subtotal']}}}")

# DESPUÉS
lines.append(rf"\SubtotalPartida{{{partida['total']}}}")
```

**Archivo:** `backend/latex.py`

### 5.6 Recálculo inline en paneles → campo directo

```python
# ANTES (paneles.py:698) — recalcula por si acaso
importe = comp.get("importe", 0) or (pu * comp.get("cantidad", 0))

# DESPUÉS — este código es de apu_matrices, NO CAMBIA
# (importe en APU no es el mismo que en estructura_presupuesto)
```

**Archivo:** `frontend/paneles.py` — SIN CAMBIO (es APU, no árbol)

---

## 6. Modelo de edición

### 6.1 Columnas del árbol después del cambio

| Índice | Columna | Visible | Editable | Almacenado en |
|--------|---------|---------|----------|---------------|
| 0 | Nivel | ✅ | ❌ | calculado (wbs) |
| 1 | Descripción | ✅ | ❌ (conceptos) / ✅ (agrupadores) | `insumos.descripcion` via JOIN /
|   |         |   |                            | `estructura_presupuesto.descripcion` |
| 2 | Cant | ✅ | ✅ | `estructura_presupuesto.cantidad` |
| 3 | Total | ✅ | ❌ | `estructura_presupuesto.total` |
| 4 | Tipo | ❌ | ❌ | `n.tipo` |
| 5 | Estado | ❌ | ❌ | `n.estado` |
| 6 | Notas | ❌ | ❌ | `n.notas_rapidas` |
| 7 | Creado | ❌ | ❌ | `n.creado_en` |
| 8 | Modificado | ❌ | ❌ | `n.modificado_en` |

`EDITABLE = {2}` (solo Cantidad). `_VISIBLE = {0, 1, 2, 3}`.

### 6.2 Editar cantidad en el árbol

Es la única edición directa en el árbol.

```
Usuario F2 en celda Cant (col 2)
  → QTreeWidget completa la edición
  → itemChanged(item, column=2)
    → extraer concepto_id de ID_ROLE (col 0)
    → validar que sea numérico
    → Api.concepto_actualizar_cantidad(concepto_id, cantidad)
      → ConceptoRepo.actualizar_cantidad(id, cantidad)
        → UPDATE estructura_presupuesto SET cantidad = ?
        → actualizar_total(id)
          → para este concepto: total = calculado según §3.2
          → para cada capítulo padre: total = SUM(hijos.total) (bottom-up)
```

### 6.3 Editar descripción de agrupador (capítulo)

```
Usuario F2 en celda Descripción (fila tipo='capitulo')
  → itemChanged(item, column=1)
    → extraer nodo_id de WBS_ROLE (col 0)
    → Api.agrupador_actualizar_descripcion(nodo_id, texto)
      → NodoRepo.actualizar_descripcion(id, texto)
        → UPDATE estructura_presupuesto SET descripcion = ?
          WHERE id = ? AND tipo = 'capitulo'
```

No hay hash ni unicidad — los nombres de capítulo son libres.

### 6.4 Editar descripción de insumo (desde catálogo)

```
Usuario → menú contextual en TablaInsumos → "Editar descripción"
  → EditarDescripcionDialog
  → Api.insumo_actualizar_descripcion(insumo_id, texto)
    → InsumoRepo.actualizar_descripcion()
      → generar_hash(texto)
      → buscar_por_hash(hash, proyecto_id) — verifica unicidad
      → si duplicado: ValueError("Ya existe...")
      → UPDATE insumos SET descripcion = ?, hash = ?
```

**Sin cascada inmediata al árbol:** el JOIN en `build_budget_tree()` captará
el cambio la próxima vez que se recargue el árbol.

### 6.5 Editar precio de insumo (desde catálogo)

```
Usuario → menú contextual → "Editar precio"
  → EditarPrecioDialog
  → Api.insumo_actualizar_precio(insumo_id, precio)
    → InsumoRepo.actualizar_precio()
      → UPDATE insumos SET costo_mn = ?, costo_final = ?
```

**Cascada necesaria (MVP: manual):** El cambio de precio de un insumo afecta
el `total` de todos los conceptos del árbol que usen ese insumo. El recálculo
completo es costoso y se pospone a un botón "Recalcular" o se hace al cambiar
de pestaña.

### 6.6 Editar APU (componentes)

```
Usuario edita cantidad/precio de un componente en el APU
  → ApuMatricesRepo.actualizar()
  → ApuResumenTotalesRepo.recalcular(matriz_id)
  → si el APU pertenece a un concepto del árbol:
       actualizar_total(concepto_id)  — ver §3.2
```

---

## 7. Estrategia de refresco del árbol

### 7.1 Refresco forzado (MVP)

Después de cualquier edición que afecte al árbol (insumo, APU), se recarga
completamente:

```python
def _refrescar_tab_activa(self):
    """Recarga la pestaña activa y el árbol del presupuesto si existe."""
    from frontend.widgets.insumos import TablaInsumos

    w = self._tabs.currentWidget()

    # Refrescar insumos si corresponde
    tabla_ins = w if isinstance(w, TablaInsumos) else w.findChild(TablaInsumos) if w else None
    if tabla_ins:
        ids = self._api.insumo_ids_con_apu()
        insumos = self._api.insumos()
        tabla_ins.poblar(insumos, ids)

    # Refrescar árbol del presupuesto si existe
    if self._arbol_presupuesto is not None:
        nodos = self._api.presupuesto_arbol()
        self._arbol_presupuesto.poblar(nodos)
```

### 7.2 Refresco lazy (futuro)

Si el recálculo completo es lento con proyectos grandes:

```python
def _on_edit_insumo(self, ...):
    ...
    self._arbol_dirty = True   # marcar como desactualizado

def _on_tab_changed(self, index):
    if self._arbol_dirty and self._tabs.tabText(index) == "Presupuesto":
        self._refrescar_arbol()
        self._arbol_dirty = False
```

Para MVP se usa el refresco forzado.

---

## 8. Plan de implementación por archivo

### Fase 0 — Schema (1 archivo)

| Archivo | Cambio |
|---------|--------|
| `backend/schema.sql` | Eliminar `clave`, `descripcion_corta`, `unidad`, `precio_unitario`, `importe`, `subtotal`. Agregar `insumo_id`, `total`, `formula`. Actualizar comentarios. |

### Fase 1 — Recálculo (3 archivos)

El CASE triple se reemplaza por `SUM(COALESCE(total,0))` en los tres sitios.
Para conceptos, el recálculo debe computar `total` según el algoritmo de §3.2.

| Archivo | Función | Cambio |
|---------|---------|--------|
| `backend/repos.py` | `actualizar_subtotal()` → `actualizar_total()` | UPDATE `total` con lógica de §3.2, sube por padres |
| `backend/repos.py` | `actualizar_precio()` / `actualizar_cantidad()` | Reflejar nuevo nombre, la lógica la maneja `actualizar_total()` |
| `backend/importar.py` | `_recalcular_subtotales()` → `_recalcular_totales()` | Mismo cambio que repos.py |
| `backend/importar.py` | INSERTs (3 sitios) | `subtotal=0` → `total=0` |
| `backend/importar.py` | L559 | `SUM(subtotal)` → `SUM(total)` |
| `backend/core.py` | `validar()` | CASE de validación usa `total` |
| `backend/core.py` | `total_obra()` | `n.get("total", 0)` directo |

### Fase 2 — `build_budget_tree()` (1 archivo)

| Archivo | Cambio |
|---------|--------|
| `backend/core.py` | SQL: LEFT JOIN insumos ON `i.id = n.insumo_id`, SELECT `n.total` + `n.insumo_id`, COALESCE descripción. Eliminar del SELECT: `n.clave, n.descripcion_corta, n.unidad, n.precio_unitario, n.importe, n.subtotal`. Actualizar docstring del dict. |

### Fase 3 — UI (1 archivo)

| Archivo | Cambio |
|---------|--------|
| `frontend/widgets/arbol.py` | COLUMNAS: de 13 a 9. `_celdas()`: `n.get("total")` directo. `_VISIBLE={0,1,2,3}`. `EDITABLE={2}`. `_search_cols={1}`. |

### Fase 4 — Conexión itemChanged (2 archivos)

| Archivo | Cambio |
|---------|--------|
| `frontend/widgets/arbol.py` | Agregar señal `itemChanged` o conexión externa |
| `frontend/paneles.py` | Conectar `tree.itemChanged` → `_on_concepto_editado()`. Agregar `_on_concepto_editado()` que llama a API para cantidad y descripción de agrupador |
| `frontend/paneles.py` | Extender `_refrescar_tab_activa()` para recargar el árbol |
| `frontend/api.py` | Exponer `concepto_actualizar_cantidad()`, `agrupador_actualizar_descripcion()` |

### Fase 5 — Lectores del dict de árbol (5 archivos)

Cambio mecánico: `importe` → `total`, `subtotal` → `total`.

| Archivo | Líneas | Cambio |
|---------|--------|--------|
| `backend/latex.py` | 134,141,166,255,258,401,428,452 | `subtotal`/`importe` → `total` |
| `backend/exportar.py` | 592,594,640 | `subtotal` → `total` |
| `frontend/api.py` | 70,137 | docstring + `r.get("total")` |
| `frontend/paneles.py` | 494 | `c.get("total", 0)` |

### Fase 6 — Documentación (6 archivos)

| Archivo | Secciones |
|---------|-----------|
| `docs/SCHEMA.md` | L106-142, 236, 251, 263 |
| `docs/DOCUMENTACION.md` | L465-466, 550 |
| `docs/GUIA_IMPLEMENTACION.md` | L132, 206-207 |
| `docs/DECISIONES_PENDIENTES.md` | L144 |
| `docs/PLAN_EXPORTACION.md` | L156, 281, 692 |
| `AGENTS.md` | L49-50 |

---

## 9. Resumen de líneas

| Fase | Archivos | Líneas aprox |
|------|----------|-------------|
| 0 — Schema | 1 | 5 |
| 1 — Recálculo | 3 | 80 |
| 2 — build_budget_tree | 1 | 30 |
| 3 — UI columnas | 1 | 25 |
| 4 — itemChanged + API | 3 | 60 |
| 5 — Lectores | 4 | 20 |
| 6 — Docs | 6 | 40 |
| **Total** | **~15** | **~260** |

---

## 10. Nota sobre migración

Este proyecto está en beta y no tiene scripts de migración de datos. El schema
se edita directamente (`schema.sql`). Las bases `.presup` existentes con el
esquema anterior son incompatibles — hay que regenerarlas desde cero con el
nuevo `schema.sql` y el importador OPUS.
