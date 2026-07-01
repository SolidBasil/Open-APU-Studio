# Plan: Factor de Salario Real (FSR)

## 1. Motivación

El FSR (Factor de Salario Real) es el multiplicador que convierte un salario
nominal en el costo real de la mano de obra, incluyendo prestaciones, IMSS,
INFONAVIT, días no laborados, etc.

### 1.1 Modelo de datos OPUS

En `*P.DBF` (insumos) hay **tres campos** relacionados con FSR:

| Campo | Tipo | Contenido |
|-------|------|-----------|
| `FSR` | Numérico(10,6) | **El factor FSR** (ej. 1.77912). Es el valor que se multiplica por el salario nominal |
| `CATFSR` | Carácter(6) | **La clave de configuración** (ej. 'JOR8HR'). Referencia al `*8.DBF` |
| `FSR_MINIMO` | Carácter(1) | Flag: ¿es salario mínimo? |

`*8.DBF` contiene UNA fila por configuración FSR con **237 campos** (parámetros
de entrada + resultados intermedios + factor final). La clave compuesta es
`FSR_TIP` + `FSR_CLV` (ej. `0` + `'JOR8HR'`). El campo `FSR_CALC` (lógico)
indica si se calculó automáticamente.

`*9.DBF` contiene 85 registros fijos con el desglose línea por línea (el libro
de Excel del FASAR con todas las variables y fórmulas).

### 1.2 Modo de uso en OPUS

- El recurso MO tiene un flag **"Usar hoja de FASAR"** (`usar_hoja_fasar` en
  nuestra tabla). Cuando está activo, el FSR se calcula desde la configuración
  `CATFSR` → `*8.DBF`. Cuando no, el usuario escribe el factor directo en `FSR`.
- La columna `CATFSR` guarda qué configuración FSR usar (referencia al `*8.DBF`)
- El campo `FSR` guarda el factor numérico (calculado o manual) — es el
  multiplicador real

### 1.3 Estado actual en la app

- `importar.py:352` lee `FSR` como `float` — **esto es correcto para el factor**
  (el campo FSR es numérico). El problema es que no leemos `CATFSR`.
- `exportar.py:493` hardcodea `FSR: 1.0` en lugar de usar el valor real
- `usar_hoja_fasar` existe pero nunca se usa — es el flag "Usar hoja de FASAR"
- No tenemos tabla para las configuraciones FSR (`*8.DBF`)
- `salario_real = PRECIO * FSR` — el cálculo es correcto, pero falta vínculo
  con la configuración

---

## 2. Nueva tabla `factores_fsr`

Una fila = una configuración FSR (una "hoja" de cálculo).

### 2.1 DDL

```sql
CREATE TABLE IF NOT EXISTS factores_fsr (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id),
    clave           TEXT    NOT NULL,            -- ej. 'JOR8HR', 'JOR7HR'
    nombre          TEXT    NOT NULL DEFAULT '',  -- ej. 'Jornada 8 horas'

    -- Metadata del cálculo
    modo_calculo    INTEGER NOT NULL DEFAULT 1,  -- AT: 1=factores, 0=dinero
    anio            INTEGER NOT NULL DEFAULT 2010, -- AV
    semestre        INTEGER NOT NULL DEFAULT 1,  -- AR: 1=ene-jun, 2=jul-dic

    -- Jornada
    tipo_jornada    INTEGER NOT NULL DEFAULT 0,  -- BB: 0=diurna, 1=mixta, 2=nocturna
    horas_jornada   REAL    NOT NULL DEFAULT 8.0,-- BC

    -- Salarios de referencia
    salario_minimo  REAL    NOT NULL DEFAULT 57.46, -- AW
    salario_nominal_base REAL NOT NULL DEFAULT 100.0, -- FSR_SABA

    -- Días pagados
    dias_calendario    REAL NOT NULL DEFAULT 365.25, -- FSR_DPCAL
    dias_aguinaldo     REAL NOT NULL DEFAULT 15.0,   -- FSR_DPAGU
    dias_vacaciones    REAL NOT NULL DEFAULT 6.0,    -- FSR_DNVAC
    prima_vacacional   REAL NOT NULL DEFAULT 25.0,   -- FSR_PPVAC (%)
    dias_dominical     REAL NOT NULL DEFAULT 0.0,    -- FSR_DNDOM
    prima_dominical    REAL NOT NULL DEFAULT 0.0,    -- FSR_PPDOM (%)
    dias_otros_pagados REAL NOT NULL DEFAULT 0.0,    -- FSR_DPOT1

    -- Días no laborados
    dias_descanso      REAL NOT NULL DEFAULT 52.18,  -- FSR_DNSEP
    dias_festivos      REAL NOT NULL DEFAULT 7.17,   -- FSR_DNFES
    dias_contrato      REAL NOT NULL DEFAULT 0.0,    -- FSR_DNDCO
    dias_sindicato     REAL NOT NULL DEFAULT 1.0,    -- FSR_DNSIN
    dias_enfermedad    REAL NOT NULL DEFAULT 0.45,   -- FSR_DNPER
    dias_clima         REAL NOT NULL DEFAULT 3.85,   -- FSR_DNCLI
    dias_arrastre      REAL NOT NULL DEFAULT 0.0,    -- FSR_DNARR
    dias_guardia       REAL NOT NULL DEFAULT 0.0,    -- FSR_DNGUA
    dias_otros_no_lab  REAL NOT NULL DEFAULT 5.0,    -- FSR_DNOT3

    -- Cuotas IMSS (%)
    imss_guarderias    REAL NOT NULL DEFAULT 1.0,     -- FSR_IMGUA
    imss_retiro        REAL NOT NULL DEFAULT 2.0,     -- FSR_IMSAR
    imss_riesgos       REAL NOT NULL DEFAULT 7.58875, -- FSR_IMRTR
    imss_invalidez     REAL NOT NULL DEFAULT 1.75,    -- FSR_IMINV
    imss_cesantia      REAL NOT NULL DEFAULT 3.15,    -- FSR_IMCE
    imss_enfermedad    REAL NOT NULL DEFAULT 5.35365, -- FSR_IMENF (suma interna)

    -- Otros impuestos (%)
    infonavit          REAL NOT NULL DEFAULT 5.0,    -- FSR_IMINF
    impuesto_nomina    REAL NOT NULL DEFAULT 0.0,    -- FSR_IMNOM
    otros_impuestos    REAL NOT NULL DEFAULT 0.0,    -- FSR_IMOT2

    -- Factor calculado (caché)
    factor_fsr         REAL,          -- NULL = pendiente de calcular
    fecha_calculo      TEXT,          -- cuándo se calculó

    -- Auditoría
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (proyecto_id) REFERENCES proyectos(id),
    UNIQUE (proyecto_id, clave)
);
```

### 2.2 Notas de diseño

- **Solo parámetros de entrada** (input): las columnas almacenan los valores
  que el usuario puede modificar (salario mínimo, días de aguinaldo, % IMSS,
  etc.), no los calculados intermedios.
- `factor_fsr` es el resultado final del cálculo, cacheado. Se recalcula si
  algún parámetro cambia.
- Las ~40 variables calculadas intermedias (BD, BE, BF, BG, FSR_SAMI,
  FSR_SACAL, AC, AD, ..., BH) no se almacenan — se computan en Python.

---

## 3. Cambios en `insumos`

### 3.1 Columnas afectadas

| Columna | Acción |
|---------|--------|
| `usar_hoja_fasar` | 🔄 Mantener — **no es typo**, es "Usar hoja de FASAR" de OPUS |
| `salario_nominal` | ✅ Mantener — input del FSR para MO |
| `salario_real` | ✅ Mantener — `salario_nominal * COALESCE(FSR, 1.0)` |
| *(nueva)* `catfsr` | ➕ FK a `factores_fsr(id)` — qué configuración FSR usar |
| *(nueva)* `fsr_minimo` | ➕ Flag: `BOOLEAN NOT NULL DEFAULT 0` |
| *(nota)* `FSR` | Ya existe como `salario_real` después de aplicar el factor |

### 3.2 Columnas finales de insumos (solo MO)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `salario_nominal` | REAL | Salario base diario |
| `salario_real` | REAL | Salario real diario (nominal * factor_fsr) |
| `usar_hoja_fasar` | BOOLEAN | True=calcular FSR desde catfsr, False=manual |
| `catfsr` | TEXT | Clave de configuración FSR (FK a factores_fsr) |
| `fsr_minimo` | BOOLEAN | True si es salario mínimo |

### 3.3 Semántica

- `salario_real = salario_nominal * COALESCE(fsr.factor_fsr, 1.0)`
- Cuando `usar_hoja_fasar = True`: el factor viene de `factores_fsr` vía `catfsr`
- Cuando `usar_hoja_fasar = False`: el usuario escribe `salario_real` directo
  (y `catfsr` puede ser NULL)
- Para insumos que NO son MO: todos estos campos son NULL/0

---

## 4. Algoritmo de cálculo FSR

### 4.0 ⚠️ Versión desactualizada

El algoritmo implementado corresponde a la **Ley Federal del Trabajo y LSS
vigente en 2010**. Las tasas IMSS, porcentajes INFONAVIT, días de ley y demás
parámetros han cambiado por reformas posteriores.

**Este cálculo es una base histórica.** Antes de usar el módulo FSR en
producción, debe actualizarse conforme a la legislación vigente al momento
del proyecto. Ver §11.

### 4.1 Pseudocódigo (versión 2010)

```python
def calcular_fsr(config: FSRConfig) -> float:
    """
    Implementa el cálculo OPUS 2010 del Factor de Salario Real.
    Retorna el factor multiplicador (ej. 1.77912).
    ADVERTENCIA: tasas y parámetros desactualizados — ver §4.0.
    """
    AT = config.modo_calculo       # 1=factores, 2=dinero
    AW = config.salario_minimo
    AV = config.anio
    AR = config.semestre
    BB = config.tipo_jornada       # 0,1,2
    BC = config.horas_jornada
    SABA = config.salario_nominal_base

    # ── Horas extras ──
    BD = BC - (8 if BB == 0 else 7.5 if BB == 1 else 7)  # extras por jornada
    BE = 1.1875 if BB == 0 else 1.2 if BB == 1 else 1.214286  # máx dobles
    BF = min(BE, BD) if BD > 0 else 0  # horas dobles
    BG = BD - BF if BD > 0 else 0       # horas triples

    # ── Salarios calculados ──
    if AT == 1:
        SAMI = 1.0
        SACAL = SABA * (1 + BG / (8 if BB == 0 else 7.5 if BB == 1 else 7)) / AW
    else:
        SAMI = AW
        SACAL = SABA * (1 + BG / (8 if BB == 0 else 7.5 if BB == 1 else 7))

    # ── Días pagados ──
    DPCAL = config.dias_calendario
    DPAGU = config.dias_aguinaldo
    DPPVA = config.prima_vacacional / 100 * config.dias_vacaciones
    DPPDO = config.prima_dominical / 100 * config.dias_dominical
    DPHEX = (BF * 2 + BG * 3) / 24 * DPCAL if BD > 0 else 0
    DPOT1 = config.dias_otros_pagados
    DPA = DPCAL + DPAGU + DPPVA + DPPDO + DPHEX + DPOT1  # Tp

    # ── Días no laborados ──
    DNSEP = config.dias_descanso
    DNFES = config.dias_festivos
    DNDCO = config.dias_contrato
    DNSIN = config.dias_sindicato
    DVAC  = config.dias_vacaciones
    DNPER = config.dias_enfermedad
    DNCLI = config.dias_clima
    DNARR = config.dias_arrastre
    DNGUA = config.dias_guardia
    DNOT3 = config.dias_otros_no_lab
    DNLA  = DNSEP + DNFES + DNDCO + DNSIN + DVAC + DNPER + DNCLI + DNARR + DNGUA + DNOT3
    DLA   = DPCAL - DNLA  # Tl

    # ── Factores ──
    FSI = DPA / DLA       # TP/TL
    FSBC = DPA / DPCAL    # Factor SBC
    SABC = SACAL * FSBC   # Salario Base de Cotización

    # ── Límites ──
    # AA = f(AV): cuota fija %
    if AV <= 2003: AA = 17.15
    elif AV == 2004: AA = 17.80
    elif AV == 2005: AA = 18.45
    elif AV == 2006: AA = 19.10
    elif AV == 2007: AA = 19.75
    else: AA = 20.40

    # AB = f(AV): excedente 3 SMGDF %
    if AV <= 2003: AB = 3.55
    elif AV == 2004: AB = 3.06
    elif AV == 2005: AB = 2.57
    elif AV == 2006: AB = 2.08
    elif AV == 2007: AB = 1.59
    else: AB = 1.10

    # AU: excedente
    AU = max(0, SABC - 3 * SAMI)

    # AS = f(AV, AR): límite inv. vida cesantía (en UM)
    if AV <= 2003: AS_UM = 20
    elif AV == 2004: AS_UM = 21
    elif AV == 2005: AS_UM = 22
    elif AV == 2006: AS_UM = 23
    elif AV == 2007 and AR == 1: AS_UM = 24
    else: AS_UM = 25

    BA = 25 * SAMI  # límite prest. patronales general
    AY = AS_UM * SAMI  # límite inv. vida cesantía
    AZ = AY  # límite INFONAVIT

    # ── Tasas IMSS ──
    IMGM = 1.05 + (0.375 if SACAL <= SAMI else 0)
    IMPE = 0.70 + (0.25 if SACAL <= SAMI else 0)
    IMINV = 1.75 + (0.625 if SACAL <= SAMI else 0)
    IMCE = 3.15 + (1.125 if SACAL <= SAMI else 0)

    def clamp(val):
        return val if val < BA else BA

    def clamp_iv(val):
        """Invalidez/vida use AY as limit."""
        return val if val < AY else AY

    AC = AA / 100 * SAMI
    AD = (AB / 100 * AU) if SABC < BA else (AB / 100 * BA)
    AE = (IMPE / 100 * SABC) if SABC < BA else (IMPE / 100 * BA)
    AF = (IMGM / 100 * SABC) if SABC < BA else (IMGM / 100 * BA)
    AG = (IMINV / 100 * SABC) if SABC < AY else (IMINV / 100 * AY)
    AH = (config.imss_guarderias / 100 * SABC) if SABC < BA else (config.imss_guarderias / 100 * BA)
    AI = (config.imss_retiro / 100 * SABC) if SABC < BA else (config.imss_retiro / 100 * BA)
    AJ = (IMCE / 100 * SABC) if SABC < AY else (IMCE / 100 * AY)
    AK = (config.imss_riesgos / 100 * SABC) if SABC < BA else (config.imss_riesgos / 100 * BA)

    AL = AC + AD + AE + AF + AG + AH + AI + AJ + AK  # Cuota patronal IMSS

    # ── INFONAVIT y otros ──
    AM = (config.infonavit / 100 * SABC) if SABC < AZ else (config.infonavit / 100 * AZ)
    AN = config.impuesto_nomina / 100 * SABC
    AO = config.otros_impuestos / 100 * SABC

    AP = AL + AM + AN + AO  # Obligaciones patronales (IOP)
    AQ = AP / SACAL if SACAL else 0

    # ── Ps(Tp/Tl) ──
    BH = AQ * FSI

    # ── FSR final ──
    FSR = BH + FSI

    return round(FSR, 5)
```

### 4.2 Uso

```python
# Calcular y cachear
config = factores_fsr_repo.obtener(proyecto_id, clave='JOR8HR')
factor = calcular_fsr(config)
config.factor_fsr = factor
factores_fsr_repo.actualizar_factor(config.id, factor)

# Aplicar a un insumo MO
insumo.salario_real = insumo.precio * config.factor_fsr
```

---

## 5. Importación desde OPUS

### 5.1 `factores_fsr` desde `*8.DBF`

Si `8.DBF` existe en el proyecto OPUS, leer su registro y mapear campos:

| OPUS `*8.DBF` | `factores_fsr` |
|---------------|----------------|
| `FSR_CLV` | `clave` |
| `FSR_DES` | `nombre` |
| `AT` | `modo_calculo` |
| `AV` | `anio` |
| `AR` | `semestre` |
| `BB` | `tipo_jornada` |
| `BC` | `horas_jornada` |
| `AW` | `salario_minimo` |
| `FSR_SABA` | `salario_nominal_base` |
| `FSR_DPCAL` | `dias_calendario` |
| `FSR_DPAGU` | `dias_aguinaldo` |
| `FSR_DNVAC` | `dias_vacaciones` |
| `FSR_PPVAC` | `prima_vacacional` |
| `FSR_DNDOM` | `dias_dominical` |
| `FSR_PPDOM` | `prima_dominical` |
| `FSR_DPOT1` | `dias_otros_pagados` |
| `FSR_DNSEP` | `dias_descanso` |
| `FSR_DNFES` | `dias_festivos` |
| `FSR_DNDCO` | `dias_contrato` |
| `FSR_DNSIN` | `dias_sindicato` |
| `FSR_DNVAC` | `dias_vacaciones` |
| `FSR_DNPER` | `dias_enfermedad` |
| `FSR_DNCLI` | `dias_clima` |
| `FSR_DNARR` | `dias_arrastre` |
| `FSR_DNGUA` | `dias_guardia` |
| `FSR_DNOT3` | `dias_otros_no_lab` |
| `FSR_IMGUA` | `imss_guarderias` |
| `FSR_IMSAR` | `imss_retiro` |
| `FSR_IMRTR` | `imss_riesgos` |
| `FSR_IMINV` | `imss_invalidez` |
| `FSR_IMCE` | `imss_cesantia` |
| `FSR_IMENF` | `imss_enfermedad` |
| `FSR_IMINF` | `infonavit` |
| `FSR_IMNOM` | `impuesto_nomina` |
| `FSR_IMOT2` | `otros_impuestos` |
| `FSR_FSR` | `factor_fsr` (pre-calculado de OPUS) |

Si no existe `8.DBF`, se crea una fila por defecto con los valores del template
(`exportar.py:864-886`) que corresponde a la configuración JOR8HR con datos
2010.

### 5.2 Insumos: leer `FSR`, `CATFSR`, `FSR_MINIMO`

El importador actual ya lee `FSR` como float — **eso está bien** (FSR es el
factor numérico). Lo que falta es `CATFSR` y `FSR_MINIMO`:

```python
# Actual (correcto para el factor, incompleto)
fsr_valor = _f(r.get("FSR") or r.get("FASAR"))  # el factor numérico
salario_real = _f(r.get("PRECIO")) * fsr_valor if fsr_valor else None

# Nuevo (completo)
fsr_valor   = _f(r.get("FSR"))          # factor numérico
catfsr      = _s(r.get("CATFSR"))        # clave de config (ej. 'JOR8HR')
fsr_minimo  = _s(r.get("FSR_MINIMO"))    # flag salario mínimo

# Buscar la config FSR en factores_fsr
fsr_config_id = factores_fsr_id_por_clave.get(catfsr) if catfsr else None

# Obtener factor: si hay config usa el suyo, si no usa el valor directo
factor_fsr = factores_fsr_por_id[fsr_config_id].factor_fsr if fsr_config_id else fsr_valor

# El flag "usar hoja fasar" = tiene CATFSR asignado
usar_hoja_fasar = 1 if catfsr else 0

salario_real = _f(r.get("PRECIO")) * factor_fsr if factor_fsr else None
```

---

## 6. Exportación a OPUS

### 6.1 `*8.DBF`

Mapeo inverso de `factores_fsr` → registro `*8.DBF`. Coincide con el template
de `exportar.py:864-886` pero con datos reales en vez de hardcodeados.

### 6.2 `*P.DBF`: campos `FSR`, `CATFSR`, `FSR_MINIMO`

En vez de hardcodear `FSR: 1.0`, escribir los valores reales:

```python
'FSR':        ins.get('factor_fsr') or 1.0,
'CATFSR':     ins.get('catfsr') or '',
'FSR_MINIMO': 'S' if ins.get('fsr_minimo') else '',
```

### 6.3 `*9.DBF`

`*9.DBF` contiene 85 registros fijos con el detalle línea por línea del cálculo
FSR. Se genera desde `exportar_plantillas.py:FSR_9_ROWS` — no cambia.

---

## 7. Archivos a tocar

| Archivo | Cambio | Líneas aprox |
|---------|--------|-------------|
| `backend/schema.sql` | Nueva tabla + FK en insumos | 60 |
| `backend/repos.py` | Nuevo `FactorFsrRepo` | 80 |
| `backend/core.py` | Nueva función `calcular_fsr()` | 100 |
| `backend/importar.py` | Leer `*8.DBF`, mapear `FASAR` como clave, calcular salario_real | 40 |
| `backend/exportar.py` | Escribir `*8.DBF` desde datos reales, escribir `FASAR` en insumos | 30 |
| `docs/SCHEMA.md` | Documentar nueva tabla | 20 |
| `.opencode/plans/PLAN_INSUMOS.md` | Actualizar: `usar_hoja_fasar` eliminado, `fsr_config_id` agregado | 5 |

---

## 8. Resumen de líneas

| Fase | Archivos | Líneas |
|------|----------|--------|
| Schema | 1 | 60 |
| Repo + Core | 2 | 180 |
| Import | 1 | 40 |
| Export | 1 | 30 |
| Docs | 2 | 25 |
| **Total** | **~7** | **~335** |

---

## 9. Dependencias

- Este plan es independiente del plan de limpieza de `insumos`.
- El orden sugerido: 1) limpieza insumos, 2) FSR.
- `usar_hoja_fasar` se elimina en la limpieza; `fsr_config_id` se agrega en FSR.

---

## 10. Sin migración

Beta — schema se edita en caliente. Bases `.presup` existentes incompatibles.
Se regeneran desde cero con el importador actualizado.

---

## 11. Nota sobre vigencia legal

El algoritmo documentado en §4 refleja la legislación mexicana de **2010**
(LFT, LSS, INFONAVIT). Desde entonces ha habido múltiples reformas:

- Modificaciones anuales a la UMA (antes SMGDF)
- Cambios en tasas de IMSS (Riesgos de Trabajo, Cesantía, etc.)
- Reformas a la Ley INFONAVIT
- Días de vacaciones progresivos (reforma 2023: 12 días primer año)
- Prima vacacional, aguinaldo, etc.

**El código debe parametrizarse por año y actualizarse conforme a la ley
vigente.** La tabla `factores_fsr` ya incluye `anio` y `semestre` para
facilitar la selección de la versión correcta, pero los cálculos intermedios
(AA, AB, AS, tasas fijas) están hardcodeados a 2010 y necesitan revisión
antes de usar en producción.

Flujo recomendado:
1. Importar FSR desde OPUS (hereda el cálculo de OPUS original)
2. El usuario puede modificar parámetros manualmente en la UI
3. El cálculo automático es opcional — el factor puede escribirse directo
4. Cuando se actualice la ley, revisar §4.1 y ajustar las fórmulas

---

## 12. Modo manual vs calculado

Como el usuario indicó, en la práctica el FSR muchas veces se conoce y se
escribe directo (cambia una vez al año). El diseño soporta ambos:

### 12.1 Columnas en `insumos`

```sql
fsr_config_id   INTEGER REFERENCES factores_fsr(id),  -- NULL si manual
factor_fsr      REAL,      -- factor FSR (calculado desde config o manual)
salario_real    REAL,      -- salario_nominal * COALESCE(factor_fsr, 1.0)
```

| Modo | `fsr_config_id` | `factor_fsr` | `salario_real` |
|------|:-:|:-:|:-:|
| **Calculado** | → config | copia de `config.factor_fsr` | `salario_nominal * factor_fsr` |
| **Manual** | NULL | lo que el usuario teclee | `salario_nominal * factor_fsr` |

### 12.2 Flujo

- Si el usuario escribe un valor directo en `factor_fsr`, `fsr_config_id` se
  pone NULL y no se recalcula automáticamente.
- Si se edita la configuración FSR referenciada, se puede propagar a los
  insumos que la referencian (botón "Recalcular desde config").
- `salario_real` siempre es `salario_nominal * COALESCE(factor_fsr, 1.0)`.
