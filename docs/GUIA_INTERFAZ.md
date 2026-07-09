# Especificación de arquitectura de la interfaz (PySide6)

Este documento define los principios, restricciones, decisiones, patrones y
convenciones de la interfaz gráfica de Open APU Studio. Su propósito es que
cualquier persona pueda desarrollar un módulo nuevo sin estudiar el código
existente.

> **Nota sobre longevidad:** Este documento describe *por qué* la UI está
> diseñada como está, no solo *qué archivos* la implementan. Las secciones
> 1-11 (principios, restricciones, decisiones, patrones, evolución) deberían
> seguir siendo válidas aunque se reescriba el 40% del código. La sección 16
> (Anexo) contiene referencias volátiles a la implementación actual.

---

## Índice

1. [Principios de diseño](#1-principios-de-diseño)
2. [Restricciones de arquitectura](#2-restricciones-de-arquitectura)
3. [Vista de dependencias](#3-vista-de-dependencias)
4. [Árbol de decisión](#4-árbol-de-decisión)
5. [Decisiones de diseño registradas](#5-decisiones-de-diseño-registradas)
6. [Arquitectura](#6-arquitectura)
7. [Patrones](#7-patrones)
8. [Convenciones](#8-convenciones)
9. [Antipatrones](#9-antipatrones)
10. [Deudas técnicas conocidas](#10-deudas-técnicas-conocidas)
11. [Evolución de la arquitectura](#11-evolución-de-la-arquitectura)
12. [Guía: Añadir un módulo nuevo](#12-guía-añadir-un-módulo-nuevo)
13. [Checklist pre-merge](#13-checklist-pre-merge)
14. [Pruebas](#14-pruebas)
15. [Mantenimiento](#15-mantenimiento)
16. [Anexo: Referencias a la implementación actual](#16-anexo-referencias-a-la-implementación-actual)

> **Orden de lectura recomendado:**
> 1. **Si solo vas a leer una cosa:** árbol de decisión (sección 4) + checklist pre-merge (sección 13) — cubren el 80% de los casos.
> 2. **Si vas a crear un módulo nuevo:** añade las secciones 7 (patrones) y 12 (guía).
> 3. **Si vas a modificar uno existente:** añade la sección 15 (mantenimiento).
> 4. **Si ves algo que no entiendes o te parece "incorrecto":** consulta primero la sección 5 (decisiones registradas) — probablemente ya se discutió.

---

# 1. Principios de diseño

Estos principios guían las decisiones de implementación. Cuando un caso nuevo
no encaja exactamente en ningún patrón, la respuesta correcta es la que
respete estos principios.

| # | Principio | Significado |
|---|-----------|-------------|
| 1 | **Una herramienta existe en un solo lugar.** | No duplicar funcionalidad. Si ya existe un "Rastrear insumo" en el menú contextual, no crear otro botón que haga lo mismo. |
| 2 | **Las acciones frecuentes requieren el menor número de clics.** | Lo que se usa cada 5 minutos debe estar a un clic de distancia. Lo que se usa una vez al mes puede estar en un submenú. |
| 3 | **El usuario nunca pierde el contexto.** | Al abrir un APU desde el árbol, la pestaña se agrega al lado, no reemplaza la vista actual. Scroll y selección se preservan en recargas. |
| 4 | **Ventanas modales solo cuando es imprescindible.** | Una ventana modal bloquea al usuario. Solo se usa para: (a) confirmaciones destructivas, (b) configuraciones que no tienen sentido fuera del diálogo. |
| 5 | **La información editable se muestra en tablas.** | Las tablas permiten ver contexto, editar inline, filtrar, ordenar y copiar. Los formularios solo se usan cuando la edición tabular no es práctica (muchos campos por ítem, relaciones complejas). |
| 6 | **Los cambios se reflejan automáticamente.** | Una edición en cualquier parte del programa debe propagarse a todas las vistas abiertas sin que el usuario pida "refrescar". Esto se logra vía EventBus, no vía llamadas directas entre widgets. |
| 7 | **La UI no sabe qué es SQL.** | La frontera entre UI y datos es la clase `Api`. La UI pide en términos de dominio ("dame el árbol del presupuesto") y recibe Python estándar. |
| 8 | **Consistencia sobre originalidad.** | Un diálogo que se ve diferente a los demás es un bug de diseño, no una mejora estética. |

---

# 2. Restricciones de arquitectura

Estas son **restricciones duras** (hard limits). Violarlas requiere revertir
antes del merge. No se negocian por conveniencia.

| # | Restricción | Consecuencia si se incumple |
|---|-------------|-----------------------------|
| 1 | El SQL solo vive en `backend/database/repos/`. | Acoplamiento UI–BD: un cambio de esquema rompe la UI sin que el compilador avise. |
| 2 | `Api` es la única fachada entre UI y backend. | Saltar `Api` pierde validación, eventos y transacciones. |
| 3 | La sincronización de estado compartido entre widgets independientes se realiza vía `EventBus`. | Sin `EventBus`, cambiar un widget obliga a cambiar el otro. Las señales Qt padre–hijo están permitidas para interacción local (ej: `QDialog.accepted`). |
| 4 | Los eventos se emiten post-commit, nunca pre-commit. | Un widget leería datos que pueden no persistirse. |
| 5 | Las transacciones las abre el servicio, no el repositorio. | Transacciones anidadas o commits parciales. |
| 6 | No hay dos fuentes de verdad para el mismo estado. | El usuario ve un valor distinto al persistido. |
| 7 | La UI no ejecuta `conn.execute()` ni importa `repos/`. | Corolario de las restricciones 1 y 2. |
| 8 | Cada widget expone `conectar_eventos()` / `desconectar_eventos()`. | Sin ciclo de vida explícito, los widgets quedan zombis y el primer evento post-cierre crashea. |

---

# 3. Vista de dependencias

Gráfico de importaciones. Una flecha significa "puede importar". Lo que no
está listado está prohibido.

```
frontend/ventana/widgets/    (dominio)
                               →  frontend/ventana/api.py           ✓
                               →  frontend/ventana/widgets/base.py  ✓ (heredar)
                               →  backend/database/*                ✗
                               →  otro widget de dominio/           ✗
                               →  widget reutilizable/              ✓

frontend/ventana/handlers/*    →  frontend/ventana/api.py           ✓
                               →  backend/database/*                ✗

frontend/ventana/paneles.py   →  frontend/ventana/widgets/*         ✓ (builders)
                               →  frontend/ventana/api.py           ✓
                               →  backend/database/*                ✗

frontend/ventana/api.py        →  backend/database/services/*       ✓
                               →  backend/database/db.py            ✓ (solo conn)
                               →  backend/database/repos/*          ✗

backend/database/services/*    →  backend/database/repos/*          ✓
                               →  backend/database/db.py            ✓
                               →  frontend/*                        ✗
```

**Reglas derivadas:**
- **Widgets de dominio** (los que modelan entidades del negocio: presupuesto, insumos, APU) no se importan entre sí. Se comunican solo por señal Qt o EventBus.
- **Widgets reutilizables de UI** (SelectorUnidad, FormularioMaterial, campos autocompletables) pueden importarse desde widgets de dominio y desde otros reutilizables. Son componentes de presentación sin conocimiento del dominio.
- `Api` es la frontera del dominio: desde `frontend/` solo se importan `Api`, `EventBus` y tipos de eventos.
- Ningún archivo fuera de `backend/database/repos/` puede contener SQL.

---

# 4. Árbol de decisión

Usa este árbol para determinar qué clase base usar y dónde poner el código.

```
¿Qué necesito crear?
        │
        ▼
¿Bloquea al usuario hasta que se cierra?
        │
  ├── Sí → QDialog (modal)
  │       ¿Hay header+footer estándar?
  │        ├── Sí → DialogoBase (cuando exista — ver sección 10.1)
  │        └── No → QDialog directo
  │
  └── No (es una pestaña o panel)
        │
        ▼
¿Muestra datos en filas y columnas?
        │
  ├── Sí → ¿Los datos son editables?
  │        ├── Sí → TreeTableWidget (subclase)
  │        └── No → TreeTableWidget (flat, editable=False)
  │
  └── No
        │
        ▼
¿Es un formulario con campos de entrada?
        │
  ├── Sí → QWidget + QVBoxLayout
  │       (nunca QDialog para paneles no modales)
  │
  └── No
        │
        ▼
¿Es un widget auxiliar reutilizable (botón, tarjeta, etc.)?
        │
  ├── Sí → widgets/nombre.py, clase separada
  │
  └── No → builder inline en el mixin (solo si < ~30 líneas
            y sin estado propio — ver sección 8.4)
```

---

# 5. Decisiones de diseño registradas

Cada decisión aquí documentada responde a una pregunta que alguien podría
intentar "corregir" sin conocer el contexto. Léelas antes de modificar
la arquitectura.

### 5.1 ¿Por qué los builders viven en `PanelesMixin`?

No hay una razón técnica para que estén en un mixin en lugar de una clase
separada. Es una decisión de organización: todos los builders están en el
mismo archivo (`paneles.py`) porque:

- Cada builder es pequeño (~10 líneas).
- Todos siguen el mismo patrón: verificar `self._db` → crear widget →
  poblar → conectar eventos → devolver.
- Tenerlos juntos hace evidente qué módulos existen y cuál es su punto
  de entrada.

**Cuándo mover un builder a otro lado:** Si un builder contiene lógica que no es
puramente de ensamblaje (validación, transformación de datos, estado), debe
refactorizarse: la lógica va al widget o a la API; el builder sigue siendo una
línea. Como orientación, un builder inline normalmente no supera ~30 líneas
(ver sección 8.4).

> Ver sección 11.1 para la distinción entre la solución actual (builders
> manuales en PanelesMixin) y el target futuro (registro automático).

### 5.2 ¿Por qué `Api` devuelve estructuras de datos simples y no objetos de dominio?

- Los objetos de dominio crean acoplamiento: cambiar el modelo de datos
  obliga a cambiar la UI.
- Las estructuras nativas (`dict`, `list`, `int`, `float`, `str`, `None`)
  son serializables, debuggeables y no requieren importar clases del backend.
- La UI solo consume datos; no necesita comportamiento de dominio.

**Excepción:** Si un objeto tiene comportamiento relevante para la UI
(formateo, validación visual), se puede crear un "view model" plano en
`frontend/`, pero nunca importar modelos del backend.

### 5.3 ¿Por qué el EventBus emite post-commit?

Porque si la emisión fuera pre-commit, un widget que reacciona al evento
leería datos que aún no están en la BD, o peor, que nunca estarán (si el
commit falla). La regla es: **solo se notifica lo que ya es verdad.**

### 5.4 ¿Por qué herencia múltiple de mixins y no composición?

Porque los mixins necesitan acceso directo a `self` (VentanaPrincipal)
para modificar el toolbar, las pestañas, la statusbar, etc. Con
composición habría que pasar referencias explícitas o usar un bus de
señales más complejo. La herencia múltiple es el mecanismo más simple
que cumple el requisito.

**Costo:** Dos mixins no pueden definir el mismo método (excepto si
uno sobreescribe al otro por orden de herencia). Por eso cada mixin
tiene un prefijo de método único (`_build_*`, `_on_*`).
---

# 6. Arquitectura

## 6.1 Estructura general

```
VentanaPrincipal (QMainWindow)
├─ Tab Bar (PROYECTO | INICIO | INFORMES | VISTA | PRINCIPAL | HERRAMIENTAS)
├─ Toolbar (QStackedWidget, una página por tab)
├─ Search Bar (QLineEdit)
├─ QSplitter
│  ├─ Sidebar (QTreeWidget — explorador fijo)
│  └─ QTabWidget (contenido central — pestañas dinámicas)
└─ Status Bar
```

**Piezas fijas:** Tab bar, Toolbar, Search bar, Sidebar, Status bar.
**Piezas dinámicas:** QTabWidget (presupuesto, insumos, APU, rastreo, explosión, diagnóstico).

## 6.2 Sistema de navegación

| Mecanismo | Comportamiento |
|---|---|
| Clic en tab de toolbar | Cambia el contenido del QStackedWidget. No afecta el contenido central. |
| Clic simple en sidebar | Abre pestaña temporal (se reemplaza al siguiente clic). |
| Doble clic en sidebar | Abre pestaña permanente. |
| Ctrl+Tab / Ctrl+Shift+Tab | Cicla entre pestañas abiertas. |
| Búsqueda | Filtra filas del widget activo. |

## 6.3 Capas de comunicación

```
┌────────────────────────────────────────────────────┐
│  UI (PySide6)                                      │
│  Widgets · Mixins · Diálogos                       │
│  No importa backend/database/repos                 │
│  No ejecuta SQL                                    │
└────────────────┬───────────────────────────────────┘
                 │  Api (fachada)
                 │  Recibe conn, devuelve dicts/listas
                 ▼
┌────────────────────────────────────────────────────┐
│  Servicios (DataService, EventBus)                  │
│  Coordinan: validar → transacción → repo → evento  │
│  Sin SQL directo                                   │
└────────────────┬───────────────────────────────────┘
                 │  Repositorios
                 │  Solo SQL
                 ▼
┌────────────────────────────────────────────────────┐
│  SQLite (.presup)                                  │
└────────────────────────────────────────────────────┘
```

## 6.4 Flujo de eventos

```
Usuario edita celda
  ↓
Qt signal (itemChanged)
  ↓
Handler en mixin (ApuMixin, etc.)
  ↓
Api.metodo_de_dominio()
  ↓
DataService.actualizar() → SQL → commit
  ↓
EventBus.emit(Evento)        ← POST-COMMIT
  ↓
Widgets suscritos se actualizan solos
```

**Reglas del EventBus:**
- Emisión post-commit.
- Cada handler en try/except.
- Widgets destruidos se desuscriben automáticamente.
- Handlers no emiten otros eventos.

## 6.5 Responsabilidades por capa

| Capa | Clase / Archivo | Responsabilidad | NO debe |
|---|---|---|---|
| **Widget** | `frontend/ventana/widgets/*.py` | Mostrar datos, capturar entrada, delegar escritura a `Api`. | Hacer validación de negocio, tocar la BD, conocer otros widgets. |
| **Mixin** | `frontend/ventana/handlers/*.py`, `frontend/ventana/apu/*.py` | Coordinar la UI: construir pestañas, conectar señales Qt, orquestar handlers de eventos de UI. | Contener SQL, importar repositorios, llamar a la BD directamente. |
| **Api** | `frontend/ventana/api.py` | Traducir peticiones de la UI a llamadas a servicios; devolver datos en formato simple. | Hacer validación de negocio, manejar transacciones, emitir eventos. |
| **Servicio** | `backend/database/services/*.py` | Validar reglas de negocio, abrir transacciones, coordinar repos, emitir eventos post-commit. | Contener SQL, conocer a la UI. |
| **Repositorio** | `backend/database/repos/*.py` | Ejecutar SQL, devolver `dict`/`list`. | Hacer validación de negocio, emitir eventos, manejar transacciones. |

**Regla de oro:** Si no sabes en qué capa poner una función, pregúntate:
"¿Esta función existiría si cambiáramos de base de datos?" → Si sí, es lógica
de negocio y va en un servicio. Si no, va en un repositorio.

## 6.6 Flujo de lectura

A diferencia de la escritura (sección 6.4), la lectura no pasa por el EventBus
porque no hay estado que sincronizar.

```
Usuario abre módulo (clic en sidebar)
  ↓
PanelesMixin._build_mi_modulo()
  ↓
Api.mis_datos()
  ↓
Service (opcional, si hay validación o transformación)
  ↓
Repo.obtener_datos() → SQL SELECT
  ↓
Api devuelve datos como list[dict]
  ↓
Widget.poblar(datos) ← llena la tabla
  ↓
Widget.conectar_eventos(bus) ← desde aquí, las escrituras
                                 externas llegan vía EventBus
```

**Reglas:**
- El builder siempre llama a `poblar()` antes que a `conectar_eventos()`.
- Si la lectura requiere lógica de negocio (calcular totales, aplicar filtros
  de autorización), esa lógica va en un servicio, no en `Api`.
- Las lecturas repetitivas (refrescar cada N segundos) deben evitarse: el
  EventBus debe ser el mecanismo que notifique cuándo los datos cambiaron,
  no un timer de sondeo.

---

# 7. Patrones

> Los ejemplos completos en Python están en `docs/examples/PATRONES.md`.
> Aquí solo se muestra pseudocódigo suficiente para entender la estructura.

## 7.1 Patrón: Tabla nueva

Toda vista que muestre datos editables en formato tabular debe heredar
de `TreeTableWidget`.

```
1. Crear clase en widgets/ heredando TreeTableWidget
2. Definir COLUMNAS (lista de strings)
3. Definir COLUMNAS_CATALOGO (lista de ColumnaDef)
4. Definir _HEADER_KEY y _CATALOGO_KEY
5. Definir EDITABLE (frozenset de índices editables)
6. Implementar __init__ → super().__init__(...), set_column_modes, etc.
7. Implementar poblar(self, data) → clear() + add_row() por ítem
8. Implementar conectar_eventos(self, event_bus, api)
9. Implementar desconectar_eventos(self)
10. Registrar builder en PanelesMixin
11. Registrar entrada en sidebar
```

Ver ejemplo completo: `docs/examples/PATRONES.md#71-tabla-nueva`

## 7.2 Patrón: Diálogo

```
QVBoxLayout
├─ Header (48px, título centrado)
├─ Separador
├─ Contenido (márgenes 16px)
├─ Stretch
├─ Separador
└─ Footer (botones Aceptar + Cancelar)
```

Pasos e implementación: ver sección [10.1](#101-dialogobase)
para entender por qué no hay una clase base aún, y después seguir la estructura
manual de `DialogoAjustes` o `DialogoExplosion` como referencia.

## 7.3 Patrón: Builder en PanelesMixin

```python
def _build_mi_modulo(self):
    from frontend.ventana.widgets.mi_widget import MiWidget
    if not self._db:
        return self._build_placeholder("📦 Mi módulo")
    w = MiWidget()
    if self._api:
        datos = self._api.mis_datos()
        w.poblar(datos)
    w.conectar_eventos(self._event_bus, self._api)
    return w
```

Luego registrar en `_open_sidebar_tab`:
```python
if title == "📦 Mi módulo":
    content = self._build_mi_modulo()
```

Ver ejemplo completo con importaciones: `docs/examples/PATRONES.md#73-builder-en-panelesmixin`

## 7.4 Patrón: Suscripción al EventBus

```python
def conectar_eventos(self, event_bus, api):
    self._api = api
    self._event_bus = event_bus
    event_bus.suscribir(InsumoActualizado, self._on_insumo_actualizado)

def desconectar_eventos(self):
    bus = getattr(self, '_event_bus', None)
    if bus is None:
        return
    bus.desuscribir(InsumoActualizado, self._on_insumo_actualizado)
    self._event_bus = None
```

Ver ejemplo completo con múltiples eventos: `docs/examples/PATRONES.md#74-suscripción-al-eventbus`

## 7.5 Patrón: Actualización reactiva

Cuando un mixin ejecuta una escritura, **no debe tocar ningún widget**
después de llamar a la API. La API emite eventos, y los widgets suscritos
se actualizan solos.

```
Mixin escribe → Api → DataService → EventBus → Widget se refresca
```

El mixin no llama a `_refrescar_tab_activa()` ni a `widget.poblar()`.

**Excepción:** Si el evento se emite dentro de la misma señal `itemChanged`
que originó la edición, el refresco debe diferirse con `QTimer.singleShot(0, ...)`
para evitar que Qt procese el `clear()` mientras aún está en el handler
de `itemChanged`.

## 7.6 Patrón: Ciclo de vida de un widget

```
crear instancia
  ↓
poblar(datos)            ← cargar datos iniciales
  ↓
conectar_eventos(bus)    ← suscribirse al EventBus
  ↓
┌───────────────────┐
│ USUARIO INTERACTÚA │  ← edita, filtra, ordena, navega
│   Y RECIBE EVENTOS │  ← EventBus notifica cambios externos
└───────────────────┘
  ↓
desconectar_eventos()    ← desuscribirse del EventBus
  ↓
destruir                 ← Qt elimina el widget, Python libera memoria
```

**Reglas:**
- `poblar()` siempre antes que `conectar_eventos()`. Si se conectan eventos
  antes de poblar, un evento puede llegar cuando el widget no tiene datos.
- `desconectar_eventos()` es obligatorio. Sin él, el callback retiene una
  referencia al widget Python, impidiendo que el GC lo libere. El próximo
  evento causa `RuntimeError: wrapped C/C++ object has been deleted`.
- Entre `poblar()` y `conectar_eventos()` el widget no debe emitir ni
  escribir datos. Es un estado transitorio de inicialización.
- El builder de `PanelesMixin` garantiza este orden.

---

# 8. Convenciones

> Estas reglas son vinculantes. Si una pull request las incumple, debe
> corregirse antes de mergear.

## 8.1 Tablas

| Regla | Razón |
|---|---|
| Toda tabla hereda de `TreeTableWidget`. | Garantiza edición, filtrado, clipboard, persistencia. |
| `COLUMNAS_CATALOGO` obligatorio. | Sin catálogo no hay personalización de columnas. |
| `_HEADER_KEY` obligatorio. | Sin key el usuario pierde su configuración al cerrar. |
| `editable_cols_fn` para editabilidad por tipo de fila. | No inferir editabilidad del texto visible (frágil). |
| `_search_cols` siempre definido. | Sin search cols, la búsqueda busca en todas las columnas. |

## 8.2 Diálogos

| Regla | Razón |
|---|---|
| Header 48px con título centrado. | Consistencia visual entre todos los diálogos. |
| Footer con Aceptar + Cancelar. | Siempre ambos, Cancelar a la derecha. |
| Márgenes de contenido: 16px. | No valores arbitrarios. |
| Sin SQL directo. | Usar `Api` o `DataService`. |

## 8.3 Builders

| Regla | Razón |
|---|---|---|
| Actualmente toda pestaña se registra con un método `_build_*` en `PanelesMixin`. | Mecanismo actual; el target futuro es registro declarativo (ver sección 11.2). |
| El builder verifica `self._db` primero. | Si no hay proyecto, mostrar placeholder. |
| El builder llama a `poblar()` + `conectar_eventos()`. | Separar construcción de población. |

## 8.4 Widgets

| Regla | Razón |
|---|---|
| Se separa a clase propia si tiene **identidad, estado o ciclo de vida propios**. | No es una regla de líneas, es de responsabilidad. Un widget de 150 líneas con estado propio merece su clase; un builder de 400 líneas que solo organiza controles quizá no. |
| No contiene SQL. | Violaría la separación de capas. |
| No conoce otros widgets. | Comunicación vía EventBus o signals. |
| Implementa `conectar_eventos()` y `desconectar_eventos()`. | Ciclo de vida explícito. Sin esto, el widget puede quedar zombi. |

### Criterio para decidir si un widget merece clase propia

Un widget debe ser una clase separada en `widgets/` cuando cumpla **al menos
uno** de estos criterios:

| Criterio | Pregunta guía |
|---|---|
| **Identidad propia** | ¿Tiene sentido existir fuera del contexto actual? ¿Podría reutilizarse en otra pestaña? |
| **Estado propio** | ¿Mantiene selección, scroll, filtros, ediciones sin confirmar? |
| **Ciclo de vida independiente** | ¿Necesita suscribirse/desuscribirse del EventBus? ¿Tiene `poblar()`, `conectar_eventos()`, `desconectar_eventos()`? |
| **Complejidad de layout** | ¿Tiene más de 3 widgets anidados o lógica de posición condicional? |
| **Testeabilidad** | ¿Necesitarías probar su comportamiento de forma aislada? |

Un builder inline normalmente no supera ~30 líneas; si contiene lógica de negocio o estado, debe refactorizarse a clase propia independientemente de su longitud.

## 8.5 Mixins

| Regla | Razón |
|---|---|
| Un mixin cubre un módulo. | Si mezcla responsabilidades, dividir. |
| No importa otros mixins. | Solo opera sobre `self`. El orden de herencia es el único acoplamiento. |
| Métodos con prefijo `_build_*` o `_on_*`. | `_build_*` crea widgets; `_on_*` maneja eventos. |

## 8.6 API (fachada)

| Regla | Razón |
|---|---|
| UI → Api → Servicio → Repositorio. | La UI nunca salta capas. |
| Api devuelve estructuras de datos simples (`dict`, `list`, `int`, `float`, `str`, `None`). | Nunca objetos de dominio — ver sección 5.2. |
| Api recibe una conexión a la base de datos en el constructor. | La UI no conoce el mecanismo de persistencia; `Api` encapsula el acceso a los servicios, que actualmente utilizan SQLite. |

### Convenciones de nomenclatura para métodos de `Api`

| Prefijo | Uso | Ejemplo |
|---|---|---|
| `obtener_*` | Un solo ítem por identificador. | `obtener_insumo(id)` → `dict` o `None` |
| `listar_*` | Colección completa (con o sin filtros). | `listar_insumos()` → `list[dict]` |
| `buscar_*` | Búsqueda textual o por criterios parciales. | `buscar_insumos(texto)` → `list[dict]` |
| `crear_*` | Insertar un nuevo registro. | `crear_insumo(datos)` → `id` del nuevo registro |
| `actualizar_*` | Modificar un registro existente. | `actualizar_insumo(id, cambios)` → `int` (filas afectadas) |
| `eliminar_*` | Borrar un registro. | `eliminar_insumo(id)` → `bool` |
| `calcular_*` | Operación de solo lectura con lógica. | `calcular_total(id)` → `float` |

**Reglas:**
- Prefijo en infinitivo, no en participio (`listar_*`, no `listado_*`).
- El primer argumento es siempre el id del recurso cuando aplica.
- No mezclar español e inglés en el mismo método.
- Métodos de solo lectura (`obtener_*`, `listar_*`, `buscar_*`, `calcular_*`) no modifican estado. Métodos de escritura (`crear_*`, `actualizar_*`, `eliminar_*`) siempre emiten evento después del commit.

## 8.7 Layout

| Regla | Razón |
|---|---|
| Márgenes: 0 para contenedores, 16px para contenido interno. | Consistencia. |
| Espaciado: valores de la serie 4-8-12-16-24-32 px. | No valores arbitrarios. |
| Iconos: emoji/unicode pintado sobre QPixmap transparente. | Sin dependencias de archivos. |

## 8.8 EventBus

| Regla | Razón |
|---|---|
| Los widgets nunca se actualizan entre sí directamente. | Siempre reaccionan a eventos. |
| `desconectar_eventos()` antes de remover un widget. | Si no, el widget queda zombi y el próximo evento crashea. |
| Usar `_cerrar_tab_widget()` para cerrar pestañas. | Llama a `desconectar_eventos()` recursivamente. |

### Convenciones de nomenclatura para eventos

| Aspecto | Regla | Ejemplo |
|---|---|---|
| Nombre | `{Entidad}{Acción}` en PascalCase español. | `InsumoActualizado`, `ProyectoRecalculado`, `NodoCreado` |
| Payload | `datos` es `dict` con los campos relevantes del registro afectado. | `evento.datos["id"]`, `evento.datos["precio"]` |
| Quién emite | Siempre `DataService` después del commit, nunca desde `Api` o el widget. | `EventBus.emit(InsumoActualizado(datos={...}))` |
| Quién escucha | Cualquier widget suscrito. El emisor no conoce a los suscriptores. | `event_bus.suscribir(InsumoActualizado, widget._on_insumo_actualizado)` |
| Granularidad | Un evento por tipo de cambio, no uno genérico "datos cambiaron". | `InsumoActualizado` ≠ `NodoActualizado` |

**Reglas adicionales:**
- El payload incluye al menos el `id` del registro afectado. Incluir campos modificados es opcional pero recomendado para actualización in-place.
- No emitir eventos para cambios locales (colapsar una fila, cambiar pestaña activa).
- Si dos cambios ocurren en la misma transacción, emitir un solo evento compuesto o eventos separados pero siempre después del commit único.

---

# 9. Antipatrones

Estos son errores que ya ocurrieron en el proyecto o que se quiere prevenir.
Si aparecen en una revisión, deben corregirse.

| # | Antipatrón | Por qué es malo | Alternativa |
|---|---|---|---|
| 1 | **SQL en la UI** (`self._db.conn.execute(...)` en mixins) | Rompe la separación de capas. Una migración de BD puede romper la UI sin que el compilador avise. | `Api.metodo()` o `DataService` |
| 2 | **Acceso directo a repositorios desde mixins** | Salta la validación, los eventos y las transacciones del servicio. | `Api.metodo()` |
| 3 | **Widgets que se actualizan entre sí directamente** (`self._arbol_presupuesto.poblar(...)` desde otro mixin) | Crea acoplamiento. Un cambio en un widget obliga a cambiar el otro. | EventBus — el widget reacciona solo |
| 4 | **Llamar a `_refrescar_tab_activa()` manual** | Ineficiente (refresca todo aunque solo cambió una celda) y rompe el flujo reactivo. | EventBus + actualización in-place |
| 5 | **Widgets inline de cientos de líneas dentro de un builder** | Ilegible, no testeable, no reutilizable. | Clase separada si cumple criterios de la sección 8.4 |
| 6 | **Crear un `EventBus` nuevo en vez de usar el de `self._event_bus`** | Los eventos no se propagan entre buses distintos. | Usar `self._event_bus` (el de VentanaPrincipal) |
| 7 | **No desconectar eventos al cerrar pestaña** | Widget zombi: el objeto Qt se destruye pero Python lo retiene. `RuntimeError: already deleted` en cada evento. | `_cerrar_tab_widget()` o `desconectar_eventos()` explícito |
| 8 | **Importar widgets desde otro módulo de widgets** | Crea dependencias circulares potenciales. | Comunicación via signals hacia arriba, no imports laterales |
| 9 | **Dos fuentes de verdad para el mismo estado** (ej: un precio en la UI y otro en la BD) | Inconsistencias. El usuario ve un valor y al recargar cambia. | El EventBus es la única fuente de notificaciones de cambio |
| 10 | **Crear diálogos con `QMessageBox` para acciones que no son mensajes** (ej: "elige un proyecto") | QMessageBox no permite widgets custom. Lleva a UI pobres. | `QDialog` con contenido propio |
| 11 | **Mezclar lógica de edición de distintas columnas en un solo `if/elif`** (ej: `_on_apu_detalle_editado`) | Difícil de leer, mantener y testear. | Un método por columna, o un diccionario `{col: handler}` |

---

# 10. Deudas técnicas conocidas

Deudas identificadas y aceptadas. No se pagan hoy porque hay prioridades más
altas, pero están documentadas para que no se olviden.

### 10.1 `DialogoBase` ausente

Los 6 diálogos existentes comparten la misma estructura (header 48px + separador +
contenido + separador + footer) pero cada uno la implementa manualmente.

**Solución:** Crear `DialogoBase(QDialog)` que implemente:
- `_build_header(titulo)` — QLabel centrado, 48px
- `_build_sep()` — QFrame HLine
- `_build_footer(btn_ok_text, btn_cancel_text)` — botones + márgenes
- `set_body(widget)` — método público para inyectar contenido

**Cuándo pagarla:** Al crear el séptimo diálogo, o como refactor planificado.

### 10.2 `_conectar_btn` con ~45 branches `if/elif`

**Resuelta.** Reemplazado por `_HANDLERS` dict en `toolbar.py` (ADR-001).
Ver sección 15.6 para el nuevo indicador de alerta.

### 10.3 `_build_placeholder` duplicado en cada builder

Cada builder en `PanelesMixin` comienza con el mismo patrón:
```python
if not self._db:
    return self._build_placeholder("📦 Módulo")
```

Esto no es crítico pero viola el Principio 1 (una herramienta existe en un
solo lugar). Idealmente `_build_placeholder` debería poder aceptar una lista
de módulos y retornar un placeholder genérico, o los builders deberían
registrarse en una config que maneje el placeholder automáticamente.

**Cuándo pagarla:** Cuando se implemente el registro automático de módulos
(sección 11.2).

### 10.4 Iconos emoji/unicode con dependencia de fuentes

Los iconos usan emoji/unicode pintados sobre `QPixmap` transparente. Esto
elimina dependencias de archivos externos, pero depende de la fuente `Segoe UI
Symbol` (Windows). En Linux sin la fuente equivalente, los iconos se ven como
cuadros.

**Solución:** Reemplazar por iconos SVG embebidos como strings (sin archivos
externos) o por una librería como `QtAwesome` que resuelve iconos
independientemente de la plataforma.

**Cuándo pagarla:** Cuando se abra el primer ticket de un usuario en Linux
sin la fuente correcta, o cuando el target Linux se vuelva oficial.

---

# 11. Evolución de la arquitectura

Esta sección documenta qué puede cambiar sin rediseño y qué requiere un
cambio estructural, además de las diferencias entre la implementación actual
y los targets futuros.

## 11.1 Cambios permitidos vs. cambios que requieren rediseño

| Cambio | ¿Permitido? | Notas |
|---|---|---|
| Agregar un widget/tabla nuevo | ✅ Permitido | Seguir el patrón de la sección 7.1 |
| Agregar un método en `Api` | ✅ Permitido | Sin modificar la firma de `Api.__init__` |
| Agregar un tipo de evento al EventBus | ✅ Permitido | Crear subclase de `Evento` en `event_bus.py` |
| Agregar un servicio nuevo | ✅ Permitido | Registrar en `RepositoryRegistry` si usa repos |
| Agregar un botón al toolbar | ✅ Permitido | Agregar entrada en `_HANDLERS` de `toolbar.py` |
| Cambiar el esquema de BD | ⚠️ Ruptura controlada | Se edita `schema.sql`, proyectos viejos incompatibles (ver AGENTS.md) |
| Reemplazar `TreeTableWidget` por otra base | ❌ Requiere rediseño | Afecta todas las tablas. Solo si se demuestra que la base actual no escala. |
| Reemplazar herencia de mixins por composición | ❌ Requiere rediseño | Cambia la estructura de `VentanaPrincipal` y todos los mixins. |
| Agregar una dirección de importación nueva (ej: widgets → repos) | ❌ Requiere rediseño | Viola la vista de dependencias (sección 3). |
| Cambiar el tipo de retorno de `Api` | ⚠️ Ruptura controlada | Afecta todos los widgets que llaman a `Api`. Migración planificada. |

## 11.2 Implementación actual vs. target futuro

| Aspecto | Hoy (MVP/v1.x) | Target futuro |
|---|---|---|
| **Registro de módulos** | Builders manuales en `PanelesMixin`, cada nuevo módulo agrega un método + un `if` en `_open_sidebar_tab` | Config declarativa: `{ "ruta": "📦 Módulo", "widget": "MiWidget", "icono": "📦" }`. El bucle itera la config, crea widgets y conecta eventos sin tocar `paneles.py`. |
| **Toolbar** | `_HANDLERS` dict resuelto (ver 10.2) | — |
| **Diálogos** | Cada diálogo implementa su propio header/footer | `DialogoBase` con `set_body()` (ver 10.1) |
| **Tema de UI** | Archivos `.qss` planos cargados en runtime. Combinación modo × acento manual. | Paleta unificada con variables CSS-like y hot-reload. |
| **Api return type** | `dict`/`list` — sin schema ni validación | View models planos en `frontend/` con validación de tipos y serialización explícita. |
| **Placeholder** | `_build_placeholder` llamado manualmente en cada builder | Placeholder automático para módulos sin proyecto abierto. |

## 11.3 Reglas de evolución

1. **No se refactoriza lo que funciona sin una razón de negocio.** Una deuda
   técnica documentada no es una emergencia.
2. **Un cambio estructural (columna ❌ en la tabla 11.1) requiere ADR antes
   de implementar.** El ADR debe explicar por qué el diseño actual no es
   suficiente y cómo el nuevo diseño evita repetir los mismos problemas.
3. **Los targets futuros (sección 11.2) son aspiracionales.** No hay fecha
   compromiso. Si alguien quiere implementar uno, debe hacerlo sin romper
   la API actual y sin obligar a migrar todos los módulos existentes.
4. **La deuda técnica se paga cuando duele, no cuando se identifica.**
    Identificarla y documentarla ya es suficiente.

## 11.4 Formato mínimo de ADR

Todo cambio estructural (columna ❌ en la tabla 11.1) requiere un ADR antes
de implementar. El ADR se escribe en `docs/adr/` como archivo Markdown.

```
# ADR-XXX: Título

**Fecha:** YYYY-MM-DD

## Problema
¿Qué necesidad concreta motiva el cambio? ¿Qué es lo que no se puede hacer
con la arquitectura actual?

## Contexto
¿Por qué la arquitectura vigente no es suficiente? ¿Qué ha cambiado (requisitos,
escala, tecnología) que invalida la decisión original?

## Alternativas consideradas
- Alternativa A: qué implica
- Alternativa B: qué implica
- Alternativa C: qué implica

## Decisión
Opción elegida y razón principal.

## Impacto
- Módulos que hay que modificar.
- ¿Hay migración de datos?
- ¿Qué deudas técnicas introduce esta decisión?

## Plan de migración
Pasos concretos para pasar del estado actual al nuevo, en orden.
Incluir qué se rompe durante la transición y cómo se mitiga.
```

Los ADR se numeran correlativamente (ADR-001, ADR-002...) y se conservan
indefinidamente aunque la decisión quede obsoleta. Un ADR obsoleto no se
borra: se marca con `**Estado:** obsoleto` y se referencia desde el ADR
que lo reemplaza.

---

# 12. Guía: Añadir un módulo nuevo

Flujo completo para agregar un módulo (ej: "Programa de suministros").

```
1. Usar el árbol de decisión (sección 4) para elegir clase base
   ↓
2. Crear widget en frontend/ventana/widgets/
   ↓
3. Implementar poblar()
   ↓
4. Implementar conectar_eventos() + desconectar_eventos()
   ↓
5. Agregar método builder en PanelesMixin
   ↓
6. Registrar entrada en _build_sidebar()
   ↓
7. Agregar caso en _open_sidebar_tab()
   ↓
8. (Opcional) Agregar botón en toolbar
   ↓
9. Verificar checklist
```

### Paso 1: Elegir clase base

Ver [árbol de decisión](#4-árbol-de-decisión).

### Paso 2: Crear widget

`frontend/ventana/widgets/mi_modulo.py` — heredar de la clase elegida.
Seguir el patrón de la [sección 7.1](#71-patrón-tabla-nueva) si es tabla,
o [7.2](#72-patrón-diálogo) si es diálogo.

### Paso 3: Implementar poblar()

```python
def poblar(self, datos):
    self.clear()
    for d in datos:
        row = self.add_row([d["campo1"], d["campo2"], ...])
        row.setData(0, Qt.ItemDataRole.UserRole, d["id"])
```

### Paso 4: EventBus

```python
def conectar_eventos(self, event_bus, api):
    self._api = api
    self._event_bus = event_bus
    # suscribir solo a eventos relevantes

def desconectar_eventos(self):
    bus = getattr(self, '_event_bus', None)
    if bus:
        bus.desuscribir(MiEvento, self._on_mi_evento)
        self._event_bus = None
```

Ver ejemplo completo en `docs/examples/PATRONES.md#74-suscripción-al-eventbus`.

### Paso 5: Builder

```python
def _build_mi_modulo(self):
    from frontend.ventana.widgets.mi_modulo import MiWidget
    if not self._db:
        return self._build_placeholder("📦 Mi módulo")
    w = MiWidget()
    if self._api:
        datos = self._api.mis_datos()
        w.poblar(datos)
    w.conectar_eventos(self._event_bus, self._api)
    return w
```

### Paso 6: Sidebar y paso 7: Router

```python
# en _build_sidebar:
secciones = [
    ("📁 Mi sección", ["📦 Mi módulo"]),
    ...
]

# en _open_sidebar_tab:
if title == "📦 Mi módulo":
    content = self._build_mi_modulo()
```

### Paso 8: Toolbar (opcional)

Agregar la entrada en `_HANDLERS` de `toolbar.py` (dict que mapea tooltip → nombre del handler).
No requiere tocar `_conectar_btn` — el bucle usa `getattr(self, handler_name)` automáticamente.

> ⚠️ **Nota de escalabilidad:** Añadir un módulo hoy requiere editar 4
> archivos (widget, builder, sidebar, router). Con 35 módulos, el costo de
> mantenimiento crece linealmente y cada nuevo punto de registro es una
> oportunidad de inconsistencia. La sección 11.2 describe el target futuro
> (registro declarativo) que eliminará este problema.
>
> El registro de botones de toolbar se hace agregando una entrada en `_HANDLERS`
> de `toolbar.py` (ver sección 8.8 para convenciones de eventos, y la
> sección 15.6 para señales de alerta sobre el tamaño del dict).

---

# 13. Checklist pre-merge

## Arquitectura

- [ ] Hereda de una clase base (`TreeTableWidget`, `QDialog`, o `QWidget` según el árbol de decisión).
- [ ] No contiene SQL directo.
- [ ] Usa `Api` para obtener/escribir datos.
- [ ] Usa `EventBus` para actualizaciones reactivas (si el módulo escribe datos).
- [ ] No llama a otros widgets directamente (usa signals o EventBus).
- [ ] No crea un `EventBus` nuevo.

## UI

- [ ] Sigue el layout estándar (márgenes 16px para contenido, header 48px si es diálogo).
- [ ] Márgenes y espaciados usan valores de la escala (4-8-12-16-24-32).
- [ ] Iconos usan emoji/unicode pintado (no archivos externos).
- [ ] Atajos de teclado definidos si aplica (al menos Ctrl+C para copiar).

## Persistencia de tabla

- [ ] `_HEADER_KEY` definido.
- [ ] `_CATALOGO_KEY` definido (si tiene columnas personalizables).
- [ ] `COLUMNAS_CATALOGO` definido.
- [ ] `_restore_header_state()` llamado en `__init__`.

## Ciclo de vida

- [ ] `conectar_eventos()` implementado.
- [ ] `desconectar_eventos()` implementado.
- [ ] Las pestañas se cierran con `_cerrar_tab_widget()` (que llama a `desconectar_eventos()`).

## Registro

- [ ] Builder en `PanelesMixin`.
- [ ] Ruta en `_open_sidebar_tab`.
- [ ] Entrada en `_build_sidebar()` (si aplica).
- [ ] Entrada agregada en `_HANDLERS` de `toolbar.py` (si aplica).

---

# 14. Pruebas

> ⚠️ Esta sección es aspiracional. No hay suite de tests automatizados hoy.
> Define qué *debería* probarse y cómo preparar el código para ello.

## 14.1 Qué probar por capa

| Capa | Qué probar | Cómo |
|---|---|---|
| **Widget** (clase en `widgets/`) | `poblar()` con datos válidos y vacíos; `conectar_eventos()` / `desconectar_eventos()` sin crashear; edición inline si es editable. | Unitario: instanciar sin `QApplication` completa no es posible, pero se puede probar la lógica de `poblar()` con un `QTableWidget` padre simulado. |
| **Builder** (método en `PanelesMixin`) | No se testea unitariamente. Si tiene lógica condicional que lo merezca, extraerla a un método aparte. | Cubierto por integración del módulo. |
| **Api** (fachada) | Cada método con datos válidos, borde y nulos. | Unitario con `conn` SQLite en `:memory:`. Poblado mínimo de esquema con `schema.sql`. |
| **Servicio** (`DataService`) | Validación, transacciones, emisión de eventos. | Unitario con repositorios mockeados o con `:memory:`. Verificar que el evento se emite post-commit. |
| **Repositorio** | Cada consulta SQL con datos reales. | Unitario con `:memory:` y datos de fixture. Verificar resultados como dicts. |
| **Mixins** (`handlers/*`, `apu/*`) | Flujo completo: UI → Api → DB → evento → Widget se actualiza. | Integración. No mockear capas internas; usar `:memory:` real. |
| **Importación OPUS** | Archivos `.dbf` reales de muestra. | Integración con archivos conocidos. Verificar que el volcado SQL coincide con valores esperados. |

## 14.2 Estrategia recomendada

1. **Comenzar por repositorios.** Son los más fáciles de aislar (`:memory:`).
2. **Después Api.** Como fachada delgada, validar que cada método retorna lo esperado.
3. **Después servicios.** Requieren mockear repos o usar `:memory:` con datos.
4. **Por último widgets.** Requieren infraestructura Qt (QApplication, signals).

No escribir tests para builders, layouts o código de presentación puro. El costo de mantenerlos supera el beneficio.

## 14.3 Lo que no se automatiza

- Compilación LaTeX de PDFs — verificación manual.
- Comportamiento visual (colores, fuentes, espaciados) — inspección visual.
- Importación de archivos OPUS reales — integración manual contra `CASA EG/`.

---

# 15. Mantenimiento

Esta sección complementa la guía de creación (sección 12) con criterios para
modificar código existente.

## 15.1 Cuándo refactorizar

No todo lo que se puede mejorar debe mejorarse hoy. Usar esta tabla:

| Situación | Acción |
|---|---|
| El cambio requerido toca 1 archivo y < 30 líneas. | Hacer el cambio directo. |
| El cambio toca 2-3 archivos y > 50 líneas. | Evaluar si revela un diseño mejorable. Si no, hacer el cambio directo y documentar la deuda. |
| El cambio requiere modificar 4+ archivos para una funcionalidad local. | Señal de acoplamiento excesivo. Refactorizar antes o documentar como deuda técnica. |
| Se detecta una violación de las restricciones de la sección 2. | Corregir inmediatamente, aunque el cambio sea grande. |
| Un módulo duplica lógica que existe en otro. | Extraer a servicio compartido o clase base. No copiar + pegar. |
| Un widget supera 300 líneas y no es una tabla. | Evaluar si merece dividirse (criterios en 8.4). |
| Un método `_on_*` supera 40 líneas. | Extraer la lógica de negocio a un método privado; el handler solo orquesta. |

## 15.2 Cuándo dejar deuda técnica

La deuda técnica es aceptable cuando:

1. **Es temporal.** Hay un plan (aunque sea borroso) para pagarla.
2. **Está documentada.** Agregar entrada en la sección 10.
3. **Está aislada.** No obliga a otros módulos a adoptar la misma deuda.
4. **No viola restricciones duras.** Las restricciones de la sección 2 nunca se negocian.

## 15.3 Cuándo dividir un archivo

| Criterio | Ejemplo |
|---|---|
| Una clase supera 500 líneas. | `VentanaPrincipal` con mixins ya está resuelto. Un widget de 600 líneas probablemente mezcla responsabilidades. |
| Un archivo mezcla widgets y lógica de negocio. | Extraer la lógica a un servicio. |
| Un archivo tiene más de 3 razones para cambiar. | Aplica el principio de responsabilidad única. |
| Dos editores modificarían el mismo archivo al mismo tiempo por razones distintas. | Señal de que el archivo hace demasiadas cosas. |

## 15.4 Cuándo extraer un servicio

Un método merece vivir en `DataService` (o un nuevo servicio) cuando:

- Contiene validación que no es solo de tipos (formatos, reglas de negocio).
- Coordina múltiples repositorios en una sola operación.
- Necesita una transacción que abarque varios repos.
- La misma lógica se necesita desde dos puntos distintos (Api y otra parte).

Un método debe quedarse en `Api` (fachada simple) cuando:

- Solo delega a un repositorio sin validación adicional.
- Es estrictamente una consulta de solo lectura sin reglas de negocio.
- Su cuerpo es `< 5 líneas` y no tiene condicionales.

## 15.5 Cuándo crear un nuevo evento vs. no hacerlo

| Crear evento | No crear evento |
|---|---|
| El cambio afecta el estado mostrado por ≥ 2 widgets distintos. | El cambio es interno a un solo widget (ej: colapsar una fila). |
| El cambio debe propagarse a widgets que no existen aún. | La reacción al cambio es local (ej: mostrar un tooltip de confirmación). |
| El evento transporta datos que varios consumidores necesitan. | El dato solo lo necesita quien originó el cambio. |

## 15.6 Señales de alerta temprana

Estos síntomas indican que el diseño está derivando y conviene revisar la arquitectura:

- El EventBus empieza a tener > 20 tipos de evento distintos.
- Un método en `Api` supera 30 líneas.
- Aparece un import `from backend.database...` en un archivo de `frontend/` (salvo `event_bus.py`).
- Un widget guarda una referencia a otro widget (`self._otro_widget = ...`).
- El dict `_HANDLERS` de `toolbar.py` supera las 60 entradas.
- Aparece un segundo `QMainWindow` o `VentanaPrincipal`.

---

# 16. Anexo: Referencias a la implementación actual

> ⚠️ Este anexo contiene referencias concretas al código actual. Puede
> quedar obsoleto tras refactors. Las secciones 1-11 están diseñadas para
> seguir siendo válidas aunque estos detalles cambien.

| Componente | Ubicación actual |
|---|---|
| VentanaPrincipal | `frontend/ventana/ventana.py` |
| Toolbar + _HANDLERS | `frontend/ventana/toolbar.py` |
| Sidebar + builders | `frontend/ventana/paneles.py` |
| Handlers generales | `frontend/ventana/handlers/__init__.py` |
| Gestión de proyectos | `frontend/ventana/handlers/gestion_proyectos.py` |
| Informes | `frontend/ventana/handlers/informes.py` |
| Diagnóstico | `frontend/ventana/handlers/diag_dialogs.py` |
| APU | `frontend/ventana/apu/apu.py` |
| Rastreo | `frontend/ventana/apu/rastreo.py` |
| Explosión | `frontend/ventana/apu/explosion.py` |
| TreeTableWidget (base) | `frontend/ventana/widgets/base.py` |
| TablaArbol | `frontend/ventana/widgets/arbol.py` |
| TablaInsumos | `frontend/ventana/widgets/insumos.py` |
| TablaExplosion + DialogoExplosion | `frontend/ventana/widgets/explosion.py` |
| Diálogos reutilizables | `frontend/ventana/widgets/dialogs.py` |
| Diálogo de ajustes | `frontend/ventana/widgets/ajustes.py` |
| EventBus | `backend/database/event_bus.py` |
| Api (fachada) | `frontend/ventana/api.py` |
| DataService | `backend/database/services/data_service.py` |
| Temas | `frontend/temas/temas.py` |
| ADR registrados | `docs/adr/` |

---

Actualizado: 2026-07-07 23:45 (hora local)
