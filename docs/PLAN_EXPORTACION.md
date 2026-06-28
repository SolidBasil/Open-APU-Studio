# Plan de Exportación: SQL → DBF OPUS

## Decisiones adoptadas

| Decisión | Opción | Razón |
|---|---|---|
| Librería DBF | **`dbf`** (Ethan Furman) | Madura, soporta VFP, Memo (FPT), encoding cp1252. Misma que usa `importar.py`. |
| Alcance v1 | **Completo** | Todas las tablas DBF necesarias para abrir obra en OPUS. |
| Categorías (PREFIJO=512) | **costo=0 y unidad=''** | Misma lógica que import. Sin cambios al esquema. |
| Destino | **Carpeta nueva** | Siempre crear `Obras/<clave_opus>/` nueva. |
| Tablas vacías | **Crear con estructura** | OPUS espera el archivo aunque esté vacío. |
| V/U/FMP | **Crear vacíos** | OPUS los completa al abrir la obra. |
| CDX | **Omitir** | OPUS los regenera automáticamente. |
| Botón UI | **Toolbar principal** | Export a 1 clic. |

## Objetivo

Exportar datos de una base SQLite al formato DBF que OPUS CMS utiliza en `Obras/[NombreObra]/`.

---

## 1. Arquitectura de una obra OPUS

Cada obra en `Obras/[Nombre]/` contiene:

### Archivos esenciales (DBF + FPT + CDX)

| Archivo | Propósito | Registros | Datos desde SQLite |
|---|---|---|---|
| `CONFIG.DBF` | Configuración general | 1 | `proyectos` + `configuracion_proyecto` |
| `TIPOSINS.DBF` | Tipos de insumo | 8 fijos | `tipos_insumo` |
| `FRENTES.DBF` | Frentes de obra | 0 (vacío) | — |
| `[Obra].DBF` | Catálogo de conceptos | variable | `estructura_presupuesto` (capítulos) |
| `[Obra]1.DBF` | **Partidas del presupuesto** | variable | `estructura_presupuesto` (todos) |
| `[Obra]P.DBF` | **Insumos básicos** | variable | `insumos` |
| `[Obra]F.DBF` | **Análisis de Precios Unitarios** | variable | `apu_matrices` |
| `[Obra]A.DBF` | Precios unitarios resumen | variable | `estructura_presupuesto` (hojas) |
| `[Obra]C.DBF` | Control de obra | 1 | `proyectos` |
| `[Obra]N.DBF` | Desglose de precios | variable | `apu_resumen_totales` |
| `[Obra]I.DBF` | Sobrecostos | variable | `sobrecostos` |
| `[Obra]5.DBF` | Composición de básicos | variable | derivado de `apu_matrices` |
| `[Obra]X.DBF` | Explosión de insumos | variable | derivado de conceptos hoja |
| `[Obra]8.DBF` | FSR (Factor Salario Real) | 1 fijo | plantilla |
| `[Obra]9.DBF` | Formatos FSR | 85 fijos | plantilla |
| `[Obra]Z.DBF` | Config equipo | 1 fijo | plantilla |
| `[Obra]0.DBF` | Vínculos | 0 | vacío |
| `[Obra]3.DBF` | Actividades/programa | 0 | vacío |
| `[Obra]D.DBF` | Descripciones WBS | 0 | vacío |
| `[Obra]H.DBF` | Historial precios | 0 | vacío |
| `[Obra]J.DBF` | Costos horarios equipo | 0 | vacío |
| `[Obra]R.DBF` | Reprogramación | variable | fuera de alcance v1 |

### Archivos auxiliares

| Archivo | Propósito | Notas |
|---|---|---|
| `CONFIG.INI` | Config texto | 10-15 líneas fijas + nombre obra |
| `[Obra].FMP` | Formato impresión | Plantilla texto, OPUS regenera |
| `[Obra].ODB` | Objeto DBF | 0 bytes |
| `[Obra]V.*` | Archivos de versión | Opcional (7 archivos) |
| `[Obra]U.*` | Preferencias usuario | Opcional (3 archivos) |
| `CONFIG.FPT` | Memo de CONFIG | 512 bytes (automático con DBF) |

### Archivos de registro maestro (fuera de la obra)

| Archivo | Propósito | Acción |
|---|---|---|
| `OBRA.DBF` | Catálogo de obras | Agregar 1 registro |
| `OBRDESC.dbf` | Descripción campos OBRA | Fijo (2 registros) |

---

## 2. Mapeo SQLite → DBF

### 2.1 Tablas con mapeo directo

#### `tipos_insumo` → `TIPOSINS.DBF`

```python
# tipo_id → PREFIJO, clave → STRTIPO
(1, 'material', 'Materiales')
(2, 'mano_obra', 'Mano de obra')
(4, 'herramienta', 'Herramienta')
(8, 'equipo', 'Equipo')
(16, 'auxiliar', 'Auxiliar')
(32, 'concepto', 'Concepto compuesto')
(64, 'flete', 'Flete')
(128, 'trabajo', 'Trabajo')
```

#### `proyectos` + `configuracion_proyecto` → `CONFIG.DBF`

| Campo DBF | Origen | Notas |
|---|---|---|
| `CCANTI` | fijo | 6 |
| `VCANTI` | fijo | 2 |
| `VPRECI` | fijo | 2 |
| `TCAMBIO` | fijo | 1.0 |
| `IMPUESTO` | `proyectos.iva_porcentaje` | |
| `MONEDA` | `proyectos.moneda_nombre` | |
| `SIMBOLO` | `proyectos.moneda_simbolo` | |
| `MONEXT` | fijo | 'DOLARES' |
| `SIMBEXT` | fijo | 'USD' |
| `LEYIMPUEST` | `proyectos.iva_nombre` | 'IVA' |
| `CVSLETRA` | fijo | .F. |
| `FSDI` | fijo | 1.0 |
| `FECHA` | `configuracion_proyecto` | fecha |
| `DIRCATGEN` | ruta + `proyectos.clave_opus` | ruta física |
| `VERSION` | fijo | '2010.05' |
| `TIPOPRESAL` | fijo | 2 |
| `CONCOMPRAS` | fijo | .T. |
| `CLAVEOBRA` | `proyectos.clave_opus` | |
| `UFECHAMOD` | hoy | |
| resto | fijo | 1, '', .F. |

#### `proyectos` → `[Obra]C.DBF`

| Campo DBF | Origen | Notas |
|---|---|---|
| `OBRDES` | `proyectos.descripcion` | |
| `OBRUBI` | `proyectos.cliente_domicilio` | |
| `OBRFEC` | `proyectos.licitacion_fecha` | |
| `OBRCOS` | calculado | suma de costos directos |
| `OBRMOGRA` | calculado | suma de mano de obra gravable |
| `OBRPRE` | `proyectos.total_obra` | precio total |
| `OBRPIND` | calculado | % indirectos |
| `OBRPUTI` | calculado | % utilidad |
| `OBRFINI` | `proyectos` | fecha inicio |
| `OBRFTER` | `proyectos` | fecha término |
| `TIPCAM` | fijo | 1.0 |
| `LEYMONNAC` | `proyectos.moneda_nombre` | |
| `SIMMONNAC` | `proyectos.moneda_simbolo` | |
| `LEYMONEXT` | fijo | 'DOLARES' |
| `SIMMONEXT` | fijo | 'USD$' |
| `VERSION` | fijo | '2010.05' |
| ~30 campos TIT* | fijo | ver plantilla |
| ~100 campos COL*, LEY*, IDFOR*, INAC*, ESPE*, ANCNIV*, FORM*, ABREV* | fijo | ver plantilla completa |
| ~30 campos PON*, TIPFUN*, PSAR, PINF, PMOI, FGRAVSAR, FSRMIN, FSRSUP, CVSLETRA, REGLA5, PORINDEST, ENOEM, YAFEN96 | fijo | ver plantilla |

#### `estructura_presupuesto` → `[Obra]1.DBF`

| Campo DBF | Origen | Notas |
|---|---|---|
| `PRE_ID` | auto-generado | raíz=0, luego +10 por registro |
| `PRE_IDUNI` | auto-generado | raíz=0, luego secuencial |
| `PRE_TIP` | `tipo` | 1=capítulo, 0=concepto hoja |
| `PRE_NIVEL` | `nivel` | |
| `PRE_IDPAD` | `padre_id` → `PRE_ID` | -1 para raíz |
| `PRE_VIS` | regla | 'S' si tiene hijos |
| `PRE_SIGNO` | fijo | '+' |
| `PRE_IDAUX` | fijo | 0 |
| `PRE_ESCOL` | fijo | .F. |
| `PRE_COM` | `clave` | |
| `PRE_EXP` | (memo) | vacío |
| `PRE_VOL` | `cantidad` | 1.0 para capítulos |
| `PRE_PRE` | `precio_unitario` en hojas, subtotal en capítulos | |
| `PRE_PMN` | = `PRE_PRE` | |
| `PRE_PME` | fijo | 0.0 |
| `PRE_VPE` | fijo | 0.0 |
| `PRE_IMP` | fijo | 0.0 |
| `PRE_WBS` | `wbs` | |
| `PRE_CAR1-3` | fijo | '' |
| `IDPROP` | fijo | 0 |
| `PRE_PAQ` | fijo | .F. |
| `PRE_ACUPRO` | fijo | 0.0 |
| `MEMOCAD` | (memo) | vacío |
| `REPROG` | fijo | 0 |

#### `insumos` → `[Obra]P.DBF`

| Campo DBF | Origen | Notas |
|---|---|---|
| `PREFIJO` | `tipo_id` | 1,2,4,8,16,32; categorías=512 |
| `NOMBRE` | `clave` | |
| `UNIDAD` | `unidad` | |
| `BASICO` | `es_basico` | 'S' si es básico |
| `FSR_MINIMO` | fijo | '' |
| `PRECIO` | `costo_final` | |
| `FSR` | fijo | 1.0 |
| `FECHA` | `fecha_precio` | |
| `MATERIALES` | calculado | desde APU resumen |
| `MANO_DEO` | calculado | desde APU resumen |
| `HERRAMIENT` | calculado | desde APU resumen |
| `EQUIPO` | calculado | desde APU resumen |
| `MARCA1-6` | fijo | '' |
| `DESCRIPCIO` | `descripcion` | (memo) |
| `COMENTARIO` | (memo) | vacío |
| `CLAVEUSUAR` | `clave_usuario` | |
| `ARCHIFOTO` | (memo) | vacío |
| `ACUMULADOR` | fijo | 0.0 |
| `SAL_BASE` | calculado | para mano_obra |
| `PUNIT` | `costo_final` | |
| `AUXILIARES` | calculado | |
| `DESCCORTA` | `descripcion_corta` | |
| `TOTALMN` | `costo_mn` | |
| `TOTALME` | `costo_me` | |
| `CATFSR` | fijo | 'FSROTR' |
| `ELE_GRUPO` | `familia_id` → `familias.nombre` | |
| `ELE_REFBAS` | fijo | '' |
| `ELE_RELBAS` | fijo | 0.0 |
| `PUNITMN` | `costo_mn` | |
| `PUNITME` | `costo_me` | |
| `SAL_GRA` | calculado | |
| `PBASEMN` | `costo_mn` | |
| `A`, `B`, `C` | `indice_1,2,3` | |
| `PBASEME` | `costo_me` | |
| `D`, `E`, `F` | `indice_4,5,6` | |
| `PESO` | `peso_kg` | |
| `CTD_MOB` | calculado | factor de MO básica |
| `WBS` | fijo | '' |
| `WBS1` | fijo | '' |
| `CLV_BDOPUS` | fijo | '' |
| `CLV_PROVEE` | `proveedor_id` → `proveedores.nombre` | |
| `PERSE` | fijo | .F. |
| `PORGEN` | fijo | .F. |

**Regla para categorías (PREFIJO=512):** insumos donde `costo_final=0` y `unidad=''` y `descripcion=''` son categorías/parent agrupadores. No tienen desglose de precios.

#### `apu_matrices` + `insumos` → `[Obra]F.DBF`

| Campo DBF | Origen | Notas |
|---|---|---|
| `PREF` | `parent.tipo_id` | |
| `NOMBRE` | `parent.clave` | |
| `PREFCOMP` | `component.tipo_id` | |
| `COMPONENTE` | `component.clave` | |
| `CLAVENUM` | `orden` × 100 | 100, 200, 300... |
| `NOELE` | `rendimiento` | número de elementos |
| `RENDTO` | fijo o `rendimiento` | 1.0 o el real |
| `CANTIDAD` | `cantidad` | = NOELE / RENDTO |
| `EXPRESION` | `formula` | o str(cantidad) |
| `COSTO` | `precio` | precio del componente |
| `TOTALMN` | `importe` o `cantidad * precio` | |
| `TOTALME` | fijo | 0.0 |
| `CAMPOREND` | fijo | chr(1) |
| `TIPOCH` | fijo | '' |
| `IMPORTE` | `importe` | |
| `IMPORTEMN` | `importe` | |
| `IMPORTEME` | fijo | 0.0 |
| `EXPRESIONM` | fijo | 0.0 |
| `EXPRESIONO` | fijo | 0.0 |
| `TIPOREND` | fijo | 2 |
| `CAMPORENDM` | fijo | chr(1) |
| `CAMPORENDO` | fijo | chr(1) |
| `DARENDIM` | fijo | .F. |
| `MEMOCAD` | (memo) | vacío |
| `MARCAAJU` | fijo | .T. |

**Dos tipos de matrices:**
- **Insumo compuesto** (SQL `matriz_id < 0`): PREF = `parent.tipo_id`
  - parent = `insumos` WHERE `id = abs(matriz_id)`
- **Concepto** (SQL `matriz_id > 0`): PREF = 32
  - parent = `estructura_presupuesto` WHERE `id = matriz_id`

#### `apu_resumen_totales` → `[Obra]N.DBF`

| Campo DBF | Origen |
|---|---|
| `NOMBRE` | `insumo.clave` (buscar por matriz_id) |
| `MM` | `materiales` |
| `OO` | `mano_obra` |
| `HH` | `herramienta` |
| `EE` | `equipo` |
| `AA` | `auxiliares` |
| `SUBCONT` | `subcontratos` (desde APU) |
| `PP` | calculado = MM+OO+HH+EE+AA+SUBCONT |
| `INDIRECTOS` | `indirectos_pct` |
| `UTILIDAD` | `utilidad_pct` |
| `INDIRECTO2` | variable |

**Regla:** matriz_id en apu_resumen puede ser positivo (insumo) o negativo (concepto). Se busca por `insumos.id = abs(matriz_id)` o `estructura_presupuesto.id = matriz_id`.

**Para 1A (Category/PREFIJO=512):** solo NOMBRE, sin desglose.

#### `estructura_presupuesto` (hojas) → `[Obra]A.DBF`

| Campo DBF | Origen |
|---|---|
| `IDUNI` | `estructura_presupuesto.id` |
| `FAMILIA` | '' |
| `COSTODIR` | `subtotal` |
| `PRECIO` | `precio_unitario` |
| `UNIDAD` | `unidad` |
| `NOMBRE` | `clave` |
| `DESC` | `descripcion` (memo) |
| `PRE_WBS` | `wbs` |
| `PRECIOMN` | = `PRECIO` |
| `PRECIOME` | 0.0 |
| `DESCCORTA` | `descripcion_corta` |

**Registro 0:** total general (IDUNI=0, PRECIO=total_obra)

#### `sobrecostos` → `[Obra]I.DBF`

| Campo DBF | Origen |
|---|---|
| `RENGLON` | `orden` |
| `VAR` | `variable` |
| `DESC1` | `descripcion` |
| `PORCEN` | fijo o `porcentaje_mn` |
| `FORMULA` | `formula` |
| `PORCENMN` | formato MN |
| `FORMULAMN` | fórmula MN |
| `PORCENME` | formato ME |
| `FORMULAME` | fórmula ME |
| `IMPORTE` | 0.0 |
| `IMPORTEMN` | 0.0 |
| `IMPORTEME` | 0.0 |
| `SE_SUMA` | `suma_en_total` |
| `SE_IMPR` | `se_imprime` |
| `SE_FIN` | `es_egreso_financ` o `es_ingreso_financ` |
| `SE_SUBRAYA` | .F. |
| `ALINEA` | '' |
| `DECIMALES` | 2 |

---

### 2.2 Tablas derivadas (cálculo)

#### `[Obra]5.DBF` — Composición de básicos

Se genera de insumos donde `es_compuesto=1` y `es_basico=1`. Agrupa los componentes de cada básico.

```
Por cada insumo compuesto básico:
  PREFIJO = tipo_id
  NOMBRE = clave
  PREFCOMP = component.tipo_id
  COMPONE = component.clave
  UNIPOR = 0
  CANTIDAD = component.cantidad / component.rendimiento (de apu_matrices)
  PRECIO = component.costo_final
  MONTO = CANTIDAD * PRECIO
  CANCONC = CANTIDAD
  PRECIOMN = PRECIO
  PRECIOME = 0.0
  MONTOMN = MONTO
  MONTOME = 0.0
```

#### `[Obra]X.DBF` — Explosión de insumos

Para cada concepto hoja (PRE_TIP=0), se expanden todos sus componentes APU recursivamente hasta llegar a insumos básicos.

```
Por cada concepto hoja:
  Para cada insumo básico en su APU (recursivo):
    PREFIJO = insumo.tipo_id
    NOMBRE = insumo.clave
    CLAVEUSUAR = ''
    UNIPOR = 0
    CANTIDAD = concepto.cantidad × factor_expansión
    PRECIO = insumo.costo_final
    MONTO = CANTIDAD * PRECIO
    ESTOTAL = 3
    EXP_GRUPO = insumo.familia (ELE_GRUPO)
    PESO = 0.0
    AJUSTA = ''
    MONT_SINAJ = MONTO
```

---

### 2.3 Tablas plantilla (valores fijos)

#### `CONFIG.DBF` — Valores fijos completos

```
CCANTI=6, VCANTI=2, VPRECI=2, TCAMBIO=1.0
IMPUESTO=15.0, MONEDA='PESOS', SIMBOLO='$'
MONEXT='DOLARES', SIMBEXT='USD', LEYIMPUEST='IVA'
CVSLETRA=.F., CLIENTE='', AUTOR='', FSDI=1.0
FECHA=<hoy>, DIRCATGEN=<ruta_obra>
TFCONTRATO=1, TFDESGLOSE=1, TFESTIMA=1
TFDESGLOES=1, TFRESPONSA=1, TFDOCSALMA=1
TFDESDOCSA=1, TFDESDOCEN=1, TFEDOALMA=1
TFDESEDOAL=1, TFACTIVIDA=4, VERSION='2010.05'
BUSCA='', CLAVE='', TIPOPRESAL=2
CONCOMPRAS=.T., CLAVEOBRA=<clave>
TFREQS=1, TFREQSDET=1
UFECHAMOD=<hoy>, TFESTIMAOC=1
```

#### `[Obra]C.DBF` — Bloques de valores fijos

**Títulos (TIT*):**
```
TITDIR='Costo Directo'
TITSAL='Total Salarios Base'
TITMOI='Mano de Obra en Indirectos'
TITGRA='Total Salario Gravable de SAR e INF'
TITIND='Indirectos'
TITIND2='Indirectos de Campo'
TITSUB1-5='Subtotal' (1-5)
TITFIN='Financiamiento'
TITUTI='Utilidad'
TITSAR='SAR'
TITINF='INFONAVIT'
TITCAD='Cargos Adicionales'
TITOTR='Otro porcentaje'
TITIVA='Impuesto'

TITPBASEM='Costo base', TITPBASEO='Sal. Base'
TITPBASEH='Costo base', TITPBASEE='Costo base'
TITPBASEA='Costo base', TITPBASEC='Costo base'

TITADM='Flete', TITADO='Viáticos', TITADH='Flete'
TITADE='Flete', TITADA='Flete', TITADC='Flete'

TITBEM='Derechos', TITBEO='Presta.', TITBEH='Derechos'
TITBEE='Derechos', TITBEA='Derechos', TITBEC='Derechos'

TITCFM='Mermas', TITCFO='Otros', TITCFH='Mermas'
TITCFE='Mermas', TITCFA='Mermas', TITCFC='Mermas'

TITOTM='Costo unitario', TITOTO='Sal. Real'
TITOTH='Costo unitario', TITOTE='Costo unitario'
TITOTA='Costo unitario', TITOTC='Costo unitario'
```

**Niveles (LEY*):**
```
LEYNIV1='Capítulo'
LEYNIV2='Subcapítulo'
LEYNIV3='Nivel 3'
LEYNIV4='Nivel 4'
LEYNIV5='Nivel 5'
LEYNIV6='Nivel 6'
LEYNIV7='Nivel 7'
LEYNIV8='Nivel 8'
LEYNIV9='Nivel 9'
LEYCON='Concepto'
```

**Fórmulas (FORMU*):**
```
FORMUMATN,FORMUMOBN,FORMUHERN,FORMUEQUN,FORMUAUXN,FORMUCONN = 'PBASEMN+A+B+C'
FORMUMATE,FORMUMOBE,FORMUHERE,FORMUEQUE,FORMUAUXE,FORMUCONE = 'PBASEME+D+E+F'
```

**Moneda (LEY*, ABREV*):**
```
LEYMONNAC='PESOS', LEYCVSMN='/100', LEYREMMN='M.N.', SIMMONNAC='$'
LEYMONEXT='DOLARES', LEYREMME='', SIMMONEXT='USD$'
ABREVMN='M.N.', ABREVME='M.E.'
```

**Permisos (PON*):**
```
PONDIR=.T., PONSAL=.F., PONMOI=.F., PONGRA=.F., PONPMOI=.F.
PONIND=.T., PONIND2=.T., PONSUB1=.T., PONFIN=.T.
PONSUB2=.T., PONUTI=.T., PONSUB3=.F., PONSAR=.F.
PONINF=.F., PONSUB4=.F., PONCAD=.T., PONSUB5=.F.
PONOTR=.T.
```

**Insumos de equipo (INAC*, ESPE*):**
```
INAC_DEP=80.0, INAC_INV=100.0, INAC_SEG=100.0, INAC_MAN=80.0, INAC_ALM=100.0
INAC_OTR=0.0, INAC_COM=0.0, INAC_LUB=0.0, INAC_LLA=0.0, INAC_OPE=100.0, INAC_OTRIN=0.0
ESPE_DEP=80.0, ESPE_INV=100.0, ESPE_SEG=100.0, ESPE_MAN=100.0, ESPE_ALM=0.0
ESPE_OTR=0.0, ESPE_COM=30.0, ESPE_LUB=30.0, ESPE_LLA=0.0, ESPE_OPE=100.0, ESPE_OTRIN=0.0
```

**Anchos de nivel (ANCNIV*):** `ANCNIV1=1, ANCNIV2=1, ANCNIV3=1, ANCNIV4=2, ANCNIV5=2. Resto=0`

**Colores (COL*):**
```
COLNIV1=117440512, COLNIV2=128, COLNIV3=50331903, COLNIV4=8388608
COLNIV5=32768, COLNIV6=32896, COLNIV7=8388736, COLNIV8=159416448, COLNIV9=8421376
COLCON=117440512
```

**Bandera:** `CVSLETRA=.F., REGLA5=.T., PORINDEST=.T., ENOEM=.F., YAFEN96=.T., VERSION=2010.05`

**ID Formatos (IDFOR*):** todos = 1 excepto:
```
IDFORHP=2, IDFOREST=2, IDFORXEST=2, IDFORACT=6, IDFORSUM=3
```

**FGRAVSAR, FSRMIN, FSRSUP:** `FGRAVSAR=1.29013, FSRMIN=0.0, FSRSUP=0.0`

**TIPOIND=1, DECPORCE=2, CDURACION='36.5c', ESCALAHIST=1**

**ANCNIVA1-9:** `ANCNIVA1=1, resto=0`

#### `[Obra]8.DBF` — FSR (único registro)

```
FSR_TIP=0, FSR_CLV='JOR8HR', FSR_DES='Factor de Salario Real FSR'
FSR_SABA=100.0, FSR_SAMI=1.0, FSR_PPVAC=25.0, FSR_PPDOM=0.0
FSR_DPCAL=365.25, FSR_DPAGU=15.0, FSR_DPPVA=1.5, FSR_DPPDO=0.0
FSR_DPHEX=0.0, FSR_DPOT1=0.0, FSR_FSI=1.3182, FSR_SABC=1.98739
FSR_IMGM=1.05, FSR_IMPE=0.7, FSR_IMEX=0.0, FSR_IMRTR=7.58875
FSR_IMENF=5.35365, FSR_IMINV=1.75, FSR_IMCE=3.15, FSR_IMGUA=1.0
FSR_IMIMS=0.28746, FSR_IMNOM=0.0, FSR_IMSAR=2.0, FSR_IMINF=5.0, FSR_IMOT2=0.0
FSR_DEIMS=74.74024, FSR_DEGUA=3.815, FSR_DENOM=0.0, FSR_DESAR=7.63, FSR_DEINF=19.075, FSR_DEOT2=0.0
FSR_DNDOM=0.0, FSR_DNSEP=52.18, FSR_DNFES=7.17, FSR_DNDCO=0.0, FSR_DNSIN=1.0
FSR_DNVAC=6.0, FSR_DVAC=6.0, FSR_DNPER=0.45, FSR_DNCLI=3.85, FSR_DNARR=0.0
FSR_DNGUA=0.0, FSR_DNOT3=5.0, FSR_DNLA=75.65, FSR_DLA=289.6, FSR_DPA=381.75
FSR_DEA=105.26024, FSR_DCA=486.76024, FSR_FSR=1.77196, FSR_CALC=.T.
FSR_FSBC=1.04517, FSR_SACAL=1.9015
AA=20.4, AB=1.1, AC=0.204, AD=0.0, AE=0.01391, AF=0.02087
AG=0.03478, AH=0.01987, AI=0.03975, AJ=0.0626, AK=0.15082, AL=0.5466, AM=0.09937
AN=0.0, AO=0.0, AP=0.64597, AQ=0.33972, AR=1.0, AS=25.0, AT=1.0, AU=0.0, AV=2010.0
AW=57.46, AX=20040101.0, AY=25.0, AZ=25.0, BA=25.0, BB=0.0, BC=8.0, BD=0.0, BE=1.1875
BF=0.0, BG=0.0, BH=0.44782
```

#### `[Obra]Z.DBF` — Config equipo (único registro)

```
ANCNIVI1=1, ANCNIVI2=1, ANCNIVI3=2, resto=0
INAC_CAPI=0.0, ESPE_CAPI=0.0, TIPODEPEN=0
INAC_PIEZ=0.0, ESPE_PIEZ=0.0, FHPKW=0.746
HORASDIA=24, MINSDIA=0, HINIDIA=0, MINIDIA=0
HORAENFECH='', DURENDT=.F.
CPO_FSBSG='FSR_FSI', CFARG=.F., CPO_FPIMSS=''
VARFINPPP='', SEGURO=0.0, TASA_INTER=0.0
IDFORESCPR=0
```

#### `[Obra]9.DBF` — Formatos FSR (85 registros fijos, extraídos de obra real)

Campos: `FFSR_REN` (N), `FFSR_CLV` (C), `FFSR_DES` (C), `FFSR_FOR` (C), `MARCA1` (L), `MARCA2` (L), `MARCA3` (L), `MARCA4` (L), `FFSR_VAL` (N), `FFSR_UNI` (C), `FFSR_IOP` (L), `DECIMALES` (N), `DEUSUARIO` (C), `COMENTARIO` (C).

85 registros que definen el cálculo del Factor de Salario Real (LFT, IMSS, INFONAVIT). Son idénticos en toda obra mexicana. Se incluyen completos en `exportar_plantillas.py`:

```python
# backend/exportar_plantillas.py

TABLA_9_DBF = [
    # (FFSR_REN, FFSR_CLV, FFSR_DES, FFSR_FOR, MARCA1, MARCA2, MARCA3, MARCA4, FFSR_VAL, FFSR_UNI, FFSR_IOP, DECIMALES, DEUSUARIO, COMENTARIO)
    (570,  ''  , 'De cuotas del IMSS', '', True, None, False, False, 0.0, '', None, 2, ' ', 'Obligaciones obrero patronales LSS e INFONAVIT'),
    (110, 'FSR_DNVAC', 'Días de vacaciones para calcular prima vacacional', '', True, None, None, True, 6.0, 'días', None, 2, ' ', 'Art. 76, 78,79, 81 Ley Federal del Trabajo'),
    (120, 'FSR_PPVAC', 'Prima vacacional', '', True, None, None, None, 25.0, '%', False, 2, ' ', 'Art. 80 Ley Federal del Trabajo'),
    (130, 'FSR_DNDOM', 'Días para el cálculo de prima dominical', '', False, None, None, True, 0.0, 'días', None, 2, ' ', 'Art. 71 Ley Federal del Trabajo'),
    (140, 'FSR_PPDOM', 'Porcentaje para prima dominical', '', False, None, None, None, 0.0, '%', None, 2, ' ', 'Art. 71 Ley Federal del Trabajo'),
    (990, ''  , 'Del TP/TL y del FSR', '', True, None, None, False, 0.0, '', None, 2, ' ', ''),
    (80,  'FSR_DPCAL', 'Días Calendario   (DC)', '', True, None, None, True, 365.25, 'días', None, 2, ' ', ''),
    (90,  'FSR_DPAGU', 'Días Aguinaldo', '', True, None, None, True, 15.0, 'días', None, 2, ' ', 'Art. 87 Ley Federal del Trabajo'),
    (500, 'FSR_DPPVA', 'Prima vacacional', 'FSR_PPVAC/100*FSR_DNVAC', True, None, None, True, 1.5, 'días', None, 2, ' ', 'Art. 80 Ley Federal del Trabajo'),
    (510, 'FSR_DPPDO', 'Prima Dominical', 'FSR_PPDOM/100*FSR_DNDOM', True, None, None, True, 0.0, 'días', None, 2, ' ', 'Art. 71 Ley Federal del Trabajo'),
    (515, 'FSR_DPHEX', 'Días equivalentes por horas extras al año', '(BF*2+BG*3)/24*FSR_DPCAL', True, None, None, True, 0.0, 'días', None, 2, ' ', 'Art. 61, 66 y 68 Ley Federal del Trabajo'),
    (150, 'FSR_DPOT1', 'Otros', '', True, None, None, True, 0.0, 'días', None, 2, ' ', ''),
    (520, 'FSR_DPA', 'SUMA de días pagados', 'FSR_DPCAL+FSR_DPAGU+FSR_DPPVA+FSR_DPPDO+FSR_DPHEX+FSR_DPOT1', True, None, None, True, 381.75, 'días', None, 2, ' ', 'Días Trabajados realmente pagados (Tp)'),
    (160, 'FSR_DNSEP', 'Días de Descanso (Ley Federal del Trabajo)', '', True, None, None, True, 52.18, 'días', False, 2, ' ', 'Art. 69 y 73 Ley Federal del Trabajo'),
    (170, 'FSR_DNFES', 'Festivos oficiales (Ley Federal del Trabajo)', '', True, None, None, True, 7.17, 'días', None, 2, ' ', 'Art. 74 Ley Federal del Trabajo'),
    (180, 'FSR_DNDCO', 'Días no laborables según contrato colectivo', '', True, None, None, True, 0.0, 'días', None, 2, ' ', ''),
    (190, 'FSR_DNSIN', 'Días Sindicato', '', True, None, None, True, 1.0, 'días', None, 2, ' ', ''),
    (490, 'FSR_DVAC', 'Vacaciones', 'FSR_DNVAC', True, None, None, True, 6.0, 'días', None, 2, ' ', 'Art. 76, 78,79, 81 Ley Federal del Trabajo'),
    (200, 'FSR_DNPER', 'Enfermedad no profesional', '', True, None, None, True, 0.45, 'días', None, 2, ' ', 'Ley Federal del Trabajo y Ley del Seguro Social'),
    (210, 'FSR_DNCLI', 'Condiciones Climat. (Lluvias y otros) Contr. Colec', '', True, None, None, True, 3.85, 'días', None, 2, ' ', ''),
    (220, 'FSR_DNARR', 'En Horas Inactivas por Arrastre', '', False, None, None, True, 0.0, 'días', None, 2, ' ', ''),
    (230, 'FSR_DNGUA', 'Días no trabajados por Guardia', '', False, None, None, True, 0.0, 'días', None, 2, ' ', ''),
    (240, 'FSR_DNOT3', 'Otros Días no trabajados por costumbre', '', True, None, None, True, 5.0, 'días', None, 2, ' ', ''),
    (530, 'FSR_DNLA', 'SUMA de días no laborados', 'FSR_DNSEP+FSR_DNFES+FSR_DNDCO+FSR_DNSIN+FSR_DVAC+FSR_DNPER+FSR_DNCLI+FSR_DNARR+FSR_DNGUA+FSR_DNOT3', True, None, None, True, 75.65, 'días', None, 2, ' ', ''),
    (540, 'FSR_DLA', 'Días realmente laborados (TL = DC - DNLA)', 'FSR_DPCAL-FSR_DNLA', True, None, None, True, 289.6, 'días', True, 2, ' ', 'Dias Trabajados realmente laborados (Tl)'),
    (630, 'FSR_IMINV', 'Invalidez y vida', '1.75+IIF(FSR_SACAL>FSR_SAMI,0,0.625)', True, None, False, None, 1.75, '%', True, 5, ' ', 'Art. 147 LSS y 97 LFT'),
    (350, 'FSR_IMRTR', 'Riesgos de trabajo', '', True, None, None, None, 7.58875, '%', None, 5, ' ', 'Art. 72 y 73 LSS'),
    (920, 'FSR_IMIMS', 'Factor de cuota patronal del IMSS = IMSS/SND', 'AL/FSR_SACAL', True, True, False, None, 0.2974, 'factor', None, 5, 'N', 'Ley del IMSS'),
    (320, 'FSR_IMGUA', 'Guarderias', '', True, None, None, None, 1.0, '%', None, 2, ' ', 'Art. 211 LSS'),
    (400, 'FSR_IMNOM', 'Impuesto Nómina', '', True, None, None, None, 0.0, '%', None, 2, ' ', ''),
    (330, 'FSR_IMSAR', 'Retiro', '', True, None, None, None, 2.0, '%', None, 2, ' ', 'Art. 168 fracc. I LSS'),
    (390, 'FSR_IMINF', 'Impuesto INFONAVIT', '', True, None, None, None, 5.0, '%', None, 2, ' ', 'Art. 29-II LINFONAVIT'),
    (410, 'FSR_IMOT2', 'Otros impuestos', '', True, None, None, None, 0.0, '%', None, 2, ' ', ''),
    (1100, 'FSR_FSR', 'FSR = Ps (Tp/Tl) + Tp/Tl', 'BH+FSR_FSI', True, True, True, True, 1.77912, '', True, 5, 'N', 'Art.160 y 161 Reglamento de la Ley de Obra Pública y Servicios Relacionadas con las Mismas'),
    (475, 'FSR_SAMI', 'Salario Mínimo General (D.F.)', 'IIF(AT=1,1,AW)', True, False, None, None, 1.0, '', False, 5, ' ', 'Art. 90 Ley Fed. del Trabajo - Comisión Nacional de Salarios Mínimos'),
    (40,  'FSR_SABA', 'Salario Nominal (SN)', '', False, None, None, None, 100.0, '$', False, 2, ' ', 'Art. 82 Ley Federal del Trabajo'),
    (560, 'FSR_SABC', 'Salario Base de Cotización (SB = FSBC * SN)', 'FSR_SACAL * FSR_FSBC', True, True, True, True, 1.81895, '', True, 5, ' ', 'Salario nominal con Factor de Empresa'),
    (620, 'FSR_IMGM', 'Gastos medicos. Pensionados (Patrón-Obrero)', '1.05+IIF(FSR_SACAL>FSR_SAMI,0,0.375)', True, None, False, None, 1.05, '%', True, 5, ' ', 'Art. 25 LSS (Prest. en especie) y 97 LFT'),
    (610, 'FSR_IMPE', 'Prestaciones en dinero (Patron+obrero)', '.7+IIF(FSR_SACAL>FSR_SAMI,0,0.25)', True, None, False, None, 0.7, '%', True, 5, ' ', 'Art. 107 LSS y 97 LFT'),
    (640, 'FSR_IMCE', 'Cesantía en edad avanzada y vejez', '3.15+IIF(FSR_SACAL>FSR_SAMI,0,1.125)', True, None, False, None, 3.15, '%', True, 5, ' ', 'Art. 168 fracc. II LSS y 97 LFT'),
    (0,   ''  , 'DATOS BASICOS', '', True, None, None, True, 0.0, '', False, 2, ' ', ''),
    (550, 'FSR_FSBC', '(FSBC = DPA/DPCAL)', 'FSR_DPA/FSR_DPCAL', True, True, True, True, 1.04517, '', True, 5, ' ', 'Factor para SBC'),
    (480, 'FSR_SACAL', 'Salario Nominal por jornada (SND)', 'IIF(AT=1,FSR_SABA*(1+BG/IIF(BB=0,8,IIF(BB=1,7.5,7)))/AW,FSR_SABA*(1+BG/IIF(BB=0,8,IIF(BB=1,7.5,7))))', True, True, True, False, 1.74034, '', False, 5, ' ', 'Art. 82 y 83 Ley Federal del Trabajo'),
    (580, 'AA', 'Porcentaje sobre salario mínimo para cuota fija', 'IIF(AV=2003,17.15,IIF(AV=2004,17.80,IIF(AV=2005,18.45,IIF(AV=2006,19.10,IIF(AV=2007,19.75,20.40))))', True, None, False, None, 20.4, '%', None, 2, 'S', 'Art. 106 Fracc. I LSS'),
    (590, 'AB', 'Porcentaje para Excedente a 3 SMGDF', 'IIF(AV=2003,3.55,IIF(AV=2004,3.06,IIF(AV=2005,2.57,IIF(AV=2006,2.08,IIF(AV=2007,1.59,1.10))))', True, None, False, None, 1.1, '%', None, 2, 'S', 'Art. 106 Fracc. II LSS'),
    (980, 'AQ', 'Obligaciones patronales entre SN', 'AP/FSR_SACAL', True, True, True, True, 0.34966, '', True, 5, 'S', 'Art.160 y 161 Reglamento de la Ley de Obra Pública y Servicios Relacionadas con las Mismas'),
    (970, 'AP', 'Obligaciones patronales (IOP)', 'AL+AM+AN+AO', True, True, False, None, 0.60852, '', None, 5, 'S', 'IMSS e INFONAVIT'),
    (820, 'AC', 'Enfermedad y maternidad. Cuota fija especie', 'AA/100*FSR_SAMI', True, True, True, None, 0.204, '', None, 5, 'S', 'Art. 106 Fracc. I LSS'),
    (830, 'AD', 'Enferm.-matern. Exc. a 3 S.M.D.F. especie', 'IIF(FSR_SABC<BA,AB/100*AU, AB/100*BA)', True, True, True, None, 0.0, '', None, 5, 'S', 'Art. 106 Fracc. II LSS'),
    (840, 'AE', 'Enfermedad y maternidad. Prestaciones en dinero', 'IIF(FSR_SABC<BA,FSR_IMPE/100*FSR_SABC, FSR_IMPE/100*BA)', True, True, True, None, 0.01273, '', None, 5, 'S', 'Art. 107 LSS'),
    (850, 'AF', 'Enfermedad y maternidad gastos médicos pensionados', 'IIF(FSR_SABC<BA,FSR_IMGM/100*FSR_SABC, FSR_IMGM/100*BA)', True, True, True, None, 0.0191, '', None, 5, 'S', 'Art. 25 LSS (Prest. en especie)'),
    (860, 'AG', 'Invalidez y vida', 'IIF(FSR_SABC<AY,FSR_IMINV/100*FSR_SABC, FSR_IMINV/100*AY)', True, True, True, None, 0.03183, '', None, 5, 'S', 'Art. 147 LSS'),
    (870, 'AH', 'Guarderías', 'IIF(FSR_SABC<BA,FSR_IMGUA/100*FSR_SABC, FSR_IMGUA/100*BA)', True, True, True, None, 0.01819, '', None, 5, 'S', 'Art. 211 LSS'),
    (880, 'AI', 'Retiro', 'IIF(FSR_SABC<BA,FSR_IMSAR/100*FSR_SABC, FSR_IMSAR/100*BA)', True, True, True, None, 0.03638, '', None, 5, 'S', 'Art. 168 fracc. I LSS'),
    (890, 'AJ', 'Cesantía en edad avanzada y vejez', 'IIF(FSR_SABC<AY,FSR_IMCE/100*FSR_SABC, FSR_IMCE/100*AY)', True, True, True, None, 0.0573, '', None, 5, 'S', 'Art. 168 fracc. II LSS'),
    (900, 'AK', 'Riesgos de trabajo', 'IIF(FSR_SABC<BA,FSR_IMRTR/100*FSR_SABC, FSR_IMRTR/100*BA)', True, True, True, None, 0.13804, '', None, 5, 'S', 'Art. 73 LSS'),
    (950, 'AN', 'Impuesto sobre Nómina', 'FSR_IMNOM/100*FSR_SABC', True, True, False, None, 0.0, '', None, 5, 'S', ''),
    (940, 'AM', 'INFONAVIT', 'IIF(FSR_SABC<AZ,FSR_IMINF/100*FSR_SABC,FSR_IMINF/100*AZ)', True, True, True, None, 0.09095, '', None, 5, 'S', 'Art. 29-II LINFONAVIT'),
    (960, 'AO', 'Otros impuestos', 'FSR_IMOT2/100*FSR_SABC', True, True, False, None, 0.0, '', None, 5, 'S', ''),
    (910, 'AL', 'Cuota patronal del IMSS', 'AC+AD+AE+AF+AG+AH+AI+AJ+AK', True, True, True, None, 0.51757, '', None, 5, 'S', 'Ley del IMSS'),
    (20,  'AT', 'Desea el cálculo: Por Factores=1, Por dinero=0', '', False, None, None, None, 1.0, '', None, 1, 'S', 'Capture 0 ó 1 según sea el caso'),
    (30,  'AW', 'Salario Mínimo General (Distrito Federal) CNSM', '', False, None, None, None, 57.46, '$', None, 2, 'S', 'Art. 90 Ley Fed. del Trabajo - Comisión Nacional de Salarios Mínimos'),
    (600, 'AU', 'Excedente de 3 SMGDF', 'IIF(FSR_SABC<=3*FSR_SAMI,0,FSR_SABC-3*FSR_SAMI)', True, None, True, None, 0.0, '', None, 5, 'S', 'Art. 106 fracc. II y 19° Transitorio 2° Párrafo'),
    (50,  'AV', 'Año (AAAA)', '', False, None, None, None, 2010.0, '', None, 0, 'S', 'Para cuota de Enfermedad y Maternidad (Arts. 19 y 106) y para Invalidez y Vida (Arts. 146 y 149 de LSS'),
    (660, 'AY', 'Límite de prest. Inv., vida, cesantía y vejez', 'AS*FSR_SAMI', True, None, False, None, 25.0, '', None, 5, 'S', 'Art. 147 y 148 LSS'),
    (930, 'AZ', 'Limite de Aportaciones INFONAVIT', 'AY', True, None, None, None, 25.0, '', None, 0, 'S', 'Art. 29 de INFONAVIT'),
    (650, 'BA', 'Límite de prest. patronales general', '25*FSR_SAMI', False, None, False, None, 25.0, '', None, 5, 'S', 'Art. 28 LSS'),
    (10,  ''  , 'De concurso', '', False, None, None, False, None, '', None, None, ' ', ''),
    (70,  ''  , 'Para el cálculo de días pagados', '', True, None, None, False, None, '', None, None, ' ', ''),
    (250, ''  , 'Para el calculo de cuotas del IMSS', '', True, None, None, False, None, '', None, None, ' ', ''),
    (380, ''  , 'Para otros impuestos', '', False, None, None, False, None, '', None, None, ' ', ''),
    (430, ''  , 'CALCULO', '', True, None, None, False, None, '', None, None, ' ', ''),
    (440, ''  , 'De datos básicos a utilizar', '', True, False, None, False, None, '', None, None, ' ', ''),
    (485, ''  , 'De días realmente pagados y SBC', '', True, None, None, None, None, '', None, None, ' ', ''),
    (545, 'FSR_FSI', 'TP/TL', 'FSR_DPA/FSR_DLA', True, None, True, True, 1.3182, '', None, 5, 'S', 'Factor de Empresa'),
    (65,  'BB', 'Jornada de trabajo: Diurna =0, mixta=1, nocturna=2', '', False, None, None, None, 0.0, '', None, 0, 'S', 'Art. 61 LFT'),
    (67,  'BC', 'Jornada de trabajo', '', False, None, None, None, 8.0, 'horas', None, 2, 'S', 'Art. 61, 66 y 68 Ley Federal del Trabajo'),
    (455, 'BD', 'Cantidad de horas extras por jornada', 'IIF(BB=0,BC-8,IIF(BB=1,BC-7.5,BC-7))', False, None, None, None, 0.0, 'horas', None, 4, 'S', 'Art. 61 LFT'),
    (460, 'BE', 'Máximas horas extra dobles considerando 9horas/sem.', 'IIF(BB=0,1.1875,IIF(BB=1,1.2,1.214286))', False, None, None, None, 1.1875, 'horas', None, 4, 'S', 'Art. 66 LFT'),
    (465, 'BF', 'Cantidad de horas extras a pagar dobles', 'IIF(BE>BD,BD,BE)', False, None, None, None, 0.0, 'horas/jor', None, 4, 'S', 'Art. 61 LFT'),
    (470, 'BG', 'Cantidad de horas extras a pagar triples', 'BD-BF', False, None, None, None, 0.0, 'horas/jor', None, 4, 'S', 'Art. 61 LFT'),
    (925, ''  , 'De INFONAVIT y otras cuotas', '', True, None, None, None, None, '', None, 5, 'S', ''),
    (1045, 'BH', 'Ps(Tp/Tl)', 'AQ*FSR_FSI', False, None, None, None, 0.46092, '', None, 5, 'S', 'Art.160 y 161 Reglamento de la Ley de Obra Pública y Servicios Relacionadas con las Mismas'),
    (655, 'AS', 'Lím. prest. Inv., vida, cesantía y vejez, cant.', 'IIF(AV=2003,20,IIF(AV=2004,21,IIF(AV=2005,22,IIF(AV=2006,23,IIF((AV=2007.AND.AR=1),24,25))))', None, None, None, None, 25.0, '', None, 5, 'S', 'Art. 147 y 148 LSS'),
    (57,  'AR', 'Semestre: enero a junio=1, julio a diciembre=2', '', None, None, None, None, 1.0, '', None, 0, 'S', ''),
]
```

Estos 85 registros son idénticos en toda obra OPUS mexicana. Se escriben tal cual en `[Obra]9.DBF` sin transformación.

#### `CONFIG.INI` — Contenido

```ini
[Explosión]
Recalcular=1
CalcExConSel=0,0,0,0,0,10,0,1,1,1,1,1,1,1,1,0,5,2
[Vista Actividades]
Recalcular=1
[Vista Suministros]
Recalcular=1
[Formato Vistas]
Archivo DFMV=C:\OPUSCMS\normal.FED
```

---

## 3. Estrategia de IDs

### `PRE_ID` en `[Obra]1.DBF`

**Regla:** `PRE_IDPAD` referencia a `PRE_IDUNI`, no a `PRE_ID`. Verificado contra obra real.

```
Root:     PRE_ID=0,   PRE_IDUNI=0,   PRE_NIVEL=0, PRE_IDPAD=-1
Level 1:  PRE_ID=10,  PRE_IDUNI=1,   PRE_NIVEL=1, PRE_IDPAD=0
Level 2:  PRE_ID=11,  PRE_IDUNI=2,   PRE_NIVEL=2, PRE_IDPAD=1    ← PAD = IDUNI del padre
...
```

Asignación por recorrido DFS del árbol:
```
PRE_ID    = contador_global + 10  (empieza en 10, +1 por nodo; raíz=0)
PRE_IDUNI = contador_global       (empieza en 0, +1 por nodo; raíz=0)
PRE_IDPAD = parent.PRE_IDUNI      (no parent.PRE_ID)
```

### `PREFIJO` en `[Obra]P.DBF`

```
PREFIJO = tipo_id (1, 2, 4, 8, 16, 32, 64, 128)
PREFIJO = 512 para insumos "categoría" (costo=0, sin unidad, sin descripción)
```

Si un insumo tiene `tipo_id=32` (concepto compuesto), se asigna `PREFIJO=32`.

### `PRE_IDUNI` en `[Obra]A.DBF`

```
IDUNI = estructura_presupuesto.id (secuencial desde SQL)
IDUNI = 0 para el total general
```

---

## 4. Algoritmos de transformación

### 4.1 Construcción de `[Obra]1.DBF`

```python
# 1. Ordenar EP por nivel, padre_id, orden
# 2. Root: PRE_ID=0, PRE_IDUNI=0
# 3. Cada nodo:
#    - PRE_ID = contador auto-incremento
#    - PRE_IDUNI = contador separado
#    - PRE_IDPAD = mapear padre_id → PRE_ID
#    - PRE_TIP = 1 si tipo='capitulo', 0 si 'concepto'
#    - PRE_NIVEL = nivel
#    - PRE_VOL = cantidad si concepto_hoja, 1.0 si capítulo
#    - PRE_PRE = precio_unitario si concepto_hoja, subtotal si capítulo
```

### 4.2 Asignación de PREFIJO en `[Obra]P.DBF`

```python
# Por cada insumo:
#   if costo_final == 0 and unidad == '' and (descripcion == '' or descripcion is None):
#       prefijo = 512  # categoría
#   else:
#       prefijo = tipo_id
```

### 4.3 Construcción de `[Obra]F.DBF`

```python
# Por cada apu_matrices:
#   if matriz_id < 0:
#       parent = insumos[abs(matriz_id)]
#       pref = parent.tipo_id
#       nombre = parent.clave
#   else:
#       parent = estructura_presupuesto[matriz_id]
#       pref = 32  # concepto compuesto
#       nombre = parent.clave  # usa la clave real del concepto EP
#
#   component = insumos[insumo_id]
#   prefcomp = component.tipo_id
#   componente = component.clave
```

### 4.4 Construcción de `[Obra]N.DBF`

```python
# Por cada apu_resumen_totales:
#   insumo = insumos.get(abs(matriz_id))
#   nombre = insumo.clave if insumo else '*TEMP' + str(matriz_id)
#   mm = materiales, oo = mano_obra, hh = herramienta, ee = equipo, aa = auxiliares
```

### 4.5 Construcción de `[Obra]A.DBF`

```python
# Record 0 (totales):
#   IDUNI=0, PRECIO=total_obra
#
# Por cada EP hoja (tipo='concepto'):
#   IDUNI=id, PRECIO=precio_unitario, NOMBRE=clave
#   DESC=descripcion, UNIDAD=unidad, PRE_WBS=wbs
```

### 4.6 Construcción de `[Obra]X.DBF`

La explosión requiere expandir recursivamente el APU de cada concepto hoja hasta llegar a insumos básicos (hojas del árbol de insumos compuestos).

**Limitación v1:** solo se expanden componentes directos de primer nivel. Insumos compuestos anidados (ej: un básico que contiene otros básicos) no se descomponen recursivamente. Esto es suficiente para que OPUS calcule correctamente el presupuesto siempre que `[Obra]F.DBF` contenga todos los componentes reales (OPUS usa F para el cálculo, X es informativa/explosión).

**Mejora futura:** implementar explosión recursiva completa usando `ExplosionRepo.calcular()` (ya existe en `repos.py:1008`).

### 4.7 Construcción de `[Obra]5.DBF`

Similar a F pero filtrando solo insumos donde `es_basico=1`.

---

## 5. Registro en OBRA.DBF

```python
import os, dbf

def registrar_en_obra(ruta_opus, clave_opus, ruta_obra):
    """
    Agrega la obra al catálogo maestro OBRA.DBF.
    
    Args:
        ruta_opus: Ruta base de OPUS CMS (ej. C:/OPUSCMS)
        clave_opus: Clave de la obra (ej. D60JALISCOT)
        ruta_obra: Ruta completa de la carpeta de obra
    """
    ruta_obra_dbf = os.path.join(ruta_opus, 'OBRA.DBF')
    
    if os.path.exists(ruta_obra_dbf):
        # Modo append: abrir existente y agregar registro
        t = dbf.Table(ruta_obra_dbf)
        t.open(mode=dbf.READ_WRITE)
    else:
        # Modo crear: crear tabla nueva con estructura
        from dbf import Field
        fields = [
            Field('OBRA', 'C', 30),
            Field('DIRECTORIO', 'C', 254),
        ]
        t = dbf.Table(ruta_obra_dbf, fields)
        t.open(mode=dbf.READ_WRITE)
    
    # Verificar si ya existe
    ya_existe = any(str(r.OBRA).strip() == clave_opus for r in t)
    if not ya_existe:
        t.append(('OBRA': clave_opus, 'DIRECTORIO': ruta_obra})
    t.close()
```

**Nota:** `ruta_opus` debe ser configurable (no hardcodeada). Se obtiene de la configuración del proyecto o se solicita al usuario en el diálogo de exportación.

`OBRDESC.dbf` ya existe en la instalación de OPUS, no es necesario crearlo.

---

## 6. Archivos de soporte

### 6.1 CDX (índices)

Los CDX son archivos binarios de índice compuesto de FoxPro. La librería `dbf` puede generarlos automáticamente al abrir una tabla si se especifican índices. Alternativamente, OPUS puede regenerarlos al abrir la obra.

**Prioridad:** BAJA. Para prueba de concepto, se omiten. OPUS los regenera.

### 6.2 Archivos V (versiones) y U (usuario)

**Decisión:** Generar archivos vacíos con estructura mínima (solo header DBF, 0 registros). OPUS los completa al abrir la obra por primera vez.

Archivos a generar:
- `[Obra]VA.DBF`, `[Obra]VC.DBF`, `[Obra]VF.DBF`, `[Obra]VI.DBF`, `[Obra]VN.DBF`, `[Obra]VP.DBF`, `[Obra]VX.DBF`
- `[Obra]UA.DB`, `[Obra]UC.DB`, `[Obra]UF.DB`

### 6.3 FMP (formato de impresión)

**Decisión:** No generar. OPUS lo crea automáticamente con valores por defecto al abrir la obra.

---

## 7. Dependencias de Python

```bash
pip install dbf
```

Librería: [`dbf`](https://pypi.org/project/dbf/) de Ethan Furman — madura, soporta VFP (Visual FoxPro), memo (FPT), nulls, encoding cp1252. Es la misma usada internamente por OPUS CMS.

### Uso básico

```python
from dbf import Table, Field

def crear_tabla(ruta, campos, registros, codepage='cp1252'):
    """
    Crea un archivo DBF.
    
    Args:
        ruta: Ruta completa del .DBF
        campos: Lista de tuplas (nombre, tipo, longitud, decimales)
        registros: Lista de dicts {campo: valor}
        codepage: Encoding del archivo (default cp1252 para OPUS)
    """
    fields = [Field(name, typ, length, decimal) 
              for name, typ, length, *decimal in campos]
    
    table = Table(ruta, fields, codepage=codepage)
    table.open(mode=dbf.READ_WRITE)
    for rec in registros:
        table.append(rec)
    table.close()
```

---

## 8. Encoding y formatos

### Encoding
- Todos los DBF deben usar **codepage cp1252** (Latin-1, Windows-1252)
- En `dbf`: especificar `codepage='cp1252'` al crear la tabla
- Strings con caracteres especiales (acentos, ñ, ¿, ¡) deben codificarse cp1252
- `dbf` maneja esto automáticamente si se especifica el codepage

### Fechas (Date fields)
- Las fechas se pasan como objetos `datetime.date`
- `dbf` las convierte automáticamente al formato interno de FoxPro (YYYYMMDD)
- Fechas vacías: `None`
- Fecha por defecto para campos obligatorios: `date(2000, 1, 1)`

### Lógicos (Logical fields)
- Valores: `True` / `False` (Python bool)
- `dbf` los convierte a `.T.` / `.F.` en FoxPro
- Nulos: `None`

### Memo fields
- Strings largos (>254 chars) se almacenan como Memo
- `dbf` crea automáticamente el archivo `.FPT` adjunto
- Strings cortos también pueden ir en Memo sin problema

### Valores nulos
- FoxPro soporta nulos en casi todos los tipos
- En SQLite los campos NULL se pasan como `None` a `dbf`

---

## 9. Arquitectura del código

### Nuevos archivos

| Archivo | Propósito |
|---|---|
| `backend/exportar.py` | Módulo principal (~500 líneas). Clase `Exportador` como espejo de `importar.py`. |
| `backend/exportar_plantillas.py` | Datos fijos de CONFIG, C, 8, 9, Z, TIPOSINS, FRENTES (~150 líneas). |

### Existente a modificar

| Archivo | Cambio |
|---|---|
| `backend/__init__.py` | Agregar `from .exportar import Exportador` |
| `frontend/toolbar.py` | Botón "Exportar a OPUS" |
| `frontend/handlers.py` | Handler `_on_exportar_opus()` (~50 líneas) |
| `requirements.txt` | Agregar `dbf` |

### Flujo de exportación (`Exportador.exportar`)

1. Crear carpeta `Obras/<clave_opus>/`
2. Fase 0: Tablas estáticas (sin datos del proyecto)
3. Fase 1: Insumos → `[Obra]P.DBF`
4. Fase 2: Presupuesto → `[Obra]1.DBF` + `[Obra]A.DBF`
5. Fase 3: APU → `[Obra]F.DBF` + `[Obra]N.DBF`
6. Fase 4: Explosión → `[Obra]5.DBF` + `[Obra]X.DBF`
7. Fase 5: Sobrecostos → `[Obra]I.DBF`
8. Cierre: copiar V/U/FMP vacíos, registrar en `OBRA.DBF`

---

## 10. Plan de implementación por fases

### Fase −1 — Extraer schemas reales (ANTES de codificar)

**Objetivo:** Obtener los field specs exactos (nombre, tipo, longitud, decimales) de cada tabla DBF desde una obra OPUS existente, para que el código generado coincida 1:1 con lo que OPUS espera.

```python
# scripts/extraer_schemas.py
import dbf, json

tablas = ['1', 'P', 'F', 'N', 'A', 'C', 'I', '5', 'X', '8', '9', 'Z', '0', '3', 'D', 'H', 'J']
obra = r'C:\OPUSCMS\Obras\D60JALISCOT\D60JALISCOT'
resultado = {}

for sufijo in tablas:
    ruta = obra + sufijo + '.DBF'
    t = dbf.Table(ruta)
    t.open()
    resultado[sufijo] = [
        {'name': f.name, 'type': f.type, 'length': f.length, 'decimal': f.decimal}
        for f in t.structure
    ]
    t.close()

# También CONFIG, TIPOSINS, FRENTES, OBRA
with open('schemas_opus.json', 'w') as f:
    json.dump(resultado, f, indent=2)
```

**Output:** `backend/schemas_opus.json` — usado por `exportar.py` para definir las estructuras exactas de cada tabla.

### Fase 0 — Preparación
- Crear `backend/exportar.py` con clase `Exportador` y helper `_crear_tabla_dbf()`
- Crear `backend/exportar_plantillas.py` con valores fijos
- Modificar toolbar y handlers para botón de exportación
- Instalar dependencia `dbf`

### Fase 1 — Tablas estáticas (valores fijos)
- `CONFIG.DBF`, `TIPOSINS.DBF`, `FRENTES.DBF`
- `[Obra]C.DBF`, `[Obra]8.DBF`, `[Obra]9.DBF` (0 registros, solo estructura), `[Obra]Z.DBF`
- `[Obra].DBF` (0 registros, solo estructura)
- `CONFIG.INI`
- `OBRA.DBF` (registrar obra nueva)

### Fase 2 — Insumos
- `[Obra]P.DBF` desde `InsumoRepo.todos()`
- PREFIJO desde `tipo_id` (1,2,4,8,16,32); 512 para categorías (costo=0 y unidad='')

### Fase 3 — Presupuesto
- `[Obra]1.DBF` desde `NodoRepo.todos()` + `core.build_budget_tree()`
- `[Obra]A.DBF` desde EP hojas con APU
- PRE_ID = contador DFS + 10 (raíz = 0), PRE_IDUNI = contador DFS (raíz = 0), PRE_IDPAD = parent.PRE_IDUNI

### Fase 4 — APU
- `[Obra]F.DBF` desde `ApuMatricesRepo.por_matriz()` para cada nodo
- `[Obra]N.DBF` desde `ApuResumenTotalesRepo.por_matriz()`
- Matriz negativa → insumo compuesto; positiva → concepto

### Fase 5 — Derivados
- `[Obra]5.DBF` composición de básicos
- `[Obra]X.DBF` explosión de insumos (recursiva, hacia abajo hasta básicos)

### Fase 6 — Sobrecostos
- `[Obra]I.DBF` desde `SobrecostosRepo.por_proyecto()`

### Fase 7 — Cierre
- Copiar V, U, FMP (archivos vacíos con estructura; OPUS los completa)
- Tablas vacías (`[Obra]0.DBF`, `[Obra]3.DBF`, `[Obra]D.DBF`, `[Obra]H.DBF`, `[Obra]J.DBF`)
- Archivos CDX: omitidos (OPUS los regenera al abrir la obra)
- FPT: generados automáticamente por `dbf` si hay campos Memo

---

## 11. Integración UI

### Botón en toolbar
- Icono de exportación (flecha hacia afuera o disco) en la barra principal
- Tooltip: "Exportar a OPUS 2010"
- Llamar handler `_on_exportar_opus()` en `handlers.py`

### Handler `_on_exportar_opus()`
```python
def _on_exportar_opus(self):
    # 1. Validación pre-exportación
    resumen = Exportador.resumen(db_path, proyecto_id)
    #    → muestra: N insumos (básicos/compuestos/categorías),
    #                N nodos (hojas/capítulos), total obra en $
    #    → si hay inconsistencias (ej. insumos sin precio), advertencia
    
    if not self._confirmar_exportacion(resumen):
        return  # usuario canceló
    
    # 2. QFileDialog.getExistingDirectory() para seleccionar carpeta destino
    #    → incluir campo para ruta de OPUS CMS (C:/OPUSCMS) para OBRA.DBF
    
    # 3. Confirmar si carpeta existe (no sobreescribir sin confirmación)
    
    # 4. Llamar Exportador.exportar(carpeta_destino, db_path, proyecto_id, ruta_opus)
    
    # 5. Mostrar resumen al terminar (# tablas, # registros)
    
    # 6. Ofrecer abrir carpeta destino en explorador
```

### Barra de progreso
- QProgressDialog durante la exportación
- Actualizar por cada tabla generada

### Método `Exportador.resumen()`
```python
@staticmethod
def resumen(db_path, proyecto_id) -> dict:
    """Calcula estadísticas pre-exportación para validación."""
    conn = sqlite3.connect(db_path)
    
    total_insumos = InsumoRepo(conn).contar(proyecto_id)
    por_tipo = InsumoRepo(conn).contar_por_tipo(proyecto_id)
    categorias = InsumoRepo(conn).contar_categorias(proyecto_id)
    
    total_nodos = NodoRepo(conn).contar(proyecto_id)
    hojas = NodoRepo(conn).contar_hojas(proyecto_id)
    capitulos = total_nodos - hojas
    
    total_obra = ProyectoRepo(conn).buscar(proyecto_id).total_obra
    
    conn.close()
    
    return {
        'insumos': total_insumos,
        'por_tipo': por_tipo,
        'categorias': categorias,
        'nodos': total_nodos,
        'hojas': hojas,
        'capitulos': capitulos,
        'total_obra': total_obra,
    }
```

---

## 12. Validación

Después de generar los DBF:

1. **Abrir en OPUS**: La obra debe aparecer en el catálogo (F5 → seleccionar)
2. **Verificar presupuesto**: Revisar que los totales coincidan con SQL
3. **Revisar APU**: Abrir análisis de precios unitarios
4. **Revisar explosión**: Verificar que la explosión de insumos calcule correctamente
5. **Comparar contra obra existente**: Usar `dbfread` para leer datos y comparar registros entre SQL esperado y DBF generado
