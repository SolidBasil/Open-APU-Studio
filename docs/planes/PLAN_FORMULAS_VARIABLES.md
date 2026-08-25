# Guía de implementación — Fórmulas y variables paramétricas (Open APU Studio)

**Fecha:** 2026-07-20
**Estado:** Diseño aprobado, pendiente de implementación
**Estimado:** 10-13 horas

---

## 1. Objetivo

Permitir que el usuario introduzca una **fórmula** en las columnas de Cantidad (árbol de presupuesto) y Valor (detalle de APU), que se evalúe automáticamente para producir un número, y que ese número alimente el resto del sistema (recálculo en cascada, exportación OPUS, etc.) exactamente igual que si se hubiera tecleado un valor manual.

Además, se añade un módulo de **variables paramétricas por proyecto** (ej. `ancho_muro = 3.5`) que el usuario puede referenciar desde cualquier fórmula.

---

## 2. Estado actual del código (punto de partida)

El sistema ya tiene 3 capas con piezas parciales, ninguna conectada:

| Capa | Qué existe | Qué falta |
|---|---|---|
| **Schema** (`backend/database/schema.sql`) | Columna `formula TEXT` en `estructura_presupuesto` (línea 284) y `apu_matrices` (línea 403). Tabla `variables_formula` (Bloque 8, líneas 417-432) con `nombre`, `expresion`, `valor`, comentada como soporte recursivo con detección de ciclos | Nada — el schema ya está listo |
| **Backend** (`repos/apu.py:89`, `repos/presupuesto.py:127`) | `SELECT` del campo `formula` | Ningún método que lo **escriba**; nada que lea/resuelva `variables_formula` |
| **Frontend** (`arbol.py` col 14, `widgets/apu.py` col 8) | Columna "Fórmula" visible (oculta por defecto), lee el valor crudo | Nada la llena ni la evalúa todavía |

**Conclusión:** no es agregar una fórmula simple — es terminar un sistema de variables nombradas estilo hoja de cálculo que ya estaba diseñado en el schema.

---

## 3. Librerías a reutilizar (nada que reinventar)

| Necesidad | Solución | Por qué |
|---|---|---|
| Evaluar una expresión aritmética de forma segura | **`simpleeval`** (PyPI, MIT) | Bloquea `__import__`, `open`, etc. por diseño (whitelist de nodos AST). Acepta `names={}` para variables y `functions={}` para funciones matemáticas |
| Resolver orden de dependencias entre variables y detectar ciclos | **`graphlib.TopologicalSorter`** (stdlib, Python 3.9+) | Cero dependencia nueva. `static_order()` ordena por dependencias y lanza `CycleError` automáticamente si hay ciclo |
| Detectar qué nombres de variable usa una expresión | **`ast`** (stdlib) | `ast.walk(ast.parse(expr, mode="eval"))` filtrando `ast.Name` → set de nombres referenciados |

El único código propio es el "pegamento" entre estas tres piezas (~150-200 líneas estimadas).

---

## 4. Decisiones de diseño (revisión aplicada al plan original)

Estas 10 decisiones corrigen o precisan puntos ciegos detectados en la primera versión del plan. **Deben incorporarse antes de empezar a codificar**, porque cambian el modelo de datos.

### 4.1 Cantidad es siempre de solo lectura — el usuario solo interactúa con Fórmula
No hay dos modos ("manual" vs "calculada"). Hay un único flujo: el usuario **siempre** escribe en la columna Fórmula, nunca en Cantidad.

- Un número simple (`15`) también se introduce en Fórmula — se trata como una fórmula trivial que evalúa a sí misma.
- Una expresión (`ancho*alto`) se introduce igual, en Fórmula.
- `cantidad` es en todos los casos un valor **derivado**: `cantidad = evaluar_formula(formula, variables)`.
- La celda Cantidad es de solo lectura siempre, sin excepción — no existe un camino en la UI para escribirla directamente.

Esto elimina la necesidad de distinguir "modo manual" vs "modo calculado": simplifica el modelo de datos (un solo camino de escritura) y evita el riesgo de que el usuario rompa la relación editando Cantidad por error.

### 4.2 No guardar `valor` en `variables_formula`
El campo `valor` es dato derivado. Ejemplo del problema:
```
a = 5
b = a * 2   →  valor(b) = 10
a = 8       →  ¿quién garantiza que valor(b) se actualizó a 16?
```
Esto crea dos fuentes de verdad. **Solución:** la tabla solo guarda `nombre` + `expresion`; el valor se resuelve siempre en memoria (`resolver_variables()`). Cachear únicamente si el rendimiento lo justifica más adelante.

### 4.3 Usar `decimal.Decimal`, no `float` — y resolverlo bien, no a medias
Los presupuestos manejan valores como `0.1 + 0.2`, que en `float` producen `0.30000000000000004`. Para ingeniería y dinero, `Decimal` es la opción correcta desde el inicio — cambiarlo después de que el proyecto esté avanzado es mucho más costoso.

**El problema real:** no basta con guardar variables como `Decimal`. `ast`/`simpleeval` parsean los literales numéricos de la fórmula (`1.5`, `0.1`) como `float` nativo de Python. Mezclar `Decimal * float` en la misma expresión lanza `TypeError` en Python — así que si no se maneja explícitamente, el motor se rompe en la primera fórmula con un decimal literal.

**Solución sin perder precisión:** interceptar la evaluación de constantes numéricas antes de que lleguen a la aritmética, y convertirlas a `Decimal` a partir de su representación en texto (no a partir del `float` ya construido):

```python
from decimal import Decimal
from simpleeval import EvalWithCompoundTypes

class EvalDecimal(EvalWithCompoundTypes):
    """Variante de simpleeval donde todo literal numérico se evalúa
    como Decimal, evitando TypeError al mezclar con variables Decimal
    y evitando el error de redondeo binario de float."""

    def _eval_constant(self, node):
        valor = node.value
        if isinstance(valor, float):
            # Decimal(str(valor)) usa la representación decimal más
            # corta que reproduce el float — para literales como 1.5
            # o 0.1 esto recupera exactamente el texto que escribió
            # el usuario, no el binario aproximado.
            return Decimal(str(valor))
        if isinstance(valor, int):
            return Decimal(valor)
        return valor
```

Por qué `Decimal(str(valor))` y no `Decimal(valor)` directo: `Decimal(0.1)` (a partir del float ya construido) da `Decimal('0.1000000000000000055511151231257827021181583404541015625')`, arrastrando el error binario. `Decimal(str(0.1))` da `Decimal('0.1')` exacto, porque `str()` en Python ya usa la representación decimal más corta que redondea de vuelta al mismo float — es el mismo texto que el usuario escribió.

**Funciones matemáticas (`sqrt`, `sin`, `cos`, `tan`):** el módulo `math` de Python no acepta `Decimal` directamente. Estas funciones deben convertir su argumento a `float` internamente, operar, y devolver el resultado envuelto de nuevo en `Decimal(str(...))`. Es una pérdida de precisión aceptada solo para esas funciones trascendentales (inevitable, ni `float` ni `Decimal` son exactos ahí) — el resto de la aritmética (`+ - * /`, que es el 95% de las fórmulas de un presupuesto: áreas, volúmenes, factores) permanece en `Decimal` puro sin tocar `float` en ningún punto.

### 4.4 Invalidación de caché: re-evaluar todo el proyecto (v1)
Cuando cambia una variable, no vale la pena construir un índice inverso de "qué celdas usan qué variable" para la primera versión. Re-evaluar todas las fórmulas del proyecto al tocar cualquier variable es aceptable: un presupuesto de miles de conceptos sigue siendo rápido de recalcular comparado con el tiempo que tarda un usuario en editar una celda.

### 4.5 Whitelist explícita de funciones
Definir desde el inicio qué funciones están permitidas en las fórmulas, en vez de descubrirlo sobre la marcha:
```
sqrt, sin, cos, tan, pi, abs, min, max, round
```
Nada fuera de esa lista.

### 4.6 UX de errores con sugerencias
No basta con "Variable no definida". Si el usuario escribe `alto*ancho` cuando la variable real es `anchura`, el mensaje debe ser:
> Variable "ancho" no existe. ¿Quisiste decir "anchura"?

Esto reduce drásticamente la frustración y se puede lograr con una comparación de similitud de strings (ej. `difflib.get_close_matches`) contra las variables/columnas conocidas.

### 4.7 No se persisten fórmulas inválidas — validar antes de guardar, no después
Simplificación deliberada: **no existe un estado "con error" guardado en la base de datos.** Solo hay un estado posible en reposo: `formula` siempre es una expresión válida y `cantidad` siempre es su resultado.

Flujo al editar una celda:
1. El usuario escribe en Fórmula y confirma (Enter / pierde foco).
2. El backend evalúa inmediatamente. Si es válida → se guarda `formula` + `cantidad` derivada, en la misma transacción.
3. Si es inválida (variable inexistente, sintaxis rota, ciclo) → **no se guarda nada**. La celda revierte al valor anterior (igual que el comportamiento actual con `float()` fallido) y se muestra el mensaje de error con sugerencia (§4.6) para que el usuario corrija ahí mismo.

Ventajas de esta simplificación:
- No hace falta modelar ni pintar un tercer estado visual ("celda en rojo persistente").
- No hay riesgo de que una variable borrada deje fórmulas "colgadas" e inválidas dispersas por el proyecto — es imposible guardar una fórmula que no evalúe.
- El recálculo en cascada (§4.4) nunca tiene que lidiar con celdas en estado de error preexistente: todo lo que hay en la base de datos es, por construcción, evaluable.

Costo aceptado, con corrección: si el usuario borra una variable que otras fórmulas usan, **no se dejan colgadas sin evaluar**. En el momento de eliminar la variable, el sistema:

1. Busca todas las fórmulas del proyecto que referencian esa variable (usando `nombres_referenciados()` sobre cada `formula` guardada — un recorrido directo, no requiere índice inverso persistido).
2. Muestra una advertencia: *"La variable 'ancho' se usa en 3 fórmulas. Al eliminarla se sustituirá por su último valor (5) en esas fórmulas."*
3. Si el usuario confirma, sustituye el nombre de la variable por su último valor numérico resuelto **directamente en el texto de la fórmula**, y re-evalúa/persiste el resultado.

Ejemplo:
```
Antes:   area = alto * ancho        (ancho = 5)
Se elimina la variable "ancho"
Después: area = alto * 5
```

Esto mantiene la invariante de §4.7 (todo lo guardado en BD siempre evalúa correctamente) sin dejar al usuario con fórmulas rotas ni con un estado de error que investigar. La fórmula sigue siendo editable después — si el usuario quiere, puede volver a escribir `alto * ancho` una vez que recree la variable.

**Nota de implementación:** esta sustitución debe hacerse con el mismo mecanismo de reemplazo por nombre de variable (nunca `replace()` de texto ciego — ver §4.8), idealmente reconstruyendo la expresión a partir del AST (reemplazar cada `ast.Name` que coincida por un `ast.Constant` con el valor, y volver a serializar con `ast.unparse`). Así se evita romper nombres parcialmente coincidentes (ej. `ancho` dentro de `ancho_muro`).

### 4.8 Cuidado con `replace("^", "**")` a ciegas
El plan original proponía normalizar el operador potencia con un reemplazo de texto global antes de parsear. Riesgo: si en el futuro se soportan funciones o cadenas, ese `replace()` puede modificar texto que no corresponde. Mejor manejarlo durante el preprocesamiento/tokenización del parser, no como reemplazo ciego de texto. No es urgente para v1, pero conviene no dejarlo como deuda técnica que "crece mal".

### 4.9 Scope de las variables (pendiente de definir)
Hoy el schema solo contempla `variables_formula` por proyecto. Preguntas abiertas:
- ¿Existirán variables también a nivel presupuesto / APU / concepto?
- Ejemplo: `espesor = 0.15` puede significar cosas distintas según el contexto.

**Recomendación:** dejar la arquitectura preparada para soportar distintos ámbitos (scope), aunque v1 solo implemente el nivel de proyecto.

### 4.10 Nombres reservados: no hace falta, y aquí está el porqué
Se evaluó agregar una lista de palabras prohibidas para nombres de variable (evitar `cantidad`, `valor`, `id`, etc.), pero no aplica: las variables del usuario viven en un **namespace aislado** — el diccionario `{nombre: Decimal}` que se pasa explícitamente como `names=` al evaluador (§5). Nunca se mezcla con nombres de columnas del programa ni con atributos internos, porque una fórmula solo puede referenciar lo que está en ese diccionario. `cantidad`, por ejemplo, ni siquiera es una variable disponible para las fórmulas — es el resultado, no un insumo.

El único límite real es sintáctico: un nombre de variable debe ser un identificador válido de Python (`ast.Name` lo exige), así que palabras clave reservadas del lenguaje (`for`, `if`, `class`, etc.) quedan excluidas automáticamente por el propio parser — no hace falta una validación adicional para eso.

### 4.11 Mover toda la lógica de decisión al backend
En vez de que el frontend intente `float()` y, si falla, intente `evaluar_formula()`, el frontend debe **solo enviar el texto crudo introducido**. El backend decide si es número, fórmula o error. Ventaja: si en el futuro hay una API web o importación masiva, se reutiliza exactamente el mismo código de decisión, sin duplicar lógica en dos lugares.

---

## 5. Diseño del motor de fórmulas — `backend/motor/formulas.py` (nuevo)

```python
import ast
import graphlib
import math
from decimal import Decimal
from simpleeval import EvalWithCompoundTypes, NameNotDefined


class ErrorFormula(Exception):
    pass


def _envolver_math(fn):
    """Convierte una función de math (float-only) para aceptar y
    devolver Decimal, sin filtrar float al resto de la aritmética."""
    def envoltura(x):
        return Decimal(str(fn(float(x))))
    return envoltura


FUNCIONES_PERMITIDAS = {
    "sqrt": _envolver_math(math.sqrt),
    "sin": _envolver_math(math.sin),
    "cos": _envolver_math(math.cos),
    "tan": _envolver_math(math.tan),
    "pi": Decimal(str(math.pi)),
    "abs": abs,       # abs() ya funciona nativo sobre Decimal
    "min": min,        # min/max ya funcionan nativo sobre Decimal
    "max": max,
    "round": round,    # round() ya funciona nativo sobre Decimal
}


class EvalDecimal(EvalWithCompoundTypes):
    """simpleeval donde todo literal numérico se evalúa como Decimal —
    ver §4.3 para el porqué de Decimal(str(valor)) en vez de Decimal(valor)."""

    def _eval_constant(self, node):
        valor = node.value
        if isinstance(valor, float):
            return Decimal(str(valor))
        if isinstance(valor, int):
            return Decimal(valor)
        return valor


def nombres_referenciados(expr: str) -> set[str]:
    """Nombres de variable que aparecen en una expresión."""
    try:
        arbol = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ErrorFormula(f"Sintaxis inválida: {e}")
    return {n.id for n in ast.walk(arbol) if isinstance(n, ast.Name)}


def resolver_variables(variables: dict[str, str]) -> dict[str, Decimal]:
    """variables: {nombre: expresion}. Devuelve {nombre: valor} resuelto
    en orden de dependencias. Lanza ErrorFormula si hay ciclo o nombre
    indefinido. No persiste el resultado — se recalcula en memoria."""
    grafo = {
        nombre: nombres_referenciados(expr) & variables.keys()
        for nombre, expr in variables.items()
    }
    try:
        orden = list(graphlib.TopologicalSorter(grafo).static_order())
    except graphlib.CycleError as e:
        raise ErrorFormula(f"Ciclo entre variables: {' → '.join(e.args[1])}")

    resueltas: dict[str, Decimal] = {}
    for nombre in orden:
        ev = EvalDecimal(names=resueltas, functions=FUNCIONES_PERMITIDAS)
        try:
            resueltas[nombre] = ev.eval(variables[nombre])
        except NameNotDefined as e:
            raise ErrorFormula(f"'{nombre}': variable no definida ({e})")
    return resueltas


def evaluar_formula(expr: str, variables_resueltas: dict[str, Decimal]) -> Decimal:
    """Evalúa la fórmula de una celda (Cant/Valor) contra las variables
    ya resueltas del proyecto."""
    ev = EvalDecimal(names=variables_resueltas, functions=FUNCIONES_PERMITIDAS)
    try:
        return ev.eval(expr)
    except NameNotDefined as e:
        raise ErrorFormula(f"Variable no definida: {e}")
    except Exception as e:
        raise ErrorFormula(str(e))


def sustituir_variable_eliminada(formula: str, nombre: str, ultimo_valor: Decimal) -> str:
    """Reemplaza cada aparición de `nombre` como variable (ast.Name) por
    su último valor resuelto, reconstruyendo la expresión desde el AST
    en vez de un replace() de texto — evita romper coincidencias
    parciales como 'ancho' dentro de 'ancho_muro' (ver §4.7 y §4.8)."""
    arbol = ast.parse(formula, mode="eval")
    arbol_nuevo = _SustitutorNombre(nombre, ultimo_valor).visit(arbol)
    return ast.unparse(arbol_nuevo)


class _SustitutorNombre(ast.NodeTransformer):
    def __init__(self, nombre: str, valor: Decimal):
        self.nombre = nombre
        self.valor = valor

    def visit_Name(self, nodo):
        if nodo.id == self.nombre:
            return ast.copy_location(ast.Constant(value=float(self.valor)), nodo)
        return nodo
```

> Nota: el fragmento anterior es una base ilustrativa, no código listo para producción. Falta añadir la lógica de "es número vs. es fórmula" (§4.11) y la sugerencia por similitud (§4.6). `pi` se pasa dentro de `FUNCIONES_PERMITIDAS` como valor, no como función — en `simpleeval` esto funciona porque `functions=` acepta cualquier callable u objeto resoluble por nombre; si la versión de `simpleeval` usada no lo permite, moverlo a `names=` combinado con las variables del proyecto en cada llamada.

---

## 6. Puntos de integración en el frontend

El punto de entrada deja de ser la columna Cantidad/Valor — pasa a ser exclusivamente la columna **Fórmula**. Cantidad/Valor se vuelven de solo lectura y se repintan con el resultado que regresa el backend; ya no reciben eventos de edición del usuario.

| Archivo | Método (renombrado/movido) | Columna editable | Hoy | Cambio |
|---|---|---|---|---|
| `mixins/apu.py` | `_on_formula_editada` (antes `_on_concepto_editado` sobre Cant) | 14 (Fórmula, árbol presupuesto) — Cant pasa a solo lectura | `_on_concepto_editado` hacía `float()` sobre Cant y con `except ValueError: return` (línea ~126-127) | Se elimina la edición directa de Cant. El handler escucha la columna Fórmula, envía el texto crudo al backend (§4.10). Si el backend confirma validez, repinta Cant con el valor derivado; si no, revierte Fórmula y muestra el error (§4.7) |
| `widgets/apu.py` | `_on_formula_item_editada` (antes `_on_item_editado` sobre Valor) | 8 (Fórmula, detalle APU) — Valor pasa a solo lectura | mismo patrón (línea ~292-297) | mismo tratamiento, contra `apu_actualizar_valor` |

**Feedback de error:** reusar el patrón que ya existe en `widgets/apu.py` línea ~304 (`QMessageBox.warning` + `self._revertir_item(...)`), pero revirtiendo la celda **Fórmula** (no Cant/Valor, que ya nunca se edita) y con el mensaje sugerido en §4.6 en vez de un genérico "variable no definida".

Como no se persisten fórmulas inválidas (§4.7), este revert es el único mecanismo de recuperación — no hay un segundo intento de "guardar como error" en ningún caso.

---

## 7. Cambios de backend necesarios

1. **`repos/presupuesto.py` y `repos/apu.py`:** agregar escritura del campo `formula` (hoy solo hay `SELECT`). Método nuevo o parámetro opcional en los `UPDATE` existentes de cantidad/valor.
2. **`api.py`:** extender `concepto_actualizar_cantidad` y `apu_actualizar_valor` para aceptar `formula: str | None = None`, guardándolo junto con el valor calculado — misma transacción, mismo evento (`ConceptoActualizado` / `ApuComponenteActualizado`), sin tocar el resto del flujo de recálculo en cascada.
3. **Nuevo repo/servicio para `variables_formula`:** CRUD básico (crear/editar/borrar variable por proyecto, sin campo `valor` — ver §4.2) + método `resolver_variables_proyecto(proyecto_id)` que lea las filas y llame a `resolver_variables()`. El resultado (`{nombre: Decimal}`) se pasa como contexto a `evaluar_formula()` en cada celda.
4. **UI para gestionar variables:** panel o diálogo con 3 columnas (nombre, expresión, descripción) por proyecto — sin columna de valor persistido. Puede vivir como pestaña del ribbon o diálogo accesible desde PROYECTO.

---

## 8. Orden de implementación sugerido

1. **Motor de fórmulas** (`backend/motor/formulas.py`) + pruebas unitarias con `pytest` — aislado, sin tocar UI ni BD. Incluir `Decimal`, whitelist de funciones y los 3 estados desde el diseño de las pruebas. **~2 h**
2. **CRUD de `variables_formula`** (sin campo `valor`) + repo/servicio de resolución en memoria. **~2 h**
3. **Escritura de `formula`** en los `UPDATE` existentes de cantidad/valor (backend), con lógica de decisión número/fórmula/error centralizada ahí (§4.10). **~1 h**
4. **Hook en los 2 handlers de frontend** (§6), enviando texto crudo y mostrando feedback de error con sugerencias. **~2 h**
5. **UI de gestión de variables** (nuevo diálogo/panel). **~2-3 h**
6. **Columna "Fórmula" visible + editable** en ambas tablas — al editarla directamente debe re-evaluar y actualizar la celda numérica asociada, respetando el estado "con error" si aplica. **~1-2 h**

**Total estimado: 10-13 h**

---

## 9. Riesgos / decisiones aún abiertas

- **Scope de variables** (§4.9): ¿solo proyecto o también presupuesto/APU/concepto? Definir arquitectura ahora aunque v1 solo implemente nivel proyecto.
- **Referencias cruzadas:** ¿las variables podrán referenciar datos del presupuesto (ej. `= cantidad_concepto_X`) o son siempre "sueltas" tipo calculadora (áreas, factores, medidas)? El schema actual no tiene columna para eso — si se quiere, es una capa adicional (por id de nodo o alias).
- **Recalculo en cascada:** confirmado para v1 — re-evaluar todo el proyecto al tocar una variable (§4.4), sin índice inverso.

---

## 10. Checklist resumen antes de codificar

- [ ] Confirmar que Cantidad/Valor son **siempre** de solo lectura — el usuario nunca las edita, solo edita Fórmula
- [ ] Confirmar que un número simple también se escribe en la columna Fórmula (no hay "modo manual" separado)
- [ ] Confirmar que no se persisten fórmulas inválidas — se valida al guardar y se revierte si falla, sin estado "con error" en BD
- [ ] Confirmar que `variables_formula` no tendrá columna `valor` persistida
- [ ] Confirmar uso de `Decimal` en todo el motor vía `EvalDecimal._eval_constant` (§4.3/§5) — no mezclar `float` salvo dentro de las funciones trascendentales envueltas
- [ ] Confirmar whitelist de funciones (§4.5) con envoltura Decimal↔float para sqrt/sin/cos/tan
- [ ] Confirmar que al eliminar una variable se advierte y se sustituye su último valor en las fórmulas que la usan, vía AST (§4.7) — no se dejan fórmulas sin evaluar
- [ ] Confirmar que la decisión número/fórmula/error vive en el backend, no en el frontend
- [ ] Decidir scope de variables (solo proyecto vs. multinivel) antes de fijar el schema definitivo de `variables_formula`
