-- =============================================================================
-- schema.sql — Open APU Studio v2
-- =============================================================================
-- CONVENCIONES:
--   - Llaves primarias: INTEGER PRIMARY KEY AUTOINCREMENT
--   - Fechas: TEXT en ISO 8601 'YYYY-MM-DD HH:MM:SS'
--   - Booleanos: INTEGER 0/1
--   - Soft-delete: columna 'activo INTEGER NOT NULL DEFAULT 1'
--   - Auditoría: creado_por, creado_en, modificado_por, modificado_en
--   - Catálogos de semilla: sin auditoría
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;


-- =============================================================================
-- BLOQUE 1: USUARIOS
-- Sin tabla de roles — app monousuario en esta versión.
-- La infraestructura de colaboración (historial, notas) ya referencia usuario_id
-- para cuando se active el trabajo en red.
-- =============================================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    email           TEXT    UNIQUE,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    ultimo_acceso   TEXT
);

-- Usuario local por defecto
INSERT OR IGNORE INTO usuarios (nombre, email) VALUES ('Usuario local', NULL);


-- =============================================================================
-- BLOQUE 2: CATÁLOGOS DEL SISTEMA (semilla fija)
-- =============================================================================

-- Tipos de insumo según OPUS (sistema de bits en campo PREFIJO)
-- ids 1-32 coinciden con el sistema de bits de OPUS
-- ids 64 y 128 son extensiones para fletes y trabajos (versiones futuras de OPUS)
CREATE TABLE IF NOT EXISTS tipos_insumo (
    id      INTEGER PRIMARY KEY,
    clave   TEXT    NOT NULL UNIQUE,
    nombre  TEXT    NOT NULL,
    orden   INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO tipos_insumo (id, clave, nombre, orden) VALUES
    (1,   'material',    'Material',           1),
    (2,   'mano_obra',   'Mano de obra',       2),
    (4,   'herramienta', 'Herramienta',        3),
    (8,   'equipo',      'Equipo',             4),
    (16,  'auxiliar',    'Auxiliar',           5),
    (32,  'concepto',    'Concepto compuesto', 6),
    (64,  'flete',       'Flete',              7),
    (128, 'trabajo',     'Trabajo',            8);


-- =============================================================================
-- BLOQUE 3: CATÁLOGOS DEL PROYECTO (editables por el usuario)
-- =============================================================================

-- Familias de insumos — nivel superior de clasificación
CREATE TABLE IF NOT EXISTS familias (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT    NOT NULL,
    activo  INTEGER NOT NULL DEFAULT 1
);

-- Subfamilias — segundo nivel, siempre ligadas a una familia
CREATE TABLE IF NOT EXISTS subfamilias (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    familia_id  INTEGER NOT NULL REFERENCES familias(id) ON DELETE CASCADE,
    nombre      TEXT    NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_subfamilias_familia ON subfamilias(familia_id);

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
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                  TEXT    NOT NULL,
    descripcion             TEXT,
    clave_opus              TEXT,       -- prefijo original de OPUS, ej 'D60JALISCOT'

    -- Concursante
    concursante_nombre      TEXT,
    concursante_domicilio   TEXT,
    concursante_ciudad      TEXT,
    concursante_cp          TEXT,
    concursante_pais        TEXT    DEFAULT 'México',
    concursante_email       TEXT,
    concursante_tel         TEXT,
    rep_legal_nombre        TEXT,
    rep_legal_cargo         TEXT,

    -- Cliente
    cliente_nombre          TEXT,
    cliente_domicilio       TEXT,
    cliente_ciudad          TEXT,
    cliente_cp              TEXT,
    cliente_pais            TEXT    DEFAULT 'México',
    cliente_email           TEXT,
    cliente_tel             TEXT,

    -- Licitación
    licitacion_desc         TEXT,
    licitacion_fecha        TEXT,
    licitacion_numero       TEXT,
    licitacion_tipo         TEXT,   -- 'publica','directa','restringida','otra'

    -- Divisiones organizacionales (gobierno / grandes empresas)
    division_1              TEXT,
    division_2              TEXT,
    division_3              TEXT,
    division_4              TEXT,
    division_5              TEXT,
    division_6              TEXT,
    division_7              TEXT,

    -- Financiero
    moneda_nombre           TEXT    NOT NULL DEFAULT 'Peso mexicano',
    moneda_simbolo          TEXT    NOT NULL DEFAULT '$',
    moneda_abrev            TEXT    NOT NULL DEFAULT 'MXN',
    iva_nombre              TEXT    NOT NULL DEFAULT 'IVA',
    iva_porcentaje          REAL    NOT NULL DEFAULT 16.0,
    tiie_nombre             TEXT    NOT NULL DEFAULT 'TIIE',
    tiie_tasa               REAL    NOT NULL DEFAULT 0.0,
    puntos_bancarios_pagar  REAL    NOT NULL DEFAULT 0.0,
    puntos_bancarios_favor  REAL    NOT NULL DEFAULT 0.0,

    -- Total (actualizado por Python al recalcular)
    total_obra              REAL    NOT NULL DEFAULT 0.0,

    -- Auditoría
    activo                  INTEGER NOT NULL DEFAULT 1,
    creado_por              INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en               TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por          INTEGER REFERENCES usuarios(id),
    modificado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    importado_en            TEXT
);

-- Configuración técnica del proyecto
CREATE TABLE IF NOT EXISTS configuracion_proyecto (
    proyecto_id             INTEGER PRIMARY KEY REFERENCES proyectos(id) ON DELETE CASCADE,
    horas_dia               REAL    NOT NULL DEFAULT 8.0,
    tasa_seguro             REAL    NOT NULL DEFAULT 0.0,
    tasa_interes            REAL    NOT NULL DEFAULT 0.0,
    decimales_costo         INTEGER NOT NULL DEFAULT 2,
    decimales_cantidad      INTEGER NOT NULL DEFAULT 3,
    decimales_factor        INTEGER NOT NULL DEFAULT 4,
    decimales_porcentaje    INTEGER NOT NULL DEFAULT 2,
    capturar_rendimientos   INTEGER NOT NULL DEFAULT 0,
    unidad_cantidad_agrup   INTEGER NOT NULL DEFAULT 0
);

-- Sobrecostos / indirectos — renglones del pie de precios unitarios
CREATE TABLE IF NOT EXISTS sobrecostos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL DEFAULT 0,
    variable        TEXT    NOT NULL,   -- ej 'CI'
    descripcion     TEXT    NOT NULL,   -- ej 'Costos indirectos'
    formula         TEXT,               -- ej 'CD'
    porcentaje_mn   REAL    NOT NULL DEFAULT 0.0,
    porcentaje_me   REAL    NOT NULL DEFAULT 0.0,
    suma_en_total   INTEGER NOT NULL DEFAULT 1,
    es_egreso_financ    INTEGER NOT NULL DEFAULT 0,
    es_ingreso_financ   INTEGER NOT NULL DEFAULT 0,
    se_imprime      INTEGER NOT NULL DEFAULT 1,
    tipo            TEXT    NOT NULL DEFAULT 'formula_porcentaje'
                    CHECK(tipo IN ('formula_porcentaje', 'solo_formula'))
);

CREATE INDEX IF NOT EXISTS idx_sobrecostos_proyecto ON sobrecostos(proyecto_id);


-- =============================================================================
-- BLOQUE 5: ESTRUCTURA DEL PRESUPUESTO
-- Fuente de verdad jerárquica: campo wbs (PRE_WBS en OPUS).
-- El importador filtra _deleted=True antes de insertar.
-- Los subtotales se recalculan en Python bottom-up al editar.
--
-- Campo estado (semáforo de confiabilidad):
--   0 = Sin revisar  (#808080 gris)
--   1 = En revisión  (#F5A623 ámbar)
--   2 = Verificado   (#4CAF7D verde)
--   3 = Cuestionado  (#E05252 rojo)
-- El frontend mapea el entero al color — sin JOIN, sin tabla auxiliar.
-- =============================================================================

CREATE TABLE IF NOT EXISTS estructura_presupuesto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    padre_id        INTEGER REFERENCES estructura_presupuesto(id) ON DELETE CASCADE,

    -- Posición en el árbol
    wbs             TEXT    NOT NULL,
    nivel           INTEGER NOT NULL,
    orden           INTEGER NOT NULL DEFAULT 0,

    -- Tipo de nodo
    tipo            TEXT    NOT NULL DEFAULT 'capitulo'
                    CHECK(tipo IN ('capitulo', 'concepto')),

    -- Identificación
    clave           TEXT,
    descripcion     TEXT    NOT NULL DEFAULT '',
    descripcion_corta TEXT,

    -- Medición (solo conceptos hoja)
    unidad          TEXT,
    cantidad        REAL,
    precio_unitario REAL,
    importe         REAL GENERATED ALWAYS AS (
                        CASE
                            WHEN cantidad IS NOT NULL AND precio_unitario IS NOT NULL
                            THEN ROUND(cantidad * precio_unitario, 6)
                            ELSE NULL
                        END
                    ) STORED,

    -- Acumulado de hijos (actualizado por Python)
    subtotal        REAL    NOT NULL DEFAULT 0.0,

    -- Semáforo de confiabilidad: 0=sin revisar, 1=en revisión, 2=verificado, 3=cuestionado
    estado          INTEGER NOT NULL DEFAULT 0,

    -- Nota rápida inline
    notas_rapidas   TEXT,

    -- Soft-delete y auditoría
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ep_proyecto ON estructura_presupuesto(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_ep_padre    ON estructura_presupuesto(padre_id);
CREATE INDEX IF NOT EXISTS idx_ep_wbs      ON estructura_presupuesto(proyecto_id, wbs);
CREATE INDEX IF NOT EXISTS idx_ep_tipo     ON estructura_presupuesto(tipo);
CREATE INDEX IF NOT EXISTS idx_ep_estado   ON estructura_presupuesto(estado);
CREATE INDEX IF NOT EXISTS idx_ep_activo   ON estructura_presupuesto(activo);


-- =============================================================================
-- BLOQUE 6: INSUMOS
-- Catálogo maestro del proyecto.
-- Un insumo puede aparecer en múltiples APUs.
-- tipo_trabajo solo aplica cuando tipo_id = 128 (trabajo), NULL en el resto.
-- subfamilia_id siempre debe pertenecer a la familia_id indicada.
-- =============================================================================

CREATE TABLE IF NOT EXISTS insumos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id         INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,

    -- Identificación
    clave               TEXT    NOT NULL,
    clave_usuario       TEXT,
    tipo_id             INTEGER NOT NULL REFERENCES tipos_insumo(id),
    es_compuesto        INTEGER NOT NULL DEFAULT 0,

    -- Descripción
    descripcion         TEXT,
    descripcion_corta   TEXT,
    unidad              TEXT,
    familia_id          INTEGER REFERENCES familias(id),
    subfamilia_id       INTEGER REFERENCES subfamilias(id),
    proveedor_id        INTEGER REFERENCES proveedores(id),

    -- Costos
    costo_mn            REAL    NOT NULL DEFAULT 0.0,
    costo_me            REAL    NOT NULL DEFAULT 0.0,
    costo_base          REAL    NOT NULL DEFAULT 0.0,
    costo_final         REAL    NOT NULL DEFAULT 0.0,

    -- Mano de obra
    salario_nominal     REAL,
    salario_real        REAL,
    usar_hoja_fasar     INTEGER NOT NULL DEFAULT 0,

    -- Material
    marca               TEXT,
    pais_origen         TEXT,

    -- Trabajo (tipo_id = 128)
    -- 'subcontrato' incluye todos los recursos
    -- 'acarreo' contempla traslado de materiales
    -- 'destajo' incluye solo la ejecución
    tipo_trabajo        TEXT    CHECK(tipo_trabajo IN ('subcontrato', 'acarreo', 'destajo')),

    -- Datos adicionales (todos los tipos)
    fecha_precio        TEXT,
    indice_inegi        TEXT,
    peso_kg             REAL,
    comentarios         TEXT,

    -- Fórmulas de costo
    formula_costo_mn    TEXT,
    formula_costo_me    TEXT,

    -- Índices numéricos para fórmulas (1-3 MN, 4-6 ME)
    indice_1            REAL,
    indice_2            REAL,
    indice_3            REAL,
    indice_4            REAL,
    indice_5            REAL,
    indice_6            REAL,

    -- Auditoría
    activo              INTEGER NOT NULL DEFAULT 1,
    es_basico           INTEGER NOT NULL DEFAULT 0,
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now')),

    UNIQUE(proyecto_id, clave)
);

CREATE INDEX IF NOT EXISTS idx_insumos_proyecto   ON insumos(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_insumos_tipo       ON insumos(tipo_id);
CREATE INDEX IF NOT EXISTS idx_insumos_clave      ON insumos(proyecto_id, clave);
CREATE INDEX IF NOT EXISTS idx_insumos_familia    ON insumos(familia_id);
CREATE INDEX IF NOT EXISTS idx_insumos_subfamilia ON insumos(subfamilia_id);
CREATE INDEX IF NOT EXISTS idx_insumos_activo     ON insumos(activo);


-- =============================================================================
-- BLOQUE 7: APU (Análisis de Precio Unitario)
-- apu_auxiliares: insumos compuestos con APU propio que no son nodos del árbol
-- apu_componentes: desglose de insumos por concepto (ligado por id entero)
-- apu_resumen: subtotales por tipo (actualizado por Python)
-- =============================================================================

-- Componentes del APU — matriz_id referencia al item padre (concepto del árbol
-- o insumo compuesto). El contexto de la llamada sabe cuál es.
CREATE TABLE IF NOT EXISTS apu_matrices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    matriz_id           INTEGER NOT NULL,
    insumo_id           INTEGER NOT NULL REFERENCES insumos(id),

    rendimiento         REAL    NOT NULL DEFAULT 0.0,
    cantidad            REAL    NOT NULL DEFAULT 0.0,
    precio              REAL    NOT NULL DEFAULT 0.0,
    importe             REAL GENERATED ALWAYS AS (ROUND(cantidad * precio, 6)) STORED,

    formula             TEXT,
    orden               INTEGER NOT NULL DEFAULT 0,

    -- Auditoría
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_apu_mat_matriz    ON apu_matrices(matriz_id);
CREATE INDEX IF NOT EXISTS idx_apu_mat_insumo    ON apu_matrices(insumo_id);

-- Resumen APU por tipo de costo
CREATE TABLE IF NOT EXISTS apu_resumen_totales (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    matriz_id           INTEGER NOT NULL UNIQUE,
    materiales          REAL    NOT NULL DEFAULT 0.0,
    mano_obra           REAL    NOT NULL DEFAULT 0.0,
    herramienta         REAL    NOT NULL DEFAULT 0.0,
    equipo              REAL    NOT NULL DEFAULT 0.0,
    auxiliares          REAL    NOT NULL DEFAULT 0.0,
    subcontratos        REAL    NOT NULL DEFAULT 0.0,
    fletes              REAL    NOT NULL DEFAULT 0.0,
    trabajos            REAL    NOT NULL DEFAULT 0.0,
    costo_directo       REAL    NOT NULL DEFAULT 0.0,
    indirectos_pct      REAL    NOT NULL DEFAULT 0.0,
    financiamiento_pct  REAL    NOT NULL DEFAULT 0.0,
    utilidad_pct        REAL    NOT NULL DEFAULT 0.0,
    cargo_adicional_pct REAL    NOT NULL DEFAULT 0.0,
    precio_venta        REAL    NOT NULL DEFAULT 0.0,
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- NOTA: la tabla auxiliares (*EGX.DBF en OPUS) fue eliminada.
-- Los insumos compuestos simples se identifican con es_compuesto=1 en la tabla insumos.
-- Sus componentes internos se almacenan en apu_matrices con insumo_compuesto_id.


-- =============================================================================
-- BLOQUE 8: COLABORACIÓN
-- historial: base para Ctrl+Z colaborativo — ver DECISIONES_PENDIENTES.md FE-02
-- notas: comentarios inline por nodo del presupuesto
-- =============================================================================

CREATE TABLE IF NOT EXISTS notas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto_id     INTEGER NOT NULL REFERENCES estructura_presupuesto(id) ON DELETE CASCADE,
    usuario_id      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    texto           TEXT    NOT NULL,
    resuelta        INTEGER NOT NULL DEFAULT 0,
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notas_concepto ON notas(concepto_id);

-- Historial de cambios — auditoría genérica y base del Ctrl+Z colaborativo
-- sesion: UUID generado en Python para agrupar cambios de una misma operación
-- valor_anterior / valor_nuevo: siempre TEXT, Python hace la conversión de tipo
CREATE TABLE IF NOT EXISTS historial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion          TEXT    NOT NULL,
    tabla           TEXT    NOT NULL,
    registro_id     INTEGER NOT NULL,
    campo           TEXT    NOT NULL,
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    usuario_id      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    cambiado_en     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_historial_registro ON historial(tabla, registro_id);
CREATE INDEX IF NOT EXISTS idx_historial_sesion   ON historial(sesion);
CREATE INDEX IF NOT EXISTS idx_historial_usuario  ON historial(usuario_id);


-- =============================================================================
-- BLOQUE 9: VERSIÓN DEL ESQUEMA
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    aplicado_en TEXT    NOT NULL DEFAULT (datetime('now')),
    descripcion TEXT
);

INSERT OR IGNORE INTO schema_version (version, descripcion) VALUES
    (3, 'v3: matriz_id unico en apu_matrices/resumen_totales, es_compuesto por presencia en F.DBF');
INSERT OR IGNORE INTO schema_version (version, descripcion) VALUES
    (2, 'v2: renombres, eliminar roles/tipos extra/estados_nodo, subfamilias, fletes/trabajos, estado como entero');
