# Plan Multiusuario — Colaboración en tiempo real

Actualizado: 2026-07-20 18:00 (hora local)

## Arquitectura

```
Cliente PySide6 → HTTP/WS → Servidor FastAPI → SQLite (único, autoritativo)
                                ↓
                         Broadcast WS a todos los clientes
```

- **Servidor:** FastAPI + uvicorn (`server/servidor.py`). Puede ejecutarse standalone o embebido desde la app.
- **Cliente HTTP:** `ApiCliente` (`frontend/ventana/api_cliente.py`) — replica la interfaz de `Api` pero habla HTTP.
- **Cliente WS:** `WebSocketClient` (`frontend/ventana/ws_client.py`) — `QThread` que recibe eventos del servidor y los reemite en el `EventBus` local.
- **Backend dual:** `Api` ya tiene soporte para backends local y HTTP (`api_backends.py`, `_use_http` toggle).

## Decisiones de diseño

| Aspecto | Decisión |
|---|---|
| Conexión | Manual (IP:puerto ingresado por usuario) |
| Lock | Pesimista, por nodo completo del árbol |
| Timeout de lock | 30s, auto-liberación al cambiar de nodo |
| Servidor al cerrar host | Preguntar "¿seguir compartiendo en segundo plano?" |
| Proyectos por servidor | 1 ahora, futuro varios |
| Crear proyectos remotos | Host sí; servidor dedicado también |
| Identidad | Cliente envía su nombre; server rechaza duplicados |
| Puerto | Automático (SO asigna puerto libre) |
| Undo/redo | Por usuario, independiente |
| Host pide lock | Sí — todo pasa por HTTP aunque sea localhost |
| Transición local→HTTP | Al compartir, Api cambia automáticamente a modo HTTP apuntando a localhost |
| Cliente: proyectos | Uno a la vez |

## Orden de implementación

### Paso 1 — Completar backend HTTP

Añadir endpoints faltantes en `servidor.py` y sus contrapartes en `ApiCliente`.

**Endpoints a añadir:**

| Endpoint | Método |
|---|---|
| `POST /proyectos/{nombre}/apu/{comp_id}/operador` | POST |
| `POST /proyectos/{nombre}/apu/{comp_id}/valor` | POST |
| `POST /proyectos/{nombre}/apu/{comp_id}/insumo` | POST |
| `GET /proyectos/{nombre}/apu/{matriz_id}/detalle` | GET |
| `POST /proyectos/{nombre}/insumo/insertar` | POST |
| `POST /proyectos/{nombre}/insumo/hash` | POST |
| `GET /proyectos/{nombre}/indirectos` | GET |
| `POST /proyectos/{nombre}/indirectos/guardar` | POST |
| `POST /proyectos/{nombre}/indirectos/insertar` | POST |
| `POST /proyectos/{nombre}/indirectos/eliminar` | POST |
| `POST /proyectos/{nombre}/indirectos/plantilla` | POST |
| `POST /proyectos/{nombre}/indirectos/calcular` | POST |
| `GET /proyectos/{nombre}/generadores` | GET |
| `POST /proyectos/{nombre}/generadores/crear` | POST |
| `POST /proyectos/{nombre}/generadores/actualizar` | POST |
| `POST /proyectos/{nombre}/generadores/eliminar` | POST |
| `POST /proyectos/{nombre}/generadores/renglon/guardar` | POST |
| `POST /proyectos/{nombre}/generadores/renglon/eliminar` | POST |
| `POST /proyectos/{nombre}/proyecto/guardar` | POST |
| `GET /proyectos/{nombre}/proyecto` | GET |

Además: añadir `usuario` (str) a todos los requests de escritura.

**Archivos:** `server/servidor.py`, `frontend/ventana/api_cliente.py`

---

### Paso 2 — Sistema de locks en servidor

Locks pesimistas en memoria con timeout.

```
POST /proyectos/{nombre}/lock/{nodo_id}   → body: {usuario}
  → Si libre: asigna, responde {ok: true}
  → Si ocupado por otro: responde {ok: false, usuario, expires}
  → Si expirado: reasigna, responde {ok: true}

POST /proyectos/{nombre}/unlock/{nodo_id}  → body: {usuario}
  → Libera solo si es del mismo usuario

GET /proyectos/{nombre}/locks
  → Todos los locks activos: [{nodo_id, usuario, expires}]
```

WebSocket broadcast: `LockAdquirido`, `LockLiberado`.

**Archivos:** `server/servidor.py`, `frontend/ventana/api_cliente.py`

---

### Paso 3 — Botón Compartir + transición a HTTP

Botón "Compartir" (icono `share-2`) en toolbar INICIO.

Flujo:
1. Dialog: IP local detectada + puerto aleatorio, nombre del usuario, checkbox "Compartir en segundo plano"
2. Arranca servidor embebido en `0.0.0.0:0`
3. Transiciona Api de local a HTTP (localhost:puerto)
4. Conecta WebSocketClient local
5. Statusbar: "Compartiendo en [IP]:[puerto]"

**Archivos:** `frontend/ventana/mixins/toolbar.py`, `frontend/ventana/mixins/gestion_proyectos.py`, `frontend/ventana/api.py`

---

### Paso 4 — Botón Conectar

Botón "Conectar" (icono `wifi`) en toolbar PROYECTO.

Flujo:
1. Dialog: Servidor (IP:puerto), nombre de usuario
2. Cliente prueba conexión HTTP
3. Si ok: cierra proyecto local (si hay), wirea servicios con servidor_url, conecta WS
4. Statusbar: "Conectado a [IP]:[puerto] como [nombre]"

**Archivos:** `frontend/ventana/mixins/toolbar.py`, `frontend/ventana/mixins/gestion_proyectos.py`, `frontend/ventana/api.py`

---

### Paso 5 — Identidad del cliente

- `usuario` (str) en todos los requests de escritura
- Server mantiene `set` de usuarios conectados por proyecto WS
- Al conectar WS: cliente envía `{"tipo": "identidad", "usuario": "María"}`
- Server valida duplicado, responde `{ok: true/false, razon: "Nombre ya en uso"}`
- Al desconectar WS: libera nombre

**Archivos:** `server/servidor.py`, `frontend/ventana/ws_client.py`, `frontend/ventana/api_cliente.py`

---

### Paso 6 — Indicadores visuales de lock

- `QTimer` cada 5s consulta `GET /locks`
- Nodo bloqueado: icono `lock`, tooltip "Editando: María", celda read-only
- Al hacer clic: pide lock, si ocupado muestra tooltip, si libre entra en edición
- Al perder foco: POST unlock

**Archivos:** `frontend/ventana/widgets/arbol.py`, `frontend/ventana/widgets/base.py`

---

### Paso 7 — Broadcast de eventos

- Evento genérico `"cambio"` con `entidad` e `id` para refresco quirúrgico
- Cliente que hizo el cambio no recarga (ya tiene UI actualizada)
- Otros clientes recargan solo el nodo afectado

**Archivos:** `server/servidor.py`, `frontend/ventana/mixins/gestion_proyectos.py`

---

### Paso 8 — Segundo plano

- Dialog al cerrar app con servidor activo: "¿Seguir compartiendo?"
- "Sí" → lanza proceso hijo independiente (`pythonw`)
- "No" → `_stop_server()`, todos se desconectan
- Se guarda en Config para reconectar o detener al reiniciar app

**Archivos:** `frontend/ventana/mixins/gestion_proyectos.py`, `server/run_background.py` (posible)

---

## Lo que NO se hace (test MVP)

| Aspecto | Razón |
|---|---|
| Registro/login con contraseña | Solo nombre textual |
| Sync offline / merge | Cliente siempre online |
| Historial de conexiones | Solo IP actual |
| Cifrado/TLS | Solo red local confiable |
| Reconexión automática avanzada | Básico ya existe en ws_client.py |
| Varios proyectos en un server | 1 ahora |
| Pruebas unitarias del server | Manual por ahora |
