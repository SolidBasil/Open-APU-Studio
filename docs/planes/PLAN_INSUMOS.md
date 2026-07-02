# Plan: Transformación de `insumos` y sistema de fórmulas

## 1. DDL actual: `insumos`

```sql
CREATE TABLE IF NOT EXISTS insumos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id         INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    hash                TEXT,
    clave_opus          TEXT,
    clave_usuario       TEXT,
    tipo_id             INTEGER NOT NULL REFERENCES tipos_insumo(id),
    es_compuesto        INTEGER NOT NULL DEFAULT 0,
    descripcion         TEXT,
    descripcion_corta   TEXT,
    unidad              TEXT,
    familia_id          INTEGER REFERENCES familias(id),
    subfamilia_id       INTEGER REFERENCES subfamilias(id),
    proveedor_id        INTEGER REFERENCES proveedores(id),
    costo_mn            REAL    NOT NULL DEFAULT 0.0,
    costo_me            REAL    NOT NULL DEFAULT 0.0,
    costo_base          REAL    NOT NULL DEFAULT 0.0,   -- ❌ DROP
    costo_final         REAL    NOT NULL DEFAULT 0.0,
    salario_nominal     REAL,
    salario_real        REAL,
    usar_hoja_fasar     INTEGER NOT NULL DEFAULT 0,
    marca               TEXT,                           -- ❌ DROP
    pais_origen         TEXT,                           -- ❌ DROP
    tipo_trabajo        TEXT    CHECK(tipo_trabajo IN ('subcontrato', 'acarreo', 'destajo')),
    fecha_precio        TEXT,
    indice_inegi        TEXT,
    peso_kg             REAL,
    comentarios         TEXT,
    formula_costo_mn    TEXT,
    formula_costo_me    TEXT,
    indice_1            REAL,
    indice_2            REAL,
    indice_3            REAL,
    indice_4            REAL,
    indice_5            REAL,
    indice_6            REAL,
    activo              INTEGER NOT NULL DEFAULT 1,
    es_basico           INTEGER NOT NULL DEFAULT 0,   -- ❌ DROP
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(proyecto_id, hash)
);
```

## 2. DDL destino: `insumos`

```sql
CREATE TABLE IF NOT EXISTS insumos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id         INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    hash                TEXT,
    clave_opus          TEXT,
    clave_usuario       TEXT,
    tipo_id             INTEGER NOT NULL REFERENCES tipos_insumo(id),
    es_compuesto        INTEGER NOT NULL DEFAULT 0,
    descripcion         TEXT,
    descripcion_corta   TEXT,
    unidad              TEXT,
    familia_id          INTEGER REFERENCES familias(id),
    subfamilia_id       INTEGER REFERENCES subfamilias(id),
    proveedor_id        INTEGER REFERENCES proveedores(id),
    costo_mn            REAL    NOT NULL DEFAULT 0.0,
    costo_me            REAL    NOT NULL DEFAULT 0.0,
    costo_directo       REAL    NOT NULL DEFAULT 0.0,  -- 🆕 sin factores de sobrecosto
    costo_final         REAL    NOT NULL DEFAULT 0.0,
    salario_nominal     REAL,
    salario_real        REAL,
    usar_hoja_fasar     INTEGER NOT NULL DEFAULT 0,
    tipo_trabajo        TEXT    CHECK(tipo_trabajo IN ('subcontrato', 'acarreo', 'destajo')),
    fecha_precio        TEXT,
    indice_inegi        TEXT,
    peso_kg             REAL,
    comentarios         TEXT,
    formula_costo_mn    TEXT,
    formula_costo_me    TEXT,
    indice_1            REAL,
    indice_2            REAL,
    indice_3            REAL,
    indice_4            REAL,
    indice_5            REAL,
    indice_6            REAL,
    activo              INTEGER NOT NULL DEFAULT 1,
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    -- Nuevas columnas FSR
    catfsr              TEXT,
    factor_fsr          REAL,
    fsr_minimo          INTEGER NOT NULL DEFAULT 0,
    UNIQUE(proyecto_id, hash)
);
```

## 3. DDL destino: `apu_matrices`

Se reemplazan `cantidad`/`rendimiento`/`importe` GENERATED por `valor`/`operador`/`importe` calculado en Python.
`formula` ya existe y se mantiene.

```sql
CREATE TABLE IF NOT EXISTS apu_matrices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    matriz_id       INTEGER NOT NULL,
    insumo_id       INTEGER NOT NULL REFERENCES insumos(id),
    valor           REAL    NOT NULL DEFAULT 0.0,  -- cantidad fija O resultado de formula
    operador        TEXT    NOT NULL DEFAULT '*' CHECK(operador IN ('*', '/')),
    precio          REAL    NOT NULL DEFAULT 0.0,
    importe         REAL    NOT NULL DEFAULT 0.0,  -- calculado en Python: valor * precio o precio / valor
    formula         TEXT,                          -- expresion opcional. Si no NULL, se evalua para obtener valor
    orden           INTEGER NOT NULL DEFAULT 0,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

## 4. DDL destino: `estructura_presupuesto`

**Sin cambios en `estructura_presupuesto`** — la unificación `importe/subtotal → total`
y la columna `formula` ya están implementadas vía `PLAN_PRESUPUESTO.md`.
El DDL actual en `schema.sql` (Bloque 5) es el correcto y no se modifica en este plan.

## 5. Tabla nueva: `factores_sobrecosto`

Factores fijos por proyecto para la cascada de sobrecostos sobre `costo_directo`.

```sql
CREATE TABLE IF NOT EXISTS factores_sobrecosto (
    proyecto_id             INTEGER PRIMARY KEY REFERENCES proyectos(id) ON DELETE CASCADE,
    pct_indirectos_campo    REAL NOT NULL DEFAULT 0.0,
    pct_indirectos_oficina  REAL NOT NULL DEFAULT 0.0,
    pct_financiamiento      REAL NOT NULL DEFAULT 0.0,
    pct_utilidad            REAL NOT NULL DEFAULT 0.0,
    pct_cargos_adicionales  REAL NOT NULL DEFAULT 0.0
);
```

Cascada de cálculo:

```
costo_directo              → CD
indirectos_campo   = CD · pct_indirectos_campo / 100
indirectos_oficina = CD · pct_indirectos_oficina / 100
subtotal1          = CD + indirectos_campo + indirectos_oficina
financiamiento     = subtotal1 · pct_financiamiento / 100
subtotal2          = subtotal1 + financiamiento
utilidad           = subtotal2 · pct_utilidad / 100
subtotal3          = subtotal2 + utilidad
cargos_adicionales = subtotal3 · pct_cargos_adicionales / 100
costo_final        = subtotal3 + cargos_adicionales
```

### 5.1 Interacción con FSR (ver `PLAN_FSR.md`)

Para insumos MO, `costo_directo` NO es el precio de compra — es `salario_real`
(que ya incorpora el Factor de Salario Real vía `factores_fsr`):

```
salario_nominal → FSR → salario_real → costo_directo → cascada → costo_final
```

**Orden completo para MO:**
1. `salario_nominal` (base diaria)
2. × `factor_fsr` de `factores_fsr` → `salario_real`
3. `costo_directo = salario_real`
4. Cascada de `factores_sobrecosto` → `costo_final`

Para el resto de tipos (material, equipo, etc.), `costo_directo` = precio de
compra/mercado.

Ambos planes (`factores_sobrecosto` y `factores_fsr`) modifican `costos_directo`
pero en etapas distintas y son independientes — no se solapan ni compiten.

## 6. Tabla nueva: `variables_formula`

Almacena variables nombradas que pueden referenciarse desde cualquier `formula`
en `apu_matrices`, `estructura_presupuesto`, o desde otras variables.

Soporte recursivo: `A = B+1`, `B = C*2`, `C = 5` → `A` = 11.

```sql
CREATE TABLE IF NOT EXISTS variables_formula (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    nombre          TEXT    NOT NULL,
    expresion       TEXT,                -- formula textual. NULL = valor fijo
    valor           REAL,                -- cachead. Si expresion=NULL es valor fijo; si no es el resultado de evaluar
    descripcion     TEXT,
    UNIQUE(proyecto_id, nombre)
);
```

## 7. Evaluador (`backend/formulas.py`)

Se vendea **simpleeval** como `backend/formulas.py` (archivo único, MIT, ~400 líneas).

### 7.1 Función pública

```python
def evaluar(expresion: str, variables: dict[str, float]) -> float:
    """Evalua una expresion aritmetica con +, -, *, /, (), potencias.
    variables: dict con nombres → valor (ya resueltos)"""
```

### 7.2 Resolución recursiva de variables

```python
def resolver(
    nombre: str,
    repo: "VariableFormulaRepo",
    proyecto_id: int,
    _resolviendo: set | None = None
) -> float:
    """Resuelve una variable recursivamente desde variables_formula.
    Detecta ciclos y levanta ValueError."""
```

### 7.3 Operadores soportados

`+` `-` `*` `/` `()` `**` `and` `or` `not` `==` `!=` `<` `>` `<=` `>=`

### 7.4 Flujo de evaluación en fórmulas

Cuando una celda tiene `formula` no NULL:

```
1. Se parsea la expresion con simpleeval
2. Cada token que no es numero/operador se busca en variables_formula
3. Se resuelve recursivamente (con deteccion de ciclos)
4. Se evalua la expresion completa con los valores resueltos
5. Se escribe el resultado en la columna `valor` (o `cantidad`)
```

## 8. Operaciones sobre `insumos`

### 8.1 DROP (4 columnas)

| Columna | Motivo |
|---------|--------|
| `costo_base` | Sin campo en ningún DBF de OPUS |
| `marca` | Sin campo en ningún DBF de OPUS |
| `pais_origen` | Sin campo en ningún DBF de OPUS |
| `es_basico` | Redundante con `es_compuesto` |

### 8.2 ADD (4 columnas)

| Columna | Tipo | Default | Origen |
|---------|------|---------|--------|
| `catfsr` | TEXT | NULL | `CATFSR` en *P.DBF |
| `factor_fsr` | REAL | NULL | `FSR` en *P.DBF |
| `fsr_minimo` | INTEGER | 0 | `FSR_MINIMO` en *P.DBF |
| `costo_directo` | REAL | 0.0 | Calculado, sin factores de sobrecosto |

## 9. Cambios en código

### 9.1 `backend/schema.sql`

- `insumos`: DROP 4 columnas, ADD 4 columnas (FSR + costo_directo)
- `apu_matrices`: DROP `rendimiento`, `cantidad`, `importe` GENERATED; ADD `valor`, `operador`, `importe` REAL
- `estructura_presupuesto`: Sin cambios — `formula` y `total` unificado ya están (vía `PLAN_PRESUPUESTO.md`)
- Nueva tabla: `factores_sobrecosto`
- Nueva tabla: `variables_formula`

### 9.2 `backend/formulas.py`

Nuevo archivo. Vendereo de simpleeval + función `resolver()`.

### 9.3 `backend/repos.py`

Nuevos repos:
- `FactoresSobrecostoRepo`
- `VariableFormulaRepo`

### 9.4 `backend/core.py`

- Nueva función `resolver_formulas()`: recorre dependencias de `variables_formula` y recalcula `valor`/`cantidad`/`importe`
- Nueva función `aplicar_cascada_sobrecosto()`: recibe `costo_directo` + `factores_sobrecosto`, devuelve `costo_final`

### 9.5 `backend/recalculo.py`

- Nueva etapa en `recalcular_proyecto()`: aplicar cascada de `factores_sobrecosto` a todos los insumos no-compuestos

### 9.6 `backend/importar.py`

- Quitar mapeo `BASICO` → `es_basico`
- Leer `COMENTARIO` → `insumos.comentarios`
- Leer `CATFSR`, `FSR`, `FSR_MINIMO`
- Leer `EXPRESION` → `apu_matrices.formula`
- `costo_directo` = `PRECIO` (mismo valor que `costo_mn`)
- Leer formulas de concepto desde `*O.DBF` → pendiente de definir

#### Mapeo `apu_matrices.valor` / `apu_matrices.operador` desde OPUS

| Tipo insumo | Campo OPUS | `valor` | `operador` |
|-------------|------------|---------|------------|
| MO (tipo_id=2) | `RENDTO` | `RENDTO` | `'/'` |
| Resto | `CANTIDAD` | `CANTIDAD` | `'*'` |

Razón: en OPUS la MO se calcula como `(CANTIDAD / RENDTO) × PRECIO`, pero `CANTIDAD`
suele ser 1.0 (una hora/día). Con `operador='/'` y `valor=RENDTO` se obtiene
`importe = PRECIO / RENDTO`, equivalente. El resto sigue siendo `CANTIDAD × PRECIO`.

### 9.7 `backend/exportar.py`

- Quitar escritura `BASICO`
- Escribir `CATFSR`, `FSR`, `FSR_MINIMO`
- Escribir `EXPRESION` desde `apu_matrices.formula`

### 9.8 Frontend

- `widgets/insumos.py`: columna "C. Directo" (oculta por defecto)
- `ajustes.py`: sección nueva "Factores de sobrecosto" con 5 spinboxes para los porcentajes

## 10. Resumen de tablas afectadas

| Tabla | Cambio |
|-------|--------|
| `insumos` | 4 DROP + 4 ADD = 40 columnas finales |
| `apu_matrices` | `cantidad`+`rendimiento` → `valor`+`operador`; `importe` no GENERATED; `formula` se queda |
| `estructura_presupuesto` | Sin cambios — unificación `total` ya implementada (vía `PLAN_PRESUPUESTO.md`) |
| `factores_sobrecosto` | 🆕 tabla nueva |
| `variables_formula` | 🆕 tabla nueva |

## 11. Pendientes futuros

| Columna | Campo OPUS | DBF | Depende de |
|---------|------------|-----|-----------|
| `costo_me` | `PUNITME` | `*P.DBF` | Módulo moneda extranjera |
| `formula_costo_mn` | fórmula | `*C.DBF` | Módulo fórmulas OPUS |
| `formula_costo_me` | fórmula | `*C.DBF` | Módulo fórmulas OPUS |
| `indice_1..6` | `A`-`F` | `*P.DBF` | Módulo fórmulas OPUS |
| Dimensiones concepto | LARGO, ANCHO... | `*O.DBF` | Integración variables_formula |

## 12. Sin migración

Beta — schema se edita en caliente. Bases `.presup` existentes incompatibles.
Regenerar desde cero con importador OPUS actualizado.
