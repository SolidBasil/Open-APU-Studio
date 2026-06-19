# Open APU Studio — Visión del producto

**Open APU Studio** es una herramienta de presupuestación y análisis de precios unitarios para la industria de la construcción que permite a los usuarios trabajar sin depender de software propietario, manteniendo un flujo de trabajo rápido, sencillo y eficiente.

La aplicación estará enfocada inicialmente en profesionales independientes, estudiantes, despachos pequeños y constructoras pequeñas que requieran una herramienta rápida, ligera y práctica para el trabajo diario.

El proyecto prioriza la velocidad, la estabilidad y la facilidad de uso sobre la acumulación de funciones. Su naturaleza de código abierto permite que cualquier usuario pueda auditar, modificar y adaptar el software a sus necesidades particulares.

La aplicación funcionará de manera nativa en **Windows y Linux**, sin requerir configuraciones adicionales ni capas de compatibilidad. Esto amplía el acceso a usuarios y organizaciones que operan en entornos Linux, algo que OPUS 2010 no contempla.

La compatibilidad con proyectos de OPUS 2010 facilita la transición desde plataformas existentes, preservando el acceso a información y flujos de trabajo ya establecidos.

---

# Casos de uso y flujo de trabajo

Las primeras versiones del sistema mantendrán un flujo de trabajo familiar para usuarios de herramientas como OPUS y Neodata, reduciendo la curva de aprendizaje y facilitando la migración desde plataformas existentes.

La estructura general de proyectos, presupuestos, análisis de precios unitarios, catálogos e insumos buscará conservar los conceptos y procesos ampliamente utilizados en la industria.

Durante las etapas iniciales del desarrollo se priorizará la compatibilidad con los métodos de trabajo ya conocidos sobre la introducción de cambios radicales en la experiencia de usuario.

Las modificaciones al flujo de trabajo deberán estar justificadas por beneficios claros en productividad, facilidad de uso o reducción de errores. Los cambios se implementarán de manera gradual y estarán basados en la experiencia práctica obtenida durante el uso cotidiano del sistema.

El objetivo no es replicar cada comportamiento de los programas existentes, sino preservar aquello que funciona bien y mejorar progresivamente aquellos procesos que representen limitaciones para el usuario.

---

# Funciones y características

## Núcleo indispensable (MVP)

> Si esto no existe, difícilmente puede considerarse una alternativa a OPUS.

### Gestión de proyectos

- Crear proyecto
- Abrir proyecto
- Guardar proyecto
- Duplicar proyecto
- Importar proyecto OPUS 2010
- Exportar a Excel

### Catálogo de conceptos

- Alta, baja y edición de conceptos
- Descripción (el usuario identifica todo por descripción, no por clave)
- Unidad
- Cantidad
- Precio unitario
- Importe

### Análisis de precios unitarios (APU)

- Materiales
- Mano de obra
- Maquinaria
- Herramienta
- Auxiliares
- Rendimientos
- Costos directos
- Indirectos, financiamiento y utilidad (por proyecto)

### Catálogo de insumos

- Materiales
- Mano de obra
- Maquinaria
- Auxiliares
- Herramienta
- Familias de insumos (agrupación y búsqueda por categoría)

### Presupuesto

- Partidas
- Subpartidas
- Conceptos
- Resumen de presupuesto
- Totales

### Reportes básicos

- Presupuesto
- Catálogo de conceptos
- Análisis de precios unitarios
- Explosión de insumos

---

## Funciones importantes (Versión 1.x)

> Estas sí existían en OPUS y mucha gente las usa.

### Frentes

- Crear frentes
- Asignar cantidades por frente
- Consultar cantidades por frente

### Explosión de insumos

- Global
- Por partida
- Por frente

### Actualización de precios

- Modificación masiva
- Actualización desde catálogo
- Historial de cambios de precio por insumo

### Catálogos reutilizables

- Importar insumos
- Exportar insumos
- Copiar análisis entre proyectos

### Búsqueda

- Por palabra en descripción
- Por familia o categoría de insumo
- Resultado unificado: insumos, conceptos y familias en una sola lista

### Herramientas de productividad

- Copiar conceptos
- Duplicar análisis
- Edición múltiple
- Atajos de teclado

---

# Diseño de interfaz

Durante las primeras versiones, la interfaz mantendrá una estructura familiar para usuarios provenientes de OPUS 2010 y Neodata, con el objetivo de reducir la curva de aprendizaje y facilitar la adopción del sistema.

La organización general de módulos, ventanas y herramientas buscará conservar patrones conocidos por los usuarios de software de presupuestación de obra, priorizando la funcionalidad y productividad sobre cambios visuales radicales.

El diseño inicial estará basado en:

- Navegación similar a herramientas existentes de presupuestos
- Uso intensivo de tablas y vistas de información jerárquicas
- Acceso rápido a catálogos, conceptos y análisis de precios unitarios
- Compatibilidad con flujos de trabajo utilizados actualmente en la industria
- Uso eficiente mediante teclado y atajos

Sin embargo, la interfaz no estará limitada a replicar diseños antiguos. Conforme el proyecto evolucione y se identifiquen problemas de usabilidad, se realizarán mejoras progresivas enfocadas en:

- Reducir pasos innecesarios
- Mejorar la organización de información
- Facilitar la búsqueda y edición de datos
- Adaptar la experiencia a las necesidades reales de los usuarios

El objetivo final es crear una interfaz propia que conserve la productividad de los sistemas tradicionales, pero con una experiencia más moderna, clara y flexible.

### Paleta de colores

**Tema oscuro** (predeterminado)

| Rol | Color |
|---|---|
| Fondo principal | `#1e1e2e` |
| Panel lateral | `#181825` |
| Encabezados de tabla | `#313244` |
| Filas alternas | `#1e1e2e` / `#24243a` |
| Acento principal | `#89b4fa` |
| Texto principal | `#cdd6f4` |
| Texto secundario | `#6c7086` |
| Partidas (nivel 1) | `#cba6f7` |
| Subpartidas (nivel 2) | `#89dceb` |

**Tema claro** — inversión limpia de los mismos roles de color, disponible como alternativa.

Los temas se implementan mediante archivos QSS intercambiables en tiempo de ejecución. El cambio de tema no requiere reiniciar la aplicación.

---

# Compatibilidad OPUS

El sistema tendrá como objetivo principal la compatibilidad con archivos generados por OPUS 2010, debido a que esta versión cuenta con una amplia adopción y sigue siendo utilizada por muchos profesionales de la construcción.

La compatibilidad inicial estará enfocada en la lectura e importación de proyectos existentes, permitiendo recuperar información como:

- Datos generales del proyecto
- Catálogo de conceptos e insumos
- Partidas y agrupaciones
- Análisis de precios unitarios
- Precios, cantidades y relaciones entre elementos

La información importada será convertida al formato interno del sistema, permitiendo su consulta, modificación y administración mediante las herramientas propias de la aplicación. Los archivos originales de OPUS no se modifican en ningún momento.

### Exportación hacia OPUS 2010

Permitir generar archivos compatibles con OPUS 2010 para mantener la interoperabilidad con usuarios y colaboradores que continúen utilizando dicho sistema.

Para proyectos creados desde cero (sin clave OPUS), el sistema genera claves numéricas automáticamente al momento de exportar, siguiendo rangos por tipo de insumo que minimizan el riesgo de colisión con catálogos existentes. El usuario nunca necesita asignar claves manualmente.

| Tipo de insumo | Rango de clave generada |
|---|---|
| Material | 1000000 – 1999999 |
| Mano de obra | 2000000 – 2999999 |
| Herramienta | 4000000 – 4999999 |
| Equipo | 8000000 – 8999999 |
| Auxiliar | 9000000 – 9499999 |
| Concepto | 9500000 – 9999999 |

La compatibilidad podrá ampliarse posteriormente mediante soporte para más versiones de OPUS y herramientas de migración entre sistemas.

---

# Formato de archivo propio

Cada proyecto se almacena en un único archivo con extensión `.presup`, que contiene una base de datos SQLite completa. No existen archivos auxiliares ni carpetas de proyecto.

Las ventajas de este formato son:

- Un archivo = un proyecto, fácil de respaldar y transferir
- Funcionamiento sin conexión y sin servidores externos
- Integridad referencial garantizada por la base de datos
- Consultas rápidas independientemente del tamaño del proyecto

La estructura interna es completamente independiente del formato de OPUS 2010. Los archivos de OPUS se usan únicamente como fuente de importación.

### Escalabilidad futura

El formato `.presup` cubre el caso de uso previsto: uso individual y equipos de hasta 10 usuarios simultáneos en red local. Para escenarios con mayor concurrencia, la capa de acceso a datos está diseñada para migrar a PostgreSQL o MariaDB sin modificar la lógica de negocio.

---

# Arquitectura técnica

La aplicación está diseñada como un sistema modular con separación estricta entre capas. Cada capa tiene una responsabilidad única y no conoce los detalles internos de las demás.

## Stack tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Lenguaje | Python 3.11+ | Desarrollo rápido, ecosistema amplio, curva de entrada baja |
| Interfaz de usuario | PySide6 (Qt6) | Widgets nativos, multiplataforma, QSS para temas, QTreeView para tablas jerárquicas |
| Base de datos | SQLite + FTS5 | Embebida, sin servidor, búsqueda de texto completo nativa |
| Acceso a datos | SQL directo con patrón repositorio | Sin dependencias externas, control total, fácil de depurar |
| Reportes PDF | LaTeX | Separación datos/diseño, plantillas personalizables |
| Distribución | PyInstaller | Ejecutable independiente para Windows y Linux |

## Plataformas objetivo

- **Windows** — plataforma principal (`.exe` standalone o con instalador)
- **Linux** — soporte completo desde el inicio (binario nativo o `.AppImage`)

## Capas de la aplicación

```
┌─────────────────────────────────────────┐
│           Interfaz (PySide6)            │  QTreeView, QAbstractItemModel, QSS
│   Nunca importa sqlite3 directamente    │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│         Servicios / Lógica              │  Recálculo, importación, reportes
│   Nunca escribe SQL directamente        │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│    Repositorios (único lugar con SQL)   │  Un repo por tabla principal
│   Nunca toma decisiones de negocio      │
└────────────────────┬────────────────────┘
                     │
┌────────────────────▼────────────────────┐
│         SQLite (.presup)                │  FTS5, triggers, WAL, foreign keys
└─────────────────────────────────────────┘
```

La regla fundamental es que **SQL solo vive en los repositorios**. Si SQL aparece en la UI o en los servicios, es un error de arquitectura.

## Estructura de carpetas

```
proyecto/
├── main.py
├── db/
│   ├── conexion.py              -- manejo de la conexión SQLite
│   ├── migraciones/
│   │   ├── 001_inicial.sql
│   │   └── 002_frentes.sql
│   └── repos/
│       ├── base.py              -- RepoBase con _uno(), _lista(), _ejecutar()
│       ├── insumos.py
│       ├── conceptos.py
│       ├── partidas.py
│       ├── apu.py
│       ├── familias.py
│       └── busqueda.py
├── servicios/
│   ├── calculo.py               -- recálculo en cascada
│   ├── importador_opus.py
│   ├── exportador.py
│   └── reportes.py
├── ui/
│   ├── ventana_principal.py
│   ├── modelos/                 -- QAbstractItemModel por vista
│   └── widgets/
└── themes/
    ├── dark.qss
    └── light.qss
```

## Interfaz de usuario

La tabla jerárquica central usa `QTreeView + QAbstractItemModel`, que carga únicamente las filas visibles en pantalla. Esto garantiza rendimiento constante sin importar el tamaño del presupuesto.

## Base de datos — decisiones técnicas

Dos pragmas activos siempre al abrir cualquier archivo `.presup`:

- `PRAGMA foreign_keys = ON` — SQLite no los activa por defecto; sin esto las claves foráneas no se validan
- `PRAGMA journal_mode = WAL` — mejor rendimiento en lecturas, más seguro ante cierres inesperados

## Búsqueda — FTS5

La búsqueda de insumos usa el módulo FTS5 de SQLite con `tokenize='unicode61 remove_diacritics 1'`, lo que permite buscar sin importar acentos ("concreto" encuentra "concreto" y "concreto"). El índice incluye descripción y nombre de familia, por lo que buscar una palabra devuelve todos los registros donde aparece en cualquiera de los dos campos.

El índice se mantiene automáticamente mediante triggers en las tablas `insumos`, `conceptos`, `partidas` y `familias`.

## Migraciones

Sin ORM, las migraciones son archivos `.sql` numerados que el sistema aplica en orden al abrir un proyecto. Una tabla `schema_version` registra qué versión tiene cada archivo. Si el ejecutable espera una versión mayor, ejecuta las migraciones pendientes antes de abrir el proyecto.

## Recálculo en cascada

Cuando cambia el precio de un insumo o un rendimiento en el APU, el sistema recalcula en el siguiente orden:

```
Precio de insumo cambia
        ↓
apu_componentes  →  importe por línea
        ↓
apu_resumen  →  subtotales por tipo + costo directo
        ↓
apu_resumen  →  montos de indirectos (usando tabla indirectos)
        ↓
apu_resumen  →  precio de venta
        ↓
conceptos  →  precio_unitario, precio_venta, importe
        ↓
totales de partida y presupuesto (calculados con SUM() en consulta)
```

Los totales de partida y presupuesto no se almacenan en tabla — se calculan en consulta para garantizar que siempre coincidan con la suma real de sus conceptos.

---

# Sistema de reportes (PDF de salida)

El sistema de reportes utiliza un motor basado en LaTeX con plantillas personalizables. La separación entre datos y diseño permite modificar el formato de un reporte sin tocar la lógica del programa.

Características principales:

- Generación de reportes profesionales
- Plantillas editables por el usuario
- Compatibilidad con diferentes estilos de presentación
- Salida en PDF mediante compilación LaTeX

Reportes disponibles en el MVP: presupuesto, catálogo de conceptos, análisis de precios unitarios y explosión de insumos.

---

# Sistema de base de datos — tablas

Referencia completa de todas las tablas del archivo `.presup`.

| Tabla | Propósito | Notas |
|---|---|---|
| `schema_version` | Control de migraciones | 1 registro por versión aplicada |
| `proyectos` | Metadatos del proyecto | 1 registro por archivo |
| `proyecto_config` | Parámetros de cálculo globales | Horas/día, tasas, moneda |
| `indirectos` | Renglones de cargos sobre CD | Ordenados por `renglon`, editables por el usuario |
| `familias` | Agrupación jerárquica de insumos | Auto-referencia vía `familia_padre_id` |
| `insumos` | Catálogo de recursos | Precios por proyecto, tipo validado |
| `insumos_precio_historial` | Auditoría de cambios de precio | Append-only |
| `partidas` | Jerarquía del presupuesto | Auto-referencia vía `padre_id`, sin límite de profundidad |
| `conceptos` | Renglones con precio unitario | Siempre bajo una partida |
| `apu_componentes` | Desglose del APU línea por línea | N registros por concepto |
| `apu_resumen` | Subtotales del APU por tipo | 1 registro por concepto, se recalcula automáticamente |
| `auxiliares` | Componentes de un insumo auxiliar | Permite insumos compuestos sin crear un concepto |
| `frentes` | Zonas físicas de obra | Versión 1.x |
| `frentes_cantidades` | Cantidades por frente y concepto | Versión 1.x |
| `log_importacion` | Errores y advertencias de importación OPUS | Solo se llena al importar |
| `busqueda` | Índice FTS5 para búsqueda global | Tabla virtual, mantenida por triggers |
