# Arquitectura de servicios — Protocolo de acceso local ↔ HTTP

Actualizado: 2026-08-31 04:55 (hora local)

Este documento define el **protocolo normativo** de la capa de acceso de Open APU
Studio: cómo conviven la fachada `Api`, los backends local/HTTP, el cliente HTTP y
el servidor, y **el orden exacto** para terminar la migración local→HTTP sin
duplicar más lógica.

> **Estado al 2026-08-31:** Fase 0 (ToqueApiBackend Protocol, 66 métodos) ✓,
> Fase 2 (api.py dispatcher puro, 67 delegaciones, 5 `if _use_http:` infraestructura) ✓,
> Fase 3 (ApiCliente transporte puro, 7 públicos vs 41) ✓,
> regla cardinal SQL corregida (NodoRepo.con_formula_por_proyecto) ✓,
> `assets/icons8` 329→116 SVGs ✓. Pendientes: Fase 1 (eventos duplicados, bloqueada hasta Fase 4 WS semántico) y Fase 4-5.

---

## 1. Objetivo

Una **única implementación** de la lógica de dominio (en `DataService` + repos) que
dos transportes distintos expongan al frontend. `api.py` deja de bifurcar
`if self._use_http:` método por método y pasa a ser un **dispatcher puro**.

```
widgets (PySide6)
   │
   ▼
frontend/ventana/api.py          ← fachada: recibe llamadas de los widgets,
   │                               valida NADA, bifurca NADA → delega en self._backend
   ├── _BackendLocal  ─────────────────┐
   └── _BackendHTTP   ──► ApiCliente ──┤   ← transporte HTTP (sin lógica de dominio)
                                       ▼
                         server/servidor.py (FastAPI/WS) ← RPC fino (sin lógica de dominio)
                                       │
                                       ▼
              backend/database/services/data_service.py  ← ÚNICA lógica de dominio
              backend/database/repos/                     ← ÚNICO lugar con SQL
```

---

## 2. Responsabilidad de cada pieza

| Pieza | Rol | Prohibido |
|---|---|---|
| `frontend/ventana/api.py` | Fachada. Traduce llamada del widget → método del backend activo. | `if self._use_http:` inline; SQL; importar repos; evaluar fórmulas; escribir `conn`. |
| `api_backends.py:_BackendLocal` | Envuelve `DataService`+repos para el proceso local (Puerto sin red). | SQL; transformar datos de presentación. |
| `api_backends.py:_BackendHTTP` | Envuelve `ApiCliente` para el modo red; traduce errores HTTP → excepciones de dominio. | Duplicar lógica ya existente en `DataService`. |
| `api_cliente.py:ApiCliente` | **Transporte** HTTP. `_get/_post/_url` + operaciones genéricas de CRUD. | Métodos de dominio (conocer entidades/endpoints por operación). |
| `ws_client.py:WebSocketClient` | Hilo que recibe eventos del servidor y los re-inyecta en el `EventBus` local. | Re-emitir eventos que generó el propio cliente. |
| `server/servidor.py` | Expone `DataService` por HTTP/WS. RPC fino. | Repos directos cuando `DataService` ya tiene el método; lógica de UI. |
| `data_service.py` | **Única** lógica de dominio transaccional (validar → transacción → repo → commit → evento). | SQL (delega en repos). |
| `backend/database/repos/*` | SQL. Único lugar con SQL. | Validación de negocio, eventos. |

---

## 3. Contrato de interfaz: el Protocolo

`_BackendLocal` y `_BackendHTTP` deben exponer **exactamente la misma interfaz**.
En el código se declara como un `typing.Protocol` (paso 1 de ejecución):

```python
# frontend/ventana/api_backends.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class ToqueApiBackend(Protocol):
    """Contrato que cumplen _BackendLocal y _BackendHTTP.

    Reglas de firma (obligatorias para TODO método nuevo):
    - Parámetros por id (int), nunca por texto/clave.
    - Retornos JSON-serializables: dict | list[dict] | int | float | str | bool | None.
      Decimal se transfiere como str y se reconstruye en el lado local.
    - Sin kw azúcar: los campos que afectan la firma van explícitos.
    """

    # PRESUPUESTO
    def arbol(self, extra: bool = False) -> list[dict]: ...
    def nodo_total(self, nodo_id: int) -> float: ...
    # APU
    def apu(self, nodo_id: int | None, insumo_id: int | None) -> dict | None: ...
    def resolver_matriz(self, nodo_id, insumo_id) -> tuple[int | None, str]: ...
    # INSUMOS
    def insumos(self, tipo_clave: str | None = None) -> list[dict]: ...
    def insumo_por_hash(self, hash_val: str) -> dict | None: ...
    # EXPLOSIÓN
    def explotar(self, concepto_ids: list[int], nivel: str, tipos_ids: list[int]) -> tuple[list[dict], float]: ...
    # VARIABLES / FÓRMULAS
    def variables_listar(self) -> list[dict]: ...
    def variables_resueltas(self) -> dict: ...
    # GENERADORES
    def generador_renglones(self, generador_id: int) -> list[dict]: ...
    # INDIRECTOS
    def indirectos_lista(self, tipo: str | None = None) -> list[dict]: ...
    # SOBRECOSTO / PROYECTO
    def factores_sobrecosto_obtener(self) -> dict: ...
    def proyecto_guardar(self, campos: dict) -> None: ...
    # RECÁLCULO / UNDO
    def recalcular_proyecto(self) -> dict: ...
    def deshacer(self, usuario_id: int = 1) -> bool: ...
```

(La lista se completa al migrar cada método; es el inventario de `Api`, ver §5.)

---

## 4. Reglas del protocolo

### R1 — La lógica de dominio vive UNA sola vez
Toda operación que requiera validación, transacción, recálculo o evento se
implementa en `DataService` (métodos específicos por operación, no solo CRUD
genérico). Ni `_BackendLocal`, ni `_BackendHTTP`, ni el servidor la reimplementan:
la **llaman**. Si una operación no tiene método en `DataService`, se agrega ahí
primero (regla del proyecto: `DataService` es la vía de escritura).

### R2 — `api.py` nunca bifurca por transporte
Proscrito el patrón:

```python
# ✗ PROHIBIDO
def concepto_actualizar_cantidad(...):
    if self._use_http:
        self._http().actualizar(...)
        self._http().recalcular()
        self._ds.emitir(ProyectoRecalculado(...))
        return
    with self._ds.transaccion(): ...
```

Estados permitidos de un método público en `api.py`:

```python
# ✓ DELEGADO SIMPLE (único estado que puede agregarse/refactorizarse)
def arbol(self, extra=False):
    return self._backend.arbol(extra=extra)

# ⚠ SOLO LOCAL (temporal): método con un solo camino, sin rama remota aún. Debe
#   documentar su ausencia de rama HTTP en el docstring, y migrarse.
# ✗ NOTA: sin # TODO en duda — cada método que no delegue a _backend
#   queda tanto en _BackendLocal como en _BackendHTTP al migrarse.
```

La selección de transporte es interna (`api.py::__init__` + promoción lazy en
`_http()`). Los widgets jamás tocan `_use_http`.

### R3 — SQL solo en `backend/database/repos/`
Si se necesita una consulta nueva, primero se agrega al repo correcto; luego ambos
backends la usan. Prohibido `conn.execute(...)` en `api.py`, `api_backends.py`,
`api_cliente.py` o `server/`.

### R4 — Eventos: uno por operación, post-commit, en el lado con autoridad
- **Modo local:** `DataService` emite el evento tras el commit (`_evento()`).
- **Modo red:** el **servidor** emite/broadcasta los eventos (vía WS); el cliente
  NO re-emite en su `EventBus` el evento que su propio write causó: se refresca por
  la respuesta y por `ws_client.py` recibe el resto. (Estado actual: `_BackendHTTP`
  re-emite localmente — se corrige en la Fase 4.)
- Un mismo evento no se emite dos veces (local + réplica manual). El broadcast
  WS del servidor es de eventos semánticos (`_serializar_evento`), no del `"cambio"`
  genérico actual (ver Fase 4).

### R5 — Errores de dominio en la frontera, no crudos
| Capa | Puente de dominio |
|---|---|
| Servidor → HTTP | `ValidationError`→`422`, `RepositoryError`→`500`, `DataServiceError`→`500`, body `{detail: str}` (exception handlers ya existentes). |
| `ApiCliente` → dominio | Si status∈{422,500} y body trae `detail`, lanzar la excepción de dominio correspondiente (adivinar tipo por código: 422→`ValidationError`). |

Los handlers del frontend deben poder cazar **`ValidationError`** en ambos modos
sin saber de httpx.

### R6 — Tipos de retorno JSON-serializables
`dict/list/int/float/str/bool/None`. `Decimal` se transfiere como **string** y se
reconstruye con `Decimal(...)` en `_BackendHTTP` (ya es el caso de
`variables_resueltas` — mantenerlo). `set` no viaja por HTTP: convertirlo a lista.

### R7 — La lógica de presentación no viaja al servidor
El enriquecimiento de dicts para la UI (íconos SVG, `tiene_sub_apu`, cantidades
derivadas) vive en código compartido del cliente (`_enriquecer_detalle_apu`),
porque el servidor no conoce ni debe conocer los íconos del tema.

### R8 — Simetría por commit
Un método nuevo o una firma modificada se agrega a **ambos** backends en el mismo
commit. Nunca se deja a `_BackendHTTP` a medias: si no se tiene el endpoint, se
implementa; si el endpoint no se justifica, se usa el CRUD genérico del transporte.

### R9 — `ApiCliente` es transporte, no dominio
Sus métodos `_get/_post`, `buscar/actualizar/insertar/eliminar/arbol/...` son
genéricos y reutilizables. Los métodos de dominio específicos de entidad
(`variables_crear`, `generador_renglones`, `factores_sobrecosto_obtener`...) se
migran al propio `_BackendHTTP` (que ya sabe qué endpoint llama) y se eliminan del
cliente. Regla práctica: si un método de `ApiCliente` embebe un endpoint por
operación, vive mal; el mapeo operación→endpoint es trabajo de `_BackendHTTP`.

---

## 5. Inventario actual (para la migración)

Métodos de `Api` (~78 públicos) — **estado al 2026-08-31** tras Fases 0-3:

| Estado | Cant. | Ejemplo |
|---|---|---|
| Delegado a `self._backend.x()` | **67** | todos los de dominio (presupuesto, APU, insumos, explosión, catálogos, variables, generadores, indirectos, undo) |
| Patrón legacy `if self._use_http:` inline | **0** | — (quedan solo 5 menciones infraestructura en `__init__`/`_backend`/`_http`) |
| Solo local / helpers | resto | `proyecto_actual_id`, `resumen_tipos_explosion`, `campo_valor`, `concepto_cantidad`, `unificar_matrices_apu` |

Estado inicial (2026-08-30) era 31 delegado / 40 legacy — migrados 35 métodos en 6 tandas.

---

## 6. Ruta de migración (orden obligatorio)

> Cada fase deja el programa **funcionando** en ambos modos y su propia
> definición de terminado. No saltar fases.

### Fase 0 — Interface
Declarar `ToqueApiBackend(Protocol)` en `api_backends.py` (esqueleto §3) y hacer que
`Api.__init__` lo exija (`assert isinstance(self._backend_local, ToqueApiBackend)`).
**DoD:** `api.py` solo toca `self._backend.*`, aún co-existe el legacy inline.

### Fase 1 — Dejar de re-emitir eventos en HTTP
`_BackendHTTP` elimina los `self._api._ds.emitir(...)` tautológicos tras un RPC
(excepto los que el servidor no genera aún). **DoD:** `grep -c "ds.emitir" api_backends.py`
baja drásticamente; los widgets no refrescan doble.
_Atención:_ mientras el servidor no emita eventos semánticos por WS, el cliente que
escribe se refresca por la **respuesta** del RPC; los otros clientes lo hacen por
`"cambio"` del WS (se mejora en Fase 4).

### Fase 2 — Migrar por sección los ~40 métodos legacy
Por cada **sección de dominio** (presupuesto → APU → insumos → explosión →
catálogos → gestión de proyecto):
1. La operación pasa a `DataService` si implica transacción/recálculo/evento (R1).
2. `_BackendLocal` implementa el método llamando a `DataService`/repos (sin SQL propio).
3. `_BackendHTTP` implementa el método llamando a `ApiCliente` (endpoint existente o
   CRUD genérico) y traduce errores (R5).
4. `api.py`: el método pasa a `return self._backend.<método>(...)`.
5. Correr el smoke correspondiente en ambos modos.

**DoD de cada método:** `grep "def <nombre>"` en `api.py` muestra UNA línea
delegada; `_BackendLocal` y `_BackendHTTP` tienen la misma firma; ni local ni HTTP
tienen `if`, SQL, ni `emitir` donde no corresponde.

### Fase 3 — `ApiCliente` a transporte puro
Eliminar los métodos de dominio de `ApiCliente`, fusionando su cuerpo en
`_BackendHTTP`. `ApiCliente` queda con `_get/_post/_url` + operaciones genéricas.
**DoD:** `ApiCliente` no referencia entidades con nombre (proyectos, insumos, apu,
generadores, variables, indirectos + endpoint); no sabe qué endpoint llama por
operación de dominio.

### Fase 4 — Eventos semánticos por WS
El servidor emite `_serializar_evento(evento)` de `EventBus` tras cada operación
(no el `"cambio"` genérico) y los clientes **ajenos** lo re-inyectan en su
`EventBus` (ws_client ya reemite: el protocolo exige que el emisor lo filtre).
**DoD:** en red, un cliente edita y los demás refrescan la UI sin eventos duplicados
ni disparos locales del emisor.

### Fase 5 — Prueba y limpieza
- Correr `tests/smoke_*http*.py` + los smoke del resto en local.
- Eliminar el comentario "migración en progreso" de `api.py:85` y las notas
  obsoletas del inventario.
- Actualizar AGENTS.md y este documento.

---

## 7. Definición de terminado (checklist por método)

- [ ] Firma idéntica en `_BackendLocal` y `_BackendHTTP`.
- [ ] `api.py` delega en `self._backend.*` (sin `if _use_http`).
- [ ] Operación transaccional vive en `DataService` (no en backends).
- [ ] Sin SQL fuera de `backend/database/repos/`.
- [ ] Sin `QMessageBox`, sin PySide6, sin widgets importados en el backend.
- [ ] Errores de dominio traducidos en la frontera; el widget caza excepciones de dominio.
- [ ] Retornos JSON-serializables (Decimal → str).
- [ ] Prueba funcional en modo local y modo servidor (`python -m server.servidor`).

---

## 8. Anti-patrones (NO hacer)

| Anti-patrón | Razón |
|---|---|
| Añadir otro `if self._use_http:` inline a un método de `api.py` | Duplica; regla R2 |
| Consulta `conn.execute` nueva fuera de repos | Regla R3 |
| Lógica idéntica en `_BackendLocal` y el endpoint del servidor | La hace el `DataService` una vez (R1) |
| `_BackendHTTP` que re-emite el evento que causó su propio RPC | Evento doble (R4) |
| Endpoint nuevo en `server/` que no pasa por `DataService` | Servidor = RPC fino, no lógica |
| Método de dominio embebiendo endpoints en `ApiCliente` | R9 |

---

## 9. Referencias

- Multi-usuario / plan original: `docs/planes/PLAN_MULTIUSUARIO.md`
- Fórmulas y variables (Decimal por la red): `docs/planes/PLAN_FORMULAS_VARIABLES.md`
- Reglas de código (imports, código muerto, stubs): `docs/GUIA_CODIGO.md`
- Estructura y regla cardinal: `AGENTS.md`