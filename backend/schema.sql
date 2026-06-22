-- =============================================================================
-- 001_inicial.sql
-- Esquema inicial de Open APU Studio
-- =============================================================================
-- CONVENCIONES:
--   - Llaves primarias: siempre INTEGER PRIMARY KEY AUTOINCREMENT
--   - Fechas: TEXT en formato ISO 8601 'YYYY-MM-DD HH:MM:SS'
--   - Booleanos: INTEGER 0/1
--   - Soft-delete: columna 'activo INTEGER NOT NULL DEFAULT 1'
--   - Toda tabla editable tiene: creado_en, modificado_en, creado_por, modificado_por
--   - Las tablas de catálogo/semilla no llevan auditoría (son datos del sistema)
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- =============================================================================
-- BLOQUE 1: IDENTIDAD Y ROLES
-- Infraestructura mínima para escalar a trabajo colaborativo.
-- La lógica de login/sesión vive en la app, no en el esquema.
-- =============================================================================

CREATE TABLE IF NOT EXISTS roles (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    clave   TEXT    NOT NULL UNIQUE,  -- 'admin','editor','revisor','lector'
    nombre  TEXT    NOT NULL,
    nivel   INTEGER NOT NULL DEFAULT 0  -- mayor nivel = más permisos
);

-- Semilla de roles
INSERT INTO roles (clave, nombre, nivel) VALUES
    ('admin',    'Administrador', 3),
    ('editor',   'Editor',        2),
    ('revisor',  'Revisor',       1),
    ('lector',   'Lector',        0);

CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    email           TEXT    UNIQUE,          -- NULL válido para uso local/offline
    rol_id          INTEGER NOT NULL REFERENCES roles(id),
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    ultimo_acceso   TEXT
);

-- Usuario local por defecto (para uso sin login)
INSERT INTO usuarios (nombre, email, rol_id) VALUES
    ('Usuario local', NULL, (SELECT id FROM roles WHERE clave = 'admin'));


-- =============================================================================
-- BLOQUE 2: CATÁLOGOS DEL SISTEMA (semilla fija, no editable por el usuario)
-- =============================================================================

-- Tipos de insumo según OPUS (sistema de bits en PREFIJO)
CREATE TABLE IF NOT EXISTS tipos_insumo (
    id      INTEGER PRIMARY KEY,   -- coincide con el bit de OPUS: 1,2,4,8,16,32
    clave   TEXT    NOT NULL UNIQUE,
    nombre  TEXT    NOT NULL,
    orden   INTEGER NOT NULL DEFAULT 0
);

INSERT INTO tipos_insumo (id, clave, nombre, orden) VALUES
    (1,  'material',    'Material',           1),
    (2,  'mano_obra',   'Mano de obra',       2),
    (4,  'herramienta', 'Herramienta',        3),
    (8,  'equipo',      'Equipo',             4),
    (16, 'auxiliar',    'Auxiliar',           5),
    (32, 'concepto',    'Concepto compuesto', 6),
    (64, 'flete',       'Flete',              7),
    (128,'trabajo',     'Trabajo',            8);

-- Subtipo de herramienta (campo "Tipo de factor" en OPUS)
CREATE TABLE IF NOT EXISTS tipos_herramienta (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    clave  TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL
);

INSERT INTO tipos_herramienta (clave, nombre) VALUES
    ('estandar',          'Estándar'),
    ('herramienta_mano',  'Herramienta de mano'),
    ('equipo_seguridad',  'Equipo de seguridad');

-- Subtipo de equipo (H=costo horario, R=renta horaria, C=compuesto)
CREATE TABLE IF NOT EXISTS tipos_equipo (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    clave  TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL
);

INSERT INTO tipos_equipo (clave, nombre) VALUES
    ('costo_horario', 'Costo horario'),
    ('renta_horaria', 'Renta horaria'),
    ('compuesto',     'Compuesto');

-- Tipo de material (consumo vs instalación permanente)
CREATE TABLE IF NOT EXISTS tipos_material (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    clave  TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL
);

INSERT INTO tipos_material (clave, nombre) VALUES
    ('consumo',      'De consumo'),
    ('instalacion',  'De instalación permanente');

-- Estados de confiabilidad (semáforo) para nodos del árbol
CREATE TABLE IF NOT EXISTS estados_nodo (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    clave   TEXT    NOT NULL UNIQUE,
    nombre  TEXT    NOT NULL,
    color   TEXT    NOT NULL,   -- hex: '#RRGGBB'
    orden   INTEGER NOT NULL DEFAULT 0
);

INSERT INTO estados_nodo (clave, nombre, color, orden) VALUES
    ('sin_revisar',  'Sin revisar',  '#808080', 0),
    ('en_revision',  'En revisión',  '#F5A623', 1),
    ('verificado',   'Verificado',   '#4CAF7D', 2),
    ('cuestionado',  'Cuestionado',  '#E05252', 3);


-- =============================================================================
-- BLOQUE 3: CATÁLOGOS DEL PROYECTO (editables por el usuario)
-- =============================================================================

-- Árbol de familias/subfamilias de insumos
-- Es un árbol recursivo: subfamilia tiene padre_id != NULL
CREATE TABLE IF NOT EXISTS familias (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    padre_id  INTEGER REFERENCES familias(id) ON DELETE CASCADE,
    nombre    TEXT    NOT NULL,
    activo    INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_familias_padre ON familias(padre_id);

-- Proveedores de insumos
CREATE TABLE IF NOT EXISTS proveedores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT    NOT NULL,
    contacto    TEXT,
    telefono    TEXT,
    email       TEXT,
    notas       TEXT,
    activo      INTEGER NOT NULL DEFAULT 1,
    creado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);


-- =============================================================================
-- BLOQUE 4: PROYECTO Y CONFIGURACIÓN
-- =============================================================================

CREATE TABLE IF NOT EXISTS proyectos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT    NOT NULL,
    descripcion         TEXT,
    clave_opus          TEXT,               -- prefijo original de OPUS, ej 'D60JALISCOT'

    -- Concursante
    concursante_nombre  TEXT,
    concursante_domicilio TEXT,
    concursante_ciudad  TEXT,
    concursante_cp      TEXT,
    concursante_pais    TEXT    DEFAULT 'México',
    concursante_email   TEXT,
    concursante_tel     TEXT,
    rep_legal_nombre    TEXT,
    rep_legal_cargo     TEXT,

    -- Cliente
    cliente_nombre      TEXT,
    cliente_domicilio   TEXT,
    cliente_ciudad      TEXT,
    cliente_cp          TEXT,
    cliente_pais        TEXT    DEFAULT 'México',
    cliente_email       TEXT,
    cliente_tel         TEXT,

    -- Licitación
    licitacion_desc     TEXT,
    licitacion_fecha    TEXT,
    licitacion_numero   TEXT,
    licitacion_tipo     TEXT,   -- 'publica','directa','restringida','otra'

    -- Divisiones organizacionales (gobierno/grandes empresas)
    division_1          TEXT,
    division_2          TEXT,
    division_3          TEXT,
    division_4          TEXT,
    division_5          TEXT,
    division_6          TEXT,
    division_7          TEXT,

    -- Financiero
    moneda_nombre       TEXT    NOT NULL DEFAULT 'Peso mexicano',
    moneda_simbolo      TEXT    NOT NULL DEFAULT '$',
    moneda_abrev        TEXT    NOT NULL DEFAULT 'MXN',
    iva_nombre          TEXT    NOT NULL DEFAULT 'IVA',
    iva_porcentaje      REAL    NOT NULL DEFAULT 16.0,
    tiie_nombre         TEXT    NOT NULL DEFAULT 'TIIE',
    tiie_tasa           REAL    NOT NULL DEFAULT 0.0,
    puntos_bancarios_pagar  REAL NOT NULL DEFAULT 0.0,
    puntos_bancarios_favor  REAL NOT NULL DEFAULT 0.0,

    -- Totales (actualizados por Python al recalcular)
    total_obra          REAL    NOT NULL DEFAULT 0.0,

    -- Auditoría
    activo              INTEGER NOT NULL DEFAULT 1,
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    importado_en        TEXT    -- fecha de última importación desde OPUS
);

-- Configuración técnica del proyecto (separada para no mezclar con metadatos)
CREATE TABLE IF NOT EXISTS proyecto_config (
    proyecto_id         INTEGER PRIMARY KEY REFERENCES proyectos(id) ON DELETE CASCADE,
    horas_dia           REAL    NOT NULL DEFAULT 8.0,
    tasa_seguro         REAL    NOT NULL DEFAULT 0.0,
    tasa_interes        REAL    NOT NULL DEFAULT 0.0,
    decimales_costo     INTEGER NOT NULL DEFAULT 2,
    decimales_cantidad  INTEGER NOT NULL DEFAULT 3,
    decimales_factor    INTEGER NOT NULL DEFAULT 4,
    decimales_porcentaje INTEGER NOT NULL DEFAULT 2,
    -- Opciones de cálculo
    capturar_rendimientos   INTEGER NOT NULL DEFAULT 0,  -- 0=cantidad directa, 1=rendimiento
    unidad_cantidad_agrup   INTEGER NOT NULL DEFAULT 0   -- habilitar cantidad en agrupadores
);

-- Pie de precios unitarios (sobrecostos/indirectos) — uno por proyecto
CREATE TABLE IF NOT EXISTS pie_precios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL DEFAULT 0,
    variable        TEXT    NOT NULL,       -- nombre de la variable, ej 'CI'
    descripcion     TEXT    NOT NULL,       -- ej 'Costos indirectos'
    formula         TEXT,                  -- ej 'CD'
    porcentaje_mn   REAL    NOT NULL DEFAULT 0.0,
    porcentaje_me   REAL    NOT NULL DEFAULT 0.0,
    suma_en_total   INTEGER NOT NULL DEFAULT 1,
    es_egreso_financ   INTEGER NOT NULL DEFAULT 0,
    es_ingreso_financ  INTEGER NOT NULL DEFAULT 0,
    se_imprime      INTEGER NOT NULL DEFAULT 1,
    tipo            TEXT    NOT NULL DEFAULT 'formula_porcentaje'
                    CHECK(tipo IN ('formula_porcentaje','solo_formula'))
);

CREATE INDEX IF NOT EXISTS idx_pie_precios_proyecto ON pie_precios(proyecto_id);


-- =============================================================================
-- BLOQUE 5: ÁRBOL DEL PRESUPUESTO
-- Fuente de verdad: PRE_WBS (ver GUIA_ONBOARDING.md sección 6.3)
-- El importador filtra _deleted=0 antes de insertar.
-- Los subtotales se recalculan en Python (bottom-up) al editar.
-- =============================================================================

CREATE TABLE IF NOT EXISTS nodos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    padre_id        INTEGER REFERENCES nodos(id) ON DELETE CASCADE,  -- NULL = raíz

    -- Posición en el árbol
    wbs             TEXT    NOT NULL,   -- '1', '11', '111', '11101' — fuente de verdad jerárquica
    nivel           INTEGER NOT NULL,   -- 0=raíz, 1=capítulo, 2=subcapítulo... 5=concepto hoja
    orden           INTEGER NOT NULL DEFAULT 0,  -- posición entre hermanos

    -- Tipo de nodo
    tipo            TEXT    NOT NULL DEFAULT 'capitulo'
                    CHECK(tipo IN ('capitulo','concepto','auxiliar')),

    -- Identificación
    clave           TEXT,               -- código OPUS ej '0201002', solo en conceptos
    descripcion     TEXT    NOT NULL DEFAULT '',
    descripcion_corta TEXT,             -- máx ~40 chars, para vistas resumidas

    -- Medición (solo conceptos hoja)
    unidad          TEXT,
    cantidad        REAL,
    precio_unitario REAL,
    -- importe = cantidad × precio_unitario, columna computada
    importe         REAL GENERATED ALWAYS AS (
                        CASE
                            WHEN cantidad IS NOT NULL AND precio_unitario IS NOT NULL
                            THEN ROUND(cantidad * precio_unitario, 6)
                            ELSE NULL
                        END
                    ) STORED,

    -- Acumulado de hijos (actualizado por Python al editar)
    subtotal        REAL    NOT NULL DEFAULT 0.0,

    -- Confiabilidad (semáforo)
    estado_id       INTEGER NOT NULL DEFAULT 1 REFERENCES estados_nodo(id),

    -- Notas rápidas inline (para notas largas o colaborativas usar tabla 'notas')
    notas_rapidas   TEXT,

    -- Soft-delete y auditoría
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_nodos_proyecto ON nodos(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_nodos_padre    ON nodos(padre_id);
CREATE INDEX IF NOT EXISTS idx_nodos_wbs      ON nodos(proyecto_id, wbs);
CREATE INDEX IF NOT EXISTS idx_nodos_tipo     ON nodos(tipo);
CREATE INDEX IF NOT EXISTS idx_nodos_estado   ON nodos(estado_id);
CREATE INDEX IF NOT EXISTS idx_nodos_activo   ON nodos(activo);


-- =============================================================================
-- BLOQUE 6: INSUMOS
-- Catálogo maestro del proyecto. Un insumo puede aparecer en múltiples APUs.
-- =============================================================================

CREATE TABLE IF NOT EXISTS insumos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id         INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,

    -- Identificación
    clave               TEXT    NOT NULL,
    clave_usuario       TEXT,               -- clave alternativa para estandarización
    tipo_id             INTEGER NOT NULL REFERENCES tipos_insumo(id),
    es_compuesto        INTEGER NOT NULL DEFAULT 0,

    -- Descripción
    descripcion         TEXT,
    descripcion_corta   TEXT,
    unidad              TEXT,
    familia_id          INTEGER REFERENCES familias(id),
    proveedor_id        INTEGER REFERENCES proveedores(id),

    -- Costos (tres monedas según OPUS)
    costo_mn            REAL    NOT NULL DEFAULT 0.0,  -- moneda nacional
    costo_me            REAL    NOT NULL DEFAULT 0.0,  -- moneda extranjera
    costo_base          REAL    NOT NULL DEFAULT 0.0,  -- suma convertida a moneda obra
    costo_final         REAL    NOT NULL DEFAULT 0.0,  -- base + fórmulas adicionales

    -- Mano de obra específico
    salario_nominal     REAL,
    salario_real        REAL,               -- nominal × FASAR
    usar_hoja_fasar     INTEGER NOT NULL DEFAULT 0,

    -- Herramienta específico
    tipo_herramienta_id INTEGER REFERENCES tipos_herramienta(id),

    -- Equipo específico
    tipo_equipo_id      INTEGER REFERENCES tipos_equipo(id),

    -- Material específico
    tipo_material_id    INTEGER REFERENCES tipos_material(id),
    marca               TEXT,
    pais_origen         TEXT,

    -- Datos adicionales (todos los tipos)
    fecha_precio        TEXT,
    indice_inegi        TEXT,
    peso_kg             REAL,               -- kg por unidad, para explosión de insumos
    comentarios         TEXT,

    -- Fórmulas de costo (invalidan la fórmula general del proyecto)
    formula_costo_mn    TEXT,
    formula_costo_me    TEXT,

    -- Índices numéricos para fórmulas (1-3 MN, 4-6 ME)
    indice_1            REAL,
    indice_2            REAL,
    indice_3            REAL,
    indice_4            REAL,
    indice_5            REAL,
    indice_6            REAL,

    -- Soft-delete y auditoría
    activo              INTEGER NOT NULL DEFAULT 1,
    es_basico           INTEGER NOT NULL DEFAULT 0,
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now')),

    UNIQUE(proyecto_id, clave)
);

CREATE INDEX IF NOT EXISTS idx_insumos_proyecto  ON insumos(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_insumos_tipo      ON insumos(tipo_id);
CREATE INDEX IF NOT EXISTS idx_insumos_clave     ON insumos(proyecto_id, clave);
CREATE INDEX IF NOT EXISTS idx_insumos_familia   ON insumos(familia_id);
CREATE INDEX IF NOT EXISTS idx_insumos_activo    ON insumos(activo);


-- =============================================================================
-- BLOQUE 7: APU (Análisis de Precio Unitario)
-- =============================================================================

-- Nodos sintéticos para insumos compuestos que no están en el árbol
-- (materiales, auxiliares, mano de obra, etc. con su propia composición)
CREATE TABLE IF NOT EXISTS apu_nodos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id),
    clave           TEXT    NOT NULL,
    descripcion     TEXT    NOT NULL DEFAULT '',
    descripcion_corta TEXT,
    unidad          TEXT,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(proyecto_id, clave)
);

CREATE INDEX IF NOT EXISTS idx_apu_nodos_clave ON apu_nodos(proyecto_id, clave);

-- Desglose de insumos por concepto
CREATE TABLE IF NOT EXISTS apu_detalle (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo_id         INTEGER REFERENCES nodos(id) ON DELETE CASCADE,
    apu_nodo_id     INTEGER REFERENCES apu_nodos(id) ON DELETE CASCADE,
    insumo_id       INTEGER NOT NULL REFERENCES insumos(id),

    rendimiento     REAL    NOT NULL DEFAULT 0.0,
    cantidad        REAL    NOT NULL DEFAULT 0.0,
    precio          REAL    NOT NULL DEFAULT 0.0,   -- snapshot del precio al momento del APU
    -- importe = cantidad × precio, columna computada
    importe         REAL GENERATED ALWAYS AS (ROUND(cantidad * precio, 6)) STORED,

    formula         TEXT,   -- fórmula de cálculo de cantidad (de OPUS campo EXPRESION)
    orden           INTEGER NOT NULL DEFAULT 0,

    -- Auditoría
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_apu_detalle_nodo      ON apu_detalle(nodo_id);
CREATE INDEX IF NOT EXISTS idx_apu_detalle_apu_nodo  ON apu_detalle(apu_nodo_id);
CREATE INDEX IF NOT EXISTS idx_apu_detalle_insumo    ON apu_detalle(insumo_id);

-- Totales APU por concepto (actualizados por Python al editar apu_detalle)
CREATE TABLE IF NOT EXISTS apu_totales (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo_id             INTEGER REFERENCES nodos(id) ON DELETE CASCADE,
    apu_nodo_id         INTEGER REFERENCES apu_nodos(id) ON DELETE CASCADE,
    materiales          REAL    NOT NULL DEFAULT 0.0,
    mano_obra           REAL    NOT NULL DEFAULT 0.0,
    herramienta         REAL    NOT NULL DEFAULT 0.0,
    equipo              REAL    NOT NULL DEFAULT 0.0,
    auxiliares          REAL    NOT NULL DEFAULT 0.0,
    subcontratos        REAL    NOT NULL DEFAULT 0.0,
    costo_directo       REAL    NOT NULL DEFAULT 0.0,   -- suma de los anteriores
    indirectos_pct      REAL    NOT NULL DEFAULT 0.0,
    financiamiento_pct  REAL    NOT NULL DEFAULT 0.0,
    utilidad_pct        REAL    NOT NULL DEFAULT 0.0,
    cargo_adicional_pct REAL    NOT NULL DEFAULT 0.0,
    precio_venta        REAL    NOT NULL DEFAULT 0.0,
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Auxiliares (insumos compuestos intermedios, tabla *EGX en OPUS)
CREATE TABLE IF NOT EXISTS auxiliares (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    insumo_id       INTEGER NOT NULL REFERENCES insumos(id) ON DELETE CASCADE,
    componente_id   INTEGER NOT NULL REFERENCES insumos(id),
    cantidad        REAL    NOT NULL DEFAULT 0.0,
    precio          REAL    NOT NULL DEFAULT 0.0,
    importe         REAL GENERATED ALWAYS AS (ROUND(cantidad * precio, 6)) STORED
);

CREATE INDEX IF NOT EXISTS idx_auxiliares_insumo ON auxiliares(insumo_id);


-- =============================================================================
-- BLOQUE 8: COLABORACIÓN
-- Infraestructura lista para escalar. La lógica de permisos vive en la app.
-- =============================================================================

-- Notas por nodo (múltiples por nodo, con autor y fecha)
CREATE TABLE IF NOT EXISTS notas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nodo_id         INTEGER NOT NULL REFERENCES nodos(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    texto           TEXT    NOT NULL,
    resuelta        INTEGER NOT NULL DEFAULT 0,   -- 0=abierta, 1=resuelta
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notas_nodo ON notas(nodo_id);

-- Historial de cambios (auditoría genérica para cualquier tabla)
-- Agrupa cambios de una misma operación por 'sesion' (UUID generado en Python)
CREATE TABLE IF NOT EXISTS historial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion          TEXT    NOT NULL,       -- UUID para agrupar cambios de una operación
    tabla           TEXT    NOT NULL,
    registro_id     INTEGER NOT NULL,
    campo           TEXT    NOT NULL,
    valor_anterior  TEXT,                   -- siempre TEXT; Python hace la conversión
    valor_nuevo     TEXT,
    usuario_id      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    cambiado_en     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_historial_registro ON historial(tabla, registro_id);
CREATE INDEX IF NOT EXISTS idx_historial_sesion   ON historial(sesion);
CREATE INDEX IF NOT EXISTS idx_historial_usuario  ON historial(usuario_id);


-- =============================================================================
-- BLOQUE 9: CONTROL DE VERSIONES DEL ESQUEMA
-- Usado por DatabaseManager.aplicar_migraciones() para saber qué SQL ya corrió.
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    aplicado_en TEXT    NOT NULL DEFAULT (datetime('now')),
    descripcion TEXT
);

INSERT INTO schema_version (version, descripcion) VALUES
    (1, 'Esquema inicial: identidad, proyecto, árbol, insumos, APU, colaboración');

