# Decisiones de diseño — Multiusuario, servidor central y Ctrl+Z

Documento vivo, complementario a `docs/DECISIONES_PENDIENTES.md`. Reúne las
decisiones tomadas para llevar Open APU Studio de app monousuario/local a
un modelo con servidor central, colaboración y deshacer/rehacer.

Formato de cada entrada:
- **Contexto** — por qué es una decisión que hay que tomar
- **Opciones consideradas** — qué se evaluó
- **Decisión** — qué se eligió y por qué
- **Consecuencias** — qué implica la decisión
- **Estado** — `✓ Decidido` / `⏳ Pendiente` / `✗ Descartado`

---

## ARQUITECTURA DE SERVIDOR

### SRV-01 — Servidor central en vez de archivo compartido en LAN

**Estado:** ✓ Decidido

**Contexto:**
`COL-02` (en `DECISIONES_PENDIENTES.md`) proponía SQLite en red vía WAL
como camino simple para colaboración en LAN. Al revisar, ese supuesto no
es confiable: el modo WAL de SQLite depende de locking que no funciona
bien sobre sistemas de archivos de red (SMB/NFS), lo que puede corromper
el `.db` compartido.

**Opciones consideradas:**
- Archivo `.db` compartido directamente por red (WAL) — descartado por el
  problema de locking arriba.
- Servidor central que es el único proceso que toca el `.db` con SQLite;
  los clientes (PySide6) le hablan por red.

**Decisión:**
Servidor central. Es el único proceso con acceso directo a SQLite; todos
los clientes acceden a través de él, nunca al archivo directamente.

**Consecuencias:**
- Resuelve el problema de WAL en red: solo un proceso, en una sola
  máquina, toca el archivo.
- `backend/` (repos, `DataService`, `EventBus`, `SchemaRegistry`) se
  convierte en el proceso servidor, con cambios de infraestructura pero
  sin rehacer la lógica de negocio.
- `frontend/ventana/api.py` deja de llamar a `DataService` en el mismo
  proceso y pasa a ser un cliente delgado que habla con el servidor.
- Ver `SRV-04` (arquitectura interna del servidor: `Database` deja de ser
  singleton, y manejo de concurrencia por conexión).

---

### SRV-02 — Transporte único: HTTP siempre, incluso en modo solo-usuario

**Estado:** ✓ Decidido

**Contexto:**
La app necesita funcionar en tres escenarios: un solo usuario sin
conexión, varios usuarios contra un servidor propio, y varios usuarios en
LAN cuando no hay internet (cada quien hostea su propio servidor). Sin
una decisión explícita, era fácil terminar manteniendo dos rutas de
escritura distintas: una local (llamando a `DataService` directo) y otra
remota (HTTP) — con el riesgo de que diverjan con el tiempo.

**Opciones consideradas:**
- Dos implementaciones de `api.py`: una local (in-process) para modo
  offline, otra HTTP para modo servidor.
- Una sola implementación: el cliente siempre habla HTTP. En modo
  offline, el servidor corre embebido/local (`http://localhost:PUERTO`)
  en vez de estar apagado.

**Decisión:**
El cliente siempre habla HTTP. La única diferencia entre offline,
"mi propio servidor" y "servidor de otro usuario en LAN" es a qué
dirección apunta el cliente — nunca qué código corre.

**Consecuencias:**
- Una sola ruta de escritura para mantener; evita que offline y online
  diverjan silenciosamente.
- El modo offline requiere levantar el servidor localmente al iniciar la
  app (embebido en el mismo proceso o como subproceso).
- El descubrimiento de servidores en LAN se resuelve por separado — ver
  `SRV-03`.

---

### SRV-03 — Descubrimiento en LAN: IP:puerto manual

**Estado:** ✓ Decidido

**Contexto:**
Si cada usuario hostea su propio servidor y otros se conectan por LAN,
hace falta que el cliente sepa a qué dirección apuntar.

**Opciones consideradas:**
- Broadcast/mDNS para descubrimiento automático en la red local.
- El host comparte su IP:puerto manualmente; el otro usuario la escribe
  en la app.

**Decisión:**
Manual. Es una fase beta; mDNS/broadcast es un subsistema adicional que
no se justifica todavía.

**Consecuencias:**
- Cero infraestructura extra que mantener por ahora.
- Requiere un campo en la UI para introducir/editar la dirección del
  servidor al que conectarse.
- Revisar más adelante si la fricción manual se vuelve un problema real
  de uso.

---

### SRV-04 — `Database` deja de ser singleton; concurrencia por conexión

**Estado:** ⏳ Pendiente (bloqueante — primer paso de implementación)

**Contexto:**
`Database` hoy es singleton de clase (`_instancia`), pensado para "un
proceso, un proyecto abierto a la vez". Un servidor central necesita
mantener varias conexiones simultáneas: distintos proyectos abiertos por
distintos equipos al mismo tiempo. Además, `sqlite3.Connection` no es
thread-safe por defecto (`check_same_thread=True`), y un servidor HTTP
normalmente atiende requests en paralelo.

**Opciones consideradas:**
- Mantener el singleton y forzar un servidor por proyecto (un proceso por
  cada `.db` abierto) — descartado, complica el despliegue sin necesidad.
- `Database` como fábrica: el servidor mantiene un
  `dict[proyecto_id, Database]`, una conexión por proyecto abierto.
- Para la concurrencia dentro de un mismo proyecto: cola de escritura por
  proyecto (single-writer, coherente con cómo funciona SQLite) en vez de
  pool de conexiones con locks explícitos.

**Decisión:**
`Database` deja de ser singleton; el servidor cachea una instancia por
proyecto abierto. Dentro de un proyecto, las escrituras se serializan
(cola por proyecto) para evitar acceso concurrente a la misma conexión.

**Consecuencias:**
- Es el cambio de infraestructura más grande y el que todo lo demás (API,
  WebSocket, historial) da por hecho — se hace primero.
- No afecta la lógica de negocio en repos/`DataService`, solo cómo se
  instancian y comparten las conexiones.
- Las lecturas pueden no necesitar la misma serialización que las
  escrituras — evaluar al implementar si vale la pena diferenciarlas.

---

### SRV-05 — Notificación de cambios entre clientes: WebSocket

**Estado:** ⏳ Pendiente

**Contexto:**
`EventBus` hoy es en memoria y por proceso — sirve para refrescar la UI
local, pero con varios clientes en procesos distintos, los eventos de un
usuario no llegan a la UI de otro.

**Opciones consideradas:**
- Polling periódico del cliente contra el servidor.
- WebSocket: el servidor reemite `EventBus.emit()` a todos los clientes
  conectados a ese proyecto.

**Decisión:**
WebSocket. El servidor hace *fan-out* de los eventos semánticos ya
existentes (`InsumoActualizado`, `ConceptoActualizado`, etc.) a los
clientes conectados al proyecto correspondiente.

**Consecuencias:**
- El cliente recibe el evento por WebSocket y lo reemite en su
  `EventBus` local — los widgets no necesitan enterarse del cambio de
  transporte, ya están suscritos a `EventBus`.
- Requiere manejar reconexión del WebSocket si se cae la red (ver
  `SRV-07`, modo offline).

---

## USUARIO Y COLABORACIÓN

### SRV-06 — Identificador de usuario de prueba, sin login real

**Estado:** ✓ Decidido

**Contexto:**
`historial`, `creado_por` y `modificado_por` necesitan un `usuario_id`
para tener sentido, pero implementar login real (`COL-01` en
`DECISIONES_PENDIENTES.md`) todavía no se justifica en esta etapa.

**Decisión:**
El cliente manda un identificador fijo por instancia (variable de
entorno, argumento al arrancar, o campo en `config.json` local). El
servidor lo acepta sin validarlo contra nada y lo usa para poblar
`creado_por`/`modificado_por`/`historial.usuario_id`, reemplazando el
`DEFAULT 1` fijo actual del schema.

**Consecuencias:**
- Cero trabajo de autenticación por ahora.
- Para que la migración a login real no obligue a tocar todo el flujo de
  escritura, `DataService.actualizar()` (y equivalentes de
  insertar/eliminar) deben recibir `usuario_id` como parámetro explícito
  desde ya, no leerlo de una constante interna.
- **Nota de seguridad:** en cuanto el servidor escuche en la red (LAN o
  internet) y no solo en `localhost`, cualquiera en esa red puede mandar
  cualquier `usuario_id`. Aceptable para uso en LAN de confianza durante
  la beta; no exponer el servidor a internet abierto sin login real.

---

### SRV-07 — Modo offline: solo proyectos no compartidos (por ahora)

**Estado:** ✓ Decidido (con extensión futura anotada)

**Contexto:**
La app debe poder usarse sin conexión para un solo usuario, y con
servidor (propio o de otro usuario en LAN) para colaborar. Hay dos
interpretaciones muy distintas de "offline" cuando el proyecto es
compartido:
1. Offline = proyectos personales, sin relación con ningún proyecto
   compartido — no hay nada que reconciliar.
2. Offline = seguir editando un proyecto *compartido* sin conexión, y
   reconciliar con los cambios de otros al reconectar — esto es sync
   offline-first con resolución de conflictos entre SQLite divergentes,
   un problema de tamaño comparable a otro proyecto completo.

**Decisión:**
Por ahora, opción 1: offline es exclusivamente para proyectos no
compartidos. La opción 2 (reconciliación) queda anotada para evaluarse a
futuro, no descartada.

**Consecuencias:**
- Evita construir un sistema de sync/merge antes de tener el servidor
  básico funcionando y probado con usuarios reales.
- Para no cerrar la puerta a la opción 2 más adelante, el identificador
  de un proyecto no debe depender únicamente del `id INTEGER
  AUTOINCREMENT` local — dos proyectos offline de dos usuarios distintos
  podrían coincidir en `id=1` sin ser el mismo proyecto. Por ahora basta
  con que el nombre de archivo (`D60JALISCOT.db`) siga siendo el
  identificador humano-legible; no hace falta UUID todavía, pero
  conviene tenerlo presente al diseñar cómo se crean/nombran proyectos.

---

## CTRL+Z / HISTORIAL

### SRV-08 — `HistorialDB`: pila por usuario, con invalidación cruzada en recálculo

**Estado:** ✓ Decidido (pendiente de implementar)

**Contexto:**
`FE-02` (en `DECISIONES_PENDIENTES.md`) ya define la interfaz
`Historial` con `HistorialMemoria` (MVP) migrable a `HistorialDB`
(multiusuario). Falta definir la regla de qué pasa cuando un recálculo
en cascada (`ProyectoRecalculado`) ocurre mientras hay cambios
pendientes de deshacer — sin regla, cualquier edición casi siempre
dispara recálculo, y "borrar el historial en cada recálculo" a secas
dejaría el Ctrl+Z inútil casi siempre, incluso para la propia acción que
el usuario acaba de hacer.

**Opciones consideradas:**
- Borrar todo el historial del proyecto en cada recálculo, sin importar
  quién lo disparó — descartado, deja el undo casi siempre vacío.
- Pila de undo por usuario (`historial.usuario_id`, ya soportado por el
  schema). Cuando el usuario A dispara un recálculo, se borra la pila de
  **los demás** usuarios, pero no la de A — su recálculo es justamente
  la consecuencia de su propia última acción, que sigue en el tope de su
  pila.

**Decisión:**
Pila de undo por usuario, con invalidación cruzada: un recálculo limpia
el historial de todos los usuarios *excepto* el que lo disparó.

**Consecuencias:**
- Evita el caso de que nadie pueda deshacer nunca.
- Simple de razonar: no hace falta rastrear qué nodos específicos tocó el
  recálculo, ni intentar mezclar/rebasar cambios de distintos usuarios.
- Requiere que `ProyectoRecalculado` incluya `usuario_id` (hoy solo lleva
  `proyecto_id`) para que el handler que limpia historial sepa a quién no
  debe tocarle la pila.
- El recálculo (`RecalculoRepo.recalcular_proyecto()`) ya es idempotente
  — siempre recalcula desde los valores crudos guardados, nunca acumula
  sobre sí mismo — así que restaurar el valor anterior y volver a llamar
  recálculo es seguro. Confirmado al revisar el código; no requiere
  cambios.
- "Borrar" en la práctica: marcar como consumidas o eliminar las filas de
  `historial` de ese proyecto para los `usuario_id` distintos al que
  disparó el recálculo.

---

### SRV-09 — Captura de estado anterior dentro de la transacción

**Estado:** ✓ Decidido (pendiente de implementar)

**Contexto:**
`DataService.actualizar()` hoy hace `repo.update()` y luego
`repo.buscar()` — el registro que obtiene ya está post-cambio. Para
poblar `historial.valor_anterior` hace falta leer el registro **antes**
del `UPDATE`, dentro de la misma transacción.

**Decisión:**
Pendiente de implementar como parte de `SVC-01`: `DataService.actualizar()`
lee el registro antes de `repo.update()`, y usa ambos estados
(anterior/nuevo) para escribir en `historial` antes del commit.

**Consecuencias:**
- Depende de que `SVC-01` esté cerrado (toda escritura pasa por
  `DataService`) — si `api.py` conserva caminos que escriben SQL
  directo, esas ediciones quedan invisibles para el historial y rompen
  el Ctrl+Z de forma silenciosa. Ejemplo concreto ya detectado:
  `insumo_actualizar_campo` en `api.py`, que emite `ProyectoRecalculado`
  sin hacer commit cuando `campo != "costo_final"` — con historial
  activo, ese evento falso dispararía la invalidación cruzada de
  `SRV-08` por un cambio que ni siquiera se guardó.
- Una "acción" del usuario no siempre es un solo campo (recálculo en
  cascada toca varios registros). El campo `sesion` (UUID) de la tabla
  `historial` ya está pensado para agrupar esto, pero `DataService`
  necesita una forma explícita de abrir "una sesión de undo" que envuelva
  varias llamadas a `actualizar()` como una sola acción deshacible.

---

### SRV-10 — Se salta `HistorialMemoria`: implementar `HistorialDB` directamente

**Estado:** ✓ Decidido

**Contexto:**
`FE-02` diseñó `HistorialMemoria` (pila en memoria, se pierde al cerrar la
app) como MVP, migrable después a `HistorialDB` cuando "llegara" el
multiusuario — en su momento, ambas cosas estaban separadas en el tiempo.
Con la decisión de ir directo a servidor central (`SRV-01`), el
multiusuario ya no es una fase futura: es la base desde el primer
`DataService` que se escriba.

**Opciones consideradas:**
- Implementar `HistorialMemoria` primero (como decía `FE-02` original) y
  migrar a `HistorialDB` después — descartado: implementar la interfaz en
  memoria para luego reemplazarla sería trabajo que se tira, ya que el
  servidor no tiene "memoria de proceso" compartida entre clientes de la
  misma forma que tenía la app de escritorio monousuario.
- Implementar `HistorialDB` directamente, usando la tabla `historial` que
  el schema ya provee.

**Decisión:**
Se implementa `HistorialDB` directamente. `HistorialMemoria` no se
construye — queda como referencia histórica del diseño original en
`FE-02`, pero no se escribe código para ella.

**Consecuencias:**
- La interfaz abstracta `Historial` (`registrar`, `deshacer`, `rehacer`,
  `puede_deshacer`, `puede_rehacer`) definida en `FE-02` se mantiene tal
  cual — sigue siendo el contrato correcto, solo cambia cuál
  implementación se escribe primero.
- Evita mantener dos implementaciones (memoria + DB) en algún punto de
  transición.
- El modo offline (`SRV-07`) también usa `HistorialDB` — el servidor
  embebido local escribe en la misma tabla `historial` de su propio
  `.db`, sin necesidad de una variante en memoria para ese caso.

---

### SRV-11 — Servidor embebido en modo offline: subprocess, lanzado al abrir proyecto

**Estado:** ✓ Decidido

**Contexto:**
`SRV-02` establece que el cliente siempre habla HTTP, incluso offline —
pero no definía cuándo ni cómo se levanta ese servidor local.

**Opciones consideradas:**
- Hilo dentro del mismo proceso de la app PySide6 — descartado: obliga a
  mantener una segunda forma de correr el servidor, distinta a como corre
  en modo remoto, con el riesgo de que diverjan.
- Subprocess separado, usando el mismo entry point/binario que el
  servidor "real", con un flag que lo limita a escuchar solo en
  `localhost`.

**Decisión:**
Subprocess, lanzado al abrir un proyecto (no al arrancar la app). Mismo
código que el servidor standalone, con un flag `--embedded` (o
equivalente) que restringe el bind a `localhost`.

**Consecuencias:**
- Una sola implementación de servidor para los tres modos (offline,
  propio, LAN) — solo cambia cómo se invoca.
- Si el usuario solo lista proyectos sin abrir ninguno, no hay servidor
  corriendo — evita procesos innecesarios.
- Requiere manejo explícito de ciclo de vida del subprocess — ver
  `SRV-13`.

---

### SRV-12 — Puerto por defecto con fallback automático

**Estado:** ✓ Decidido

**Contexto:**
Sin definir el puerto, es común que choque (dos proyectos abiertos,
reinicio rápido tras un crash que no liberó el puerto anterior).

**Decisión:**
El subprocess intenta un puerto fijo por defecto; si está ocupado, pide
al sistema operativo uno libre (bind a `0`) y lo comunica al proceso
padre (el cliente PySide6, que lo capturó como subprocess) vía stdout.
El cliente nunca asume el puerto default a ciegas — siempre lee el
puerto real que el subprocess reporta.

**Consecuencias:**
- Evita que abrir un segundo proyecto (o reintentar tras un crash) falle
  por puerto ocupado.
- El protocolo de arranque del subprocess debe imprimir el puerto de
  forma parseable (por ejemplo, una línea `PUERTO:XXXXX` al inicio de
  stdout) antes de aceptar conexiones.

---

### SRV-13 — Apagado ordenado del servidor embebido

**Estado:** ✓ Decidido

**Contexto:**
Si el cliente cierra la app sin apagar el subprocess de forma ordenada,
puede quedar el `.db` con un lock de SQLite colgado, o el proceso
huérfano corriendo.

**Decisión:**
Hook en el evento de cierre de la ventana principal: `terminate()` al
subprocess del servidor embebido, esperar un timeout corto, `kill()` si
no respondió a tiempo.

**Consecuencias:**
- Requiere que el punto de cierre de `main.py`/`ventana.py` conozca la
  referencia al subprocess lanzado en `SRV-11` para poder señalizarlo.
- Un crash de la app (no un cierre ordenado) puede seguir dejando el
  subprocess huérfano — aceptable para la beta, no se resuelve con
  supervisor de procesos por ahora.

---

### SRV-14 — Promoción de proyecto offline a compartido: subir el `.db` completo

**Estado:** ✓ Decidido

**Contexto:**
`SRV-07` define offline como exclusivo para proyectos no compartidos,
pero no había ruta definida para el caso inverso: alguien empieza un
proyecto offline y luego quiere compartirlo en el servidor de otro
usuario (o en el propio, expuesto a la LAN).

**Opciones consideradas:**
- Sync granular / merge contra un proyecto existente en el servidor —
  descartado, es el mismo problema de fondo que la opción 2 de `SRV-07`
  (reconciliación), que se decidió posponer.
- Subir el archivo `.db` completo a un endpoint del servidor destino, que
  lo valida contra el schema y lo coloca como proyecto nuevo.

**Decisión:**
Subir el `.db` completo (`POST /proyectos/importar` o equivalente). Es
coherente con el modelo "documento" que la app ya tiene (`BD-01`/`BD-02`)
— pasar de "mi copia local" a "la copia del servidor" es una operación de
una sola vía, no una fusión.

**Consecuencias:**
- No requiere resolver merge/conflictos — es exactamente la misma
  operación que hoy sería "copiar el archivo a otra máquina", solo que
  automatizada por un endpoint.
- El proyecto offline original queda como una copia local separada tras
  la promoción — no se sincroniza automáticamente con la versión ahora
  compartida (eso sería la opción 2 de `SRV-07`, fuera de alcance).
- El endpoint debe validar el schema del `.db` subido antes de aceptarlo,
  ya que no hay migraciones formales (decisión ya tomada) y un `.db` de
  una versión anterior de la app podría no coincidir con el schema del
  servidor destino.

---

## SIN CAMBIOS RESPECTO A `DECISIONES_PENDIENTES.md`

Para referencia rápida, estas decisiones previas se mantienen tal cual:

- **`BD-01`** (un `.db` por proyecto) — sigue firme; ahora el archivo vive
  en la máquina que hostea el servidor.
- **Migraciones de schema** — se decide explícitamente **no** construir
  un sistema de migraciones formal mientras la app esté en beta y el
  schema siga cambiando en cada iteración. El trato con quien prueba la
  app: al cambiar el schema, borrar y reimportar el `.db` de prueba. Esto
  es intencional para no generar código de migración que se vuelve
  basura antes de estabilizar el modelo de datos — se revisita cuando
  haya datos reales de usuarios finales que no se puedan simplemente
  borrar.
- **`SVC-01`** (todo pasa por `DataService`) — sigue siendo prerequisito
  bloqueante, ahora con más motivo: ver `SRV-09`.
- **`COL-01`/`COL-03`** (login real, permisos) — siguen pendientes,
  deliberadamente pospuestos por `SRV-06`.

---

*Última actualización: Julio 2026*
