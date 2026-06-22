# Guía de implementación — Nuevo importador y esquema

Cómo integrar `001_inicial.sql` e `importador_opus.py` al proyecto
Open APU Studio existente sin romper lo que ya funciona.

---

## Resumen de lo que cambia

| Archivo | Acción |
|---|---|
| `backend/db/migraciones/001_inicial.sql` | **Reemplazar** con el nuevo |
| `backend/servicios/importador_opus.py` | **Reemplazar** con el nuevo |
| `backend/db/repos/` (5 archivos) | **Conservar** — los repos existentes siguen siendo válidos con el nuevo esquema, solo cambian algunos nombres de columna |
| `backend/db/conexion.py` | **Sin cambios** — el sistema de migraciones ya funciona correctamente |
| `backend/opus/core.py` | **Sin cambios** por ahora |
| `frontend/` | **Sin cambios** — esta guía no toca el frontend |
| `main.py` | **Sin cambios** |

---

## Paso 1 — Reemplazar la migración inicial

Borra el archivo actual y pon el nuevo en su lugar:

```
backend/
└── db/
    └── migraciones/
        └── 001_inicial.sql   ← reemplazar con el archivo nuevo
```

> ⚠️ Si ya tienes bases de datos `.db` generadas con el esquema anterior,
> **no son compatibles** con el nuevo. Elimínalas y vuelve a importar.
> Las bases nuevas se generan desde cero con el importador nuevo.

---

## Paso 2 — Reemplazar el importador

```
backend/
└── servicios/
    └── importador_opus.py   ← reemplazar con el archivo nuevo
```

El nuevo importador **no usa** `PartidaRepo`, `ConceptoRepo` ni los repos
anteriores para insertar — escribe directo con `cur.execute()` porque necesita
control preciso del orden de inserción para el algoritmo WBS. Los repos
siguen siendo útiles para **leer** datos desde la app.

---

## Paso 3 — Actualizar los repos

El nuevo esquema renombró algunas columnas. Estos son los cambios que
afectan a los repos existentes:

### `insumos.py`

```python
# ANTES
CAMPOS = ["clave", "tipo", "unidad", "precio", ...]

# AHORA — 'tipo' se llama 'tipo_id' y es FK a tipos_insumo
CAMPOS = ["clave", "tipo_id", "unidad", "costo_final", ...]

# Actualizar también las queries de búsqueda:
def todos(self):
    return self._lista("""
        SELECT i.*, t.clave as tipo_clave, t.nombre as tipo_nombre
        FROM insumos i
        JOIN tipos_insumo t ON t.id = i.tipo_id
        WHERE i.activo = 1
        ORDER BY i.tipo_id, i.clave
    """)

def por_tipo(self, tipo_clave):
    # tipo_clave: 'material', 'mano_obra', 'herramienta', etc.
    return self._lista("""
        SELECT i.* FROM insumos i
        JOIN tipos_insumo t ON t.id = i.tipo_id
        WHERE t.clave = ? AND i.activo = 1
        ORDER BY i.clave
    """, [tipo_clave])
```

### `partidas.py` → ahora se llama `nodos`

La tabla `partidas` ya no existe — el árbol completo vive en `nodos`.
Renombrar el repo y actualizar las queries:

```python
# backend/db/repos/nodos.py  (renombrar partidas.py)

class NodoRepo(RepoBase):
    TABLA = "nodos"

    def hijos(self, padre_id=None):
        if padre_id is None:
            return self._lista("""
                SELECT * FROM nodos
                WHERE padre_id IS NULL AND activo = 1
                ORDER BY wbs
            """)
        return self._lista("""
            SELECT * FROM nodos
            WHERE padre_id = ? AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    def arbol(self, proyecto_id):
        """Devuelve todos los nodos del proyecto ordenados por WBS."""
        return self._lista("""
            SELECT n.*, e.nombre as estado_nombre, e.color as estado_color
            FROM nodos n
            JOIN estados_nodo e ON e.id = n.estado_id
            WHERE n.proyecto_id = ? AND n.activo = 1
            ORDER BY n.wbs
        """, [proyecto_id])

    def descendientes(self, nodo_id):
        """CTE recursiva — todos los hijos, nietos, etc."""
        return self._lista("""
            WITH RECURSIVE sub AS (
                SELECT * FROM nodos WHERE id = ? AND activo = 1
                UNION ALL
                SELECT n.* FROM nodos n
                JOIN sub s ON n.padre_id = s.id
                WHERE n.activo = 1
            )
            SELECT * FROM sub ORDER BY wbs
        """, [nodo_id])

    def ruta(self, nodo_id):
        """Breadcrumb: del nodo hasta la raíz."""
        return self._lista("""
            WITH RECURSIVE ruta AS (
                SELECT * FROM nodos WHERE id = ?
                UNION ALL
                SELECT n.* FROM nodos n
                JOIN ruta r ON n.id = r.padre_id
            )
            SELECT * FROM ruta ORDER BY nivel
        """, [nodo_id])

    def actualizar_subtotal(self, nodo_id):
        """Recalcula subtotal del nodo y sube hasta la raíz."""
        cur = self._cursor
        actual = nodo_id
        while actual is not None:
            cur.execute("""
                UPDATE nodos SET
                    subtotal = (
                        SELECT COALESCE(SUM(
                            CASE WHEN tipo = 'concepto'
                                 THEN COALESCE(importe, 0)
                                 ELSE COALESCE(subtotal, 0)
                            END
                        ), 0)
                        FROM nodos WHERE padre_id = ? AND activo = 1
                    ),
                    modificado_en = datetime('now')
                WHERE id = ?
            """, (actual, actual))
            row = cur.execute(
                "SELECT padre_id FROM nodos WHERE id = ?", (actual,)
            ).fetchone()
            actual = row["padre_id"] if row else None
        self._conn.commit()
```

### `conceptos.py`

La tabla `conceptos` ya no existe — los conceptos son nodos con
`tipo = 'concepto'`. Eliminar el archivo o reemplazarlo con:

```python
# backend/db/repos/conceptos.py
# Alias de conveniencia sobre NodoRepo

class ConceptoRepo(RepoBase):

    def por_partida(self, padre_id):
        return self._lista("""
            SELECT * FROM nodos
            WHERE padre_id = ? AND tipo = 'concepto' AND activo = 1
            ORDER BY wbs
        """, [padre_id])

    def buscar_por_clave(self, clave, proyecto_id):
        return self._uno("""
            SELECT * FROM nodos
            WHERE clave = ? AND proyecto_id = ? AND activo = 1
        """, [clave, proyecto_id])
```

### `apu.py`

Los cambios son menores — solo el nombre de una columna en `apu_totales`:

```python
# ANTES
"INSERT INTO apu_resumen (concepto_clave, total_materiales, ...)"

# AHORA — la tabla se llama apu_totales y liga por nodo_id (entero)
class ApuDetalleRepo(RepoBase):
    def por_nodo(self, nodo_id):
        return self._lista("""
            SELECT ad.*, i.descripcion, i.descripcion_corta,
                   i.unidad, t.clave as tipo_clave, t.nombre as tipo_nombre
            FROM apu_detalle ad
            JOIN insumos i ON i.id = ad.insumo_id
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE ad.nodo_id = ?
            ORDER BY ad.orden
        """, [nodo_id])

class ApuTotalesRepo(RepoBase):
    def por_nodo(self, nodo_id):
        return self._uno("""
            SELECT * FROM apu_totales WHERE nodo_id = ?
        """, [nodo_id])
```

---

## Paso 4 — Actualizar la llamada al importador en la UI

Busca en el frontend dónde se llama a `importar_opus()` y actualiza
la firma — el nuevo importador recibe `(carpeta, db_path, nombre_proyecto)`:

```python
# ANTES (importador viejo)
from backend.servicios.importador_opus import importar_opus
resultado = importar_opus(ruta_carpeta, db_path)

# AHORA (importador nuevo)
from backend.servicios.importador_opus import importar
resultado = importar(ruta_carpeta, db_path, nombre_proyecto="Mi Obra")

# resultado es un dict con:
# {
#   'proyecto_id': 1,
#   'nodos': 172,
#   'insumos': 330,
#   'apu_detalle': 484,
#   'apu_totales': 142,
#   'auxiliares': 235,
#   'pie_precios': 0,
# }
```

---

## Paso 5 — Actualizar `build_budget_tree()` en `core.py`

El `core.py` de `Conversor de opus` lee el SQLite viejo.
Si lo usas desde la app de PyQt, actualiza la query principal:

```python
# La nueva query para leer el árbol del presupuesto
def build_budget_tree(db_path, proyecto_id=1):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT
            n.id, n.padre_id, n.wbs, n.nivel, n.tipo,
            n.clave, n.descripcion, n.descripcion_corta,
            n.unidad, n.cantidad, n.precio_unitario,
            n.importe, n.subtotal,
            e.nombre  AS estado_nombre,
            e.color   AS estado_color
        FROM nodos n
        JOIN estados_nodo e ON e.id = n.estado_id
        WHERE n.proyecto_id = ? AND n.activo = 1
        ORDER BY n.wbs
    """, (proyecto_id,))

    filas = [dict(r) for r in cur.fetchall()]
    con.close()

    # Reconstruir árbol en memoria (igual que antes)
    by_id  = {f["id"]: f for f in filas}
    raices = []
    for f in filas:
        f["hijos"] = []
        pid = f["padre_id"]
        if pid and pid in by_id:
            by_id[pid]["hijos"].append(f)
        else:
            raices.append(f)
    return raices
```

> Con el nuevo esquema **no necesitas el algoritmo WBS en Python** para
> construir el árbol — `padre_id` ya está correctamente resuelto desde
> la importación. La query con `ORDER BY wbs` garantiza el orden visual.

---

## Paso 6 — Eliminar `core.py` del lazy import

El archivo `backend/opus/core.py` hace un import dinámico a
`Conversor de opus/backend/core.py` que es frágil (ver análisis previo).

Una vez que el nuevo importador esté funcionando, reemplaza ese archivo con:

```python
# backend/opus/core.py — versión limpia
import sqlite3


def build_budget_tree(db_path: str, proyecto_id: int = 1) -> list:
    """Lee el árbol de presupuesto desde el SQLite generado por el importador."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""
        SELECT n.id, n.padre_id, n.wbs, n.nivel, n.tipo,
               n.clave, n.descripcion, n.descripcion_corta,
               n.unidad, n.cantidad, n.precio_unitario,
               n.importe, n.subtotal,
               e.nombre AS estado_nombre, e.color AS estado_color
        FROM nodos n
        JOIN estados_nodo e ON e.id = n.estado_id
        WHERE n.proyecto_id = ? AND n.activo = 1
        ORDER BY n.wbs
    """, (proyecto_id,))
    filas = [dict(r) for r in cur.fetchall()]
    con.close()
    by_id  = {f["id"]: f for f in filas}
    raices = []
    for f in filas:
        f["hijos"] = []
        pid = f["padre_id"]
        if pid and pid in by_id:
            by_id[pid]["hijos"].append(f)
        else:
            raices.append(f)
    return raices


def count_nodes(nodes: list) -> int:
    total = len(nodes)
    for n in nodes:
        total += count_nodes(n.get("hijos", []))
    return total


def count_concepts(nodes: list) -> int:
    total = sum(1 for n in nodes if n["tipo"] == "concepto")
    for n in nodes:
        total += count_concepts(n.get("hijos", []))
    return total
```

---

## Orden de ejecución recomendado

```
1. Reemplazar 001_inicial.sql
2. Reemplazar importador_opus.py
3. Actualizar repos (nodos.py, apu.py, insumos.py)
4. Probar importación:
       python importador_opus.py "ruta/D60JALISCOT" test.db
   Verificar: nodos=172, insumos=330, apu_detalle=484
5. Actualizar core.py (quitar lazy import)
6. Probar que la app abre y muestra el árbol
```

---

## Números de referencia para validar

Si importas D60JALISCOT y el resultado es diferente a esto, hay un bug:

| Métrica | Esperado |
|---|---|
| Nodos totales | 172 |
| Nodos tipo concepto | 148 |
| Nodos tipo capítulo | 24 |
| Insumos | 330 |
| APU detalle (componentes) | ~484 |
| APU totales (resúmenes) | 142 |
| Auxiliares | 235 |
| Nodos resueltos por WBS | 122 |
| Nodos sin resolver | 0 |

