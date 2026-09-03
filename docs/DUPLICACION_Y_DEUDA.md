# Duplicación y deuda técnica — Auditoría completa

Actualizado: 2026-08-31 04:55 (hora local)

---

## 1. Datos maestros duplicados

Eliminado: 2026-07-11 — todos unificados en `frontend/ventana/tipos_insumo.py`.

| # | Qué | Dónde | Fix | Prioridad |
|---|-----|-------|-----|-----------|
| 1.1 | **Tipo → Emoji** (6 copias, 1 incompleta) | `api.py:38` _EMOJI (falta 64,128), `arbol.py:20` _ICONOS_TIPO, `dialogs.py:333` _TIPO_ICONO, `explosion.py:30` TIPO_ICONO, `insumos.py:83` TIPO_NOMBRE (emoji+texto) | ~~Un solo `TIPO_ICONO` en módulo compartido~~ ✅ `tipos_insumo.ICONO` | **P0** |
| 1.2 | **Tipo → Nombre** (4 copias, singular vs plural) | `dialogs.py:338` _TIPO_NOMBRE (plural), `insumos.py:83` TIPO_NOMBRE (singular), `explosion.py:52` TIPOS_INSUMO (singular), `exportar_plantillas.py:19` TIPOSINS_ROWS | ~~Un solo `TIPOS_INSUMO` tuple list~~ ✅ `tipos_insumo.TIPOS` | **P0** |
| 1.3 | **Sidebar titles** (3+ copias hardcoded) | `paneles.py:38-56` secciones, `paneles.py:179` tipo_map, `handlers/__init__.py:232` insumos_titles + router if/elif | ~~Definir sidebar items una vez~~ ✅ `INSUMOS_ITEMS` + `INSUMOS_TITLES` en paneles.py | **P1** |
| 1.4 | **ESTADO_NOMBRE** (2 copias idénticas) | `repos/presupuesto.py:13`, `widgets/arbol.py:135` | ~~Frontend importa desde backend~~ ✅ arbol.py importa de presupuesto.py | **P1** |
| 1.5 | **Colores hex** (12+ colores en múltiples sitios) | `#7FAFD6` en dialogs.py:33,228,408,661 + arbol.py:127. `#E8EDF2` en toolbar.py:34, arbol.py:36, base.py:190. `#2A4158` en dialogs.py:23, base.py:153,156. `#A06A6A`, `#D5B39B`, `#5B8A72` en 2+ sitios c/u | ~~Módulo `temas/colores.py` con constantes nombradas~~ ✅ `colores.py` con ACCENT, TEXT, SEL_BG, SUCCESS, WARNING, ERROR | **P2** |
| 1.6 | **Emoji-to-Icon function** (3 copias) | `toolbar.py:26` _icon, `arbol.py:32` _emoji_icon, `base.py:185` _menu_icon — misma lógica, diferentes defaults | ~~Una función `_make_icon(char, size, font_size)` en base.py~~ ✅ `make_icon()` en base.py | **P1** |
| 1.7 | **SISTEMA_PREFIJOS regex** (hardcoded emoji list) | `base.py:182` — debe coincidir con TIPO_ICONO manualmente | ~~Derivar de TIPO_ICONO automáticamente~~ ✅ derivado de `ICONO` | **P2** |

## 2. Patrones de código duplicados

| # | Qué | Dónde | Fix | Prioridad |
|---|-----|-------|-----|-----------|
| 2.1 | **conectar/desconectar_eventos** (4 widgets, boilerplate ~30 líneas c/u) | `arbol.py:364-409`, `insumos.py:241-275`, `apu.py:195-243`, `explosion.py:545-563` | Dict `_EVENT_HANDLERS` en base class + conectar/desconectar genérico (patrón apu.py ya funciona) | **P1** |
| 2.2 | **_on_proyecto_recalculado** (2 impl, esqueleto idéntico) | `arbol.py:532-577`, `insumos.py:339-374` | `_repoblar_con_estado(getter_fn)` en base class | **P2** |
| 2.3 | **blockSignals/try/finally** (6 sitios) | `arbol.py:552`, `insumos.py:301,349`, `apu.py:149,328`, `paneles.py:255` | Context manager `_block_signals()` en base class | **P2** |
| 2.4 | **Scroll save/restore** (5 sitios) | `arbol.py:541,562`, `insumos.py:345,361`, `apu.py:144,175` | Context manager `_preserve_scroll()` o incluir en 2.2 | **P2** |
| 2.5 | **Context menu Copy/Cut/Paste** (3 construcciones manuales) | `base.py:859-876`, `rastreo.py:90-108`, `explosion.py:608-630` | Helper `_add_clipboard_actions(menu)` en base.py | **P2** |
| 2.6 | **_build_placeholder vs _build_sin_proyecto** (2 impl casi idénticas) | `handlers/__init__.py:168-191`, `paneles.py:131-171` | Una función `_build_empty_state(icon, title, msg, clickable)` | **P2** |
| 2.7 | **Dialog footer buttons** (5+ diálogos) | `ajustes.py:170`, `explosion.py:371`, `dialogs.py:234,302,449,699`, `diag_dialogs.py:188,244,333` | `DialogoBase` con `_build_footer()` estándar (ya documentado en GUIA_INTERFAZ §10.1) | **P1** |
| 2.8 | **_get_active_table inline** (4 duplicados vs método existente) | `handlers/__init__.py:80,93,106,283` — inline vs método canonical en línea 399 | Reemplazar inline por `self._get_active_table()` | **P0** |
| 2.9 | **_mover_nodo/_izquierda/_derecha preamble** (3× 9 líneas idénticas) | `handlers/__init__.py:526-537, 584-595, 656-667` | Helper `_get_move_context()` → `(repo, proyecto_id, seleccionados)` | **P1** |
| 2.10 | **Init column visibility sequence** (4 widgets) | `arbol.py:182-205`, `insumos.py:135-151`, `apu.py:110-119`, `explosion.py:443-455` | `_init_column_visibility(catalogo)` en TreeTableWidget | **P2** |
| 2.11 | **"Sin proyecto" guard** (10+ sitios, inconsistente) | `handlers/__init__.py:199,212`, `paneles.py:108`, `apu/explosion.py:21,84`, `diag_dialogs.py:18,37,276,365`, `informes.py:22` | `require_project()` decorator o helper que unifica silently-return vs QMessageBox | **P2** |
| 2.12 | **QMessageBox confirmation** (5+ variaciones) | `handlers/__init__.py:729,748`, `gestion_proyectos.py:204,333`, `handlers/__init__.py:382` | Helper `_confirm(message, title)` → bool | **P2** |

## 3. Inconsistencias funcionales

| # | Qué | Dónde | Fix | Prioridad |
|---|-----|-------|-----|-----------|
| 3.1 | **_EMOJI incompleto** — faltan 64 (🚛) y 128 (🏗️) | `api.py:38` | Agregar keys faltantes (o mejor: eliminar y usar módulo compartido 1.1) | **P0** |
| 3.2 | **Singular vs plural** en nombres de tipo | insumos.py "Material" vs dialogs.py "Materiales" | Estandarizar en 1.2 | **P1** |
| 3.3 | **poblar() scroll guard inconsistente** — apu.py guarda scroll dentro de poblar(), arbol/insumos fuera | `apu.py:144` vs `arbol.py:541` / `insumos.py:345` | Contrato claro: poblar() solo limpia y puebla, el caller preserva estado | **P2** |
| 3.4 | **5 sidebar items sin handler real** — caen a placeholder genérico | `paneles.py` define: 🚚 Programa de suministros, 👷 Personal en indirectos, 📝 Estimaciones, ➕ Conceptos fuera de catálogo, 📈 Ajustes de costos | Marcar como "En desarrollo" explícitamente o remover del sidebar | **P2** |
| 3.5 | **Event name strings frágiles** en WS deserialization | `gestion_proyectos.py:52-69` — map de strings a clases, sin validación | Usar `getattr(event_bus, class_name)` o registrar eventos en dict central | **P2** |

## 4. Código muerto / innecesario

Eliminado: 2026-07-11 — todos eliminados excepto 4.17 (usuario_id en Api).

| # | Qué | Dónde | Fix | Prioridad |
|---|-----|-------|-----|-----------|
| 4.1 | **`flatten()`** — función recursiva nunca llamada | `core.py:71` | ~~Eliminar~~ ✅ | **P0** |
| 4.2 | **`_buscar_campo()`** — método de RepoBase nunca llamado | `repos/base.py:56` | ~~Eliminar~~ ✅ | **P0** |
| 4.3 | **`ProyectoRepo.obtener()`** — nunca llamado, `buscar()` se usa | `repos/proyecto.py:25` | ~~Eliminar~~ ✅ | **P1** |
| 4.4 | **`FamiliaRepo.insertar()`** — muerto, `insert()` se usa via registry | `repos/catalogos.py:27` | ~~Eliminar~~ ✅ | **P1** |
| 4.5 | **`SubfamiliaRepo.insertar()`** — muerto, `insert()` se usa via registry | `repos/catalogos.py:57` | ~~Eliminar~~ ✅ | **P1** |
| 4.6 | **`NotaRepo.por_nodo()`** — nunca llamado | `repos/catalogos.py:79` | ~~Eliminar~~ ✅ | **P1** |
| 4.7 | **`NotaRepo.insertar()`** — muerto, `insert()` se usa via registry | `repos/catalogos.py:89` | ~~Eliminar~~ ✅ | **P1** |
| 4.8 | **`NotaRepo.resolver()`** — nunca llamado | `repos/catalogos.py:97` | ~~Eliminar~~ ✅ | **P1** |
| 4.9 | **`NotaRepo.abiertas()`** — nunca llamado | `repos/catalogos.py:101` | ~~Eliminar~~ ✅ | **P1** |
| 4.10 | **`HistorialRepo.capturar_batch()`** — nunca llamado, DataService usa loop de `capturar()` | `repos/historial.py:47` | ~~Eliminar~~ ✅ | **P2** |
| 4.11 | **`HistorialRepo.sesiones_usuario()`** — nunca llamado | `repos/historial.py:107` | ~~Eliminar~~ ✅ | **P1** |
| 4.12 | **`HistorialRepo.limpiar_sesion()`** — nunca llamado | `repos/historial.py:132` | ~~Eliminar~~ ✅ | **P1** |
| 4.13 | **`HistorialRepo.existe_registro()`** — nunca llamado | `repos/historial.py:145` | ~~Eliminar~~ ✅ | **P1** |
| 4.14 | **`ApuMatricesRepo.buscar()`** — wrapper trivial `return super().buscar()` | `repos/apu.py:22` | ~~Eliminar~~ ✅ | **P2** |
| 4.15 | **`FactoresSobrecostoRepo.buscar()`** — wrapper trivial `return super().buscar()` | `repos/proyecto.py:59` | ~~Eliminar~~ ✅ | **P2** |
| 4.16 | **`NodoRepo.actualizar_cantidad(usuario_id)`** — param nunca usado | `repos/presupuesto.py:353` | ~~Quitar param~~ ✅ | **P2** |
| 4.17 | **`usuario_id` ignorado** en 5 métodos de Api que no lo forwardanean a DataService | `api.py:658,696,720,746,800` | Pendiente | **P2** |
| 4.18 | **Import duplicado `Qt`** | `dialogs.py:13` + `dialogs.py:21` | ~~Eliminar~~ ✅ | **P2** |
| 4.19 | **`ConflictError`** importado con noqa, nunca usado | `data_service.py:26` | ~~Eliminar~~ ✅ | **P2** |
| 4.20 | **`generar_hash`** re-exportado desde `base.py`, nadie lo importa de ahí | `repos/base.py:19` | ~~Eliminar~~ ✅ | **P2** |

## 5. Lógica redundante (misma función, implementación doble)

| # | Qué | Dónde | Fix | Prioridad |
|---|-----|-------|-----|-----------|
| 5.1 | **`insumo_ids_con_apu()` ejecutado 2×** en mismo flow — `insumos.py:352` lo llama, luego `api.insumos_con_matrices()` lo llama de nuevo internamente | `insumos.py:352`, `api.py:520` | Pasar `ids` pre-fetched a `insumos_con_matrices(ids=...)` | **P0** |
| 5.2 | **`insumos_con_matrices()` fetch + filter en Python** — trae TODOS los insumos (7 JOINs) y filtra en Python en vez de SQL WHERE | `api.py:520-523` | SQL `WHERE i.id IN (SELECT insumo_id FROM apu_matrices)` | **P1** |
| 5.3 | **ALIASES + mapa de unidades** — copy-paste idéntico en 2 funciones | `diagnostico.py:92-100`, `diagnostico.py:115-122` | Constante `_ALIASES` + helper `_unidades_mapa()` a nivel módulo | **P1** |
| 5.4 | **Apply-and-emit pattern** — misma lógica de batch update + commit + emit + refresh en 2 diálogos | `diag_dialogs.py:196-212`, `diag_dialogs.py:252-265` | Helper `_aplicar_cambios_unidades(cambios)` | **P1** |
| 5.5 | **Search re-application** — `win._on_search(win._search_input.text())` al final de `_on_proyecto_recalculado` | `arbol.py:573`, `insumos.py:370` | Helper `_refresh_search()` en base class | **P2** |
| 5.6 | **UNION ALL subquery** repetida 3× en RecalculoRepo | `recalculo.py:96,116,150` | CTE a nivel de clase o constante SQL | **P2** |

## 6. Top 5 fixes por impacto/esfuerzo (actualizado)

| # | Fix | Líneas eliminadas | Archivos tocados | Esfuerzo |
|---|-----|-------------------|------------------|----------|
| ~~1~~ | ~~**Eliminar código muerto** — 20 métodos/funciones nunca llamados (4.1-4.20)~~ | ~~180~~ | ~~7~~ | ~~Bajo~~ ✅ |
| ~~2~~ | ~~**Reemplazar 4 inline `_get_active_table()`** por el método existente (2.8)~~ | ~~20~~ | ~~1~~ | ~~Bajo~~ ✅ |
| ~~3~~ | ~~**`_get_move_context()`** — eliminar preamble duplicado (2.9)~~ | ~~18~~ | ~~1~~ | ~~Bajo~~ ✅ |
| 4 | **Módulo compartido de tipos** — unificar 1.1 + 1.2 + 1.6 + 1.7 | ~120 | 6-8 | Medio |
| 5 | **Base class event subscription** — dict pattern (2.1 + 2.12) | ~120 | 4 | Medio |

## 7. Progreso de sesión de refactor (2026-07-19)

- **Reorganización de `frontend/ventana/`**: nuevo paquete `mixins/` agrupa los
  9 mixins que se mezclan en `VentanaPrincipal` (antes repartidos en
  `apu/`, `generador/`, `handlers/` y sueltos en la raíz, con nombres que
  colisionaban con `widgets/`). Carpetas viejas eliminadas.
- **Bug corregido**: `backend/database/repos.py` estaba shadowed por el
  paquete `repos/` — el import en `sidebar_estructura.py` fallaba en
  runtime. Renombrado a `hoja_bindings.py`.
- **Código muerto eliminado**: 5 imports sin uso, `RepositoryRegistry.entidades()`
  y `EventBus.suscriptores_count()` (helpers de debug sin caller).
- **Código muerto identificado, no eliminado** (parece trabajo a medio
  construir, no basura — requiere decisión): `api.py` (6 métodos de
  gestión de generadores), `data_service.py` (`iniciar_sesion`/
  `cerrar_sesion` ligados a SRV-09, `reasignar_generador`),
  `DiagnosticoRepo.estadisticas()`/`resumen_integridad()`, `ConflictError`.
- **Subsistema huérfano identificado** (¿conservar como WIP o eliminar?):
  `toolbar_estructural.py` (682 líneas, nunca mezclado en `VentanaPrincipal`,
  fork copy-paste de `mixins/toolbar.py`), `widgets/sidebar_estructura.py`,
  `widgets/viewport3d.py`, `backend/motor/opensees_repo.py`, y 5 helpers
  CAD sin ninguna referencia externa (`calibracion.py`, `panel_capas.py`,
  `filtro_nombres.py`, `agregacion.py`, `busqueda_texto.py`). Sin tocar,
  pendiente de decisión.
- **Duplicación resuelta**: `recalculo.py`/`importar.py` (SQL de totales
  extraído a `recalcular_totales_conceptos()`/`recalcular_totales_capitulos()`),
  `gestion_proyectos.py`/`servidor.py` (factory `crear_registry()`).
- **Pasos redundantes eliminados**: `api.py` — `concepto_reasignar_insumo()`
  y `eliminar_nodo()` llamaban `recalcular_desde()` inmediatamente
  sobreescrito por `recalcular_proyecto()`.
- **Migración `Api` a backends** (completada 2026-08-31): patrón
  `ToqueApiBackend` (Protocol, 66 métodos) reemplaza el `if
  self._use_http` por método. `api.py` es dispatcher puro (67
  delegaciones, 5 `if` infraestructura). Ver
  `frontend/ventana/api_backends.py` y `docs/ARQUITECTURA_SERVICIOS.md`
  Fases 0-3. `ApiCliente` 41→7 públicos (transporte puro). Secciones
  migradas: TODAS (PRESUPUESTO, APU, EXPLOSIÓN, CATÁLOGOS, INSUMOS,
  VARIABLES, GENERADORES, INDIRECTOS, UNDO). Pendiente solo Fase 1
  (eventos duplicados en `_BackendHTTP`, bloqueada hasta WS semántico Fase 4).
- **`tests/smoke_api_backends.py`** + `smoke_presupuesto_http.py` (local),
  `smoke_variables_eliminar.py`, etc.: cubren backends contra BD real.

## 8. Sesión de auditoría (2026-07-24)

**Eliminado en esta sesión** (huérfanos confirmados, cero referencias en
todo el proyecto):
- Subsistema completo de "Análisis Estructural" — `toolbar_estructural.py`,
  `widgets/viewport3d.py`, `widgets/sidebar_estructura.py` (el que la
  sesión del 19-jul dejó "pendiente de decisión" en la sección 7).
- 5 helpers de CAD nunca conectados: `cad/panel_capas.py`,
  `cad/filtro_nombres.py`, `cad/calibracion.py`, `cad/busqueda_texto.py`,
  `cad/agregacion.py`.
- `cad/visor.py.orig` (respaldo suelto).
- `ConflictError` (clase, ya sin uso desde que 4.19 se resolvió),
  `lector_dxf.entities_to_json()`, y en `api.py`:
  `concepto_actualizar_pu`, `proyectos_disponibles`, `generadores`,
  `generador_actualizar`, `generador_eliminar` — y el
  `GeneradorRepo.listar_por_proyecto()` que este último dejó huérfano.

**Investigado y dejado tal cual — NO es código muerto, es funcionalidad
real sin terminar de conectar. Decisión: documentar, no tocar todavía:**

| Qué | Dónde | Por qué no se borra |
|---|---|---|
| `DataService.iniciar_sesion()`/`cerrar_sesion()` (SRV-09) | `data_service.py:62-69` | `self._sesion` SÍ se lee en `actualizar()`/`eliminar()` (línea 102, 173) — como nadie llama `iniciar_sesion()`, cada edición cae al fallback `or str(uuid.uuid4())` y genera su propia sesión en vez de agruparse. El undo campo-por-campo funciona bien; falta conectar el agrupado de operaciones batch en un solo Ctrl+Z. |
| `DataService.reasignar_generador()` | `data_service.py:476` | Método completo y correcto (reasigna generador a otro concepto + recalcula ambos). Cero llamadores en la UI — parece una acción pensada (¿arrastrar generador a otro capítulo?) nunca cableada a un botón/menú. |
| `DiagnosticoRepo.estadisticas()` | `diagnostico.py:136` | Su docstring dice "para el diálogo de información" — pero `_on_info_proyecto()` en `diag_dialogs.py` no la llama ni tiene conteos propios. El diálogo de info del proyecto hoy no muestra estadísticas. |
| `DiagnosticoRepo.resumen_integridad()` | `diagnostico.py:245` | `core.py` documenta su propia migración: "`validar()` → `DiagnosticoRepo.resumen_integridad()`" (Fase 4, ver ARQUITECTURA_SERVICIOS.md). El punto que debía llamarla en su nueva ubicación nunca se actualizó. |

Si se retoma alguno de estos, no hace falta re-auditar — la tabla de
arriba ya tiene el motivo y la línea exacta donde conectar cada uno.

**También de esta sesión** (ver conversación completa para detalle):
código muerto de `except Exception` genéricos acotado a excepciones
específicas en `db.py`; cableado de eventos de `TablaArbol`/`TablaInsumos`/
`TablaApuDetalle` unificado vía `EVENTOS_SUSCRITOS` declarativo en
`TreeTableWidget` (reemplaza 2.1); cableado de señales de `TablaArbol`
unificado vía `conectar_handlers()` (encontró y corrigió un bug real:
`PresupuestoPopup` no conectaba `agregar_agrupador`/`agregar_concepto`/
`eliminar_seleccion`); estilo de fila vacía unificado vía
`_estilizar_fila_vacia()` en `TreeTableWidget`.

**Bug real encontrado, sin corregir** (fuera del alcance de "código
muerto" — es lo opuesto, código que falta escribir): `cad/undo_stack.py`
`push_undo()` nunca se llama desde `mixins/generador.py`. El botón
"Deshacer" del panel CAD (dibujo/anotaciones) está siempre deshabilitado
porque la pila de undo nunca se llena — no relacionado con el undo de
SRV-09 (ese es para presupuesto/insumos vía `HistorialRepo`, y ese sí
funciona por edición individual).


## 9. Sesión 2026-08-30/31 — Protocolo y migración completa (punto 3)

**Protocolo definido:** `docs/ARQUITECTURA_SERVICIOS.md` creado (ToqueApiBackend Protocol, reglas R1-R9, 6 fases, DoD por método). `AGENTS.md` actualizado (LOCAL vs HTTP, stack, estructura real con `server/`, `cad/`, `mixins/`).

**Migración ejecutada (35 métodos en 6 tandas):**
- Fase 0: `ToqueApiBackend` Protocol declarado (31→66 métodos) + asserts en `Api.__init__`.
- Fase 2: `api.py` 40 → 5 `if _use_http:` (solo infraestructura), 31 → 67 delegaciones. Secciones: PRESUPUESTO (12), APU escritura (6), EXPLOSIÓN+CATÁLOGOS (6), INSUMOS (7), UNDO (4).
- Fase 3: `ApiCliente` 41 → 7 públicos (`_get`/`_post` + `buscar`/`actualizar`/`insertar`/`eliminar`/`recalcular`/`reindexar`/`close`). Inlinéados a `_BackendHTTP._get/_post` con traducción `422→ValueError` y `Decimal`: familias/subfamilias (2), factores/insumos/rastrear/todos/conceptos/descendientes/explotar (8), variables/apu (7), generadores/indirectos (10), factores_guardar/deshaer (3).
- Regla cardinal: `NodoRepo.con_formula_por_proyecto()` y reemplazo de raw `SELECT` en `api_backends.py:455`.
- `assets/icons8` 329→116 SVGs (213 sin mapear eliminados).
- `frontend/ventana/iconos.py:268` stub duplicado `_colored_icon` eliminado.

**Pendiente:** Fase 1 (quitar `ds.emitir` duplicado en `_BackendHTTP`, bloqueada hasta Fase 4 WS semántico) y Fase 4-5 (WS semántico + limpieza docs). Ver `docs/ARQUITECTURA_SERVICIOS.md` §6.
