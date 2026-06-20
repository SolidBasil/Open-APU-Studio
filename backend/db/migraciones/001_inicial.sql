CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    aplicado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proyectos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    clave_opus TEXT,
    fecha_creacion TEXT DEFAULT (datetime('now')),
    fecha_modificacion TEXT DEFAULT (datetime('now')),
    notas TEXT
);

CREATE TABLE IF NOT EXISTS proyecto_config (
    proyecto_id INTEGER PRIMARY KEY DEFAULT 1,
    horas_dia REAL DEFAULT 8,
    tasa_seguro REAL DEFAULT 0,
    tasa_interes REAL DEFAULT 0,
    moneda TEXT DEFAULT 'MXN'
);

CREATE TABLE IF NOT EXISTS indirectos (
    proyecto_id INTEGER DEFAULT 1,
    renglon INTEGER NOT NULL,
    variable TEXT,
    descripcion TEXT,
    formula TEXT,
    se_suma INTEGER DEFAULT 1,
    se_imprime INTEGER DEFAULT 1,
    PRIMARY KEY (proyecto_id, renglon)
);

CREATE TABLE IF NOT EXISTS familias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    familia_padre_id INTEGER REFERENCES familias(id),
    nombre TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insumos (
    clave TEXT PRIMARY KEY,
    tipo INTEGER NOT NULL DEFAULT 0,
    unidad TEXT,
    precio REAL DEFAULT 0,
    descripcion TEXT,
    descripcion_corta TEXT,
    es_basico INTEGER DEFAULT 0,
    fecha_precio TEXT,
    costo_materiales REAL DEFAULT 0,
    costo_mano_obra REAL DEFAULT 0,
    costo_herramienta REAL DEFAULT 0,
    costo_equipo REAL DEFAULT 0,
    costo_auxiliares REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS insumos_precio_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insumo_clave TEXT NOT NULL REFERENCES insumos(clave),
    precio_anterior REAL,
    precio_nuevo REAL,
    fecha_cambio TEXT DEFAULT (datetime('now')),
    motivo TEXT
);

CREATE TABLE IF NOT EXISTS partidas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER DEFAULT 1,
    padre_id INTEGER REFERENCES partidas(id),
    clave TEXT,
    nombre TEXT,
    orden INTEGER DEFAULT 0,
    nivel INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conceptos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id INTEGER DEFAULT 1,
    partida_id INTEGER NOT NULL REFERENCES partidas(id),
    clave TEXT NOT NULL,
    orden INTEGER DEFAULT 0,
    cantidad REAL DEFAULT 1,
    precio_unitario REAL DEFAULT 0,
    importe REAL DEFAULT 0,
    unidad TEXT,
    descripcion TEXT
);

CREATE TABLE IF NOT EXISTS apu_componentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    concepto_clave TEXT NOT NULL,
    insumo_clave TEXT NOT NULL,
    tipo_insumo INTEGER DEFAULT 0,
    rendimiento REAL DEFAULT 0,
    num_elementos REAL DEFAULT 1,
    cantidad_total REAL DEFAULT 0,
    precio_unitario REAL DEFAULT 0,
    importe REAL DEFAULT 0,
    formula TEXT
);

CREATE TABLE IF NOT EXISTS apu_resumen (
    concepto_clave TEXT PRIMARY KEY,
    total_materiales REAL DEFAULT 0,
    total_mano_obra REAL DEFAULT 0,
    total_herramienta REAL DEFAULT 0,
    total_equipo REAL DEFAULT 0,
    total_auxiliares REAL DEFAULT 0,
    total_subcontratos REAL DEFAULT 0,
    indirectos REAL DEFAULT 0,
    financiamiento REAL DEFAULT 0,
    utilidad REAL DEFAULT 0,
    precio_venta REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS auxiliares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insumo_clave TEXT NOT NULL,
    tipo INTEGER DEFAULT 0,
    cantidad REAL DEFAULT 0,
    precio REAL DEFAULT 0,
    importe REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS log_importacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla TEXT,
    registro_clave TEXT,
    mensaje TEXT,
    tipo TEXT DEFAULT 'warning'
);

-- FTS5 index for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS busqueda USING fts5(
    contenido,
    tokenize='unicode61 remove_diacritics 1'
);

-- Type lookup table
CREATE TABLE IF NOT EXISTS tipos_insumo (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL
);

INSERT OR IGNORE INTO tipos_insumo (id, nombre) VALUES
    (1, 'Material'),
    (2, 'Mano de obra'),
    (4, 'Herramienta'),
    (8, 'Equipo'),
    (16, 'Auxiliar'),
    (32, 'Concepto');

INSERT OR IGNORE INTO schema_version (version) VALUES (1);
