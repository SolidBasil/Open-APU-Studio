# Arquitectura de Servicios — Guía de Implementación

**Fecha:** 2026-07-03
**Estado:** Plan aprobado, listo para implementar
**Versión del documento:** v2.0

---

## 1. Objetivo

Rediseñar la capa de persistencia y notificación de Open APU Studio para que:

- Ningún widget acceda directamente a repositorios ni a SQLite.
- Todas las escrituras pasen por un único `DataService`.
- Las validaciones vivan en Python, no en SQL ni en PRAGMA.
- Tras cada escritura exitosa, se emita un evento semántico con el registro completo.
- Los widgets escuchen eventos y refresquen solo los elementos afectados.
- Sea extensible: agregar una nueva tabla no requiere modificar servicios centrales.

---

## 2. Ciclo de vida

| Objeto | Cuándo se crea | Cuántas instancias |
|--------|---------------|-------------------|
| `Database` | Al iniciar la app (o al abrir un `.db`) | 1 por proyecto abierto |
| `EventBus` | Al iniciar la app | 1 por proyecto |
| `Api` | Al abrir un proyecto | 1 por proyecto |
| `DataService` | Al abrir un proyecto | 1 por proyecto |
| `RepositoryRegistry` | Al abrir un proyecto (ligado al DataService) | 1 por proyecto |
| `Repositorios` | Pre-creados al registrar en el RepositoryRegistry | 1 instancia por repo por proyecto |

**Multi-proyecto (futuro):** Si se abren dos proyectos, cada uno tiene su propio
`Database` → `RepositoryRegistry` → `DataService` → `Api`. No comparten estado.

---

## 3. Diagrama de dependencias

### Permitido

```
UI (widgets, handlers, paneles)
    ↓
Api (fachada de lectura y escritura)
    ↓
DataService (actualizar / insertar / eliminar)
├── SchemaRegistry (validación)
├── RepositoryRegistry (resuelve repo)
│   └── repos (SQL)
└── EventBus (notificación post-commit)
    └── suscriptores (widgets)
```

### Prohibido

```
UI → Repositorio
UI → DataService (excepto vía Api)
Repositorio → Servicio
Repositorio → EventBus
Servicio → SQL directo
Cualquier capa → Database.instancia().conn (excepto repos vía Database)
```

---

## 4. Reglas de lectura

**Toda consulta desde la UI pasa por `Api`.** Los repositorios nunca se
instancian directamente desde el frontend.

```python
# Correcto (en un widget)
resultado = self._api.insumos(tipo="material")

# Prohibido
from backend.database.repos import InsumoRepo
repo = InsumoRepo(self._db)
resultado = repo.todos(self._api.proyecto_actual_id())
```

**Api** es la única fachada visible para el frontend. Expone métodos de
lectura (que delegan a repos) y métodos de escritura (que delegan a DataService).

---

## 5. Principios acordados

### 5.1 Separación de responsabilidades

| Capa | Responsabilidad | Prohíbe |
|------|----------------|---------|
| **Repositorios** | Ejecutar SQL (SELECT/INSERT/UPDATE/DELETE) | Conocer eventos, validaciones de negocio |
| **DataService** | Coordinar: validar → transacción → repo → commit → evento | Conocer SQL, abrir conexiones directas |
| **SchemaRegistry** | Definir tipos de campo y reglas de validación por tabla | Conocer SQLite, acceder a la conexión |
| **EventBus** | Notificar cambios exitosos a los suscriptores | Modificar datos, validar |
| **Widgets** | Escuchar eventos, actualizar solo filas afectadas | Consultar la BD tras cada cambio, instanciar repos |

### 5.2 Reglas inquebrantables

1. **Ningún servicio conoce SQL.** Si necesitas datos, llama al repositorio.
2. **Ningún repositorio conoce eventos.** Si necesitas notificar, eso es trabajo del servicio.
3. **Los eventos representan cambios confirmados, no cambios intentados.** Se emiten después del `COMMIT`, nunca antes.
4. **Las transacciones las controla el servicio, no el repositorio.** El repositorio ejecuta SQL dentro de la transacción que el servicio abre.
5. **Los repos no devuelven solo los campos modificados.** El servicio lee el registro completo después del update y lo incluye en el evento.
6. **Cada tabla tiene un único repositorio que la representa.** No hay dos repos escribiendo en la misma tabla.
7. **La fuente de verdad es siempre SQLite.** Ningún repositorio ni servicio mantiene estado en memoria.
8. **La UI nunca consulta la BD tras un cambio.** La relectura del registro es responsabilidad del servicio; el widget recibe el estado completo via evento.
9. **Los eventos son notificación, no lógica de negocio.** No se encadenan eventos (A genera B genera C). La lógica principal vive en DataService.
10. **Toda consulta desde la UI pasa por Api.** Los repos nunca se instancian desde el frontend.

---

## 6. Componentes

### 6.1 `event_bus.py` — Bus de eventos semánticos

**Archivo:** `backend/database/event_bus.py`

```python
class EventBus:
    def __init__(self):
        self._suscriptores: dict[type[Evento], list[Callable]] = {}

    def suscribir(self, tipo_evento: type[Evento], callback: Callable):
        self._suscriptores.setdefault(tipo_evento, []).append(callback)

    def emit(self, evento: Evento):
        for cb in self._suscriptores.get(type(evento), []):
            try:
                cb(evento)
            except Exception:
                import traceback
                traceback.print_exc()  # Un widget roto no rompe la cadena
```

**Regla de excepciones:** `emit()` captura excepciones de cada suscriptor
individualmente. Si el Widget A lanza error, Widget B y C siguen recibiendo.
El error se imprime en consola pero no detiene la aplicación.

**Eventos semánticos:**

| Evento | Campos | Cuándo se emite |
|--------|--------|----------------|
| `InsumoActualizado` | `insumo_id`, `cambios`, `registro` | Tras UPDATE insumos |
| `ConceptoActualizado` | `concepto_id`, `cambios`, `registro` | Tras UPDATE estructura_presupuesto |
| `ApuComponenteActualizado` | `componente_id`, `cambios`, `registro` | Tras UPDATE apu_matrices |
| `NodoInsertado` | `nodo_id`, `tipo`, `padre_id` | Tras INSERT estructura_presupuesto |
| `NodoEliminado` | `nodo_id`, `tipo` | Tras soft-delete |
| `ProyectoRecalculado` | `proyecto_id` | Tras recálculo completo |
| `FactoresSobrecostoActualizados` | `proyecto_id`, `registro` | Tras UPDATE factores_sobrecosto |
| `NotaInsertada` | `nota_id`, `concepto_id` | Tras INSERT notas |
| `NotaResuelta` | `nota_id` | Tras UPDATE notas |

**Regla de encadenamiento:** Los eventos no generan otros eventos.
La lógica que reacciona a un evento puede hacer cualquier cosa
excepto emitir otro evento.

---

### 6.2 `schema_registry.py` — Validación por tipos de campo

**Archivo:** `backend/database/schema_registry.py`

**Fields disponibles:**

| Field | Parámetros | Valida |
|-------|-----------|--------|
| `FloatField` | `min`, `max`, `required` | Tipo numérico, rango |
| `StringField` | `choices`, `max_length`, `required` | Tipo string, opciones |
| `BoolField` | `required` | 0/1 |
| `IntField` | `min`, `max`, `required` | Tipo entero, rango |

**Uso:**

```python
class SchemaRegistry:
    _rules = {
        "insumos": {
            "costo_final": FloatField(min=0),
            "descripcion": StringField(required=True),
            "unidad": StringField(),
            "es_compuesto": BoolField(),
        },
        "estructura_presupuesto": {
            "cantidad": FloatField(min=0),
            "tipo": StringField(choices=("capitulo", "concepto")),
        },
        "apu_matrices": {
            "valor": FloatField(min=0),
            "operador": StringField(choices=("*", "/")),
        },
    }

    def validate(self, tabla, campos):
        reglas = self._rules.get(tabla, {})
        for campo, valor in campos.items():
            if campo in reglas:
                reglas[campo].validate(valor)
```

**Regla:** Las reglas viven en Python, no se inspeccionan `PRAGMA table_info()`.

---

### 6.3 `exceptions.py` — Excepciones propias

**Archivo:** `backend/database/exceptions.py`

```python
class DataServiceError(Exception):
    """Base para errores del servicio de datos."""

class ValidationError(DataServiceError):
    """Validación de SchemaRegistry fallida."""

class RepositoryError(DataServiceError):
    """Error en operación de repositorio (SQL, integridad, etc.)."""

class ConflictError(DataServiceError):
    """Conflicto de concurrencia (registro modificado por otro proceso)."""
```

**Uso desde DataService:**

```python
def actualizar(self, entidad, registro_id, **campos):
    try:
        self._registry.validate(entidad, campos)
    except ValueError as e:
        raise ValidationError(str(e)) from e
    # ... resto del flujo
```

**La UI captura estas excepciones** y muestra un mensaje al usuario:
```python
try:
    self._api.actualizar("insumos", insumo_id, costo_final=precio)
except ValidationError as e:
    QMessageBox.warning(self, "Dato inválido", str(e))
```

---

### 6.4 `Database.transaction()` — Transacciones

**Archivo:** `backend/database/db.py`

```python
class Database:
    def transaction(self):
        """Context manager: abre transacción, commitea al salir, rollback si falla."""
        ...
```

**Uso desde DataService:**

```python
with self._db.transaction():
    repo.update(id, campos)
    registro = repo.buscar(registro_id)
# COMMIT aquí. Si hubo excepción → ROLLBACK.
```

---

### 6.5 `repos/base.py` — Métodos genéricos de escritura

**Archivo:** `backend/database/repos/base.py`

```python
class RepoBase:
    def __init__(self, db: Database):
        self._db = db
        self._conn = db.conn
        self._cursor = db.conn.cursor()

    def _update(self, tabla, registro_id, campos):
        """UPDATE genérico. No hace commit (asume transacción externa)."""
        set_clause = ", ".join(f"{k} = ?" for k in campos)
        valores = list(campos.values()) + [registro_id]
        self._cursor.execute(
            f"UPDATE {tabla} SET {set_clause}, "
            f"modificado_en = datetime('now') WHERE id = ?",
            valores
        )

    def _insert(self, tabla, campos) -> int:
        """INSERT genérico. No hace commit. Devuelve lastrowid."""
        cols = ", ".join(campos.keys())
        placeholders = ", ".join("?" for _ in campos)
        self._cursor.execute(
            f"INSERT INTO {tabla} ({cols}) VALUES ({placeholders})",
            list(campos.values())
        )
        return self._cursor.lastrowid

    def _delete(self, tabla, registro_id):
        """Soft-delete genérico. No hace commit."""
        self._update(tabla, registro_id, {"activo": 0})

    def buscar(self, tabla, registro_id) -> dict | None:
        """SELECT genérico."""
        row = self._cursor.execute(
            f"SELECT * FROM {tabla} WHERE id = ?", (registro_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── MÉTODO LEGADO ─────────────────────────────────────────────
    def _ejecutar(self, sql, params=None):
        """DEPRECATED: hace commit(). Solo código no migrado."""
        self._cursor.execute(sql, params or [])
        self._conn.commit()
        return self._cursor.lastrowid
```

---

### 6.6 Repositorios — Cada uno con `TABLA` + `update()` + `insert()`

```python
class InsumoRepo(RepoBase):
    TABLA = "insumos"

    def update(self, registro_id, campos):
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id):
        return self._delete(self.TABLA, registro_id)
```

**Repositorios que necesitan adaptación:**

| Repositorio | TABLA | Métodos a deprecar |
|-------------|-------|-------------------|
| `InsumoRepo` | `insumos` | `actualizar_precio()`, `actualizar_campo()`, `actualizar_descripcion()`, `insertar()` |
| `NodoRepo` | `estructura_presupuesto` | `actualizar_cantidad()`, `actualizar_total()`, `actualizar_descripcion_agrupador()` |
| `ApuMatricesRepo` | `apu_matrices` | `actualizar_campo()` |
| `FactoresSobrecostoRepo` | `factores_sobrecosto` | `guardar()` |
| `NotaRepo` | `notas` | `insertar()`, `resolver()` |
| `FamiliaRepo` | `familias` | `insertar()` |
| `SubfamiliaRepo` | `subfamilias` | `insertar()` |

**Regla:** Los repos son stateless. Cada instancia se crea con una referencia
a `Database`. No mantienen caché ni estado en memoria. La fuente de verdad
es siempre SQLite.

---

### 6.7 `RepositoryRegistry` — Ligado al DataService

**Archivo:** `backend/database/services/repository_registry.py`

```python
class RepositoryRegistry:
    def __init__(self, db: Database):
        self._db = db
        self._repos: dict[str, RepoBase] = {}

    def registrar(self, entidad: str, repo_cls: type[RepoBase]):
        """Crea y almacena la instancia del repo."""
        self._repos[entidad] = repo_cls(self._db)

    def obtener(self, entidad: str) -> RepoBase:
        if entidad not in self._repos:
            raise KeyError(f"No hay repositorio registrado para '{entidad}'")
        return self._repos[entidad]
```

**No es singleton.** Se crea una vez por proyecto. Si en el futuro se abren
dos proyectos, cada uno tiene su propio `RepositoryRegistry` con sus propios
repos apuntando a su propia `Database`.

**Registro** (se hace una vez al abrir un proyecto):

```python
registry = RepositoryRegistry(db)
registry.registrar("insumos", InsumoRepo)
registry.registrar("estructura_presupuesto", NodoRepo)
registry.registrar("apu_matrices", ApuMatricesRepo)
# ... etc
```

---

### 6.8 `DataService` — Coordinador único de escritura

**Archivo:** `backend/database/services/data_service.py`

Un único servicio para todas las operaciones de escritura.

```python
class DataService:
    def __init__(self, db: Database, registry: RepositoryRegistry,
                 event_bus: EventBus):
        self._db = db
        self._registry = registry
        self._schema = SchemaRegistry()
        self._event_bus = event_bus

    def actualizar(self, entidad: str, registro_id: int, **campos):
        self._schema.validate(entidad, campos)
        repo = self._registry.obtener(entidad)
        with self._db.transaction():
            repo.update(registro_id, campos)
            registro = repo.buscar(registro_id)
        evento = self._evento(entidad, registro_id, campos, registro)
        self._event_bus.emit(evento)

    def insertar(self, entidad: str, **campos) -> int:
        self._schema.validate(entidad, campos)
        repo = self._registry.obtener(entidad)
        with self._db.transaction():
            registro_id = repo.insert(campos)
        self._event_bus.emit(NodoInsertado(registro_id, entidad, campos.get("padre_id")))
        return registro_id

    def eliminar(self, entidad: str, registro_id: int):
        repo = self._registry.obtener(entidad)
        with self._db.transaction():
            repo.delete(registro_id)
        self._event_bus.emit(NodoEliminado(registro_id, entidad))
```

**Por qué un solo servicio:** Los tres (update/insert/delete) comparten
el 90% del flujo: transacción, validación, resolución de repo, eventos,
manejo de errores. Separarlos ahora duplica infraestructura innecesaria.

**Operaciones masivas** (importar, duplicar árbol, eliminar capítulo completo,
pegar 400 conceptos) usan el mismo `DataService` dentro de una única
`Database.transaction()`. Ejemplo:

```python
def eliminar_capitulo(self, capitulo_id):
    """Elimina un capítulo y todos sus hijos."""
    with self._db.transaction():
        for nodo in reversed(repo.descendientes(capitulo_id)):
            repo.delete(nodo["id"])
    self._event_bus.emit(NodoEliminado(capitulo_id, "capitulo"))
```

---

### 6.9 `api.py` — Fachada expuesta al frontend

```python
class Api:
    def __init__(self, db: Database, data_service: DataService):
        self._db = db
        self._data_service = data_service

    def proyecto_actual_id(self) -> int:
        return self._pid

    # ── Escritura (delega a DataService) ──────────────────────────
    def actualizar(self, entidad, id, **campos):
        self._data_service.actualizar(entidad, id, **campos)

    def insertar(self, entidad, **campos) -> int:
        return self._data_service.insertar(entidad, **campos)

    def eliminar(self, entidad, id):
        self._data_service.eliminar(entidad, id)

    # ── Lectura (delega a repos) ──────────────────────────────────
    def presupuesto_arbol(self):
        from backend.database.core import build_budget_tree
        return build_budget_tree(self._db.db_path)

    def apu(self, ...):
        # ... como hoy
```

---

## 7. Orden de implementación

### Fase 1 — Infraestructura (sin migrar nada)

| Paso | Archivo | Contenido |
|------|---------|-----------|
| 1 | `event_bus.py` | EventBus + eventos semánticos + manejo de excepciones |
| 2 | `schema_registry.py` | Field types + reglas por tabla |
| 3 | `exceptions.py` | ValidationError, RepositoryError, ConflictError |
| 4 | `db.py` | Agregar `Database.transaction()` |
| 5 | `repos/base.py` | `_update()`, `_insert()`, `_delete()` sin commit. `_ejecutar()` deprecated |
| 6 | `repos/*.py` | Agregar `TABLA`, `update()`, `insert()`, `delete()` en cada repo (convive con métodos viejos) |
| 7 | `services/repository_registry.py` | RepositoryRegistry (ligado a Database, no singleton) |
| 8 | `services/data_service.py` | DataService (actualizar, insertar, eliminar) |
| 9 | `api.py` | Exponer DataService |
| 10 | `main.py` | Crear DataService, registrar repos, inyectar |

### Fase 2 — Migrar writes existentes

Reemplazar cada método de mutación en `api.py` por llamadas a `DataService.actualizar()`.

### Fase 3 — Widgets escuchan eventos

- Eliminar `_refrescar_tab_activa()` completo.
- Cada widget se suscribe a eventos semánticos.
- Refresco in-place por id.

### Fase 4 — Limpiar repos + core.py

- Mover `build_budget_tree` → `NodoRepo.arbol()`.
- Mover `get_proyecto` → `ProyectoRepo.obtener()`.
- Mover `get_apu` → `ApuMatricesRepo.con_detalle()`.
- Eliminar métodos de escritura deprecados.
- Reducir `core.py` a solo `generar_hash()` y `flatten()`.

### Fase 5 — Futuro

Domain models, commands, undo/redo.

---

## 8. Convivencia durante la migración

| Método | Estado | Usa commit | Cuándo usar |
|--------|--------|-----------|------------|
| `_ejecutar()` | **DEPRECATED** | Sí | Solo código legacy no migrado |
| `_update()` | **NUEVO** | No | Todo código nuevo |
| `_insert()` | **NUEVO** | No | Todo código nuevo |
| `_delete()` | **NUEVO** | No | Todo código nuevo |

**Regla:** Si escribes código nuevo, usa `_update()` / `_insert()` / `_delete()`
y nunca llames a `_ejecutar()`.

---

## 9. Checklist de revisión

Al terminar cada fase, verificar:

- [x] **Fase 1:**
  - [x] `event_bus.py` funciona con prueba manual
  - [x] `schema_registry.py` rechaza valores inválidos
  - [x] `exceptions.py` centraliza DataServiceError/ValidationError/RepositoryError/ConflictError
        (antes vivían repartidas entre schema_registry.py y data_service.py sin heredar
        entre sí; unificado fuera de fase, ver nota al final de este documento)
  - [x] `Database.transaction()` commitea y hace rollback en excepción
  - [x] `RepoBase._update()` no hace commit interno
  - [x] Al menos `InsumoRepo` tiene `TABLA` + `update()` funcionando
  - [x] `RepositoryRegistry` resuelve `InsumoRepo` desde string
  - [x] `DataService.actualizar()` emite evento post-commit con registro completo
  - [x] `api.py` expone los servicios correctamente

- [x] **Fase 2:**
  - [x] Ningún `_ejecutar()` nuevo (solo legacy)
  - [x] Todos los writes pasan por `DataService`
  - [x] Cada repo tiene `TABLA` + `update()` / `insert()` / `delete()`
  - [x] `_ejecutar()` marcado deprecated en todos los repos

- [x] **Fase 3:**
  - [x] `_refrescar_tab_activa()` eliminado o vacío
  - [x] Widgets se suscriben a eventos y actualizan filas in-place
  - [x] No hay `self._refrescar_tab_activa()` en handlers de edición

- [x] **Fase 4:**
  - [x] `core.py` no tiene SQL
  - [~] `api.py` no tiene métodos de mutación — **nota:** este ítem contradice
        el propio diseño de Fase 2 (api.py expone las mutaciones como
        wrappers finos sobre DataService; si no viviera ahí, no habría
        forma de llamar a DataService desde la UI). Se interpreta como
        aspiracional para una futura Fase 5 (Command objects/undo-redo,
        ver §7), no como pendiente de esta fase. No se tocó.
  - [x] No hay `_ejecutar()` en ningún archivo nuevo (se eliminó por
        completo junto con `_muchos()`/`_actualizar_campo()`, sin uso
        tras Fase 2)

- [x] **Reglas permanentes:**
  - [x] Ningún servicio conoce SQL
  - [x] Ningún repositorio conoce eventos
  - [x] Los eventos se emiten después del COMMIT
  - [x] Las transacciones las controlan los servicios
  - [x] `SchemaRegistry` no inspecciona PRAGMA
  - [x] UI → Api → DataService → Repos → SQL
  - [x] No se instancian repos desde widgets
  - [x] Los eventos no se encadenan

---

## 10. Archivos a crear/modificar

| Archivo | Acción |
|---------|--------|
| `backend/database/event_bus.py` | **NUEVO** |
| `backend/database/schema_registry.py` | **NUEVO** |
| `backend/database/exceptions.py` | **NUEVO** |
| `backend/database/services/__init__.py` | **NUEVO** |
| `backend/database/services/repository_registry.py` | **NUEVO** |
| `backend/database/services/data_service.py` | **NUEVO** |
| `backend/database/db.py` | **MOD** — agregar `transaction()` |
| `backend/database/repos/base.py` | **MOD** — `_update`, `_insert`, `_delete`, deprecar `_ejecutar` |
| `backend/database/repos/insumos.py` | **MOD** — `TABLA`, `update()`, `insert()`, `delete()` |
| `backend/database/repos/presupuesto.py` | **MOD** — `TABLA`, `update()`, `insert()`, `delete()` |
| `backend/database/repos/apu.py` | **MOD** — `TABLA`, `update()`, `insert()`, `delete()` |
| `backend/database/repos/proyecto.py` | **MOD** — `TABLA`, `update()`, `insert()`, `delete()` |
| `backend/database/repos/catalogos.py` | **MOD** — `TABLA`, `update()`, `insert()`, `delete()` |
| `frontend/ventana/api.py` | **MOD** — exponer DataService |
| `main.py` | **MOD** — crear DataService, registrar repos |

---

## 11. Futuro (no implementar aún)

- `domain/models.py` — Objetos de dominio (Insumo, Concepto, etc.)
- `commands/` — Patrón Command para operaciones compuestas
- Undo/Redo, historial de operaciones
- Unit of Work para transacciones multi-repo
- Collaborative editing
