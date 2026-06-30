# Migración: limpieza de código legacy

Guía completa para eliminar código muerto, huérfano y retrocompatibilidad
ahora que el proyecto está en fase beta y no requiere soporte de versiones anteriores.

> **Estado de limpiezas previas:** ya se eliminaron comentarios legacy en
> `schema.sql`, `repos.py`, `importar.py` y se borró `docs/CAMBIOS_SCHEMA_V2.md`.

---

## Prerrequisito

Confirmar que **no existen archivos `.db` creados con schema v2** en producción.

```powershell
sqlite3 ruta/proyecto.db "SELECT version FROM schema_version;"
# Si devuelve algo distinto de 3, hay migración pendiente
```

---

## LOTE 1 — Schema y base de datos

### 1.1 `backend/db.py` — método `_aplicar_schema()`

**Ubicación:** líneas 243–285

**Qué hace hoy:** Crea `schema_version` manualmente, consulta versiones aplicadas,
y bifurca entre "BD nueva" y "migración v2→v3".

**Código a eliminar:**

```python
cur = self._conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER PRIMARY KEY,
        aplicado_en TEXT NOT NULL DEFAULT (datetime('now')),
        descripcion TEXT
    )
""")

aplicadas = {r[0] for r in cur.execute(
    "SELECT version FROM schema_version"
).fetchall()}

if 2 not in aplicadas:
    # DB nueva: ejecuta schema.sql completo (v3)
    sql = schema_path.read_text(encoding="utf-8")
    self._conn.executescript(sql)
    self._conn.commit()
elif 3 not in aplicadas:
    # Migración v2 → v3 — todo este bloque
    cur.executescript("""
        ALTER TABLE apu_matrices ADD COLUMN matriz_id INTEGER;
        UPDATE apu_matrices SET matriz_id = COALESCE(concepto_id, insumo_compuesto_id);
        CREATE INDEX IF NOT EXISTS idx_apu_mat_matriz ON apu_matrices(matriz_id);
        ALTER TABLE apu_resumen_totales ADD COLUMN matriz_id INTEGER;
        UPDATE apu_resumen_totales SET matriz_id = COALESCE(concepto_id, insumo_compuesto_id);
        INSERT OR IGNORE INTO schema_version (version, descripcion)
            VALUES (3, 'v3: matriz_id unico');
    """)
    self._conn.commit()
```

**Reemplazar por:**

```python
def _aplicar_schema(self):
    """Aplica schema.sql completo. Crea tablas si no existen."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"No se encontró el schema en {schema_path}")
    sql = schema_path.read_text(encoding="utf-8")
    self._conn.executescript(sql)
    self._conn.commit()
```

**Razón:** `schema.sql` ya tiene `CREATE TABLE IF NOT EXISTS schema_version`
e `INSERT OR IGNORE INTO schema_version VALUES (3, ...)`. No necesita orquestación.

**Líneas a eliminar:** 244–285 completas (42 → 7 líneas).

---

### 1.2 `backend/migrations/001_agregar_hash_insumos.py`

**Acción:** Eliminar archivo completo (168 líneas).

**Razón:** Agrega columna `hash` a `insumos` — columna que ya está en `schema.sql`
desde v3. No es llamado por ningún código. Si la carpeta `backend/migrations/`
queda vacía, eliminar también la carpeta.

---

## LOTE 2 — Código legacy general

### 2.1 `backend/core.py` — import `sqlite3` no usado

**Ubicación:** línea 19

```python
import sqlite3   # <-- nunca usado en este archivo
```

Eliminar la línea. El archivo usa `Database.instancia().conn` para todo.

---

### 2.2 `backend/exportar.py` — import `shutil` no usado

**Ubicación:** línea 14

```python
import shutil   # <-- nunca usado en este archivo
```

Eliminar la línea.

---

### 2.3 `frontend/toolbar.py` — import `QHeaderView` no usado

**Ubicación:** línea 14

```python
QHeaderView,   # <-- en la tupla de imports, nunca referenciado
```

Eliminar de la línea de import.

---

### 2.4 `frontend/paneles.py` — import `QSplitter` no usado

**Ubicación:** línea 14

```python
QSplitter,   # <-- en la tupla de imports, nunca referenciado
```

Eliminar de la línea de import.

---

### 2.5 `frontend/api.py` — import `Any` no usado

**Ubicación:** línea 30

```python
from typing import Any
```

`Any` nunca se usa en el archivo. Todos los type hints usan tipos concretos.

---

### 2.6 `frontend/widgets/explosion.py` — import `QRadioButton` no usado

**Ubicación:** línea 19

```python
QRadioButton,   # <-- en la tupla de imports de PySide6.QtWidgets
```

El archivo usa `_TarjetaRadio` (widget personalizado) en lugar de `QRadioButton`.

---

### 2.7 `frontend/ventana.py` — método `_init_db` no-op

**Ubicación:** líneas 57–60

```python
def _init_db(self):
    self._db = None
    self._api = None
```

Llama a `_init_db()` en `__init__` (línea 53), pero `__init__` ya asigna
`self._db = None` y `self._api = None` en líneas 49–50. Es un no-op.

**Acción:** eliminar el método y su llamada.

---

### 2.8 `frontend/ventana.py` — imports redundantes de `Temas`

**Ubicación:** líneas 94 y 101

```python
from frontend.temas import Temas
```

Aparece dentro de `_build_statusbar` y `_update_statusbar`, pero `Temas`
ya está importado a nivel de módulo (línea 19).

**Acción:** eliminar ambas líneas.

---

### 2.9 `frontend/widgets/dialogs.py` — atributo de clase `_items` no usado

**Ubicación:** línea 16

```python
_items: list[QListWidgetItem] = []
```

Se declara en `ProjectDialog` pero nunca se lee, escribe o itera.

**Acción:** eliminar la línea.

---

### 2.10 `frontend/paneles.py` — parámetro `matriz_id` no usado

**Ubicación:** línea 162

```python
def _build_apu_tab(self, clave: str, matriz_id: int, descripcion: str = ""):
```

El parámetro `matriz_id` se pasa desde `_abrir_apu` (línea 264) pero **nunca
se usa** en el cuerpo del método. La APU se resuelve vía `self._api.apu(clave)`.

**Acción:** eliminar `matriz_id` de la firma y de quien lo llama.

---

### 2.11 `frontend/handlers.py` — imports redundantes locales

A lo largo de `handlers.py` hay imports de `QMessageBox`, `QDialog`,
`QInputDialog`, y `pathlib.Path` que ya están importados al inicio del archivo.

**Ubicaciones:** líneas 42, 72, 79, 105–106, 143–144, 188–190, 960, 986, 994,
1050, 1087, 1093, 1099, 1142.

```python
from PySide6.QtWidgets import QMessageBox   # ya en el módulo top-level
```

**Nota:** los imports dentro de los 8 stubs v1.x desaparecen junto con los stubs
(Lote 3). Los demás son redundantes pero inofensivos.

---

## LOTE 3 — Stubs placeholder de v1.x

### 3.1 `frontend/handlers.py` — 8 métodos placeholder

**Ubicación:** líneas 958–1144

Todos son iguales: muestran un `QMessageBox.information` y no hacen nada más.

| Método | Línea | Título del placeholder |
|--------|-------|------------------------|
| `_on_formato_columnas` | 958 | "Formato de columnas" |
| `_on_filtro` | 984 | "Filtro avanzado" |
| `_on_parametros_proyecto` | 992 | "Parámetros de proyecto" |
| `_on_usuarios` | 1048 | "Usuarios" |
| `_on_generar_apu` | 1085 | "Reporte APU" |
| `_on_generar_explosion` | 1091 | "Reporte explosión" |
| `_on_generar_catalogo` | 1097 | "Reporte catálogo" |
| `_on_tema_latex` | 1140 | "Tema LaTeX" |

**Acción para cada uno:** eliminar el método completo (3–5 líneas c/u).
Si los métodos están conectados a acciones de menú/toolbar (en `toolbar.py`),
desconectar también esas conexiones.

**Total:** ~40 líneas eliminadas.

---

## LOTE 4 — Docstrings desactualizados

### 4.1 `frontend/__init__.py`

**Ubicación:** archivo completo (21 líneas)

**Problemas:**
- Línea 8: `ventana.py — Ventana principal (~1200 líneas)` → ventana.py tiene 103 líneas
- Líneas 10-13: lista 4 widgets en `widgets/` pero faltan `ajustes.py` y `explosion.py`
- No menciona `handlers.py`, `toolbar.py`, `paneles.py`, `api.py`

**Actualizar a:**

```python
"""
frontend/
=========
Paquete de interfaz gráfica de Open APU Studio.

Archivos:
    ventana.py       — Ventana principal (conecta handlers + toolbar + paneles)
    handlers.py      — Eventos y acciones de la UI
    toolbar.py       — Barra de herramientas superior
    paneles.py       — Paneles de contenido del área de trabajo
    api.py           — API de lectura para frontend
    temas.py         — Gestión de temas QSS (6 temas)
    widgets/
        base.py      — TreeTableWidget reutilizable
        arbol.py     — Tabla jerárquica del presupuesto
        insumos.py   — Tabla plana de catálogo de insumos
        dialogs.py   — Diálogos (ProjectDialog, etc.)
        ajustes.py   — Panel de ajustes de importación
        explosion.py — Panel de explosión de insumos
    temas/
        dark.qss     — Tema oscuro
        light.qss    — Tema claro
        hybrid.qss   — Tema híbrido
        rosa.qss     — Tema rosa
        cafe.qss     — Tema café
        verde.qss    — Tema verde
"""
```

### 4.2 `backend/__init__.py`

**Ubicación:** archivo completo (12 líneas)

**Problema:** no menciona `exportar.py`, `latex/`, ni el schema.

**Actualizar a:**

```python
"""
backend/
========
Paquete de lógica de negocio de Open APU Studio.

Archivos:
    db.py       — Conexión SQLite y aplicación del esquema
    schema.sql  — Esquema completo de la base de datos
    repos.py    — Repositorios de acceso a datos
    core.py     — Lógica de negocio pura (árbol, métricas, validación)
    importar.py — Importador de proyectos OPUS 2010 (.DBF → SQLite)
    exportar.py — Exportación a formato OPUS (.DBF)
    latex.py    — Generación de reportes en LaTeX
    latex/      — Plantillas .tex para reportes
"""
```

---

## LOTE 5 — Bugs por refactor incompleto (solo documentados, NO corregir aún)

Los siguientes no son legacy muerto sino **bugs activos** causados por un refactor
incompleto. Se listan aquí para cuando se decida intervenir.

### 5.1 Archivos huérfanos

| Archivo | Líneas | Problema |
|---------|--------|----------|
| `frontend/dialogs.py` | 259 | Contiene `EditarDescripcionDialog` y `EditarPrecioDialog`. No es importado por nadie. El import real en `paneles.py:393,406` apunta a `frontend.widgets.dialogs` que NO tiene esas clases. |
| `frontend/insumos.py` | 148 | Contiene `TablaInsumos` con señales `editar_descripcion`/`editar_precio` y columna "Hash". El widget activo es `frontend/widgets/insumos.py` que NO tiene esas señales. |

**Fix necesario (cuando se aborde):**
1. Mover las clases `EditarDescripcionDialog` y `EditarPrecioDialog` de `frontend/dialogs.py` a `frontend/widgets/dialogs.py`
2. Copiar las señales `editar_descripcion`, `editar_precio` y la columna "Hash" de `frontend/insumos.py` a `frontend/widgets/insumos.py`
3. Eliminar `frontend/dialogs.py` y `frontend/insumos.py`

### 5.2 Código duplicado

**`frontend/handlers.py:64-67`** y **`frontend/handlers.py:314-317`**:

```python
from frontend.api import Api
self._api = Api(self._db.conn, self._db.db_path)
from frontend.api import Api       # ← duplicado
self._api = Api(self._db.conn, ...) # ← duplicado
```

**Fix:** eliminar las líneas duplicadas (66-67 y 316-317).

---

## Verificación final

```powershell
# 1. Schema crea BD limpia
python -c "
import sqlite3
con = sqlite3.connect(':memory:')
con.executescript(open('backend/schema.sql', encoding='utf-8').read())
cur = con.cursor()
cur.execute('SELECT version FROM schema_version')
print('Versiones:', cur.fetchall())
"

# 2. No quedan imports legacy
rg -n 'concepto_id|insumo_compuesto_id|apu_auxiliares|apu_nodos' --include='*.py' backend/
```

---

## Resumen

| Lote | Archivos afectados | Líneas ± | Prioridad |
|------|--------------------|----------|-----------|
| L1 Schema | `db.py`, `migrations/001_...py` | −203 | Alta |
| L2 Imports / dead code | `core.py`, `exportar.py`, `toolbar.py`, `paneles.py`, `api.py`, `explosion.py`, `ventana.py`, `dialogs.py` | −17 | Alta |
| L3 Stubs | `handlers.py` (8 métodos) | −40 | Media |
| L4 Docs | `frontend/__init__.py`, `backend/__init__.py` | −5 / +30 | Baja |
| L5 Bugs† | `dialogs.py`, `insumos.py`, `handlers.py` | — | Crítica† |

**Total líneas eliminables (L1–L4):** ~265  
† L5 documentado pero pendiente de corrección.
