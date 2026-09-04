# Guía de deuda técnica — Open APU Studio

Actualizado: 2026-09-04 (hora local)

Basada en análisis del código (rama `main`) + auditorías internas del repo
(`docs/DUPLICACION_Y_DEUDA.md`, `docs/PLAN_REPARACION.md`) contrastadas
contra el código real. Cada punto incluye ubicación y cómo tratarlo.

---

## 1. Código muerto

| # | Punto | Dónde | Cómo tratarlo |
|---|-------|-------|----------------|
| 1.1 | `usuario_id` recibido pero nunca reenviado a `DataService` | ~~`api.py:658,696,720,746,800` (5 métodos)~~ | **RESUELTO (2026-09-04). El sistema SÍ es multiusuario → forward conectado** en los 5 métodos de insumos: `_BackendLocal` pasa `usuario_id` a `ds.actualizar/insertar`; `_BackendHTTP` lo manda por `cliente.actualizar/insertar` o en el body de `/actualizar_y_recalcular`. `usuario_id` ya no se descarta: el historial atribuye el cambio al usuario correcto. Regresión cubierta por `tests/test_historial.py::test_usuario_id_se_reenvia_a_historial` (path local) y `test_usuario_id_viaja_por_red` (path HTTP con cliente espía). Pendiente menor: `eliminar_insumo` siguen sin `usuario_id` (fuera del scope de los 5 métodos). |
| 1.2 | `DataService.reasignar_generador()` — completo y correcto, sin llamadores | ~~`data_service.py:476`~~ | **RESUELTO (2026-09-04). Cableado a la UI** en el panel de renglones de cada generador: botón "Vincular" con "Asignar a concepto…" (selector `DialogoSeleccionarConcepto`) y "Desvincular (Extraordinario)". Confirmación QMessageBox si el concepto destino/saliente tiene cantidad != 0. Protocolo 77→78 (`Api.generador_reasignar`), `_BackendLocal`→`ds.reasignar_generador`, `_BackendHTTP`→`POST /generadores/{id}/reasignar`. Regresión en `test_generadores_http.py` (paridad local-HTTP) y `test_generador_historial.py` (handlers + diálogo vacío). Ver `docs/GUIA_GENERADOR_OBRA.md` §4.1. |
| 1.3 | `iniciar_sesion()`/`cerrar_sesion()` sin llamar — el undo no agrupa operaciones batch | `data_service.py:62-69` | Cablear en el flujo de edición batch para que un Ctrl+Z deshaga la operación completa, no campo por campo. |
| 1.4 | `DiagnosticoRepo.estadisticas()` / `resumen_integridad()` no llamadas donde su docstring dice que deberían | `diagnostico.py` | **Resuelto (2026-09-04).** `estadisticas()` se cableó al tab "General" del diálogo de información (`Api.estadisticas_proyecto()` → protocolo → `_BackendLocal`/`_BackendHTTP` → `GET /estadisticas`), mostrando nodos/conceptos/insumos/componentes APU. `resumen_integridad()` (y sus helper `nodos_huerfanos()`/`totales_desincronizados()`) se eliminaron — eran huérfanos y `nodos_huerfanos()` tenía además un bug latente (su subconsulta no filtraba por `proyecto_id`). `core.py` docstring actualizado. Protocolo 76→77. Suite 117/117. | — |
| 1.5 | Subsistema CAD/estructural huérfano completo (682 líneas fork de `toolbar.py` + viewport 3D + sidebar + repo OpenSees + 5 helpers CAD) | `toolbar_estructural.py`, `widgets/viewport3d.py`, `widgets/sidebar_estructura.py`, `backend/motor/opensees_repo.py`, `cad/{calibracion,panel_capas,filtro_nombres,agregacion,busqueda_texto}.py` | **Decisión de producto, no técnica.** Si no está en roadmap a corto plazo: eliminar (es la limpieza de mayor impacto/línea del repo). Si sí: crear ticket de "conectar" con fecha, o quedará como deuda perpetua. |
| 1.6 | `push_undo()` nunca llamado desde `mixins/generador.py` → botón "Deshacer" del panel CAD siempre deshabilitado | `cad/undo_stack.py` | No es código muerto sino incompleto — cablear la llamada donde se dibuja/anota en el panel CAD. |
| 1.7 | ~15 imports sin uso detectados vía análisis estático (pyflakes), no listados en la auditoría interna | `widgets/base.py`, `widgets/arbol.py`, `widgets/apu.py`, varios `mixins/*.py` (`QMessageBox`, `QApplication`, `QColor`, `QPoint`, etc.) | Bajo esfuerzo, alto volumen. Correr `pyflakes` o `ruff --select F401` en CI y limpiar en un solo PR mecánico. |
| 1.8 | Import local de `ToqueApiBackend` dentro de `__init__` usado luego como type hint fuera de ese scope | **Corregido (2026-09-04).** `ToqueApiBackend` ahora se importa bajo `TYPE_CHECKING` a nivel módulo (los type hints locales son strings con `from __future__ import annotations`), manteniendo el import runtime local en `__init__` para evitar un ciclo: probé mover el import runtime completo a nivel módulo y eso disparó un segfault reproducible en `test_filtro_local.py:52` (carrera de teardown Qt al importar `httpx`/`api_backends` antes que el primer `QApplication`) — revertido y documentado aquí para no reintroducirlo. Suite estable 114/114 (3 corridas seguidas). | — |

---

## 2. Sobreingeniería

| # | Punto | Dónde | Cómo tratarlo |
|---|-------|-------|----------------|
| 2.1 | Subsistema CAD/3D construido y nunca activado (ver 1.5) | Mismo listado de arriba | Mismo fix: decidir retomar o eliminar. Es el ejemplo más claro de esfuerzo invertido sin uso. |
| 2.2 | SQL crudo (6 `.execute()`, 2 `commit()`) directamente en la capa de fachada `Api`, violando la regla propia del proyecto ("SQL solo vive en repos") | `api.py` — método `unificar_matrices_apu()`, líneas 262-621 | Extraer las consultas a métodos nuevos en los repos correspondientes, siguiendo el patrón ya usado en el resto de `api.py`. |
| 2.3 | Migración a `ToqueApiBackend` Protocol (66 métodos, 6 fases) quedó a medias — Fase 1 bloqueada hasta WS semántico Fase 4 | Ver `docs/ARQUITECTURA_SERVICIOS.md` §6 | La arquitectura en sí es razonable, no es el problema — el problema es dejarla a medio camino. Priorizar cerrar Fase 4 (WS semántico) para poder completar Fase 1, o congelar explícitamente con fecha de retomo. |

---

## 3. Deuda técnica — duplicación y patrones repetidos

| # | Punto | Dónde | Cómo tratarlo |
|---|-------|-------|----------------|
| 3.1 | Boilerplate de conectar/desconectar eventos (~30 líneas c/u) repetido en 4 widgets | `arbol.py`, `insumos.py`, `apu.py`, `explosion.py` | Mover a un dict `_EVENT_HANDLERS` + método genérico en la clase base (`TreeTableWidget`), siguiendo el patrón que ya funciona en `apu.py`. |
| 3.2 | `_on_proyecto_recalculado` con esqueleto casi idéntico | `arbol.py:532-577`, `insumos.py:339-374` | Extraer a `_repoblar_con_estado(getter_fn)` en la clase base. |
| 3.3 | `blockSignals`/try-finally repetido en 6 sitios | `arbol.py`, `insumos.py`, `apu.py`, `paneles.py` | Context manager `_block_signals()` en la base class. |
| 3.4 | Guardado/restauración de scroll repetido en 5 sitios, con contrato inconsistente (`apu.py` lo hace dentro de `poblar()`, `arbol`/`insumos` fuera) | `arbol.py`, `insumos.py`, `apu.py` | Definir contrato único: `poblar()` solo limpia y puebla; el caller preserva scroll. Extraer a context manager `_preserve_scroll()`. |
| 3.5 | Menú de contexto Copy/Cut/Paste construido a mano 3 veces | `base.py:859-876`, `rastreo.py:90-108`, `explosion.py:608-630` | Helper único `_add_clipboard_actions(menu)` en `base.py`. |
| 3.6 | Botones de footer de diálogo reconstruidos en 5+ diálogos | `ajustes.py`, `explosion.py`, `dialogs.py`, `diag_dialogs.py` | Ya está documentado el patrón esperado (`GUIA_INTERFAZ.md §10.1`) — aplicar `DialogoBase._build_footer()` de forma consistente. |
| 3.7 | Guard "sin proyecto" implementado de 10+ formas distintas (return silencioso vs `QMessageBox`) | `handlers/__init__.py`, `paneles.py`, `apu/explosion.py`, `diag_dialogs.py`, `informes.py` | Unificar en un decorator `require_project()` o helper común, eligiendo un solo comportamiento por defecto. |
| 3.8 | `insumo_ids_con_apu()` se ejecuta dos veces en el mismo flujo | `insumos.py:352` → `api.insumos_con_matrices()` la vuelve a llamar internamente | Pasar los `ids` ya calculados como parámetro: `insumos_con_matrices(ids=...)`. |
| 3.9 | `insumos_con_matrices()` trae **todos** los insumos (7 JOINs) y filtra en Python en vez de SQL | `api.py:520-523` | Cambiar a `WHERE i.id IN (SELECT insumo_id FROM apu_matrices)` — impacto de performance real, no solo estilo. |
| 3.10 | 5+ diálogos de tipo confirmación (`QMessageBox`) con variaciones menores | `handlers/__init__.py`, `gestion_proyectos.py` | Helper `_confirm(message, title) -> bool`. |

---

## 4. Bugs de persistencia / arquitectura relacionados (encontrados en la misma auditoría)

Estos no son "deuda estética" sino fallas funcionales reales — priorizarlos por encima de la limpieza cosmética.

| # | Punto | Dónde | Cómo tratarlo |
|---|-------|-------|----------------|
| 4.1 | `insumo_actualizar_campo` solo hace `commit()` si el campo es `costo_final`; para cualquier otro campo el cambio queda en transacción implícita sin cerrar | `api.py:418-427` | **Prioridad alta.** Agregar `commit()` en el branch que no recalcula, o forzar recalcular siempre. |
| 4.2 | Widgets se comunican trepando al padre (`self.window()._on_search(...)`) en vez de usar el EventBus — mismo bloque copiado 2 veces | `widgets/arbol.py:476-478`, `widgets/insumos.py:380-382` | Reemplazar por filtro local dentro de `_on_proyecto_recalculado`, ya que el widget escucha el EventBus. |
| 4.3 | `unificar_matrices_apu()` hace DELETE/UPDATE sin emitir eventos → widgets quedan con datos obsoletos hasta recrear la pestaña | `api.py:583-621` | Emitir el evento correspondiente post-commit. |
| 4.4 | Corrección de unidades en diálogo no emite `InsumoActualizado` | `diag_dialogs.py:194-198,245-249` (SQL directo vía `executemany` + `commit`) | Reemplazar SQL directo por `DataService.actualizar()` + emitir evento. |
| 4.5 | No existen eventos `ProyectoAbierto` / `ProyectoCerrado` | — | Crear las clases de evento y emitirlas en `_on_abrir_proyecto` / `_on_cerrar_proyecto`, para que widgets puedan reinicializarse limpiamente. |

---

## 5. Orden de trabajo recomendado

Agrupado en fases por impacto/riesgo vs esfuerzo. Seguir este orden secuencial;
dentro de cada fase, los puntos marcados como paralelizables se pueden repartir
entre más de una persona.

### Fase 1 — Bugs de persistencia (primero, sin excepción) — ✅ REVISADA

Causan pérdida silenciosa de datos hoy. Cualquier otra limpieza es secundaria
mientras esto exista. **Verificado contra el código real (2026-09-04):** la
auditoría interna (`docs/PLAN_REPARACION.md`, fechada 2026-08-31) estaba
desactualizada — 4 de los 5 puntos ya se habían corregido entre esa fecha y
hoy. Solo quedaba pendiente el punto 4.2, que se corrigió en esta sesión.

| # | Punto | Estado al verificar | Acción tomada |
|---|-------|----------------------|----------------|
| 4.1 | `insumo_actualizar_campo` no comitea salvo en `costo_final` | **Ya resuelto.** El `actualizar()` corre dentro de `with self._ds.transaccion():`, y ese context manager (`Database.transaction()`) comitea siempre al salir del bloque, sin importar el campo — solo el *recálculo* es condicional a `costo_final`, no el commit. | Ninguna. |
| 4.4 | Corrección de unidades no emite `InsumoActualizado` | **Ya resuelto.** Tanto `_on_estandarizar_unidades` como `_on_corregir_case_unidades` (`diag_dialogs.py`) ya emiten el evento por cada cambio tras el commit. | Ninguna. Nota: sigue vigente el punto 5.4 (las dos funciones duplican la misma lógica de batch-update+commit+emit) — eso se trata en Fase 3. |
| 4.3 | `unificar_matrices_apu()` sin eventos post-commit | **Ya resuelto.** La lógica se centralizó en `DataService.unificar_matrices_apu()`, corre dentro de `self.transaccion()` y emite `ProyectoRecalculado` tras el commit si hubo migraciones. | Ninguna. |
| 4.2 | Widgets trepan a `self.window()._on_search(...)` en vez de usar su propio método | **Confirmado pendiente.** | **Corregido.** `arbol.py` e `insumos.py` ahora llaman `self.filter_rows(texto)` directamente — `filter_rows` ya vive en la clase base `TreeTableWidget` (`widgets/base.py:1355`), así que no hace falta pasar por la ventana. Se quitó también la comprobación `hasattr(..., '_on_search')` que ya no aplica. |
| 4.5 | Faltan eventos `ProyectoAbierto`/`ProyectoCerrado` | **Ya resuelto.** Ambas clases existen en `event_bus.py` y se emiten desde `gestion_proyectos.py` al abrir/cerrar proyecto. | Ninguna. |

**Verificación:** suite completa de tests (103 casos, `pytest tests/`) pasa
sin fallos tras el cambio de 4.2.

**Lección para el proceso:** los documentos de auditoría interna (`docs/*.md`)
son muy útiles pero se desactualizan rápido — conviene re-verificar contra
el código antes de empezar a "arreglar" cada punto, no asumir que la lista
sigue vigente tal cual.

### Fase 2 — Subsistema CAD/estructural — ✅ REVISADA (ya no requiere decisión)

**Corrección a la guía original:** al verificar contra el filesystem real
(2026-09-04), el subsistema huérfano descrito en 1.5/2.1
(`toolbar_estructural.py`, `widgets/viewport3d.py`,
`widgets/sidebar_estructura.py`, `backend/motor/opensees_repo.py`, y 5
helpers de CAD) **ya no existe en el repo** — `backend/cad/` hoy solo
contiene `lector_dxf.py` (activo, usado por tests). Este punto ya se había
resuelto en una sesión de limpieza anterior (documentada en
`docs/DUPLICACION_Y_DEUDA.md` §8, sesión 2026-07-24) y mi síntesis inicial
lo listó por error como si siguiera pendiente. No hace falta ninguna acción
ni decisión aquí.

| # | Punto | Estado al verificar | Acción |
|---|-------|----------------------|--------|
| 1.5 / 2.1 | Subsistema CAD/3D huérfano | **Ya eliminado** en sesión previa. Cero rastro en el filesystem actual. | Ninguna. |
| 1.6 | `push_undo()` nunca llamado desde `mixins/generador.py` | **Reclasificado.** No es un bug de wiring: busqué en todo `frontend/ventana/cad/` y `mixins/generador.py` y no existe ninguna herramienta de creación/edición de anotaciones sobre el plano — solo existen la estructura de datos del undo (`undo_stack.py`) y los botones Deshacer/Rehacer que la leen (`can_undo`/`can_redo`/`pop_undo`/`pop_redo`, todos ya cableados). `push_undo()` no se llama porque no hay ningún punto del código que cree, borre o edite una anotación todavía. | **No se implementó a ciegas.** Se documenta como feature pendiente de construir (herramienta de dibujo/anotación en el panel CAD), no como fix — requiere diseño de interacción (mouse, tipos de anotación, snapshot antes/después) antes de tocar código. Mover a backlog de producto, no a la lista de deuda técnica. |

**Conclusión de la Fase 2:** no había nada que decidir ni que corregir — el
único hallazgo real (1.6) no es deuda técnica sino una feature a medio
diseñar, y se saca de esta lista para no mezclar "limpieza" con "trabajo
nuevo".

### Fase 3 — Refactor de boilerplate en widgets — 🔶 EN PROGRESO

**Verificado contra el código real (2026-09-04):**

| # | Punto | Estado al verificar | Acción tomada |
|---|-------|----------------------|----------------|
| 3.1 | Conectar/desconectar eventos duplicado en 4 widgets | **Ya resuelto** desde antes. `TreeTableWidget` (`base.py`) ya tiene el patrón declarativo `EVENTOS_SUSCRITOS` + `conectar_eventos()`/`desconectar_eventos()` genéricos; `arbol.py`, `insumos.py` y `apu.py` lo usan. Las dos únicas clases que sobreescriben el método (`TablaExplosion`, `PestañaExplosion` en `explosion.py`) lo hacen a propósito y documentado (stub para futuro refresco en caliente, y delegación de contenedor) — no es duplicación accidental. | Ninguna. |
| 3.3 | `blockSignals`/try-finally repetido | **Confirmado pendiente — corregido en esta sesión.** 10 sitios (más de los 6 documentados originalmente), 3 de ellos sin `try/finally` (riesgo real de señales bloqueadas para siempre ante una excepción). | **Corregido.** Context manager `blocked_signals(*widgets)` en `base.py`, aplicado en los 10 sitios de `arbol.py`, `insumos.py`, `apu.py`, `paneles.py`. Verificado con pyflakes + suite completa (103/103). |
| 3.7 | Guard "sin proyecto" con 10+ variaciones | **Ya resuelto para el caso que importa.** `_requiere_proyecto(*, ruta, api)` (`navegacion.py:104`) ya existe y ya se usa consistentemente en los 8 sitios donde el guard protege una **acción disparada por el usuario** desde el ribbon/menú (`diag_dialogs.py` ×5, `informes.py` ×1, `navegacion.py` ×2) — muestra `QMessageBox` y retorna. Los ~10 sitios restantes con `if not self._api: return` silencioso (`generador.py`, `paneles.py`, widgets) protegen handlers de **menú contextual o doble clic sobre una fila existente** — solo alcanzables cuando ya hay un proyecto abierto (si no lo hay, la fila/menú ni existe). Convertirlos a `_requiere_proyecto()` agregaría un `QMessageBox` en un caso estructuralmente inalcanzable, o sería puramente cosmético sin reducir riesgo real. | **Ninguna — evaluado y descartado a propósito.** No es duplicación real, son dos guards distintos para dos situaciones distintas (acción siempre visible vs. acción solo alcanzable con proyecto abierto). Forzar la unificación bajaría claridad, no la subiría. |
| 3.4 | Guardado/restauración de scroll repetido | **Confirmado pendiente, pero un context manager simple NO es la solución correcta.** Investigado a fondo: en los 3 sitios (`arbol.py`, `insumos.py`, `apu.py`) el valor de scroll se captura en la función externa y se restaura dentro de una función diferida vía `QTimer.singleShot(0, ...)` — a propósito, para no pisar un item que Qt todavía está procesando en una cadena `itemChanged`. Un `with preserve_scroll(self):` no puede envolver esto: el bloque `with` saldría (y restauraría el scroll) antes de que el timer siquiera dispare, porque la función diferida corre de forma asíncrona después de que la función externa ya retornó. | **No se implementó.** Documentado en vez de forzado: el fix correcto es el más grande ya previsto en 3.2 (`_repoblar_con_estado(getter_fn)` en la clase base, que administre captura/restauración de scroll + selección + expansión + item actual como una sola operación consciente del `QTimer`), no un wrapper superficial. Requiere diseño cuidadoso por widget (cada uno restaura columnas/roles distintos) y verificación manual de UI (el comportamiento de scroll no lo cubre la suite de tests headless). Recomendado como tarea aparte, no como parte de una limpieza mecánica. |
| 3.2 | `_on_proyecto_recalculado` con esqueleto casi idéntico | Ligado a 3.4 (ver arriba) — mismo motivo para no forzarlo en esta pasada. | — |
| 3.5 | Menú de contexto Copy/Cut/Paste construido a mano 3 veces | **Corregido (2026-09-04).** Helper `_add_clipboard_actions(menu, con_corte=...)` en `TreeTableWidget` (`widgets/base.py`) construye Copiar/Cortar/Pegar con iconos+atajos y separador final; reutilizado en `base.py` (menú propio, `con_corte` según editabilidad) y en los menús externos de `rastreo.py` y `explosion.py` (el método se auto-pasa para binar `_copy`/`_cut`/`_paste` de la tabla interna). Se eliminaron los imports `QKeySequence` huérfanos. Testeado: suite 114/114. | — |
| 3.6 | Footer de diálogo reconstruido en 5+ diálogos | **Corregido (2026-09-04).** `crear_footer_dialogo()` en `widgets/base.py` era el helper compartido (ya usado por `ajustes.py` y `config_impresion.py`); `DialogoExplosion._build_footer()` era el único manual restante (Cancelar + Calcular a mano) y ahora delega en el helper con `texto_guardar="Calcular", on_guardar=self._on_accept`. Los 3 diálogos de la lista usan el mismo footer por QSS. Testeado: suite 114/114. | — |
| 3.10 | `_confirm()` helper para diálogos de confirmación | **Ya resuelto** — verificado (2026-09-04). `confirmar()` en `ui_utils.py:74` (Sí/No español, botón default en "Cancelar", `destructivo`) ya se usa en 8 sitios (`navegacion.py` ×5, `generador.py` ×2, `widgets/dialogs.py` ×1). El único `QMessageBox` manual restante (`gestion_proyectos.py:233`) es un diálogo elaborado a propósito. | Ninguna. |

**Siguiente incremento sugerido dentro de esta fase:** 3.5 (clipboard actions)
y 3.6 (footer de diálogos) — ambos son duplicación mecánica real, sin el
problema de timing de 3.2/3.4, y de bajo riesgo.

### Fase 4 — Performance puntual — ✅ RESUELTA

| # | Punto | Estado al verificar | Acción tomada |
|---|-------|----------------------|----------------|
| 3.9 | `insumos_con_matrices()` trae todo y filtra en Python | **Resuelto (2026-09-04).** Nuevo `InsumoRepo.con_matrices()` filtra en SQL (`es_compuesto = 1`, mismo shape y orden que `todos`/`por_tipo`); `Api.insumos_con_matrices` delega al backend. En HTTP, `GET /insumos_con_matrices` (1 RPC en vez de 2: catálogo + ids). | — |
| 3.8 | Doble ejecución de `insumo_ids_con_apu()` | **Resuelto** junto con 3.9 — el filtro ya no pasa por Python, así que el flujo no vuelve a llamar `insumo_ids_con_apu()`. | — |

Test de equivalencia añadido (`test_insumos.py::test_insumos_con_matrices_equivale_filtro_viejo`).

### Fase 5 — Limpieza mecánica (automatizable, al final o en paralelo con CI)

15. **1.7** — imports sin uso (correr `ruff --select F401` y aplicar). **Resuelto (2026-09-04).** vía `pyflakes` (3.4.0, instalado en el venv): 12 F401 en producción + 23 en tests/smokes, todos limpiados. En producción solo quedan los re-exports intencionales (`frontend/temas/__init__.py`, `frontend/ventana/__init__.py`). Además pyflakes destapó un **bug latente real** (ver nota al final): `_menu_icon` se usaba sin importar en `mixins/rastreo.py` y `widgets/explosion.py` → NameError al abrir los menús contextuales de rastreo/explosión. Corregido e importado bajo test de regresión.
16. **1.8** — mover el import de `ToqueApiBackend` a nivel de módulo.
17. **1.3** — código "muerto pero intencional": no borrar sin decidir primero (igual que el CAD, decisión de producto pequeña — 15 min de conversación con el equipo). **PENDIENTE confirmado por el usuario como pendiente (2026-09-04).** **1.1 y 1.2 resueltos (2026-09-04). 1.4 resuelto (2026-09-04).**
18. **2.2** — sacar el SQL crudo de `unificar_matrices_apu()` (se resuelve naturalmente al tocar esa función en la Fase 1, punto 3).
19. **2.3** — cerrar Fase 4 (WS semántico) de la migración `ToqueApiBackend` cuando haya ancho de banda; no urgente mientras el sistema dual funcione.

> Nota 2026-09-04: **2.2 y 2.3 ya cumplimentados de facto.** `api.py` no
> tiene SQL (0 × execute/commit; el único `import sqlite3` es para el
> type-hint de `conn` en `__init__`) y es dispatcher puro — los únicos
> usos de `_use_http` son infraestructura (constructor, `_http()`),
> sin `if _use_http` por método. La Fase 4/WS semántico ya está cerrada
> (Fases 0-5 + A-E completadas, ver §9-§10). Marcar esto como el punto
> 2.2/2.3 resuelto evita re-auditar.

**Regla general de secuencia:** arreglar lo que pierde datos → decidir lo que
bloquea claridad arquitectónica → refactor de duplicación con patrón ya
probado → performance → limpieza cosmética automatizable. Evitar el error
común de empezar por los imports sin uso (Fase 5) solo porque es lo más fácil
de ver — ahí no está el riesgo real.

---

## 6. Hallazgos de la sesión 2026-09-04 (además de la guía original)

1. **`_menu_icon` sin importar** en `frontend/ventana/mixins/rastreo.py`
   (`_on_rastrear_context_menu`) y `frontend/ventana/widgets/explosion.py`
   (`_on_context_menu`) → `NameError` en runtime al abrir el menú contextual
   de las tablas de rastreo y de la pestaña de explosión. **Fix:**
   `explosion.py` importa `_menu_icon` a nivel módulo (ya importaba de `base`);
   `rastreo.py` lo importa **local al método** (a propósito: un import de
   módulo en `rastreo.py` altera el grafo en la recolección de pytest porque
   `ventana.py:28` importa `RastreoMixin` en módulo, y eso adelantó la carga
   de `widgets.base` y disparó la carrera de teardown — ver 2). Test de
   regresión en `tests/test_dblclick_vacio.py::test_rastreo_menu_icon_no_nameerror`.
   Suite 119/119.

2. **Carrera de teardown Qt intermitente** en la suite headless: ~1 de cada
   2-3 corridas completas de `pytest tests`. Segfault en
   `test_filtro_local.py:52` (`tree.poblar(...)`) con frames de
   `QEventDispatcherGlib::processEvents` — callbacks `QTimer` pendientes de
   tests anteriores disparando contra widgets ya liberados (mismo patrón
   documentado en 1.8 y en el punto 3.4 del scroll diferido). **No es un
   fallo del código**: los subconjuntos estables (más de 15 archivos sin
   smoke) pasan 5/5 repetidas veces, y la suite completa pasa en corridas
   consecutivas (119/119 but también crasheó 6/6 en un mal momento). Se
   agrava con `PYTHONMALLOC=malloc` (3/3 → 139). **Workaround:**
   re-correr; cada archivo por separado es estable. Mitigación real para CI
   (no urgente): `pytest-forked` (cada test en subproceso) o cerrar el early
   `QApplication` con teardown explícito tras cada test que abra widgets.
