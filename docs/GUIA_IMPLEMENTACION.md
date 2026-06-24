# Guía de implementación — Nuevo importador y esquema

Cómo integrar `001_inicial.sql` e `importador_opus.py` al proyecto
Open APU Studio existente sin romper lo que ya funciona.

---

## Resumen de lo que cambia

| Archivo | Acción |
|---|---|
| `backend/schema.sql` | Archivo único del esquema (v3: `matriz_id`, es_compuesto, renombres) |
| `backend/importar.py` | Importador OPUS completo — lee DBF, resuelve árbol por WBS, inserta todo |
| `backend/repos.py` | Todos los repos en un solo archivo: NodoRepo, InsumoRepo, ConceptoRepo, ApuMatricesRepo, etc. |
| `backend/core.py` | Lógica de negocio: build_budget_tree, get_apu, validar, recalcular |
| `backend/db.py` | Conexión SQLite con auto-migración v2→v3 |
| `frontend/` | Widgets PyQt: arbol.py (árbol jerárquico), insumos.py (tabla plana), base.py (TreeTableWidget genérico) |

---

## Paso 1 — Reemplazar la migración inicial

Borra el archivo actual y pon el nuevo en su lugar:

```
backend/
└── schema.sql   ← esquema completo v3 (se aplica automáticamente al crear DB nueva)
```

> ⚠️ Si ya tienes bases de datos `.db` generadas con el esquema anterior,
> la migración v2→v3 se aplica automáticamente al abrir la DB
> (renombres + columna `matriz_id`).

---

## Paso 2 — Reemplazar el importador

```
backend/
└── importar.py   ← importador OPUS completo
```

El importador **no usa** repos para insertar — escribe directo con `cur.execute()`
porque necesita control preciso del orden de inserción para el algoritmo WBS.
Los repos se usan para **leer** datos desde la app.

---

## Paso 3 — Actualizar los repos

El nuevo esquema renombró algunas columnas. Estos son los cambios que
afectan a los repos existentes:

### `InsumoRepo` (en `repos.py`)

Los métodos `todos()` y `por_tipo()` ya incluyen JOIN con `tipos_insumo`
y agregan `tipo_clave` y `tipo_nombre` a cada fila.
El campo `es_compuesto` identifica insumos con APU propio.

### `NodoRepo` (en `repos.py`)

La tabla se llama `estructura_presupuesto`. El repo está en `backend/repos.py`.
`estado` es un entero (0-3), sin JOIN a `estados_nodo`.

### `ConceptoRepo` (en `repos.py`)

Filtra `estructura_presupuesto WHERE tipo = 'concepto'`.
Métodos: `todos()`, `buscar_por_clave()`.

### `ApuMatricesRepo` y `ApuResumenTotalesRepo` (en `repos.py`)

Tablas: `apu_matrices` y `apu_resumen_totales`, ambas con `matriz_id` unificado
(reemplaza los antiguos `concepto_id` e `insumo_compuesto_id` por separado).

```python
class ApuMatricesRepo(RepoBase):
    def por_matriz(self, matriz_id):
        """Componentes de un concepto o insumo compuesto."""
        return self._lista("""
            SELECT am.*, i.descripcion, i.descripcion_corta,
                   i.unidad, t.clave as tipo_clave, t.nombre as tipo_nombre
            FROM apu_matrices am
            JOIN insumos i ON i.id = am.insumo_id
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE am.matriz_id = ?
            ORDER BY am.orden
        """, [matriz_id])

class ApuResumenTotalesRepo(RepoBase):
    def por_matriz(self, matriz_id):
        return self._uno("""
            SELECT * FROM apu_resumen_totales WHERE matriz_id = ?
        """, [matriz_id])
```

---

## Paso 4 — Llamada al importador

```python
from backend.importar import importar
resultado = importar(carpeta_opus, db_path, nombre_proyecto="Mi Obra")

# resultado es un dict con:
# {
#   'proyecto_id': 1,
#   'nodos': 172,
#   'insumos': 330,
#   'apu_matrices': 686,
#   'apu_resumen_totales': 148,
#   'insumos_compuestos': 120,
#   'sobrecostos': 2,
# }
```

---

## Paso 5 — `build_budget_tree()` en `core.py`

Ya implementado en `backend/core.py`. Lee `estructura_presupuesto` sin JOIN
a `estados_nodo`, con `estado` como entero.

> Con el esquema actual **no necesitas el algoritmo WBS en Python** para
> construir el árbol — `padre_id` ya está correctamente resuelto desde
> la importación. La query con `ORDER BY wbs` garantiza el orden visual.

---

## Paso 6 — `backend/core.py`

Contiene toda la lógica de negocio: `build_budget_tree`, `get_apu`, `validar`,
`recalcular_subtotales`. Lee del SQLite generado por el importador.
No hay `backend/opus/` separado — todo está en `backend/`.

---

## Orden de ejecución recomendado

```
1. Editar `backend/schema.sql` (esquema completo v3)
2. Editar `backend/importar.py` (importador OPUS)
3. Editar `backend/repos.py`, `backend/core.py`, `backend/db.py`
4. Probar importación:
       python -c "from backend.importar import importar; importar(r'C:\OPUSCMS\Obras\D60JALISCOT', 'test.db')"
   Verificar: nodos=172, insumos=330, apu_matrices=686
5. Verificar que la app abre y muestra el árbol
```

---

---

## Paso 7 — Búsqueda multi-columna en frontend

La barra de búsqueda en la parte superior de la ventana filtra filas del widget activo
(tree de presupuesto o tabla de insumos). Por defecto busca en las columnas de texto
más relevantes, pero el usuario puede ajustarlo.

### Columnas de búsqueda por widget

| Widget | Columnas por defecto | Columnas disponibles en menú |
|---|---|---|
| `TablaArbol` (presupuesto) | Nivel, Clave, Descripción, Tipo | Todas las visibles |
| `TablaInsumos` (insumos) | Clave, Descripción, Familia | Todas las visibles |

### Mecanismo

- **Clic derecho** sobre la barra de búsqueda → menú con checkboxes por columna visible
- `triggered` (no `toggled`) evita que `setChecked()` durante la construcción del menú dispare el filtro
- `_search_cols: set[int] | None` donde `None` = buscar en todas, `set()` = buscar en ninguna
- `_on_search_col_toggle` recibe el conjunto `all_cols` de columnas visibles para gestionar
  la transición desde/hacia "buscar en todas"

### Archivos involucrados

- `frontend/widgets/base.py`: `filter_rows()` multi-columna con `_filter_item_multi()`,
  API `get_searchable_columns()`, `get/set_search_columns()`
- `frontend/widgets/arbol.py`: `_search_cols = {0, 1, 2, 8}`, `get_searchable_columns()`
- `frontend/widgets/insumos.py`: `_search_cols = {0, 1, 5}`, `get_searchable_columns()`
- `frontend/ventana.py`: `_on_search_context_menu()`, `_on_search_col_toggle()`

---

## Paso 8 — Familias y subfamilias en insumos

Las familias se importan desde el campo `ELE_GRUPO` del archivo `*P.DBF`
(además de `ELE_FAM`, `FAMILIA`, etc. para compatibilidad con formatos clásicos).

### Visualización

En la tabla de insumos, la columna "Familia" muestra `"Familia › Subfamilia"` si existe
subfamilia, o solo el nombre de la familia. Ambas se incluyen en la búsqueda multi-columna.

### Queries

`InsumoRepo` incluye `LEFT JOIN familias f ON f.id = i.familia_id` y
`LEFT JOIN subfamilias sf ON sf.id = i.subfamilia_id` en todos sus métodos,
retornando `familia_nombre` y `subfamilia_nombre`.

---

## Paso 9 — Columna Total unificada (presupuesto)

La antigua columna "Subtotal" se eliminó de la UI. La columna "Total" ahora muestra:

- **Conceptos** → `importe` (cantidad × precio_unitario, columna GENERATED en SQLite)
- **Capítulos** → `subtotal` (acumulado incluyendo hijos, recalculado por Python)

No hay cambios en el esquema — ambas columnas siguen en la DB. Solo se fusionó
la presentación en `arbol.py:_celdas()`.

---

## Números de referencia para validar

Si importas D60JALISCOT y el resultado es diferente a esto, hay un bug:

| Métrica | Esperado |
|---|---|
| Nodos totales | 172 |
| Nodos tipo concepto | 148 |
| Nodos tipo capítulo | 24 |
| Insumos | 330 |
| Insumos compuestos (es_compuesto=1) | 120 |
| APU matrices (componentes) | 686 |
| APU resumen totales | 148 |
| Sobrecostos | 2 |
| Nodos resueltos por WBS | 170 |
| Nodos sin resolver | 2 (raíces: WBS="" y WBS="1") |

