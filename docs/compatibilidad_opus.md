# Compatibilidad con OPUS 2010

Documento técnico que define cómo el sistema importa, interpreta y convierte los archivos de OPUS 2010 al formato interno (SQLite).

---

## 1. Archivos de OPUS que se leen

De todos los archivos que genera OPUS 2010, solo se requieren los `.DBF` y sus `.FPT` asociados. Los archivos `.CDX` (índices), `.DCD`, `.FDD`, `.FED`, `.FID`, `.UTD`, `.UTI`, `.UTV` son auxiliares internos y se ignoran.

| Archivo OPUS | Contenido | Prioridad |
|---|---|---|
| `*EGP.DBF` + `*EGP.FPT` | Catálogo completo de precios e insumos | Indispensable |
| `*EGF.DBF` + `*EGF.FPT` | Desglose del presupuesto (jerarquía) | Indispensable |
| `*EGN.DBF` | Análisis de precios unitarios (APU) | Indispensable |
| `*EGX.DBF` | Auxiliares | Importante |
| `*EGZ.DBF` | Configuración general del proyecto | Importante |
| `*EGR.DBF` + `*EGR.FPT` | Programación de recursos / frentes | Versión 1.x |
| `*EGI.DBF` | Definición de ingresos / indirectos | Versión 1.x |
| `FRENTES.DBF` | Catálogo de frentes de obra | Versión 1.x |
| `CONFIG.INI` | Preferencias de cálculo e indirectos | Versión 1.x |

> Los nombres de archivo varían según el nombre del proyecto. El prefijo (`CASA`, `EDIFICIO`, etc.) cambia; el sufijo (`EGP`, `EGF`, etc.) es fijo.

---

## 2. Lectura técnica de los archivos

### Librería

```python
from dbfread import DBF

tabla = DBF('CASA EGP.DBF', encoding='cp850')
for registro in tabla:
    print(registro['NOMBRE'], registro['PRECIO'])
```

### Consideraciones de codificación

- Los archivos `.DBF` pueden usar **CP850** o **Latin-1/ISO-8859-1** según la configuración regional donde se generaron. En la práctica, los archivos mexicanos suelen usar Latin-1. Usar `encoding='latin-1'` al leer; si hay errores de decodificación, probar con `'cp850'`.
- Los campos tipo **Memo** (`M`) se almacenan en el `.FPT` asociado. `dbfread` los carga automáticamente si el `.FPT` está en la misma carpeta.
- Los campos tipo **Lógico** (`L`) devuelven `True`, `False` o `None`.
- Los campos tipo **Numérico** (`N`) llegan como `Decimal` en Python. Convertir a `float` al guardar en SQLite.
- Los valores nulos llegan como `None`. Manejar siempre con `or 0` o `or ''` según el tipo.

---

## 3. Sistema de prefijos (tipos de insumo)

OPUS codifica el tipo de cada recurso con un sistema de **bits** en el campo `PREFIJO`:

| Valor | Tipo |
|---|---|
| 1 | Material |
| 2 | Mano de obra |
| 4 | Herramienta |
| 8 | Equipo / Maquinaria |
| 16 | Auxiliar |
| 32 | Concepto compuesto |

Los valores pueden combinarse por suma. Para leer el tipo real:

```python
def tipo_insumo(prefijo):
    tipos = []
    if prefijo & 1:  tipos.append('material')
    if prefijo & 2:  tipos.append('mano_obra')
    if prefijo & 4:  tipos.append('herramienta')
    if prefijo & 8:  tipos.append('equipo')
    if prefijo & 16: tipos.append('auxiliar')
    if prefijo & 32: tipos.append('concepto')
    return tipos
```

Para la importación, el tipo **dominante** se determina por el bit de mayor peso presente.

---

## 4. Mapeo OPUS → modelo interno

### 4.1 Insumos (EGP → tabla `insumos`)

EGP es el catálogo maestro. Cada registro es un insumo o concepto.

| Campo OPUS (EGP) | Campo interno | Notas |
|---|---|---|
| `NOMBRE` | `clave` | Identificador único |
| `PREFIJO` | `tipo` | Convertir con función de bits |
| `UNIDAD` | `unidad` | Texto libre |
| `PRECIO` | `precio` | `float` |
| `DESCRIPCIO` | `descripcion` | Campo Memo, puede ser largo |
| `DESCCORTA` | `descripcion_corta` | Máx. 20 caracteres |
| `FECHA` | `fecha_precio` | Fecha de última actualización |
| `BASICO` | `es_basico` | `'S'` → `True` |
| `MATERIALES` | `costo_materiales` | Subtotal por tipo |
| `MANO_DEO` | `costo_mano_obra` | Subtotal por tipo |
| `HERRAMIENT` | `costo_herramienta` | Subtotal por tipo |
| `EQUIPO` | `costo_equipo` | Subtotal por tipo |
| `AUXILIARES` | `costo_auxiliares` | Subtotal por tipo |

### 4.2 Presupuesto jerárquico (EGF → tablas `conceptos` + `apu_componentes`)

EGF contiene dos tipos de registros mezclados, diferenciados por `PREF`:

| `PREF` | Significado | Destino |
|---|---|---|
| `16` | Concepto principal (partida/concepto) | tabla `conceptos` |
| `32` | Sub-componente del APU | tabla `apu_componentes` |

**Conceptos (PREF=16):**

| Campo OPUS (EGF) | Campo interno | Notas |
|---|---|---|
| `NOMBRE` | `clave` | Coincide con EGP.NOMBRE |
| `CLAVENUM` | `orden` | Posición en el presupuesto |
| `NOELE` | `cantidad` | Cantidad de obra |
| `COSTO` | `precio_unitario` | Precio unitario |
| `IMPORTE` | `importe` | `cantidad × precio_unitario` |

**Componentes del APU (PREF=32):**

| Campo OPUS (EGF) | Campo interno | Notas |
|---|---|---|
| `NOMBRE` | `concepto_clave` | A qué concepto pertenece |
| `COMPONENTE` | `insumo_clave` | Qué insumo es |
| `PREFCOMP` | `tipo_insumo` | Tipo del componente (bits) |
| `RENDTO` | `rendimiento` | Cantidad por unidad de concepto |
| `NOELE` | `num_elementos` | Multiplicador |
| `CANTIDAD` | `cantidad_total` | `NOELE × RENDTO` |
| `COSTO` | `precio_unitario` | Precio del insumo |
| `TOTALMN` | `importe` | Costo total en MN |
| `EXPRESION` | `formula` | Fórmula de cálculo (Memo) |

### 4.3 APU — resumen por tipo (EGN → tabla `apu_resumen`)

EGN almacena los subtotales del APU por categoría de insumo.

| Campo OPUS (EGN) | Campo interno | Notas |
|---|---|---|
| `NOMBRE` | `concepto_clave` | Llave a `conceptos` |
| `MM` | `total_materiales` | |
| `OO` | `total_mano_obra` | |
| `HH` | `total_herramienta` | |
| `EE` | `total_equipo` | |
| `AA` | `total_auxiliares` | |
| `SUBCONT` | `total_subcontratos` | |
| `INDIRECTOS` | `indirectos` | Porcentaje |
| `FINANCIA` | `financiamiento` | Porcentaje |
| `UTILIDAD` | `utilidad` | Porcentaje |
| `RENDMTO` | `rendimiento` | |
| `PP` | `precio_venta` | Precio de venta final |

### 4.4 Auxiliares (EGX → tabla `auxiliares`)

| Campo OPUS (EGX) | Campo interno | Notas |
|---|---|---|
| `NOMBRE` | `insumo_clave` | Llave a `insumos` |
| `PREFIJO` | `tipo` | Tipo con sistema de bits |
| `CANTIDAD` | `cantidad` | |
| `PRECIO` | `precio` | |
| `MONTO` | `importe` | `cantidad × precio` |

### 4.5 Configuración del proyecto (EGZ → tabla `proyecto_config`)

| Campo OPUS (EGZ) | Campo interno | Notas |
|---|---|---|
| `HORASDIA` | `horas_dia` | Horas laborales por día |
| `SEGURO` | `tasa_seguro` | Porcentaje |
| `TASA_INTER` | `tasa_interes` | Porcentaje |

---

## 5. Jerarquía del presupuesto

OPUS no almacena partidas y subpartidas de forma explícita en EGF — todo vive en EGP con `PREFIJO=32` (concepto compuesto). La jerarquía se reconstruye a partir del orden y las relaciones entre registros.

La estructura interna del sistema usa una tabla con campo `padre_id` para representar el árbol:

```
proyecto
└── partida (nivel 1)
    └── subpartida (nivel 2)
        └── concepto (nivel 3)  ←  tiene APU en EGN + componentes en EGF
```

Durante la importación, los conceptos compuestos (`PREFIJO=32` en EGP) que no tienen APU propio se tratan como **partidas o subpartidas**. Los que sí tienen APU en EGN son **conceptos con precio unitario**.

---

## 6. Flujo de importación

```
1. El usuario selecciona la carpeta del proyecto OPUS
         ↓
2. El sistema detecta los archivos *EGP, *EGF, *EGN, *EGX, *EGZ
         ↓
3. Se lee EGP completo → se pobla la tabla `insumos`
         ↓
4. Se lee EGF → registros PREF=16 → tabla `conceptos`
              → registros PREF=32 → tabla `apu_componentes`
         ↓
5. Se lee EGN → tabla `apu_resumen` (subtotales por tipo)
         ↓
6. Se lee EGX → tabla `auxiliares`
         ↓
7. Se lee EGZ → tabla `proyecto_config`
         ↓
8. Se reconstruye la jerarquía partida → subpartida → concepto
         ↓
9. Se genera el archivo .sqlite del proyecto
         ↓
10. El usuario ve el proyecto importado en la interfaz
```

---

## 7. Datos que no se importan en el MVP

Los siguientes datos de OPUS quedan fuera del MVP por complejidad o prioridad:

| Dato | Archivo | Razón |
|---|---|---|
| Programación de obra | EGR | Requiere módulo de frentes (v1.x) |
| Frentes de obra | FRENTES.DBF | Requiere módulo de frentes (v1.x) |
| Definición de indirectos | EGI | Requiere módulo de indirectos (v1.x) |
| Configuración de vistas | CONFIG.INI | Solo afecta presentación, no datos |
| WBS / estructura de desglose | EGD | Vacío en la mayoría de proyectos |
| Mediciones en campo | EGH | Vacío en la mayoría de proyectos |

---

## 8. Validaciones durante la importación

Antes de guardar en SQLite, verificar:

- Que cada `COMPONENTE` en EGF exista en EGP (integridad referencial)
- Que cada `NOMBRE` en EGN exista en EGP
- Que cada `NOMBRE` en EGX exista en EGP (98.6% de los casos según datos reales)
- Que los valores numéricos no sean `None` — reemplazar con `0.0`
- Que los campos de texto no excedan el límite definido en el modelo interno

Los registros con referencias rotas se registran en un **log de importación** visible para el usuario, sin detener el proceso.

---

## 9. Notas sobre la exportación hacia OPUS

La exportación hacia OPUS 2010 requiere generar archivos `.DBF` con la estructura exacta de cada tabla. Esto implica:

- Usar una librería que permita **escribir** `.DBF` (por ejemplo `dbfwrite` o `simpledbf`)
- Respetar los tipos de campo (`N`, `C`, `M`, `L`, `D`) y sus longitudes exactas
- Generar el `.FPT` para campos Memo
- Usar codificación **CP850** en todos los textos

Esta funcionalidad se implementa en una versión posterior al MVP.
