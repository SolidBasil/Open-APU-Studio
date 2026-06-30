# Plan de implementación gradual — limpieza de código legacy

Estrategia por fases, de menor a mayor riesgo, con verificación después de cada paso.

---

## Convención de verificación

Cada fase termina con:

```powershell
# 1. Verificar que la app arranca sin errores
python main.py --test   # o simplemente python main.py durante 3 segundos

# 2. Verificar que no hay referencias rotas
rg -n 'NombreClaseEliminada|MetodoEliminado' --include='*.py' frontend/ backend/

# 3. Probar funcionalidad afectada (abrir proyecto, navegar pestañas)
```

---

## Fase 0: Preparación (5 min)

```powershell
# 1. Hacer backup del estado actual
git add -A
git commit -m "backup antes de limpieza legacy"
git tag pre-limpieza-legacy

# 2. Identificar bases de datos existentes
Get-ChildItem -Recurse -Filter "*.db" | Select-Object FullName

# 3. Abrir la app y probar que todo funciona (estado basal)
python main.py
```

---

## Fase 1: Imports muertos y no-ops (seguro, 10 min)

> Sin cambio de comportamiento. Solo código que el intérprete nunca ejecuta.

### Paso 1.1 — Eliminar import `sqlite3` en `backend/core.py`

**Archivo:** `backend/core.py:19`

| Antes | Después |
|-------|---------|
| `import hashlib`<br>`import sqlite3` | `import hashlib` |

**Verificar:**
```powershell
python -c "from backend.core import generar_hash; print(generar_hash('Prueba'))"
```

### Paso 1.2 — Eliminar import `shutil` en `backend/exportar.py`

**Archivo:** `backend/exportar.py:14`

| Antes | Después |
|-------|---------|
| `import shutil` | *(eliminar línea)* |

**Verificar:**
```powershell
python -c "from backend.exportar import Exportador; print('OK')"
```

### Paso 1.3 — Eliminar import `QHeaderView` en `frontend/toolbar.py`

**Archivo:** `frontend/toolbar.py:14`

| Antes | Después |
|-------|---------|
| `QHeaderView, QApplication,` | `QApplication,` |

**Verificar:** arrancar app y abrir toolbar.

### Paso 1.4 — Eliminar import `QSplitter` en `frontend/paneles.py`

**Archivo:** `frontend/paneles.py:14`

| Antes | Después |
|-------|---------|
| `QAbstractItemView, QHeaderView, QMenu, QSplitter, QTabWidget,` | `QAbstractItemView, QHeaderView, QMenu, QTabWidget,` |

**Verificar:** arrancar app, navegar entre pestañas.

### Paso 1.5 — Eliminar import `Any` en `frontend/api.py`

**Archivo:** `frontend/api.py:30`

| Antes | Después |
|-------|---------|
| `from typing import Any` | *(eliminar línea)* |

**Verificar:** arrancar app, abrir proyecto.

### Paso 1.6 — Eliminar import `QRadioButton` en `frontend/widgets/explosion.py`

**Archivo:** `frontend/widgets/explosion.py:19`

| Antes | Después |
|-------|---------|
| `QRadioButton,` en la tupla | *(eliminar de la tupla)* |

**Verificar:** arrancar app, generar explosión de insumos.

### Paso 1.7 — Eliminar método `_init_db` en `frontend/ventana.py`

**Archivo:** `frontend/ventana.py:49-60`

Cambios:

| Línea | Antes | Después |
|-------|-------|---------|
| 49–50 | `self._db = None`<br>`self._api = None` | *(dejar igual, se queda en `__init__`)* |
| 53 | `self._init_db()` | *(eliminar línea)* |
| 57–60 | método `_init_db` completo | *(eliminar)* |

**Verificar:** arrancar app, el `__init__` sigue asignando `self._db = self._api = None`.

### Paso 1.8 — Eliminar imports redundantes de `Temas` en `frontend/ventana.py`

**Archivo:** `frontend/ventana.py:94,101`

```python
# Eliminar ambas ocurrencias de:
from frontend.temas import Temas
```

**Verificar:** arrancar app, el statusbar sigue funcionando y mostrando tema.

### Paso 1.9 — Eliminar atributo `_items` en `frontend/widgets/dialogs.py`

**Archivo:** `frontend/widgets/dialogs.py:16`

| Antes | Después |
|-------|---------|
| `_items: list[QListWidgetItem] = []` | *(eliminar línea)* |

**Verificar:** arrancar app, abrir diálogo de proyecto (Ctrl+N / botón Nuevo).

### Paso 1.10 — Eliminar parámetro `matriz_id` en `frontend/paneles.py`

**Archivo:** `frontend/paneles.py`

Cambios:

| Línea | Antes | Después |
|-------|-------|---------|
| 162 | `def _build_apu_tab(self, clave: str, matriz_id: int, descripcion: str = ""):` | `def _build_apu_tab(self, clave: str, descripcion: str = ""):` |
| 264 | `tab = self._build_apu_tab(clave, matriz_id, descripcion)` | `tab = self._build_apu_tab(clave, descripcion)` |

**Verificar:** arrancar app, abrir APU de un concepto → debe cargar sin error.

### Verificación de cierre de Fase 1

```powershell
# Arrancar la app
python main.py

# Probar navegación completa
# 1. Abrir/crear proyecto
# 2. Click en árbol del presupuesto
# 3. Abrir APU
# 4. Ir a pestaña insumos
# 5. Ir a pestaña conceptos
# 6. Generar reporte
```

---

## Fase 2: Stubs placeholder v1.x (riesgo bajo, 15 min)

> 8 métodos que solo muestran "Esta función estará disponible en una próxima versión."
> Al eliminar los métodos hay que desconectar los botones en la toolbar.

### Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `frontend/handlers.py` | Eliminar 8 métodos (3–5 líneas c/u) |
| `frontend/toolbar.py` | Eliminar 8 conexiones en `_conectar_btn()` |

### Paso 2.1 — Decidir destino de cada botón

Opción A — **Ocultar botón**: eliminar entrada de `_TOOLBAR_CFG` + eliminar handler + eliminar conexión.  
Opción B — **Atenuar botón**: eliminar handler + eliminar conexión (se cae al `else: conn = False`).  

Recomendación (opción A para los 8 — si no hay funcionalidad, el botón sobra):

| Botón | Pestaña | Grupo | Acción |
|-------|---------|-------|--------|
| `"Formato columnas"` | VISTA | Presentación | Eliminar de toolbar + handler |
| `"Filtro"` | VISTA | Ver | Eliminar de toolbar + handler |
| `"Parámetros proyecto"` | INICIO | Proyecto | Eliminar de toolbar + handler |
| `"Usuarios"` | INICIO | Sistema | Eliminar de toolbar + handler |
| `"APU"` | INFORMES | Generar | Eliminar de toolbar + handler |
| `"Explosión"` | INFORMES | Generar | Eliminar de toolbar + handler |
| `"Catálogo"` | INFORMES | Generar | Eliminar de toolbar + handler |
| `"Tema LaTeX"` | INFORMES | Plantilla | Eliminar de toolbar + handler |

### Paso 2.2 — Modificar `frontend/toolbar.py`

**a) Eliminar de `_TOOLBAR_CFG` los botones obsoletos:**

```python
# Antes (INICIO tab, líneas 61-62):
("Proyecto", [("⚙", "Parámetros proyecto"), ("🛈", "Información proyecto")]),
("Sistema",  [("⚙", "Configuración general"), ("👥", "Usuarios")]),

# Después:
("Proyecto", [("🛈", "Información proyecto")]),
("Sistema",  [("⚙", "Configuración general")]),
```

```python
# Antes (INFORMES, líneas 64-70):
("Generar", [
    ("📄", "Presupuesto"),
    ("📋", "APU"),
    ("📦", "Explosión"),
    ("📚", "Catálogo"),
]),

# Después:
("Generar", [
    ("📄", "Presupuesto"),
]),
```

```python
# Antes (INFORMES, Plantilla, líneas 75-77):
("Plantilla", [
    ("🎨", "Tema LaTeX"),
]),

# Después:
("Plantilla", []),   # o eliminar el grupo entero
```

```python
# Antes (VISTA tab, líneas 83-93 aprox):
"VISTA": [
    ...
    ("Presentación", [("🎨", "Formato columnas"), ...]),
    ("Ver", [..., ("🔍", "Filtro"), ...]),
],

# Después — eliminar entradas específicas de esos grupos
```

**b) Eliminar de `_conectar_btn()` las 8 líneas `elif tip == ...:`:**

```python
# Eliminar estas líneas (427-458):
elif tip == "Formato columnas":     # línea 427
elif tip == "Filtro":                # línea 433
elif tip == "Parámetros proyecto":  # línea 437
elif tip == "Usuarios":             # línea 443
elif tip == "APU":                  # línea 447
elif tip == "Explosión":            # línea 449
elif tip == "Catálogo":             # línea 451
elif tip == "Tema LaTeX":           # línea 457
```

### Paso 2.3 — Eliminar los 8 métodos de `frontend/handlers.py`

```python
# Eliminar estos métodos completos:
_on_formato_columnas      # líneas 958-962
_on_filtro                 # líneas 984-988
_on_parametros_proyecto   # líneas 992-996
_on_usuarios               # líneas 1048-1052
_on_generar_apu            # líneas 1085-1089
_on_generar_explosion      # líneas 1091-1095
_on_generar_catalogo       # líneas 1097-1101
_on_tema_latex             # líneas 1140-1144
```

### Verificación de Fase 2

```powershell
# 1. Arrancar app
python main.py

# 2. Verificar que los botones eliminados ya no aparecen en la toolbar
#    - Pestaña INICIO: no debe mostrar "Parámetros proyecto" ni "Usuarios"
#    - Pestaña INFORMES: solo "Presupuesto", "Compilar PDF", "Vista previa"
#    - Pestaña VISTA: no debe mostrar "Formato columnas" ni "Filtro"

# 3. Verificar que no quedan referencias a los métodos eliminados
rg -n '_on_formato_columnas|_on_filtro|_on_parametros_proyecto|_on_usuarios|_on_generar_apu|_on_generar_explosion|_on_generar_catalogo|_on_tema_latex' --include='*.py' frontend/
# Debe devolver 0 resultados

# 4. Probar todas las pestañas y botones restantes
```

---

## Fase 3: Schema y migraciones (riesgo medio, 10 min)

> Cambia cómo se abre la base de datos. Probar con una BD real.

### Paso 3.1 — Simplificar `backend/db.py:_aplicar_schema()`

**Archivo:** `backend/db.py:243-285`

Reemplazar:

```python
def _aplicar_schema(self):
    """Aplica schema.sql si la base de datos es nueva.
    Migra v2→v3 automáticamente en DBs existentes (agrega matriz_id).
    """
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"No se encontró el schema en {schema_path}")

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
        # DB nueva (ni v2 ni v3): ejecuta schema.sql completo (v3)
        sql = schema_path.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()
    elif 3 not in aplicadas:
        # Migración v2 → v3
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

Por:

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

### Verificación de Paso 3.1

```powershell
# 1. Probar que schema.sql se aplica correctamente en BD nueva
python -c "
from backend.db import Database
import tempfile, os
path = os.path.join(tempfile.gettempdir(), 'test_limpia.db')
db = Database.abrir(path)
cur = db.conn.execute('SELECT version, descripcion FROM schema_version')
print('Versiones:', cur.fetchall())
Database.cerrar()
os.remove(path)
print('OK - BD nueva creada correctamente')
"

# 2. Probar apertura de BD existente v3
python -c "
from backend.db import Database
db = Database.abrir('ruta/a/tu/proyecto_real.db')
print('Proyecto:', db.db_path)
print('Versiones:', db.conn.execute('SELECT version FROM schema_version').fetchall())
# Debe mostrar: [(2, 'v2: ...'), (3, 'v3: ...')]
Database.cerrar()
print('OK - BD existente abierta correctamente')
"
```

### Paso 3.2 — Eliminar `backend/migrations/001_agregar_hash_insumos.py`

```powershell
Remove-Item -LiteralPath "backend/migrations/001_agregar_hash_insumos.py"

# Si la carpeta queda vacía:
Remove-Item -LiteralPath "backend/migrations"
```

**Verificar:**
```powershell
python -c "print('OK - migrations eliminado')"
# No debe haber error por import faltante (ningún código lo importa)
```

### Paso 3.3 — Actualizar `docs/SCHEMA.md`

Cambiar cabecera de línea 3 y sección "Migraciones aplicadas" según
lo detallado en `MIGRACION_LIMPIEZA_RETROCOMPAT.md` Lote 4.

### Verificación de cierre de Fase 3

```powershell
# 1. Abrir la app con un proyecto real
python main.py

# 2. Importar un proyecto OPUS de prueba
# 3. Verificar que el árbol del presupuesto carga correctamente
# 4. Verificar que los APU se muestran sin error
# 5. Verificar que la exportación funciona
```

---

## Fase 4: Docstrings desactualizados (bajo riesgo, 5 min)

### Paso 4.1 — Actualizar `frontend/__init__.py`

Reemplazar el docstring completo por la versión actualizada
(detallada en `MIGRACION_LIMPIEZA_RETROCOMPAT.md` Lote 4.1).

### Paso 4.2 — Actualizar `backend/__init__.py`

Reemplazar el docstring completo por la versión actualizada
(detallada en `MIGRACION_LIMPIEZA_RETROCOMPAT.md` Lote 4.2).

### Verificación

```powershell
python -c "import frontend; print(frontend.__doc__)"
python -c "import backend; print(backend.__doc__)"
```

---

## Fase 5: Bugs por refactor incompleto ⚠️ (riesgo alto, pospuesto)

> **No ejecutar hasta que se tenga tiempo de pruebas exhaustivas.**
> Estos cambios corrigen bugs reales (crash al editar insumo, código duplicado).

### Pendiente para cuando se aborde

```powershell
# Preparación
git branch fix/refactor-orphaned-files
git checkout fix/refactor-orphaned-files
```

| Paso | Acción |
|------|--------|
| 5.1 | Mover `EditarDescripcionDialog` y `EditarPrecioDialog` de `frontend/dialogs.py` a `frontend/widgets/dialogs.py` |
| 5.2 | Copiar señales `editar_descripcion` y `editar_precio` + columna "Hash" de `frontend/insumos.py` a `frontend/widgets/insumos.py` |
| 5.3 | Eliminar `frontend/dialogs.py` y `frontend/insumos.py` |
| 5.4 | Eliminar líneas duplicadas `self._api = Api(...)` en `frontend/handlers.py:66-67,316-317` |

Detalles completos en `MIGRACION_LIMPIEZA_RETROCOMPAT.md` Lote 5.

---

## Resumen de ejecución

```powershell
# EJECUCIÓN COMPLETA (una línea por fase)
git tag pre-limpieza-legacy                              # Fase 0
# ... Fase 1 ...
git commit -m "fase 1: imports muertos y no-ops"
# ... Fase 2 ...
git commit -m "fase 2: stubs placeholder v1.x"
# ... Fase 3 ...
git commit -m "fase 3: schema simplificado y migrations eliminado"
# ... Fase 4 ...
git commit -m "fase 4: docstrings actualizados"
# ... Fase 5 (cuando corresponda) ...
git commit -m "fase 5: correcion archivos huerfanos del refactor"
```

## Rollback

Si algo sale mal en cualquier fase:

```powershell
git checkout -- .           # descartar cambios
git checkout pre-limpieza-legacy  # volver al estado original
```
