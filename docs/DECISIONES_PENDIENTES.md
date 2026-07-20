# Decisiones de diseño — Open APU Studio

Documento vivo que registra decisiones tomadas, pendientes y descartadas.
Actualizar cada vez que se tome una decisión relevante.

Formato de cada entrada:
- **Contexto** — por qué es una decisión que hay que tomar
- **Opciones consideradas** — qué se evaluó
- **Decisión** — qué se eligió y por qué
- **Consecuencias** — qué implica la decisión
- **Estado** — `✓ Decidido` / `⏳ Pendiente` / `✗ Descartado`

---

## BASE DE DATOS

### BD-01 — Una DB por proyecto
**Estado:** ✓ Decidido

**Contexto:**
Definir si todos los proyectos viven en una sola base de datos SQLite
o cada proyecto tiene su propio archivo.

**Opciones consideradas:**
- DB global con `proyecto_id` en cada tabla
- Un archivo `.db` por proyecto

**Decisión:**
Un archivo `.db` por proyecto.

**Consecuencias:**
- Los proyectos se pueden compartir enviando un solo archivo
- Un error en un proyecto no afecta a los demás
- La app necesita un mecanismo para abrir/cerrar proyectos
- Las queries no necesitan filtrar por `proyecto_id` si solo hay un proyecto abierto a la vez
- Si en el futuro se abre más de un proyecto simultáneamente, se necesita gestionar múltiples conexiones

---

### BD-02 — Carpeta de datos del usuario
**Estado:** ✓ Decidido

**Contexto:**
Definir dónde se guardan los archivos `.db` y la configuración de la app.

**Decisión:**
Carpeta estándar del sistema operativo para datos de usuario:

```
Windows: C:/Users/<usuario>/AppData/Local/Open APU Studio/
├── config.json          ← preferencias: tema, último proyecto abierto, etc.
├── proyectos/
│   ├── D60JALISCOT.db
│   └── CASA_EG.db
└── logs/
```

En Python se obtiene con:
```python
from pathlib import Path
import platformdirs
BASE = Path(platformdirs.user_data_dir("Open APU Studio", "OpenAPU"))
```

**Consecuencias:**
- Requiere `pip install platformdirs`
- Los proyectos no se borran al actualizar la app
- El usuario puede hacer backup copiando esa carpeta

---

### BD-03 — Campos del esquema pendientes (20%)
**Estado:** ⏳ Pendiente

**Contexto:**
Al diseñar el esquema quedó un 20% de campos sin definir,
principalmente relacionados con programa de obra y frentes.

**Decisión:**
Pendiente. Cuando se definan, se implementan como migraciones numeradas
siguiendo el sistema ya establecido en `db.py`.

**Consecuencias:**
- No bloquea el desarrollo actual
- El esquema v3 está completo y funcional para importación y visualización
- Las tablas `estructura_presupuesto` y `insumos` ya incluyen todos los campos OPUS esenciales

---

## IMPORTACIÓN

### IMP-01 — Reimportación de un proyecto existente
**Estado:** ✓ Implementado (borrar DB + reimportar)

**Contexto:**
Si el usuario intenta importar una carpeta OPUS cuyo proyecto ya existe
en la DB, hay que decidir qué hacer.

**Opciones a evaluar:**
- Reemplazar todo (borrar y reimportar)
- Merge inteligente (actualizar precios, conservar notas y estados)
- Crear una nueva versión del proyecto
- Bloquear y pedir confirmación

**Nota:**
El merge inteligente es el más útil pero el más complejo.
Reemplazar es simple pero destruye notas, estados del semáforo
y cualquier edición manual.

---

### IMP-02 — Exportación de vuelta a OPUS
**Estado:** ⏳ Pendiente

**Contexto:**
OPUS 2010 lee archivos `.DBF`. Exportar de vuelta requiere generar
esos archivos con la estructura exacta de cada tabla.

**Decisión:**
Fuera del alcance actual. Se evalúa en versiones posteriores.

**Consecuencias:**
- Requiere una librería que escriba `.DBF` (ej. `dbfwrite`)
- Requiere respetar tipos de campo (`N`, `C`, `M`, `L`, `D`) y longitudes exactas
- Requiere generar `.FPT` para campos Memo
- Usar codificación CP850

---

## FRONTEND

### FE-01 — Frontend solo lectura hasta pulir la lectura
**Estado:** ✓ Decidido

**Contexto:**
Definir cuándo habilitar la edición en la interfaz.

**Decisión:**
El frontend permanece en modo solo lectura hasta que la lectura y
visualización de datos esté 100% pulida y verificada contra proyectos reales.

**Consecuencias:**
- El árbol (`arbol.py`) permite edición de celdas (clave, descripción, unidad, cant, precio)
- La edición dispara recálculo de totales bottom-up
- `insumos.py` y `apu` detail permanecen solo lectura
- Cuando se habilite la edición total, el primer paso es implementar el Historial

---

### FE-02 — Ctrl+Z: historial en memoria con interfaz migrable
**Estado:** ✓ Decidido

**Contexto:**
Implementar deshacer/rehacer. Dos opciones evaluadas:
- Stack en memoria (simple, se pierde al cerrar)
- Historial en DB (persiste, soporta multiusuario)

**Decisión:**
Historial en memoria para el MVP, con una interfaz abstracta que
permite migrar a historial en DB sin tocar el resto de la app.

**Implementación:**

```python
# backend/historial.py

class Historial:
    """Interfaz común — toda la app usa esta clase, nunca la implementación."""

    def registrar(self, tabla, registro_id, campo,
                  valor_anterior, valor_nuevo, usuario_id=1):
        raise NotImplementedError

    def deshacer(self, usuario_id=1):
        raise NotImplementedError

    def rehacer(self, usuario_id=1):
        raise NotImplementedError

    def puede_deshacer(self, usuario_id=1) -> bool:
        raise NotImplementedError

    def puede_rehacer(self, usuario_id=1) -> bool:
        raise NotImplementedError


class HistorialMemoria(Historial):
    """MVP — stack en memoria. Se pierde al cerrar la app."""

    def __init__(self):
        self._pila    = []   # [(tabla, id, campo, anterior, nuevo)]
        self._futura  = []   # para rehacer

    def registrar(self, tabla, registro_id, campo,
                  valor_anterior, valor_nuevo, usuario_id=1):
        self._pila.append((tabla, registro_id, campo, valor_anterior, valor_nuevo))
        self._futura.clear()   # nueva acción cancela el rehacer

    def deshacer(self, usuario_id=1):
        if not self._pila:
            return None
        entrada = self._pila.pop()
        self._futura.append(entrada)
        return entrada   # la app aplica el valor_anterior

    def rehacer(self, usuario_id=1):
        if not self._futura:
            return None
        entrada = self._futura.pop()
        self._pila.append(entrada)
        return entrada   # la app aplica el valor_nuevo

    def puede_deshacer(self, usuario_id=1) -> bool:
        return bool(self._pila)

    def puede_rehacer(self, usuario_id=1) -> bool:
        return bool(self._futura)


class HistorialDB(Historial):
    """
    Multiusuario — escribe en la tabla `historial` del esquema.
    Implementar cuando se active la colaboración.
    Cada usuario deshace solo sus propios cambios.
    La sesion (UUID) agrupa cambios de una misma operación.
    Ver schema.sql tabla historial para la estructura.
    """
    # TODO: implementar cuando llegue multiusuario
    pass
```

Al arrancar la app:
```python
# main.py — cambiar esta línea cuando llegue multiusuario
from backend.historial import HistorialMemoria
historial = HistorialMemoria()
```

**Consecuencias:**
- La migración a `HistorialDB` requiere solo escribir esa clase (~40 líneas)
  y cambiar una línea en `main.py`
- La tabla `historial` en el esquema ya está lista para cuando se necesite
- **Regla importante:** nunca usar `HistorialMemoria` directamente en el código
  — siempre a través de la interfaz `Historial`

---

### FE-03 — Búsqueda multi-columna con menú contextual en la barra de búsqueda
**Estado:** ✓ Implementado

**Contexto:**
La barra de búsqueda solo filtraba por la columna "Descripción".
El usuario necesitaba buscar también por clave, familia, tipo, etc.

**Decisión:**
Se implementó búsqueda multi-columna client-side (sin re-consultar DB)
con un menú contextual en la barra de búsqueda para seleccionar columnas.

**Detalles técnicos:**
- `_search_cols: set[int] | None` — `None` = todas las columnas, `set()` = ninguna
- Menú usa `triggered` (no `toggled`) para evitar re-filtros durante construcción
- Solo aparecen columnas visibles en la tabla
- Cada widget define sus columnas por defecto (`_search_cols`) y las disponibles
  (`get_searchable_columns()`)
- `TablaArbol` por defecto: Nivel, Clave, Descripción, Tipo
- `TablaInsumos` por defecto: Clave, Descripción, Familia

**Archivos:**
- `frontend/widgets/base.py`: `filter_rows()` multi-columna, API de columnas
- `frontend/ventana.py`: `_on_search_context_menu()`, `_on_search_col_toggle()`

---

### FE-04 — Notas por nodo: panel inline en la fila
**Estado:** ✓ Decidido

**Contexto:**
La tabla `notas` del esquema permite comentarios por nodo.
Definir cómo aparecen en la interfaz: inline en la fila o panel lateral.

**Decisión:**
Las notas aparecen inline dentro de la misma fila del nodo,
expandiéndose al hacer clic en un icono de la columna de estado.

**Implementación futura:**
- Agregar columna "📝" en `arbol.py` que muestre el número de notas del nodo
- Al hacer clic expande una subfila con el hilo de comentarios
- Cada nota muestra: autor, fecha, texto, botón "Resolver"
- Las notas sin resolver muestran el ícono en color, las resueltas en gris

**Consecuencias:**
- No requiere panel lateral — mantiene el foco en el presupuesto
- El widget `TablaArbol` necesita soportar filas expandibles anidadas
- Requiere que el frontend esté en modo edición (depende de FE-01)

---

## COLABORACIÓN

### COL-01 — Sistema de login
**Estado:** ⏳ Pendiente

**Contexto:**
La infraestructura de `usuarios` y `roles` ya existe en el esquema.
Falta definir el flujo de autenticación.

**Opciones a evaluar:**
- Sin login: el usuario escribe su nombre al abrir la app (simple)
- Login local: usuario + contraseña guardados en la DB
- Login centralizado: servidor de autenticación (complejo, requiere backend web)

**Nota:**
Para uso de pequeña empresa probablemente basta con login local.
El login centralizado solo tiene sentido si hay sync en red.

---

### COL-02 — Sincronización entre usuarios
**Estado:** ⏳ Pendiente

**Contexto:**
Si varios usuarios trabajan en el mismo proyecto, necesitan
ver los cambios del otro.

**Opciones a evaluar:**
- Archivo compartido (Dropbox/Drive) — simple pero con riesgo de conflictos
- Servidor central con API — complejo, requiere infraestructura
- SQLite en red (WAL mode) — funciona en LAN, no en internet

**Nota:**
El modo WAL ya está activado en `db.py`. SQLite soporta múltiples
lectores simultáneos y un escritor — viable para equipos pequeños en LAN.

---

### COL-03 — Semáforo: quién puede cambiar el estado
**Estado:** ⏳ Pendiente

**Contexto:**
Los nodos tienen un estado de confiabilidad (sin revisar / en revisión /
verificado / cuestionado). Hay que decidir quién puede cambiarlo.

**Opciones a evaluar:**
- Cualquier usuario puede cambiar cualquier estado
- Solo el rol `revisor` o superior puede marcar como `verificado`
- El autor del nodo no puede verificar su propio trabajo

**Nota:**
La tabla `roles` ya tiene niveles (0-3). La lógica de permisos
vive en la app, no en el esquema.

---

## DISTRIBUCIÓN

### DIS-01 — Empaquetado con PyInstaller
**Estado:** ⏳ Pendiente

**Contexto:**
Distribuir la app sin requerir que el usuario instale Python.

**Decisión:**
Pendiente hasta tener el lector de datos 100% funcional.

**Nota:**
PyInstaller ya está en el plan original. Considerar también
`Nuitka` como alternativa más rápida en ejecución.

---

## LIMPIEZA DE CÓDIGO (Julio 2026)

### LIM-01 — Eliminación de código muerto
**Estado:** ✓ Implementado

Eliminados ~20 métodos muertos de repos (`presupuesto.py`, `insumos.py`, `apu.py`, `proyecto.py`)
y la clase entera `ApuResumenTotalesRepo`.

### LIM-02 — Eliminación de SQL raw en frontend
**Estado:** ✓ Implementado

Toda query SQL en `handlers.py` y `paneles.py` migrada a `DiagnosticoRepo` o `api.py`.
`handlers.py` pasó de ~15 queries raw a 0. `paneles.py` eliminó imports de repos.

### LIM-03 — Deduplicación de header persistence
**Estado:** ✓ Implementado

`_save_header_state`, `_restore_header_state`, `_header_context_menu` movidos de
`arbol.py` + `insumos.py` a `TreeTableWidget` base. Subclases solo setean `_HEADER_KEY`.

### LIM-04 — Deduplicación de `actualizar_campo`
**Estado:** ✓ Implementado

Patrón genérico movido a `RepoBase._actualizar_campo()`. `ApuMatricesRepo` e `InsumoRepo` delegan.

### LIM-05 — División de archivos oversized
**Estado:** ✓ Implementado

`handlers.py` (~1000 líneas) → paquete `handlers/` (4 archivos, max 341 líneas).
`paneles.py` (~1083 líneas) → `paneles.py` (302 líneas) + paquete `apu/` (3 archivos).

---

## ARQUITECTURA DE SERVICIOS

### SVC-01 — DataService como único punto de escritura
**Estado:** ✓ Decidido (pendiente de implementar)

**Contexto:**
Los métodos de mutación están esparcidos en `api.py` (15+ métodos), repos
tienen lógica de negocio mezclada, y no hay validación centralizada ni
sistema de eventos post-commit.

**Opciones consideradas:**
- Mantener现状: métodos individuales por campo
- Tres servicios separados: UpdateService, InsertService, DeleteService
- Un único DataService con actualizar(), insertar(), eliminar()

**Decisión:**
Un único `DataService`. Los tres comparten el 90% del flujo (transacción,
validación, resolución de repo, eventos, manejo de errores). Separarlos
ahora duplica infraestructura innecesaria. Cada repo tiene `TABLA = "..."`
y un método `update(registro_id, campos)`.

**Consecuencias:**
- Agregar una tabla = registrar el repo en `RepositoryRegistry`
- `DataService` no se modifica al agregar nuevas entidades
- Convivencia temporal: `_ejecutar()` (deprecated) + `_update()` (nuevo, sin commit)

**Ver:** `docs/ARQUITECTURA_SERVICIOS.md`

### SVC-02 — EventBus con eventos semánticos
**Estado:** ✓ Implementado (Fase 3 completa, ver ARQUITECTURA_SERVICIOS.md §7)

**Contexto:**
Los widgets recargaban toda la UI tras cada edición (`_refrescar_tab_activa`,
ya eliminado). No había notificación de cambios entre módulos.

**Opciones consideradas:**
- Qt signals embebidos en repos
- EventBus simple con eventos por tabla
- EventBus con eventos semánticos + registro completo

**Decisión:**
EventBus con eventos semánticos (`InsumoActualizado`, `ConceptoActualizado`,
etc.). Cada evento incluye `cambios` (campos modificados) y `registro`
(estado completo post-commit). Los eventos NO se encadenan.

**Consecuencias:**
- Widgets se suscriben y actualizan solo filas afectadas
- Los eventos se emiten después del COMMIT (no antes)
- `emit()` captura excepciones de cada suscriptor (widget roto no rompe la cadena)
- Los eventos son notificación, no lógica de negocio crítica

### SVC-03 — SchemaRegistry con Field types en Python
**Estado:** ✓ Decidido (pendiente de implementar)

**Contexto:**
No hay validación centralizada de tipos de datos o reglas de negocio
antes de persistir.

**Opciones consideradas:**
- Inspeccionar `PRAGMA table_info()` en runtime
- SchemaRegistry con Field types definidos en Python
- Validación distribuida en cada repo

**Decisión:**
SchemaRegistry con Field types (`FloatField(min=0)`, `StringField(choices=...)`,
`BoolField`). Las reglas viven en Python, no dependen de SQLite.

**Consecuencias:**
- Cambiar de motor de BD (ej. PostgreSQL) no rompe la validación
- Agregar reglas de negocio = agregar un Field type
- No inspecciona PRAGMA — más rápido y predecible

### SVC-04 — Transacciones en Database, no en RepoBase
**Estado:** ✓ Decidido (pendiente de implementar)

**Contexto:**
Las transacciones multi-repo necesitan coordinación centralizada.

**Opciones consideradas:**
- `RepoBase.transaction()` como context manager
- `Database.transaction()` como context manager
- Sin transacciones explícitas (cada `_ejecutar` hace commit)

**Decisión:**
`Database.transaction()` como context manager. Las transacciones las
abren los servicios, no los repos. Los repos ejecutan SQL dentro de
la transacción que el servicio abre.

**Consecuencias:**
- `_update()` / `_insert()` / `_delete()` no hacen commit
- `_ejecutar()` (legacy) sigue haciendo commit hasta completar la migración
- El servicio controla cuándo commitea y cuándo hace rollback

### SVC-05 — RepositoryRegistry no es singleton
**Estado:** ✓ Decidido (pendiente de implementar)

**Contexto:**
El `RepositoryRegistry` mantiene instancias de repos. ¿Debe ser global
o estar ligado a cada `DataService`/`Database`?

**Opciones consideradas:**
- Singleton global (una instancia para toda la app)
- Instancia por proyecto (ligada al DataService)

**Decisión:**
Instancia por proyecto. Cada `DataService` tiene su propio
`RepositoryRegistry` con repos que apuntan a su `Database`.

**Consecuencias:**
- Si en el futuro se abren dos proyectos simultáneamente, cada uno tiene
  su propio registro de repos sin contaminar al otro
- No hay estado global que sincronizar

### SVC-06 — Regla de no encadenamiento de eventos
**Estado:** ✓ Decidido

**Contexto:**
¿Puede un handler de evento emitir otro evento?

**Decisión:**
No. Los eventos son notificación, no lógica de negocio. La lógica que
reacciona a un evento puede hacer cualquier cosa excepto emitir otro
evento. Esto mantiene el flujo evidente y depurable.

---

## TOOLBAR

### TB-01 — Botones placeholder (beta) en la toolbar
**Estado:** ✓ Documentado

**Contexto:**
La toolbar ribbon tiene 15 botones marcados como `(beta)` con estilo atenuado
que no tienen handler conectado. Se documenta cuáles se van a implementar,
cuándo, y por qué se mantienen visibles.

**Botones y su estado:**

| Botón | Ribbon | Estado | Plan |
|-------|--------|--------|------|
| **Exportar** | PROYECTO > Transferir | Pendiente | Se activará cuando se restaure `backend/exportar/` (roto tras cambios de schema) |
| **Usuarios** | INICIO > Sistema | Planeado | Multi-usuario está en roadmap (ver COL-01, COL-02) |
| **APU** | INFORMES > Generar | Futuro | Generar PDF de matrices APU (similar a ReportePresupuesto) |
| **Explosión** | INFORMES > Generar | Futuro | Generar PDF/Excel de explosión de insumos |
| **Catálogo** | INFORMES > Generar | Futuro | Generar PDF del catálogo de insumos por tipo |
| **Tema LaTeX** | INFORMES > Plantilla | Futuro | Seleccionar template LaTeX desde `latex/templates/` |
| **Formato columnas** | VISTA > Presentación | Planeado | Dialog de formato por columna: alineación, márgenes (izq/der/arriba/abajo), padding |
| **Filtro** | VISTA > Ver | Cableado | Toggle visibilidad de la barra de búsqueda (`_on_filtro_toolbar`) |
| **Cortar** | PRINCIPAL > Portapapeles | Cableado | `widget._cut()` sobre tabla activa |
| **Pegar** | PRINCIPAL > Portapapeles | Cableado | `widget._paste()` sobre tabla activa |
| **En catálogos** | PRINCIPAL > Buscar | Futuro | Activar búsqueda con scope en columnas de catálogo |
| **En vista** | PRINCIPAL > Buscar | Futuro | Activar búsqueda con scope en columnas visibles |
| **Rastrear uso** | PRINCIPAL > Rastreo | Cableado | Abre pestaña de rastreo del insumo seleccionado |

**Decisión:**
Los botones se mantienen visibles con estilo `(beta)` para que el usuario sepa
que van a existir. No se eliminan porque tienen funcionalidad planeada.

**Consecuencias:**
- Los botones `(beta)` no hacen nada al hacer clic (solo muestran tooltip)
- Se cablean a medida que la funcionalidad subyacente está lista
- El grupo Filtrar se eliminó de PRINCIPAL (3 botones sin backend)

---

*Última actualización: Julio 2026*
