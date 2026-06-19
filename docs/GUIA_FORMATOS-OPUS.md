# GUÍA DE ARCHIVOS — OPUS 2010 (Ecosoft)

## Proyecto: CASA EG

---

## 1. INTRODUCCIÓN

OPUS 2010 es un software de presupuestación y administración de obras desarrollado por **Ecosoft**. Almacena los datos en archivos con formato **dBase/FoxPro** (`.DBF`, `.CDX`, `.FPT`), un estándar de bases de datos de los años 90 que sigue siendo legible con herramientas modernas.

Este documento explica qué contiene **cada archivo**, cómo se **relacionan** entre sí y cómo interpretar los datos.

---

## 2. FORMATOS DE ARCHIVO

| Extensión | Propósito | Descripción |
|-----------|-----------|-------------|
| `.DBF` | Datos | Tabla principal con registros (filas) y campos (columnas). |
| `.CDX` | Índices | Archivo de índices que acelera búsquedas en el DBF. Se regenera automáticamente. |
| `.FPT` | Memo | Almacena texto largo o binario asociado a campos tipo `Memo` del DBF (descripciones, fórmulas, fotos). |
| `.DCD`, `.DCI` | Categorías Frente | Catálogo de frentes de obra (datos de captura). |
| `.FDD`, `.FDI` | Categorías Frente | Configuración de frentes de obra. |
| `.FED`, `.FEI` | Estructura de obra | Configuración de estructura de proyecto. |
| `.FID` | Frentes | Configuración adicional de frentes de obra. |
| `.UTD` | Utilidades | Datos de configuración de vistas. |
| `.UTI` | Utilidades | Índices de utilidades. |
| `.UTV` | Utilidades | Configuración de vistas guardadas. |
| `CONFIG.INI` | Configuración | Preferencias de visualización, cálculo y reportes. |

> Los archivos `.CDX`, `.FPT`, `.DCD`, `.DCI`, `.FDD`, `.FDI`, `.FED`, `.FEI`, `.FID` no son necesarios para **consultar** los datos; solo son auxiliares internos de OPUS.

---

## 3. TABLAS PRINCIPALES

### 3.1 EGF — Presupuesto (2712 registros, 26 campos)

**Archivo:** `CASA EGF.DBF` / `CASA EGF.CDX` / `CASA EGF.FPT`

Es la tabla **central del presupuesto**. Contiene la descomposición jerárquica de cada precio unitario en sus componentes (materiales, mano de obra, equipo, etc.).

#### Campos clave

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `PREF` | N(5) | Nivel jerárquico. `16` = concepto principal, `32` = sub-componente. |
| `NOMBRE` | C(20) | Identificador único del concepto. Coincide con `NOMBRE` en EGP. |
| `PREFCOMP` | N(5) | `PREFIJO` del componente en EGP. |
| `COMPONENTE` | C(20) | `NOMBRE` del componente en EGP. |
| `CLAVENUM` | N(11) | Número de renglón consecutivo. |
| `NOELE` | N(20,6) | Número de elementos (cantidad de veces que se repite). |
| `RENDTO` | N(20,6) | Rendimiento (cantidad de recurso por unidad de concepto). |
| `CANTIDAD` | N(20,6) | Cantidad total calculada (`NOELE × RENDTO`). |
| `EXPRESION` | M | Fórmula de la cantidad (p. ej. `.007529`). |
| `COSTO` | N(20,6) | Costo unitario del componente. |
| `TOTALMN` | N(20,6) | Costo total en moneda nacional. |
| `TOTALME` | N(20,6) | Costo total en moneda extranjera. |
| `IMPORTE` | N(20,6) | Importe calculado. |
| `IMPORTEMN` | N(20,6) | Importe en moneda nacional. |
| `CAMPOREND` | C(1) | Indicador de campo de rendimiento. |
| `TIPOREND` | C(1) | Tipo de rendimiento. |
| `MEMOCAD` | M | Memo con fórmula en cadena. |
| `MARCAAJU` | L | Flag de ajuste. |
| `CVEEROG` | C(25) | Clave de erogación. |

#### Interpretación

Cada registro de EGF representa una **línea de desglose** de un precio. Por ejemplo:

```
PREF=16  NOMBRE=8900500  →  Concepto "8900500" (cimbra metálica, nivel 16)
PREF=32  NOMBRE=9602930  →  Detalle "9602930" dentro del concepto anterior (nivel 32)
```

- `PREF=16` son **conceptos** del presupuesto (capítulos/partidas).
- `PREF=32` son sub-componentes que detallan cómo se compone cada concepto.

---

### 3.2 EGP — Precios (603 registros, 52 campos)

**Archivo:** `CASA EGP.DBF` / `CASA EGP.FPT`

Catálogo completo de **precios unitarios** y recursos básicos. Todo concepto en el presupuesto (EGF) tiene su precio definido aquí.

#### Campos clave

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `PREFIJO` | N(5) | **Tipo de recurso**. Usa un sistema de **bits** (ver sección 6). `1`=Material, `2`=Mano de Obra, `4`=Herramienta, `8`=Equipo, `16`=Auxiliar, `32`=Concepto compuesto. |
| `NOMBRE` | C(20) | Identificador único del precio. |
| `UNIDAD` | C(8) | Unidad de medida (ml, Pza, Kg, Tramo, etc.). |
| `BASICO` | C(1) | `S` = es un recurso básico (no desglosable). |
| `PRECIO` | N(20,6) | Precio unitario del recurso. |
| `FECHA` | D | Fecha de actualización del precio. |
| `MATERIALES` | N(20,6) | Costo de materiales que lo componen. |
| `MANO_DEO` | N(20,6) | Costo de mano de obra. |
| `HERRAMIENT` | N(20,6) | Costo de herramienta. |
| `EQUIPO` | N(20,6) | Costo de equipo. |
| `AUXILIARES` | N(20,6) | Costo de auxiliares. |
| `DESCRIPCIO` | M | Descripción extensa del concepto. |
| `DESCCORTA` | C(20) | Descripción corta (para reportes). |
| `CATFSR` | C(6) | Categoría FSR (Factor de Sobrerrendimiento). |
| `WBS` | C(25) | Código WBS (Work Breakdown Structure). |
| `PERSE` | L | `True` = es un concepto persistente (no se borra al recalcular). |
| `PORGEN` | L | `True` = se genera automaticamente su precio. |
| `PESO` | N(20,6) | Peso del concepto. |
| `CTD_MOB` | N(20,6) | Cantidad de mobiliario/equipo. |

#### Interpretación

Los primeros registros (por orden de aparición) son **conceptos compuestos** (PREFIJO=16) que corresponden directamente con los `PREF=16` de EGF. Luego vienen los **recursos básicos** (PREFIJO=1, 2, 4, 8).

Ejemplos reales:
- `(PREFIJO=16, NOMBRE=8900500)` → "Habilitado de cimbra metálica" (concepto compuesto, ml)
- `(PREFIJO=1, NOMBRE=1010003)` → "Perfil Mon ten 3mt14" (material básico, Tramo, $861.90)
- `(PREFIJO=1, NOMBRE=1010018)` → "Solera de 2\" x 1/8\"" (material básico, Pza, $345.12)

---

### 3.3 EGN — Generadores (322 registros, 17 campos)

**Archivo:** `CASA EGN.DBF` / `CASA EGN.CDX`

Contiene los **generadores** o análisis de precios unitarios (APU): el desglose de cada precio en sus componentes elementales (materiales, mano de obra, herramienta, equipo y auxiliares).

#### Campos clave

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `NOMBRE` | C(20) | Identificador del precio (coincide con EGP.NOMBRE). |
| `MM` | N(20,6) | Materiales. |
| `OO` | N(20,6) | Mano de Obra. |
| `HH` | N(20,6) | Herramienta. |
| `EE` | N(20,6) | Equipo. |
| `AA` | N(20,6) | Auxiliares. |
| `SUBCONT` | N(20,6) | Subcontratos. |
| `ACARREOS` | N(20,6) | Acarreos. |
| `DESTAJOS` | N(20,6) | Destajos. |
| `INDIRECTOS` | N(11,6) | Indirectos. |
| `FINANCIA` | N(11,6) | Financiamiento. |
| `UTILIDAD` | N(11,6) | Utilidad. |
| `OTROS` | N(11,6) | Otros costos. |
| `RENDMTO` | N(20,6) | Rendimiento. |
| `PP` | N(20,6) | Precio de venta. |
| `INDIRECTO2` | N(11,6) | Segundo indirecto. |
| `SINPORCE` | C(1) | Sin porcentaje. |

#### Interpretación

Cada registro de EGN suma los componentes que forman el precio total. Por ejemplo, para el concepto `8900500`:
- MM (materiales) = $9.15
- AA (auxiliares) = $0.92
- PP (precio de venta) = $0.00 (se calcula después con indirectos+utilidad)

---

### 3.4 EGX — Auxiliares (302 registros, 12 campos)

**Archivo:** `CASA EGX.DBF` / `CASA EGX.CDX`

Lista de recursos **auxiliares** que intervienen en el presupuesto. Cada registro vincula un recurso con un precio y una cantidad.

#### Campos clave

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `PREFIJO` | N(5) | Tipo de recurso (1=Material, 2=Mano Obra, 4=Herramienta, 8=Equipo, 16=Auxiliar, 32=Concepto). |
| `NOMBRE` | C(20) | Identificador del recurso (coincide con EGP.NOMBRE). |
| `UNIPOR` | N(5) | Unidades por. |
| `CANTIDAD` | N(20,6) | Cantidad. |
| `PRECIO` | N(20,6) | Precio unitario. |
| `MONTO` | N(20,6) | Monto total (`CANTIDAD × PRECIO`). |
| `ESTOTAL` | C(1) | `3` = es total (se muestra en reporte). |
| `EXP_GRUPO` | C(20) | Grupo de explosión. |
| `PESO` | N(20,6) | Peso. |
| `AJUSTA` | C(1) | Ajusta. |
| `MONT_SINAJ` | N(20,6) | Monto sin ajuste. |

---

### 3.5 EGR — Recursos (88 registros, 75 campos)

**Archivo:** `CASA EGR.DBF` / `CASA EGR.FPT`

Programación de **recursos** en el tiempo (calendario de obra). Cada registro es una actividad o asignación con fechas de inicio/fin, avances y costos.

#### Campos clave

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ID` | N(10) | Identificador único del recurso. |
| `IDUNICO` | N(10) | ID único de la actividad. |
| `FRENTE` | N(3) | Frente de obra al que pertenece. |
| `DESCRIPCIO` | M | Descripción de la actividad. |
| `NIVEL` | C(1) | Nivel jerárquico en el WBS. |
| `NOMBRE` | C(20) | Nombre del concepto asociado (coincide con EGP.NOMBRE). |
| `CANTIDAD` | N(15,5) | Cantidad programada. |
| `AVANZADO` | N(15,5) | Cantidad avanzada a la fecha. |
| `FINI` | D | Fecha de inicio. |
| `FTER` | D | Fecha de término. |
| `HINI` | N(2) | Hora de inicio. |
| `HTER` | N(2) | Hora de término. |
| `CADURA` | C(10) | Duración. |
| `COSTO` | N(15,2) | Costo total. |
| `PAGADO` | N(15,2) | Monto pagado. |
| `AVANESTVOL` | N(15,5) | Avance estimado en volumen. |
| `AVANCONVOL` | N(15,5) | Avance contratado en volumen. |
| `FECHAVAEST` | D | Fecha de valuación estimada. |
| `FECHAVACON` | D | Fecha de valuación contratada. |
| `DIASTRAB` | N(12,6) | Días trabajados. |

---

### 3.6 EGI — Ingresos (2 registros, 18 campos)

**Archivo:** `CASA EGI.DBF`

Define cómo se calculan los **ingresos** del presupuesto (Costo Directo, Precio Unitario, etc.).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `RENGLON` | N(3) | Orden del renglón (0, 500). |
| `VAR` | C(10) | Variable: `CD` = Costo Directo, `PU` = Precio Unitario. |
| `DESC1` | C(60) | Descripción. |
| `FORMULA` | C(100) | Fórmula de cálculo (p. ej. `P->PRECIO`). |
| `SE_SUMA` | L | Si se suma al total. |
| `SE_IMPR` | L | Si se imprime en reportes. |
| `SE_FIN` | L | Si es un total final. |
| `DECIMALES` | N(1) | Número de decimales a mostrar. |

---

### 3.7 EGZ — Configuración General (1 registro, 45 campos)

**Archivo:** `CASA EGZ.DBF`

Configuración global del proyecto. Un solo registro con parámetros como:

| Campo | Descripción |
|-------|-------------|
| `ANCNIVI1` a `ANCNIVI9` | Anchos de columna para niveles jerárquicos. |
| `HORASDIA` | Horas por día laboral. |
| `MINSDIA` | Minutos por día laboral. |
| `HINIDIA` | Hora de inicio del día. |
| `MINIDIA` | Minuto de inicio del día. |
| `CPO_FSBSG` | Campo FSR de seguro. |
| `SEGURO` / `TASA_INTER` | Porcentajes de seguro e interés. |

---

### 3.8 Tablas auxiliares

| Archivo | Registros | Propósito |
|---------|-----------|-----------|
| `CASA EGD.DBF` | 0 | WBS / Estructura de desglose de trabajo. |
| `CASA EGH.DBF` | 0 | Mediciones en campo. |
| `CASA EGJ.DBF` | 0 | Justificantes de precios (maquinaria). |
| `FRENTES.DBF` | 0 | Catálogo de frentes de obra. |
| `TIPOSINS.DBF` | 6 | Catálogo de tipos de insumo (bits). |

---

## 4. RELACIONES ENTRE TABLAS

```
                    ┌──────────────────────────────────────────────┐
                    │              EGP  (Precios)                  │
                    │  PREFIJO + NOMBRE  ← clave única              │
                    │  603 registros                               │
                    └──────┬──────────────┬──────────────┬─────────┘
                           │              │              │
                    PREFCOMP+NOMBRE  NOMBRE         NOMBRE
                           │              │              │
                    ┌──────▼──────┐ ┌────▼────┐ ┌──────▼──────┐
                    │EGF(Desglose)│ │EGN(APU) │ │EGX(Auxilia)│
                    │2712 regs    │ │322 regs │ │302 regs    │
                    │PREF+NOMBRE  │ │NOMBRE   │ │NOMBRE      │
                    │→ EGP        │ │→ EGP    │ │→ EGP       │
                    └─────────────┘ └─────────┘ └─────────────┘
                                              │
                                              │ NOMBRE
                                        ┌────▼──────┐
                                        │EGR(Recursos)│
                                        │88 regs     │
                                        │NOMBRE→EGP   │
                                        └─────────────┘
```

### Relaciones clave:

1. **EGF → EGP**: `EGF.PREFCOMP + EGF.COMPONENTE` → `EGP.PREFIJO + EGP.NOMBRE`. El 100% de los conceptos en EGF tienen su precio en EGP.

2. **EGN → EGP**: `EGN.NOMBRE` → `EGP.NOMBRE`. Todos los generadores corresponden a un precio existente.

3. **EGX → EGP**: `EGX.NOMBRE` → `EGP.NOMBRE`. 281 de 285 auxiliares (98.6%) referencian precios existentes.

4. **EGR → EGP**: `EGR.NOMBRE` → `EGP.NOMBRE`. Recursos programados vinculados a conceptos del catálogo.

5. **EGF jerarquía interna**: `EGF.PREF + EGF.NOMBRE` forma un árbol:
   - `PREF=16` son conceptos principales (401 registros)
   - `PREF=32` son sub-componentes (2311 registros)
   - Ambos niveles referencian a EGP mediante `PREFCOMP+COMPONENTE`

---

## 5. JERARQUÍA DEL PRESUPUESTO

El presupuesto se organiza como un **árbol de 2 niveles** en EGF:

```
Nivel 16 (Concepto)
├── CLAVENUM=100, 200, 300...  ───→  Componentes en EGP
├── ...
└── Nivel 32 (Detalle)
    ├── CLAVENUM=0
    ├── ...
    └── Referencia a EGP (materiales, mano de obra, etc.)
```

Los conceptos de nivel 16 en EGF tienen su precio en EGP con `PREFIJO=16`. Estos mismos conceptos aparecen en EGN con su desglose por tipo de recurso.

---

## 6. SISTEMA DE PREFIJOS (TIPOS DE INSUMO)

| Prefijo | Tipo | Descripción |
|---------|------|-------------|
| 1 | Materiales | Insumos físicos (acero, concreto, etc.) |
| 2 | Mano de Obra | Jornales, salarios |
| 4 | Herramienta | Herramienta menor |
| 8 | Equipo | Maquinaria y equipo |
| 16 | Auxiliar | Conceptos auxiliares |
| 32 | Concepto | Conceptos compuestos (sub-presupuestos) |

Los valores son **potencias de 2** y se pueden combinar mediante suma binaria. Por ejemplo:
- `33` = `32 + 1` = Concepto compuesto que incluye materiales
- `63` = `32 + 16 + 8 + 4 + 2 + 1` = Todos los tipos
- `32767` = todos los bits (15 bits = 32767, usado para conceptos que abarcan todos los tipos)

---

## 7. ARCHIVOS DE CONFIGURACIÓN

### CONFIG.INI

Almacena preferencias de la interfaz y configuración de cálculo:

| Sección | Propósito |
|---------|-----------|
| `[Explosión]` | Configuración de explosión de insumos. |
| `[Vista Actividades]` | Configuración del calendario / programación. |
| `[Vista Suministros]` | Configuración de vista de suministros. |
| `[Titulos de Reportes]` | Títulos y fuentes para reportes impresos. |
| `[Cálculo Indirectos]` | Parámetros de cálculo de indirectos. |
| `[Personal Indirectos]` | Configuración de personal indirecto. |
| `[VINDIP_1]`, `[VACTI_4]` | Configuración de vistas (anchos, colores, escalas). |

---

## 8. CÓMO USAR LOS DATOS

### Opción A: Visor HTML (recomendado)

Usar el archivo `opus_visor.html` generado con el script `_exportar.py`. Abrir en cualquier navegador. Las tablas tienen búsqueda y ordenamiento.

### Opción B: Python directo

```python
from dbfread import DBF

tbl = DBF('CASA EGP.DBF', encoding='cp850')
for rec in tbl:
    print(rec['NOMBRE'], rec['PRECIO'])
```

### Opción C: Excel

Usar Python con `dbfread` + `openpyxl` o `pandas` para exportar a `.xlsx`.

### Opción D: Power BI / Tableau

Conectar mediante ODBC dBase (.DBF) o importar desde CSV/Excel exportado.

---

## 9. NOTAS TÉCNICAS

- **Encoding**: Los textos usan **CP850** (Latin-1 / OEM multilingüe). Al leer en Python usar `encoding='cp850'`.
- **Campos tipo M (Memo)**: El texto largo se almacena en el archivo `.FPT`. `dbfread` los carga automáticamente si el `.FPT` está presente.
- **Campos tipo L (Lógico)**: `True/False` o `None` (nulo).
- **Campos tipo D (Fecha)**: Formato `YYYY-MM-DD`.
- **Campos tipo N (Numérico)**: Formato `N(tamaño, decimales)`. Ej: `N(20,6)` = 20 dígitos, 6 decimales.
- **Campos tipo C (Carácter)**: Texto de longitud fija.
- **Valores nulos**: Aparecen como `None` en Python. En el visor HTML se muestran como celdas vacías.
- **Bit flags**: El campo `PREFIJO` en EGP y EGX usa valores que son suma de potencias de 2 para codificar múltiples categorías.

---

## 10. GLOSARIO

| Término | Significado |
|---------|-------------|
| APU | Análisis de Precio Unitario |
| CD | Costo Directo |
| FSR | Factor de Sobrerrendimiento |
| PU | Precio Unitario |
| WBS | Work Breakdown Structure |
| Frente | Área o zona de la obra |
| Generador | Desglose de un precio en sus componentes |
| Indirecto | Costo indirecto (administración, seguros, etc.) |
| Explosión | Cálculo de la cantidad total de cada insumo sumando todas sus apariciones |
