# Decisiones de diseño — Open APU Studio

Documento vivo que registra decisiones tomadas, pendientes y descartadas.
Actualizar cada vez que se tome una decisión relevante.

Formato de cada entrada:
- **Contexto** — por qué es una decisión que hay que tomar
- **Opciones consideradas** — qué se evaluó
- **Decisión** — qué se eligió y por qué
- **Consecuencias** — qué implica la decisión
- **Estado** — `✓ Decidido` / `⏳ Pendiente` / `✗ Descartado`

---

## BASE DE DATOS

### BD-01 — Una DB por proyecto
**Estado:** ✓ Decidido

**Contexto:**
Definir si todos los proyectos viven en una sola base de datos SQLite
o cada proyecto tiene su propio archivo.

**Opciones consideradas:**
- DB global con `proyecto_id` en cada tabla
- Un archivo `.db` por proyecto

**Decisión:**
Un archivo `.db` por proyecto.

**Consecuencias:**
- Los proyectos se pueden compartir enviando un solo archivo
- Un error en un proyecto no afecta a los demás
- La app necesita un mecanismo para abrir/cerrar proyectos
- Las queries no necesitan filtrar por `proyecto_id` si solo hay un proyecto abierto a la vez
- Si en el futuro se abre más de un proyecto simultáneamente, se necesita gestionar múltiples conexiones

---

### BD-02 — Carpeta de datos del usuario
**Estado:** ✓ Decidido

**Contexto:**
Definir dónde se guardan los archivos `.db` y la configuración de la app.

**Decisión:**
Carpeta estándar del sistema operativo para datos de usuario:

```
Windows: C:/Users/<usuario>/AppData/Local/Open APU Studio/
├── config.json          ← preferencias: tema, último proyecto abierto, etc.
├── proyectos/
│   ├── D60JALISCOT.db
│   └── CASA_EG.db
└── logs/
```

En Python se obtiene con:
```python
from pathlib import Path
import platformdirs
BASE = Path(platformdirs.user_data_dir("Open APU Studio", "OpenAPU"))
```

**Consecuencias:**
- Requiere `pip install platformdirs`
- Los proyectos no se borran al actualizar la app
- El usuario puede hacer backup copiando esa carpeta

---

### BD-03 — Campos del esquema pendientes (20%)
**Estado:** ⏳ Pendiente

**Contexto:**
Al diseñar el esquema quedó un 20% de campos sin definir,
principalmente relacionados con programa de obra y frentes.

**Decisión:**
Pendiente. Cuando se definan, se implementan como migraciones numeradas
siguiendo el sistema ya establecido en `db.py`.

**Consecuencias:**
- No bloquea el desarrollo actual
- El esquema v3 está completo y funcional para importación y visualización
- Las tablas `estructura_presupuesto` y `insumos` ya incluyen todos los campos OPUS esenciales

---

## IMPORTACIÓN

### IMP-01 — Reimportación de un proyecto existente
**Estado:** ✓ Implementado (borrar DB + reimportar)

**Contexto:**
Si el usuario intenta importar una carpeta OPUS cuyo proyecto ya existe
en la DB, hay que decidir qué hacer.

**Opciones a evaluar:**
- Reemplazar todo (borrar y reimportar)
- Merge inteligente (actualizar precios, conservar notas y estados)
- Crear una nueva versión del proyecto
- Bloquear y pedir confirmación

**Nota:**
El merge inteligente es el más útil pero el más complejo.
Reemplazar es simple pero destruye notas, estados del semáforo
y cualquier edición manual.

---

### IMP-02 — Exportación de vuelta a OPUS
**Estado:** ⏳ Pendiente

**Contexto:**
OPUS 2010 lee archivos `.DBF`. Exportar de vuelta requiere generar
esos archivos con la estructura exacta de cada tabla.

**Decisión:**
Fuera del alcance actual. Se evalúa en versiones posteriores.

**Consecuencias:**
- Requiere una librería que escriba `.DBF` (ej. `dbfwrite`)
- Requiere respetar tipos de campo (`N`, `C`, `M`, `L`, `D`) y longitudes exactas
- Requiere generar `.FPT` para campos Memo
- Usar codificación CP850

---

## FRONTEND

### FE-01 — Frontend solo lectura hasta pulir la lectura
**Estado:** ✓ Decidido

**Contexto:**
Definir cuándo habilitar la edición en la interfaz.

**Decisión:**
El frontend permanece en modo solo lectura hasta que la lectura y
visualización de datos esté 100% pulida y verificada contra proyectos reales.

**Consecuencias:**
- El árbol (`arbol.py`) permite edición de celdas (clave, descripción, unidad, cant, precio)
- La edición dispara recálculo de subtotales bottom-up
- `insumos.py` y `apu` detail permanecen solo lectura
- Cuando se habilite la edición total, el primer paso es implementar el Historial

---

### FE-02 — Ctrl+Z: historial en memoria con interfaz migrable
**Estado:** ✓ Decidido

**Contexto:**
Implementar deshacer/rehacer. Dos opciones evaluadas:
- Stack en memoria (simple, se pierde al cerrar)
- Historial en DB (persiste, soporta multiusuario)

**Decisión:**
Historial en memoria para el MVP, con una interfaz abstracta que
permite migrar a historial en DB sin tocar el resto de la app.

**Implementación:**

```python
# backend/historial.py

class Historial:
    """Interfaz común — toda la app usa esta clase, nunca la implementación."""

    def registrar(self, tabla, registro_id, campo,
                  valor_anterior, valor_nuevo, usuario_id=1):
        raise NotImplementedError

    def deshacer(self, usuario_id=1):
        raise NotImplementedError

    def rehacer(self, usuario_id=1):
        raise NotImplementedError

    def puede_deshacer(self, usuario_id=1) -> bool:
        raise NotImplementedError

    def puede_rehacer(self, usuario_id=1) -> bool:
        raise NotImplementedError


class HistorialMemoria(Historial):
    """MVP — stack en memoria. Se pierde al cerrar la app."""

    def __init__(self):
        self._pila    = []   # [(tabla, id, campo, anterior, nuevo)]
        self._futura  = []   # para rehacer

    def registrar(self, tabla, registro_id, campo,
                  valor_anterior, valor_nuevo, usuario_id=1):
        self._pila.append((tabla, registro_id, campo, valor_anterior, valor_nuevo))
        self._futura.clear()   # nueva acción cancela el rehacer

    def deshacer(self, usuario_id=1):
        if not self._pila:
            return None
        entrada = self._pila.pop()
        self._futura.append(entrada)
        return entrada   # la app aplica el valor_anterior

    def rehacer(self, usuario_id=1):
        if not self._futura:
            return None
        entrada = self._futura.pop()
        self._pila.append(entrada)
        return entrada   # la app aplica el valor_nuevo

    def puede_deshacer(self, usuario_id=1) -> bool:
        return bool(self._pila)

    def puede_rehacer(self, usuario_id=1) -> bool:
        return bool(self._futura)


class HistorialDB(Historial):
    """
    Multiusuario — escribe en la tabla `historial` del esquema.
    Implementar cuando se active la colaboración.
    Cada usuario deshace solo sus propios cambios.
    La sesion (UUID) agrupa cambios de una misma operación.
    Ver schema.sql tabla historial para la estructura.
    """
    # TODO: implementar cuando llegue multiusuario
    pass
```

Al arrancar la app:
```python
# main.py — cambiar esta línea cuando llegue multiusuario
from backend.historial import HistorialMemoria
historial = HistorialMemoria()
```

**Consecuencias:**
- La migración a `HistorialDB` requiere solo escribir esa clase (~40 líneas)
  y cambiar una línea en `main.py`
- La tabla `historial` en el esquema ya está lista para cuando se necesite
- **Regla importante:** nunca usar `HistorialMemoria` directamente en el código
  — siempre a través de la interfaz `Historial`

---

### FE-03 — Notas por nodo: panel inline en la fila
**Estado:** ✓ Decidido

**Contexto:**
La tabla `notas` del esquema permite comentarios por nodo.
Definir cómo aparecen en la interfaz: inline en la fila o panel lateral.

**Decisión:**
Las notas aparecen inline dentro de la misma fila del nodo,
expandiéndose al hacer clic en un icono de la columna de estado.

**Implementación futura:**
- Agregar columna "📝" en `arbol.py` que muestre el número de notas del nodo
- Al hacer clic expande una subfila con el hilo de comentarios
- Cada nota muestra: autor, fecha, texto, botón "Resolver"
- Las notas sin resolver muestran el ícono en color, las resueltas en gris

**Consecuencias:**
- No requiere panel lateral — mantiene el foco en el presupuesto
- El widget `TablaArbol` necesita soportar filas expandibles anidadas
- Requiere que el frontend esté en modo edición (depende de FE-01)

---

## COLABORACIÓN

### COL-01 — Sistema de login
**Estado:** ⏳ Pendiente

**Contexto:**
La infraestructura de `usuarios` y `roles` ya existe en el esquema.
Falta definir el flujo de autenticación.

**Opciones a evaluar:**
- Sin login: el usuario escribe su nombre al abrir la app (simple)
- Login local: usuario + contraseña guardados en la DB
- Login centralizado: servidor de autenticación (complejo, requiere backend web)

**Nota:**
Para uso de pequeña empresa probablemente basta con login local.
El login centralizado solo tiene sentido si hay sync en red.

---

### COL-02 — Sincronización entre usuarios
**Estado:** ⏳ Pendiente

**Contexto:**
Si varios usuarios trabajan en el mismo proyecto, necesitan
ver los cambios del otro.

**Opciones a evaluar:**
- Archivo compartido (Dropbox/Drive) — simple pero con riesgo de conflictos
- Servidor central con API — complejo, requiere infraestructura
- SQLite en red (WAL mode) — funciona en LAN, no en internet

**Nota:**
El modo WAL ya está activado en `db.py`. SQLite soporta múltiples
lectores simultáneos y un escritor — viable para equipos pequeños en LAN.

---

### COL-03 — Semáforo: quién puede cambiar el estado
**Estado:** ⏳ Pendiente

**Contexto:**
Los nodos tienen un estado de confiabilidad (sin revisar / en revisión /
verificado / cuestionado). Hay que decidir quién puede cambiarlo.

**Opciones a evaluar:**
- Cualquier usuario puede cambiar cualquier estado
- Solo el rol `revisor` o superior puede marcar como `verificado`
- El autor del nodo no puede verificar su propio trabajo

**Nota:**
La tabla `roles` ya tiene niveles (0-3). La lógica de permisos
vive en la app, no en el esquema.

---

## DISTRIBUCIÓN

### DIS-01 — Empaquetado con PyInstaller
**Estado:** ⏳ Pendiente

**Contexto:**
Distribuir la app sin requerir que el usuario instale Python.

**Decisión:**
Pendiente hasta tener el lector de datos 100% funcional.

**Nota:**
PyInstaller ya está en el plan original. Considerar también
`Nuitka` como alternativa más rápida en ejecución.

---

*Última actualización: Junio 2026*
