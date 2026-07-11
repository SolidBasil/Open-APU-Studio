# Ruta de implementación — Servidor central, multiusuario y Ctrl+Z

Complementa `docs/DECISIONES_MULTIUSUARIO.md` (el *qué* y el *por qué*).
Este documento es el *cómo* y *en qué orden* — pensado como "esqueleto
caminante": validar la arquitectura completa en miniatura antes de
invertir en las partes de mayor volumen de trabajo.

Cada fase indica: objetivo, qué construir, archivos que toca, cómo saber
que está lista, y riesgos/cosas a vigilar específicas de este código.

---

## Fase 0 — Antes de escribir código de servidor

No es una fase de implementación, es una checklist de precondiciones.
Saltarla no bloquea, pero cualquier cosa marcada aquí que se ignore va a
reaparecer como bug confuso más adelante, ya con más capas encima.

- [ ] Confirmar que `RecalculoRepo.recalcular_proyecto()` sigue siendo
      puramente idempotente (recalcula desde valores crudos, no acumula)
      antes de tocarlo. Es un supuesto del que depende todo el diseño de
      Ctrl+Z (`SRV-08`, `SRV-09`). Si alguien lo modifica en paralelo,
      re-verificar.
- [ ] Tener claro que **no** se va a construir sistema de migraciones
      (decisión ya tomada). Esto significa: cualquier cambio de schema
      durante las fases siguientes (por ejemplo, si se necesita una
      columna nueva) implica borrar y reimportar `.db` de prueba, no
      escribir un script de migración.
- [ ] Tener un proyecto de prueba con datos representativos (varios
      niveles de árbol, algún insumo compuesto anidado) — el recálculo en
      cascada solo se valida de verdad con un árbol no trivial.

---

## Fase 1 — Cerrar `SVC-01`: toda escritura pasa por `DataService`

**Objetivo:** que no exista ningún camino de escritura que no pase por
`DataService.actualizar()/insertar()/eliminar()`. Es la base de todo lo
demás — el historial (`SRV-09`) y la fiabilidad del servidor dependen de
que este sea el único punto de entrada.

**Qué hacer:**
- Auditar `frontend/ventana/api.py` (762 líneas) método por método:
  cualquiera que ejecute SQL directo o llame a un repo sin pasar por
  `DataService` se migra.
- Arreglar el bug ya conocido: `insumo_actualizar_campo` emite
  `ProyectoRecalculado` **sin commit** cuando `campo != "costo_final"`.
  Este es el ejemplo concreto de por qué esta fase es bloqueante — con
  historial activo más adelante, ese evento falso dispararía la
  invalidación cruzada de `SRV-08` por un cambio que ni siquiera se
  guardó.
- Revisar `frontend/ventana/apu/explosion.py:125` (finding `#22b` del
  audit): accede a `self._api._resolver_matriz()`, un método privado.
  No es bloqueante para esta fase, pero si se toca `api.py` de todos
  modos, es buen momento para quitar el prefijo `_` y resolverlo de paso.

**No hacer todavía:** no tocar `Database`, no levantar servidor, no
escribir historial. Esta fase se valida 100% en modo monousuario local,
tal como funciona la app hoy.

**Cómo validar que está lista:**
- Buscar en el repo cualquier `sqlite3` o `conn.execute` fuera de
  `backend/database/repos/` y `backend/database/services/` — no debería
  quedar ninguno en `frontend/`.
- Probar el flujo que tenía el bug (editar un campo de insumo distinto a
  `costo_final`) y confirmar que el cambio persiste tras cerrar y volver
  a abrir el proyecto.

**Riesgo específico:** al migrar métodos de `api.py`, es fácil que alguno
dependa de un efecto secundario que `DataService` no reproduce todavía
(por ejemplo, algún caso de recálculo parcial). Ir método por método y
probar cada uno en la UI antes de pasar al siguiente, no migrar todos de
un jalón.

---

## Fase 2 — `Database` sin singleton (versión mínima)

**Objetivo:** que `Database` se pueda instanciar más de una vez sin
pisarse, como precondición para que un servidor la use. **Versión
mínima** — no resolver todavía concurrencia entre varios proyectos ni
cola de escritura (eso es `SRV-04` completo, Fase 9).

**Qué hacer:**
- En `backend/database/db.py`, quitar la dependencia de
  `Database._instancia` como único punto de acceso. La forma más simple:
  mantener `Database.abrir(db_path)` devolviendo una instancia nueva en
  vez de reutilizar el singleton, y que quien la use (por ahora, el
  propio servidor de la Fase 3) sea responsable de guardarla.
- Revisar todo lugar que hoy llama `Database.instancia()` o
  `Database.cerrar()` asumiendo un singleton global (probablemente en
  `main.py` y en los handlers de `frontend/ventana/handlers/
  gestion_proyectos.py`) y decidir, caso por caso, si ese código sigue
  siendo válido en modo "app de escritorio pura" o si ya debe hablarle al
  servidor local en su lugar.

**Cómo validar que está lista:**
- Poder crear dos instancias de `Database` en el mismo proceso apuntando
  a `.db` distintos, sin que una interfiera con la otra (prueba unitaria
  simple, no hace falta UI todavía).

**Riesgo específico:** este es el cambio con más superficie de "romper
algo que no se ve a simple vista", porque el singleton probablemente se
usa implícitamente en varios lugares (`Config.guardar_ultimo_proyecto`,
por ejemplo, se dispara dentro de `_abrir()`). Revisar `db.py` completo
línea por línea antes de tocarlo, no solo la clase `Database`.

---

## Fase 3 — Servidor HTTP mínimo: un solo endpoint

**Objetivo:** probar que el transporte funciona de punta a punta antes
de construir nada más. Un único endpoint, sin autenticación, sin
WebSocket, sin historial.

**Qué hacer:**
- Proceso nuevo (por ejemplo `server/main.py`, fuera de `frontend/` y
  `backend/` para no mezclar capas) con FastAPI.
- Un endpoint: `POST /proyectos/{id}/actualizar` que reciba
  `{entidad, registro_id, campos}`, abra/reutilice el `Database` del
  proyecto (Fase 2), y llame al `DataService.actualizar()` que ya
  existe sin modificarlo.
- Correr el servidor en `localhost` para las pruebas de esta fase.
- Aunque en esta fase todavía se corre manualmente (no como subprocess
  embebido), conviene construirlo ya con el protocolo de arranque que
  asume `SRV-12`: imprimir el puerto real por stdout al iniciar, en vez
  de asumir uno fijo — así la Fase 4 no tiene que rediseñar esa parte.
- **Detalle técnico a prever:** `uvicorn.run(app, host="127.0.0.1",
  port=0)` — el atajo obvio para "que el SO elija puerto libre" — no
  sirve para esto: bloquea el hilo y no expone el socket antes de
  arrancar, así que no hay forma sencilla de leer el puerto real para
  imprimirlo. Hace falta la API de bajo nivel: `uvicorn.Config` +
  `uvicorn.Server`, arrancar el server en un hilo/task, y leer
  `server.servers[0].sockets[0].getsockname()[1]` una vez que el socket
  ya está bindeado, antes de imprimir la línea `PUERTO:XXXXX` por
  stdout.

**Cómo validar que está lista:**
- Con `curl` o similar, mandar un request y confirmar en el `.db` (por
  fuera de la app) que el valor cambió. No hace falta la UI todavía.

**Riesgo específico:** decidir aquí, aunque sea provisionalmente, el
formato de error HTTP para `ValidationError`/`RepositoryError`/
`ConflictError` (ya definidas en `backend/database/exceptions.py`). No
hace falta la lógica de conflicto todavía, pero si el formato de
respuesta de error se define bien desde este endpoint mínimo, los
siguientes no tienen que rediseñarlo.

---

## Fase 4 — Un método de `api.py` como cliente HTTP

**Objetivo:** cerrar el primer ciclo completo UI → servidor → SQLite →
respuesta → UI, con el mínimo alcance posible.

**Qué hacer:**
- Elegir el método más simple y ya usado en la UI (candidato natural:
  actualizar cantidad o precio de un insumo, que ya es el ejemplo que
  usamos para razonar el bug de la Fase 1).
- Cambiar solo ese método en `frontend/ventana/api.py` para que haga el
  request HTTP de la Fase 3 en vez de llamar a `DataService` en el mismo
  proceso.
- Correr la app apuntando a `localhost:PUERTO` (servidor de la Fase 3
  corriendo aparte) y editar esa celda desde la UI real.
- Es en esta fase donde conviene implementar de una vez el arranque del
  servidor embebido como subprocess (`SRV-11`) en vez de seguir
  corriéndolo a mano — así el ciclo completo (abrir proyecto → subprocess
  arranca → cliente lee el puerto real vía stdout, `SRV-12` → conecta)
  queda probado antes de extender al resto de métodos en la Fase 5.
- Implementar también el apagado ordenado (`SRV-13`) al cerrar la
  ventana principal, aunque sea en su forma más simple — dejarlo para
  después hace más probable que se te olvide y termines depurando `.db`
  bloqueados sin relación aparente con el bug real.

**Cómo validar que está lista:**
- El flujo de edición en la UI se comporta exactamente igual que antes,
  pero ahora con el servidor de por medio — mismo recálculo visible,
  mismo refresco de la tabla.

**Riesgo específico:** este es el punto donde se descubre si el
`EventBus` local necesita algo especial para seguir refrescando la UI
sin WebSocket todavía (en esta fase, sin fan-out entre clientes, el
propio cliente que hizo el cambio debe poder refrescar su propia UI a
partir de la respuesta HTTP directa, no del evento). Si esto no
funciona limpio, es una señal temprana de que el diseño de `SRV-05`
necesita ajuste antes de escalarlo.

---

## Fase 5 — Extender el resto de `api.py`

**Objetivo:** que ningún método de `api.py` llame a `DataService`
in-process; todos pasan por HTTP.

**Qué hacer:**
- Repetir el patrón de la Fase 4 para el resto de métodos de escritura.
- Aprovechar para unificar: probablemente conviene un cliente HTTP
  pequeño y compartido (una clase `ApiCliente` con `get/post`) en vez de
  repetir manejo de requests en cada método.

**Cómo validar que está lista:**
- Recorrer manualmente los flujos principales de la UI (edición de
  árbol, insumos, notas si ya existen) contra el servidor.

**Riesgo específico:** los métodos de solo lectura (listar proyectos,
obtener árbol completo) también deben decidir si pasan por HTTP o si se
mantiene alguna lectura local directa para modo offline. Mantener la
regla de `SRV-02` (siempre HTTP, incluso offline) evita tener que
decidirlo método por método.

---

## Fase 6 — Usuario de prueba (`SRV-06`)

**Objetivo:** que cada request lleve un `usuario_id`, reemplazando el
`DEFAULT 1` fijo del schema.

**Qué hacer:**
- Definir de dónde sale el identificador en el cliente (variable de
  entorno o campo en `config.json` local, según se decidió en
  `SRV-06`).
- Agregar `usuario_id` como parámetro explícito en
  `DataService.actualizar()/insertar()/eliminar()` — no leerlo de una
  constante interna, para que el día que llegue login real solo cambie
  *de dónde sale* el valor.
- El servidor lo recibe en cada request (ya sea en el body o en un
  header) y lo pasa tal cual, sin validarlo contra nada.

**Cómo validar que está lista:**
- Confirmar en `historial`/`creado_por`/`modificado_por` que el valor
  que llega desde el cliente es el que queda persistido.

**Riesgo específico:** ninguno grande — es intencionalmente la fase más
barata. El único cuidado es no exponer el servidor a una red no
confiable en este estado (nota de seguridad ya documentada en
`SRV-06`).

---

## Fase 7 — WebSocket (`SRV-05`)

**Objetivo:** que los cambios de un usuario aparezcan en la UI de otro
sin recargar.

**Qué hacer:**
- Endpoint WebSocket en el servidor, por proyecto (`/proyectos/{id}/ws`).
- El servidor reemite los eventos semánticos existentes
  (`InsumoActualizado`, `ConceptoActualizado`, etc. — ya definidos en
  `backend/database/event_bus.py`) a todos los clientes conectados a ese
  proyecto, después del commit.
- El cliente PySide6 recibe el evento por WebSocket y lo vuelve a emitir
  en su `EventBus` local — los widgets ya están suscritos ahí desde
  antes, no deberían necesitar cambios.
- Manejar reconexión: si el WebSocket se cae, reintentar; mientras tanto
  el cliente sigue pudiendo escribir por HTTP (que es independiente del
  WebSocket), solo deja de recibir actualizaciones en vivo de otros
  usuarios hasta reconectar.

**Cómo validar que está lista:**
- Dos instancias de la app (o dos perfiles de prueba) contra el mismo
  servidor y mismo proyecto; editar en una y confirmar que la otra
  refresca sin acción manual.

**Riesgo específico:** esta es la primera fase donde de verdad hay dos
clientes escribiendo al mismo proyecto. Es el momento de observar si
aparecen problemas de escritura concurrente aunque `SRV-04` completo
(Fase 9) todavía no esté — con solo dos personas de prueba, un
`RepositoryError` ocasional es tolerable y da información real de dónde
aprieta, antes de diseñar la cola de escritura definitiva.

**Nota — buen momento para `SRV-14`:** con dos usuarios de prueba y
WebSocket funcionando, esta fase es también la ocasión natural para
implementar la promoción de proyecto offline → compartido (subir el
`.db` completo al servidor). No es prerequisito técnico de nada de esta
fase, pero probarlo aquí aprovecha que ya hay un segundo cliente
disponible para confirmar que el proyecto promovido se ve igual desde
ambos lados.

---

## Fase 8 — Ctrl+Z (`SRV-08`, `SRV-09`, `SRV-10`)

**Objetivo:** deshacer/rehacer funcionando contra `HistorialDB`,
directamente (sin pasar por `HistorialMemoria`, según `SRV-10`).

**Qué hacer, en este orden:**
1. **`SRV-09` primero:** modificar `DataService.actualizar()` para leer
   el registro *antes* del `UPDATE`, dentro de la misma transacción, y
   escribir la fila en `historial` (tabla ya existente en el schema)
   antes del commit.
2. **Sesión de undo:** dar a `DataService` una forma explícita de
   agrupar varias llamadas bajo un mismo `sesion` (UUID) — necesario
   para que un recálculo en cascada se deshaga como una sola acción, no
   campo por campo.
3. **`SRV-08`:** agregar `usuario_id` al evento `ProyectoRecalculado`
   (hoy solo lleva `proyecto_id`), e implementar el handler que, al
   recibir ese evento, borra/marca como consumido el `historial` de
   todos los `usuario_id` distintos al que disparó el recálculo.
4. Implementar `HistorialDB.deshacer()`/`rehacer()`: aplican
   `valor_anterior`/`valor_nuevo` vía `DataService.actualizar()` (no SQL
   directo, para que el propio undo también quede registrado en
   `historial` y también dispare recálculo si corresponde) y luego
   llaman a `RecalculoRepo.recalcular_proyecto()` para que los totales en
   cascada queden consistentes — nunca restaurar el valor crudo sin
   volver a recalcular.
5. Endpoints HTTP: `POST /proyectos/{id}/deshacer` y `/rehacer`,
   recibiendo `usuario_id`.

**Cómo validar que está lista:**
- Editar un campo que dispare recálculo en cascada, deshacer, confirmar
  que tanto el campo como los totales del árbol vuelven al estado
  anterior.
- Con dos usuarios de prueba: A edita y recalcula, B tenía algo
  pendiente de deshacer → confirmar que la pila de B se limpió y la de A
  sigue disponible.

**Riesgo específico:** el orden 1→2→3→4 importa — implementar el undo
(`paso 4`) antes de tener la captura de estado anterior (`paso 1`) no
tiene con qué trabajar. Es tentador saltar directo a "hacer que el botón
Ctrl+Z funcione" porque es la parte visible, pero sin los pasos previos
va a deshacer datos incompletos o inconsistentes.

---

## Fase 9 — `SRV-04` completo: concurrencia real entre proyectos

**Objetivo:** el servidor soporta varios proyectos abiertos a la vez y
varias escrituras concurrentes al mismo proyecto sin corromper estado.
Se deja para el final a propósito — con tráfico real de las fases
anteriores ya se sabe dónde aprieta de verdad, en vez de diseñarlo en
abstracto.

**Qué hacer:**
- Cola de escritura por proyecto (single-writer), en vez de pool de
  conexiones con locks explícitos — más simple y coherente con cómo
  funciona SQLite.
- Confirmar que `sqlite3.Connection` no cruza threads sin control
  (`check_same_thread`) y que la cola respeta eso.
- Decidir si las lecturas necesitan la misma serialización que las
  escrituras (probablemente no, pero validar con las fases anteriores ya
  corriendo).

**Cómo validar que está lista:**
- Prueba de carga simple: varios requests de escritura concurrentes al
  mismo proyecto, confirmar que no se pierde ninguno y que no hay
  bloqueos indefinidos.

**Riesgo específico:** si en las fases 1-8 no apareció ningún síntoma de
concurrencia (por ejemplo, con solo dos usuarios de prueba en Fase 7),
es fácil subestimar esta fase. No saltarla solo porque "no dio
problemas" con poco tráfico — el objetivo explícito es que aguante más
de dos usuarios reales.

---

## Cosas transversales a vigilar en todas las fases

- **No introducir SQL directo en `frontend/`** en ningún punto de este
  proceso — sería repetir exactamente el problema que `SVC-01` (Fase 1)
  buscaba cerrar.
- **No mantener dos rutas de escritura** (local + HTTP) más tiempo del
  necesario para probar cada fase — apenas un método funcione por HTTP,
  borrar su versión in-process, no dejarla "por si acaso".
- **Cada fase se prueba con la app real**, no solo con requests sueltos
  — el objetivo de ir por fases pequeñas es justamente encontrar
  fricciones de integración temprano.
- **Nada de migraciones de schema** durante todo este proceso (decisión
  ya tomada) — cualquier cambio de columna implica borrar y reimportar
  el `.db` de prueba.

---

*Última actualización: Julio 2026*
