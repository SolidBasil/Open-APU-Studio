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

Se agrega `formula` para calcular `cantidad` de forma opcional.

```sql
CREATE TABLE IF NOT EXISTS estructura_presupuesto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    padre_id        INTEGER REFERENCES estructura_presupuesto(id) ON DELETE CASCADE,
    wbs             TEXT    NOT NULL,
    nivel           INTEGER NOT NULL,
    orden           INTEGER NOT NULL DEFAULT 0,
    tipo            TEXT    NOT NULL DEFAULT 'capitulo'
                    CHECK(tipo IN ('capitulo', 'concepto')),
    clave           TEXT,
    descripcion     TEXT    NOT NULL DEFAULT '',
    descripcion_corta TEXT,
    unidad          TEXT,
    cantidad        REAL,                         -- valor fijo O resultado de formula
    formula         TEXT,                          -- 🆕 expresion opcional para cantidad
    precio_unitario REAL,
    importe         REAL,                          -- 🆕 calculado en Python (antes GENERATED)
    subtotal        REAL    NOT NULL DEFAULT 0.0,
    estado          INTEGER NOT NULL DEFAULT 0,
    notas_rapidas   TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

## 5. Tabla nueva: `variables_formula`

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

## 6. Evaluador (`backend/formulas.py`)

Se vendea **simpleeval** como `backend/formulas.py` (archivo único, MIT, ~400 líneas).

### 6.1 Función pública

```python
def evaluar(expresion: str, variables: dict[str, float]) -> float:
    """Evalua una expresion aritmetica con +, -, *, /, (), potencias.
    variables: dict con nombres → valor (ya resueltos)"""
```

### 6.2 Resolución recursiva de variables

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

### 6.3 Operadores soportados

`+` `-` `*` `/` `()` `**` `and` `or` `not` `==` `!=` `<` `>` `<=` `>=`

### 6.4 Flujo de evaluación en fórmulas

Cuando una celda tiene `formula` no NULL:

```
1. Se parsea la expresion con simpleeval
2. Cada token que no es numero/operador se busca en variables_formula
3. Se resuelve recursivamente (con deteccion de ciclos)
4. Se evalua la expresion completa con los valores resueltos
5. Se escribe el resultado en la columna `valor` (o `cantidad`)
```

## 7. Operaciones sobre `insumos`

### 7.1 DROP (4 columnas)

| Columna | Motivo |
|---------|--------|
| `costo_base` | Sin campo en ningún DBF de OPUS |
| `marca` | Sin campo en ningún DBF de OPUS |
| `pais_origen` | Sin campo en ningún DBF de OPUS |
| `es_basico` | Redundante con `es_compuesto` |

### 7.2 ADD (3 columnas)

| Columna | Tipo | Default | OPUS |
|---------|------|---------|------|
| `catfsr` | TEXT | NULL | `CATFSR` |
| `factor_fsr` | REAL | NULL | `FSR` |
| `fsr_minimo` | INTEGER | 0 | `FSR_MINIMO` |

## 8. Cambios en código

### 8.1 `backend/schema.sql`

- `insumos`: DROP 4 columnas, ADD 3 columnas FSR
- `apu_matrices`: DROP `rendimiento`, `cantidad`, `importe` GENERATED; ADD `valor`, `operador`, `importe` REAL
- `estructura_presupuesto`: ADD `formula TEXT`, cambiar `importe` de GENERATED a REAL
- Nueva tabla: `variables_formula`

### 8.2 `backend/formulas.py`

Nuevo archivo. Vendereo de simpleeval + función `resolver()`.

### 8.3 `backend/repos.py`

- Nuevo `VariableFormulaRepo`

### 8.4 `backend/core.py`

- Nueva función `resolver_formulas()`: recibe lista de variables/expresiones modificadas, recorre dependencias, recalcula `valor`/`cantidad`/`importe` afectados

### 8.5 `backend/importar.py`

- Quitar mapeo `BASICO` → `es_basico`
- Leer `COMENTARIO` → `insumos.comentarios`
- Leer `CATFSR`, `FSR`, `FSR_MINIMO`
- Leer `EXPRESION` → `apu_matrices.formula`
- Leer formulas de concepto desde `*O.DBF` → pendiente de definir

### 8.6 `backend/exportar.py`

- Quitar escritura `BASICO`
- Escribir `CATFSR`, `FSR`, `FSR_MINIMO`
- Escribir `EXPRESION` desde `apu_matrices.formula`

## 9. Resumen de tablas afectadas

| Tabla | Cambio |
|-------|--------|
| `insumos` | 4 DROP + 3 ADD = 39 columnas finales |
| `apu_matrices` | `cantidad`+`rendimiento` → `valor`+`operador`; `importe` no GENERATED; `formula` se queda |
| `estructura_presupuesto` | +`formula`; `importe` pasa a calculado en Python |
| `variables_formula` | 🆕 tabla nueva |

## 10. Pendientes futuros

| Columna | Campo OPUS | DBF | Depende de |
|---------|------------|-----|-----------|
| `costo_me` | `PUNITME` | `*P.DBF` | Módulo moneda extranjera |
| `formula_costo_mn` | fórmula | `*C.DBF` | Módulo fórmulas OPUS |
| `formula_costo_me` | fórmula | `*C.DBF` | Módulo fórmulas OPUS |
| `indice_1..6` | `A`-`F` | `*P.DBF` | Módulo fórmulas OPUS |
| Dimensiones concepto | LARGO, ANCHO... | `*O.DBF` | Integración variables_formula |

## 11. Sin migración

Beta — schema se edita en caliente. Bases `.presup` existentes incompatibles.
Regenerar desde cero con importador OPUS actualizado.
