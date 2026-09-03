# Plan de reparación — Auditoría GUIA_INTERFAZ.md

Actualizado: 2026-08-31 04:55 (hora local)

## 1. Resumen ejecutivo

46 hallazgos en 6 categorías tras auditar todo `frontend/` contra `docs/GUIA_INTERFAZ.md`.
11 pasos de reparación priorizados por costo/beneficio. ~5-6 h de esfuerzo total estimado.

| Categoría | Hallazgos | Críticos |
|-----------|-----------|----------|
| A. SQL fuera de repos | 3 archivos, 9 statements | 2 bugs de persistencia |
| B. Bypass de EventBus | 4 patrones, 7 call sites | 2 widgets stale, 1 privado violado |
| C. Import directo de backend | 9 archivos | 0 (diferido) |
| D. Eventos faltantes | 4 problemas | 1 widget stale, 1 bug de persistencia |
| E. Ciclo de vida widget | 4 problemas | 1 riesgo zombi |
| F. API return types | 3 métodos | 0 (documentar) |

## 2. Metodología

- **Búsqueda:** grep + AST parse + lectura manual de todos los archivos en `frontend/`
- **Criterio:** cada hallazgo se contrasta contra una sección específica de `GUIA_INTERFAZ.md`
- **Verificación:** 9 hallazgos verificados contra código real por el usuario (anexo A)
- **Severidades:**
  - **ALTA:** bug funcional observable o violación irreversible de la arquitectura
  - **MEDIA:** violación de capas o convención con consecuencia funcional potencial
  - **BAJA:** incumplimiento formal sin consecuencia funcional hoy

## 3. Hallazgos por categoría

### 3.A SQL fuera de repos (Restricción #1 de GUIA_INTERFAZ.md)

> "SQL solo vive en `backend/database/repos/`". Violarlo requiere revertir el PR.

| # | Sev | Archivo | Línea | Código ofensor | Problema | Fix |
|---|-----|---------|-------|----------------|----------|-----|
| 1 | ALTA | `api.py` | 262-621 | 6 `.execute()`, 8 cursor/`fetch`, 2 `commit()`, `import sqlite3` | SQL crudo en la fachada. `unificar_matrices_apu()` hace DELETE/UPDATE sin eventos. | Extraer consultas a nuevos métodos en repos existentes |
| 2 | ALTA | `handlers/diag_dialogs.py` | 194-198, 245-249 | `self._db.conn.executemany("UPDATE insumos ...")` + `.commit()` | SQL UPDATE directo desde handler. Sin evento → widgets stale. | Reemplazar por `DataService.actualizar()` + emitir `InsumoActualizado` |
| 3 | MEDIA | `apu/apu.py` | 349 | `self._api._conn.execute(f"SELECT {campo} FROM {tabla} WHERE id=?", ...)` | SQL con f-string (hoy literales hardcodeados, riesgo si se reusa con datos dinámicos). Accede a atributo privado `_conn`. | Mover a `RepoBase._buscar_campo(tabla, campo, id)` |

### 3.B Bypass de EventBus (Restricción #6, #7)

> "Ningún widget se comunica directamente con otro widget no-hermano". "Toda sincronización de estado entre widgets va por EventBus".

| # | Sev | Archivo | Línea | Problema | Fix |
|---|-----|---------|-------|----------|-----|
| 4 | ALTA | `widgets/arbol.py` | 476-478 | `self.window()._on_search(...)` — trepa al window() para invocar búsqueda. Mismo bloque copiado en 2 archivos (viola Principio 1). | Reemplazar por filtro local en `_on_proyecto_recalculado` (el widget ya escucha EventBus) |
| 5 | ALTA | `widgets/insumos.py` | 380-382 | Idéntico a #4 | Idéntico a #4 |
| 6 | MEDIA | `handlers/__init__.py` | 55-63 | `_reload_presupuesto()` destruye y recrea widget entero. Llamado desde 4 sitios. Redundante con el EventBus que el árbol ya escucha. | Reemplazar cada call site por emitir `ProyectoRecalculado` |
| 7 | MEDIA | `apu/explosion.py` | 26-31, 92-97 | Lee `self._arbol_presupuesto.selectedItems()` directamente — acopla ExplosionMixin a TablaArbol. | Emitir evento `ConceptosSeleccionados` o pasar IDs como parámetro |

### 3.C Import directo de backend (separación de capas)

> "frontend solo se comunica con backend a través de frontend/ventana/api.py"

| # | Archivo | Import | Uso |
|---|---------|--------|-----|
| 8 | `temas/temas.py` | `from backend.database.db import Config` | Leer configuración de tema |
| 9 | `widgets/base.py` | `from backend.database.db import Config` | Persistencia de columnas |
| 10 | `widgets/ajustes.py` | `from backend.database.db import Config` | Diálogo de ajustes |
| 11 | `paneles.py` | `from backend.database.db import Rutas` | Rutas de proyecto |
| 12 | `handlers/__init__.py` (x2) | `from backend.database.db import Rutas` | Adjuntar archivos |
| 13 | `handlers/informes.py` | `from backend.database.db import Rutas` | Ruta de PDF |
| 14 | `api.py` | `from backend.database.db import Rutas` | (en la fachada — aceptable) |
| 15 | `handlers/gestion_proyectos.py` (x6) | `from backend.database.db import Database, Rutas, Config` | Abrir/crear/importar proyectos |
| 16 | `widgets/dialogs.py` | `from backend.database.core import generar_hash` | Hash de insumos |

**Decisión:** Diferir a post-MVP. Mover `Config` y `Rutas` detrás de Api requiere agregar métodos fachada, y toca 9 archivos sin beneficio funcional inmediato.

### 3.D Eventos faltantes / timing

> "Los eventos se emiten después del COMMIT, no antes" (Reglas de servicios)

| # | Sev | Problema | Impacto | Fix |
|---|-----|----------|---------|-----|
| 17 | ALTA | `diag_dialogs.py`: estandarizar/corregir unidades no emiten `InsumoActualizado` | Widgets con datos obsoletos hasta refresco manual | Emitir `InsumoActualizado` tras cada batch |
| 18 | MEDIA | `api.py:418-427`: `insumo_actualizar_campo` condiciona recalcular a `campo == "costo_final"`. Cuando no lo es, DataService escribe sin commit posterior. | **Bug de persistencia:** cambios quedan en transacción implícita, perdidos si no hay otra escritura. | Agregar `self._conn.commit()` en el branch sin recalcular, o llamar a recalcular siempre |
| 19 | BAJA | `api.py:583-621`: `unificar_matrices_apu()` hace DELETE/UPDATE sin emitir eventos | Widgets stale hasta recrear pestaña | Emitir evento post-commit |
| 20 | BAJA | No existen `ProyectoAbierto` / `ProyectoCerrado` | No hay ciclo de vida de proyecto para widgets que necesiten reinicializarse | Crear clases de evento + emitir en `_on_abrir_proyecto` / `_on_cerrar_proyecto` |

### 3.E Ciclo de vida de widgets (§7.6)

> `crear → poblar() → conectar_eventos() → [uso] → desconectar_eventos() → destruir`

| # | Sev | Problema | Impacto | Fix |
|---|-----|----------|---------|-----|
| 21 | MEDIA | APU inline widget (`_build_apu_tab`): `desconectar_eventos` como atributo dinámico, no método de clase. 3 suscripciones EventBus en closures. | **Riesgo zombi** si se destruye sin pasar por `_cerrar_tab_widget()` | Extraer clase `TablaApuDetalle(TreeTableWidget)` siguiendo patrón de TablaArbol |
| 22 | BAJA | `PestañaExplosion` (explosion.py:546): sin `poblar()`/`conectar_eventos()`/`desconectar_eventos()` | No sigue la convención | Agregar métodos que deleguen a `TablaExplosion` interna |
| 23 | BAJA | `TablaExplosion` (explosion.py:431): sin `conectar_eventos()`/`desconectar_eventos()` | No sigue la convención (hoy no se subscribe, pero es extensible) | Agregar stubs |
| 24 | BAJA | Ninguna clase en `frontend/` tiene `closeEvent` o `__del__` | Sin capa de seguridad si un widget se cierra sin pasar por `_cerrar_tab_widget()` | Agregar `closeEvent` en VentanaPrincipal que itere pestañas |

### 3.F API return types (§6.2)

> "Api retorna solo dict, list, int, float, str, None"

| # | Método | Retorna | ¿Violación? | Decisión |
|---|--------|---------|-------------|----------|
| 25 | `insumo_ids_con_apu()` | `set[int]` | No listado en tipos permitidos | Todos los callers usan `in` (funciona en cualquier iterable). **Documentar como excepción aceptada.** |
| 26 | `explotar()` | `tuple[list[dict], float]` | No listado | Todos los callers desestructuran correctamente. **Documentar como excepción aceptada.** |
| 27 | `_resolver_matriz()` (privado) | `tuple[int\|None, str]` | Privado + no listado | Método privado, no aplica la regla pública. **Ignorar.** |

## 4. Hallazgos adicionales (post-verificación)

Descubiertos durante la verificación cruzada de los hallazgos principales:

| # | Sev | Archivo | Línea | Problema | Fix |
|---|-----|---------|-------|----------|-----|
| 28 | MEDIA | `apu/explosion.py` | 125 | `self._api._resolver_matriz(...)` — accede a método privado de Api desde fuera de la clase | Exponer método público o mover la lógica a Api y acceder por método público |
| 29 | BAJA | `api.py` | 531-569 | `_resolver_matriz` privado pero llamado externamente (hallazgo #28) | Hacer público o refactorizar |
| 30 | BAJA | `widgets/arbol.py` + `widgets/insumos.py` | 476-478, 380-382 | Bloque `self.window()._on_search()` copiado literalmente en 2 archivos (viola Principio 1: una herramienta en un solo lugar) | Se resuelve con el fix de #4-5 |

## 5. Orden de reparación priorizado

| Paso | Hallazgos | Acción | Esfuerzo | Riesgo | Dependencias |
|------|-----------|--------|----------|--------|-------------|
| 1 | #17 | `diag_dialogs.py`: emitir `InsumoActualizado` tras estandarizar/corregir unidades | ~30 min | Bajo | — |
| 2 | #18 | `api.py`: fix bug de persistencia en `insumo_actualizar_campo` (commit condicional) | ~15 min | Bajo | — |
| 3 | #3 | `apu.py`: mover SQL inline a `RepoBase._buscar_campo()` | ~15 min | Muy bajo | — |
| 4 | #22-23 | `PestañaExplosion`/`TablaExplosion`: agregar lifecycle stubs | ~10 min | Bajo | — |
| 5 | #4-5, #30 | `arbol.py`/`insumos.py`: reemplazar `self.window()._on_search()` por filtro local en EventBus | ~45 min | Bajo | — |
| 6 | #28-29 | `explosion.py`: exponer `resolver_matriz()` como método público en Api | ~15 min | Bajo | — |
| 7 | #6 | Eliminar `_reload_presupuesto()`, reemplazar por eventos | ~30 min | Medio | Paso 5 (misma área de código) |
| 8 | #20 | Crear eventos `ProyectoAbierto`/`ProyectoCerrado` + emitir | ~30 min | Bajo | — |
| 9 | #7 | Crear evento `ConceptosSeleccionados` para explosion | ~1 h | Medio | — |
| 10 | #21 | Extraer `TablaApuDetalle(TreeTableWidget)` como clase separada | ~2-3 h | Medio | Pasos 4, 7 (familiaridad con patrón) |
| 11 | #25-27 | Documentar `set`/`tuple` como excepción en `GUIA_INTERFAZ.md` §6.2 | ~15 min | Bajo | — |

**Total estimado:** ~5-6 h

## 6. Casos diferidos (post-MVP)

| Hallazgos | Motivo |
|-----------|--------|
| #1: api.py raw SQL (6 consultas, `unificar_matrices_apu`) | **Resuelto 2026-08-31:** `api.py` ya no tiene SQL; `unificar_matrices_apu` sigue local pero sin `if _use_http:` (dispatcher). Pendiente extraer 1 `SELECT` restante de `api_backends.py:455` → hecho vía `NodoRepo.con_formula_por_proyecto()` (ver Fase 2). |
| #2: diag_dialogs.py UPDATE directos (migrar a DataService) | Depende de #1. Misma área de código. |
| #3: apu.py f-string SQL | **Resuelto 2026-08-31:** movido a `NodoRepo`/`ApuMatricesRepo` vía backends (Fase 2). |
| #8-16: imports directos de `backend.database.db` (9 archivos) | No hay beneficio funcional inmediato. Mover Config/Rutas detrás de Api es trabajo mecánico sin impacto visible. |
| #18: bug commit condicional `insumo_actualizar_campo` | **Resuelto 2026-08-31:** `insumo_actualizar_campo` ahora pasa por `_BackendLocal` con `transaccion()` + `recalcular` + `emitir` unificado (Fase 2). |
| #19: `unificar_matrices_apu()` sin eventos | Pendiente — extraer a repo manteniendo eventos (Fase 1). |
| #24: closeEvent en VentanaPrincipal | Bajo riesgo, mitigado por `_cerrar_tab_widget()`. |
| #28-29: `resolver_matriz` privado | **Resuelto 2026-08-31:** `api.py:693` `resolver_matriz` ya es público y delegado a `ToqueApiBackend` (Fase 2). |

## 7. Referencias cruzadas

| Hallazgo | GUIA_INTERFAZ.md | PATRONES.md |
|----------|-----------------|-------------|
| A (SQL en UI) | §2 Restricción #1, §6.3 Capas | — |
| B (EventBus bypass) | §2 Restricciones #6-#7, §7.4 EventBus, §7.5 Eventos | PATRONES.md §7.4 |
| C (imports backend) | §3 Vista de dependencias, §6.5 Responsabilidades por capa | — |
| D (eventos faltantes) | §7.5 Eventos semánticos, §8.8 Naming eventos | PATRONES.md §7.3, §7.5 |
| E (ciclo de vida) | §7.6 Ciclo de vida de widget, §8.4 Convención métodos | PATRONES.md §7.1 |
| F (API return types) | §6.2 Api facade, §6.5 Responsabilidades por capa | — |

## Anexo A: Log de verificación

Hallazgos verificados contra código real por el usuario (9 de 22 confirmados con precisión):

| Hallazgo | Verificado | Resultado |
|----------|------------|-----------|
| #1: api.py 6 execute + 2 commit + import sqlite3 | ✅ | Coincide exactamente |
| #2: UPDATE directos diag_dialogs.py | ✅ | Coincide exactamente |
| #3: apu.py f-string SQL | ✅ | Coincide. Matiz: literales hardcodeados, no inyectable hoy. |
| #4-5: self.window()._on_search() duplicado | ✅ | Mismo bloque 3 líneas copiado en 2 archivos |
| #6: _reload_presupuesto() 4 call sites | ✅ | Coincide exactamente |
| #7: explosion selectedItems | ✅ | Confirmado |
| #8-16: imports backend.database.db | ✅ | 9 archivos (8 Config/Rutas + 1 generar_hash) |
| #15: commits en api.py | ✅ | **Corregido:** no hay dual commit. Database.transaction() usa savepoints. El único commit real está dentro de RecalculoRepo.recalcular_proyecto(). |
| #18: bug commit condicional | ✅ | Confirmado: insumo_actualizar_campo sin commit cuando campo != "costo_final" |
| #20: insumo_ids_con_apu() retorna set[int] | ✅ | Coincide. Todos los callers usan solo `in`. |
| #22: _resolver_matriz() privado | ✅ | Confirmado. Además explosion.py:125 lo llama desde fuera. |
