# Guía de código — Open APU Studio

Convenciones y decisiones de diseño para mantener el código limpio y coherente.
Esta guía recoge lecciones aprendidas durante el desarrollo; aplica a todo código
nuevo y a cualquier modificación de código existente.

---

## 1. Base de datos

### 1.1 Sin retrocompatibilidad con esquemas anteriores

El proyecto está en beta. No se escriben scripts de migración para bases de datos
existentes ni ramas `elif version not in aplicadas` en `db.py`. Si el schema cambia,
se modifica `schema.sql` directamente y se reimporta el proyecto.

**Mal:**
```python
elif 3 not in aplicadas:
    cur.execute("ALTER TABLE apu_matrices ADD COLUMN matriz_id INTEGER")
    cur.execute("UPDATE apu_matrices SET matriz_id = COALESCE(concepto_id, ...)")
```

**Bien:** editar `schema.sql` y documentar el cambio en `docs/SCHEMA.md`.

### 1.2 Identificadores: siempre por `id` (INTEGER PRIMARY KEY)

Toda navegación, relación entre tablas y lógica de negocio usa el `id` entero.
`clave_opus` es solo un campo referencial para mostrar al usuario que importó de OPUS;
nunca se usa como llave en queries ni como parámetro de funciones internas.

**Mal:**
```python
insumo = repo.buscar_por_clave("MCONC001", proyecto_id)
self._api.apu(clave="0202002")
```

**Bien:**
```python
insumo = repo.buscar(insumo_id)
self._api.apu(insumo_id=42)
```

### 1.3 Sin soft-delete implícito en consultas nuevas

Toda query sobre tablas con columna `activo` debe incluir `AND activo = 1`.
El soft-delete existe para soportar Ctrl+Z futuro, no como papelera visible al usuario.

**Mal:**
```sql
SELECT * FROM insumos WHERE proyecto_id = ?
```

**Bien:**
```sql
SELECT * FROM insumos WHERE proyecto_id = ? AND activo = 1
```

### 1.4 Sin UNIQUE en `clave_opus`

`clave_opus` no tiene restricción UNIQUE. Insumos creados desde la app tienen
`clave_opus = NULL`. El mecanismo de deduplicación real es el `hash` (UNIQUE por proyecto).

### 1.5 Alias SQL para compatibilidad de contratos

Cuando una query devuelve un campo con nombre distinto al de la columna real,
usar `AS nombre_contrato` en el SELECT en lugar de renombrar en Python.

**Ejemplo correcto:**
```sql
SELECT i.clave_opus AS clave, i.costo_final AS clave_opus AS clave ...
```

Esto preserva el contrato de los dicts que consume la UI sin romper la nomenclatura
del schema.

### 1.6 El `historial` no se usa todavía

La tabla `historial` existe en el schema como infraestructura para Ctrl+Z colaborativo
(ver `docs/DECISIONES_PENDIENTES.md` FE-02). No escribir código que la lea ni la llene
hasta que se decida implementar ese feature. El Ctrl+Z de sesión actual se implementará
con un stack en memoria en `Api`, no en la DB.

---

## 2. Backend

### 2.1 Sin código muerto

No dejar variables construidas que no se usan, funciones que solo retornan `None`,
ni ramas `if` que nunca se ejecutan. Si una función deja de usarse, se elimina
en el mismo commit que la hace obsoleta.

**Señales de código muerto a eliminar:**
- Dict construido con comprehension que no se lee después
- Método `buscar_por_clave` que retorna `None` incondicional
- Importación en el encabezado del archivo que no aparece en el cuerpo
- Comentario `# TODO` o `# NOTA: ... eliminado en vX` de más de dos semanas

### 2.2 Stub explícito > función rota silenciosa

Si una función ya no tiene implementación válida pero otras partes del código
aún la llaman, mejor dejarla como stub explícito que como función que falla
silenciosamente.

**Bien:**
```python
def buscar_por_clave(self, clave, proyecto_id):
    """Columna clave eliminada del schema — usar buscar() por id."""
    return None
```

### 2.3 Importaciones dentro de funciones solo cuando hay circularidad

`from backend.repos import InsumoRepo` dentro de un método es aceptable solo
si hay riesgo de importación circular. En los demás casos, el import va al inicio
del archivo.

### 2.4 Un solo punto de verdad para el precio

El precio vigente de un insumo siempre viene de `insumos.costo_final`.
Nunca usar `PRE_PRE` del DBF de OPUS como precio final — es el valor que OPUS
tenía al momento de exportar y puede estar desactualizado. El importador lo usa
solo como valor provisional antes de vincular el `insumo_id`.

### 2.5 `clave_a_insumo` ya no existe

El dict `clave_a_insumo` fue eliminado. El cruce concepto→insumo se resuelve
directamente por `estructura_presupuesto.insumo_id`. No recrear ese dict.

---

## 3. Frontend

### 3.1 Navegación siempre por `id`, nunca por texto de celda

El `id` del registro se guarda en `UserRole` del item de Qt al poblar la tabla.
Para cualquier acción (editar, rastrear, abrir APU) se lee ese rol, no el texto
de ninguna columna.

**Mal:**
```python
clave = item.text(0)
self._api.apu(clave=clave)
```

**Bien:**
```python
insumo_id = item.data(0, Qt.ItemDataRole.UserRole)
self._api.apu(insumo_id=insumo_id)
```

### 3.2 La columna "Clave" es de solo lectura y oculta por defecto

Muestra `clave_opus` para usuarios que migraron desde OPUS y reconocen sus códigos.
No se usa para navegar ni buscar. No conectar señales de edición a esa columna.

### 3.3 Edición diferenciada por tipo de nodo en el árbol

El delegado `_Delegate` en `base.py` controla qué columna es editable según
el tipo del nodo. No usar `editable=True/False` en `add_row` para controlar
esto — el delegado lo maneja con `_EDITABLE_POR_TIPO`.

- Capítulos → col 4 (Descripción) editable
- Conceptos → col 6 (Cant) editable; Descripción es solo lectura (refleja el insumo)

### 3.4 Stubs en toolbar con `pass`, no con `QMessageBox`

Los botones de features pendientes se conectan con `pass` en `_conectar_btn`.
No crear handlers `_on_xxx` que solo muestran un `QMessageBox` de "próxima versión" —
eso es ruido en `handlers.py`.

**Mal:**
```python
elif tip == "Filtro":
    btn.clicked.connect(self._on_filtro)

def _on_filtro(self):
    QMessageBox.information(self, "Filtro", "Próxima versión.")
```

**Bien:**
```python
elif tip == "Filtro":
    pass  # pendiente de implementar
```

### 3.5 `claves_con_apu()` es para conceptos del árbol; `insumo_ids_con_apu()` para insumos

Son dos conjuntos distintos. No mezclarlos para marcar el ícono ▶ en la UI.

---

## 4. Importador

### 4.1 El nodo raíz de OPUS no se importa

El primer registro de `*1.DBF` con `PRE_NIVEL=0` y sin `PRE_COM` es un
contenedor interno de OPUS, no una partida real. Se filtra con:

```python
if nivel == 0 and not pre_com:
    continue
```

### 4.2 `*X.DBF` (EGX) no se lee

La tabla de auxiliares de OPUS fue eliminada en v3. No agregar `regs_x = dbf("X")`.
Los insumos compuestos se identifican por `es_compuesto = 1` en la tabla `insumos`.

### 4.3 El vínculo concepto→insumo se resuelve por `insumo_id`, no por `clave_opus`

Después de insertar el árbol, el importador hace un UPDATE que escribe `insumo_id`
en cada concepto de `estructura_presupuesto`. Todo código posterior usa ese campo
directamente. No reconstruir el cruce por `clave_opus` en runtime.

### 4.4 Deduplicación en reimportación

- Si `hash IS NOT NULL` → `UNIQUE(proyecto_id, hash)` previene duplicados automáticamente
- Si `hash IS NULL` (insumo sin descripción) → verificar por `clave_opus` manualmente
  antes de insertar, porque SQLite no detecta colisión entre NULLs en un índice UNIQUE

---

## 5. Limpieza general

### 5.1 Cuándo eliminar, cuándo convertir en stub

| Situación | Acción |
|---|---|
| Función que nada llama | Eliminar |
| Función llamada pero sin implementación válida | Stub con docstring explicando por qué |
| Columna SQL eliminada del schema | Actualizar todas las queries en el mismo commit |
| Import no usado | Eliminar en el mismo commit que lo hace obsoleto |

### 5.2 Comentarios históricos

Los comentarios `# NOTA: tabla X eliminada en vY` se eliminan junto con el código
que documentaban. Una vez que el código está limpio, el comentario solo añade ruido.
La historia vive en git, no en comentarios inline.

### 5.3 No anticipar features

No agregar columnas al schema, parámetros a funciones, ni ramas `if` para features
que no se van a implementar en el ciclo actual. La columna `formula` en
`estructura_presupuesto` es la excepción acordada explícitamente — está en el schema
pero `NULL` en todos los registros hasta que se diseñe la implementación.
