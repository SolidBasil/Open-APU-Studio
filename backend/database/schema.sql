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

    -- Cliente
    cliente_nombre          TEXT,
    cliente_domicilio       TEXT,
    cliente_ciudad          TEXT,
    cliente_cp              TEXT,
    cliente_pais            TEXT    DEFAULT 'México',
    cliente_email           TEXT,
    cliente_tel             TEXT,

    -- Financiero
    moneda_nombre           TEXT    NOT NULL DEFAULT 'Peso mexicano',
    moneda_simbolo          TEXT    NOT NULL DEFAULT '$',
    moneda_abrev            TEXT    NOT NULL DEFAULT 'MXN',
    iva_nombre              TEXT    NOT NULL DEFAULT 'IVA',
    iva_porcentaje          REAL    NOT NULL DEFAULT 16.0,

    -- Configuración técnica (fusionado desde configuracion_proyecto)
    horas_dia               REAL    NOT NULL DEFAULT 8.0,
    tasa_seguro             REAL    NOT NULL DEFAULT 0.0,
    tasa_interes            REAL    NOT NULL DEFAULT 0.0,
    capturar_rendimientos   INTEGER NOT NULL DEFAULT 0,
    unidad_cantidad_agrup   INTEGER NOT NULL DEFAULT 0,

    -- Ubicación de la obra
    obra_domicilio          TEXT,
    obra_ciudad             TEXT,
    obra_estado             TEXT,
    obra_cp                 TEXT,
    obra_pais               TEXT    DEFAULT 'México',
    obra_latitud            REAL,
    obra_longitud           REAL,
    obra_descripcion        TEXT,

    -- Contacto
    contacto_nombre         TEXT,
    contacto_cargo          TEXT,
    contacto_email          TEXT,
    contacto_tel            TEXT,

    -- Constructora
    constructora_nombre     TEXT,
    constructora_rfc        TEXT,
    constructora_domicilio  TEXT,
    constructora_ciudad     TEXT,
    constructora_estado     TEXT,
    constructora_cp         TEXT,
    constructora_pais       TEXT    DEFAULT 'México',
    constructora_tel        TEXT,
    constructora_email      TEXT,
    constructora_sitio_web  TEXT,
    constructora_logo_path  TEXT,

    -- Moneda extranjera
    moneda_ext_nombre       TEXT    DEFAULT 'Dólar USD',
    moneda_ext_simbolo      TEXT    DEFAULT '$',
    moneda_ext_abrev        TEXT    DEFAULT 'USD',
    tipo_cambio             REAL    NOT NULL DEFAULT 1.0,

    -- Programa de obra
    duracion_obra_dias      INTEGER,

    -- Reportes
    reporte_responsable     TEXT,
    reporte_version         TEXT    DEFAULT '1.0',
    reporte_observaciones   TEXT,
    reporte_fecha           TEXT,

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

-- Factores de sobrecosto para cascada sobre insumos (indirectos, utilidad, etc.)
-- costo_final = costo_directo * COALESCE(factor_fsr, 1.0) * COALESCE(factor_total, 1.0)
CREATE TABLE IF NOT EXISTS factores_sobrecosto (
    proyecto_id             INTEGER PRIMARY KEY REFERENCES proyectos(id) ON DELETE CASCADE,
    pct_indirectos_campo    REAL NOT NULL DEFAULT 0.0,
    pct_indirectos_oficina  REAL NOT NULL DEFAULT 0.0,
    pct_financiamiento      REAL NOT NULL DEFAULT 0.0,
    pct_utilidad            REAL NOT NULL DEFAULT 0.0,
    pct_cargos_adicionales  REAL NOT NULL DEFAULT 0.0,
    factor_total            REAL NOT NULL DEFAULT 1.0
);

-- Factores FSR — configuraciones de Factor de Salario Real para mano de obra
CREATE TABLE IF NOT EXISTS factores_fsr (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id             INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    clave                   TEXT    NOT NULL,
    nombre                  TEXT    NOT NULL DEFAULT '',
    modo_calculo            INTEGER NOT NULL DEFAULT 1,
    anio                    INTEGER NOT NULL DEFAULT 2010,
    semestre                INTEGER NOT NULL DEFAULT 1,
    tipo_jornada            INTEGER NOT NULL DEFAULT 0,
    horas_jornada           REAL    NOT NULL DEFAULT 8.0,
    salario_minimo          REAL    NOT NULL DEFAULT 57.46,
    salario_nominal_base    REAL    NOT NULL DEFAULT 100.0,
    dias_calendario         REAL    NOT NULL DEFAULT 365.25,
    dias_aguinaldo          REAL    NOT NULL DEFAULT 15.0,
    dias_vacaciones         REAL    NOT NULL DEFAULT 6.0,
    prima_vacacional        REAL    NOT NULL DEFAULT 25.0,
    dias_dominical          REAL    NOT NULL DEFAULT 0.0,
    prima_dominical         REAL    NOT NULL DEFAULT 0.0,
    dias_otros_pagados      REAL    NOT NULL DEFAULT 0.0,
    dias_descanso           REAL    NOT NULL DEFAULT 52.18,
    dias_festivos           REAL    NOT NULL DEFAULT 7.17,
    dias_contrato           REAL    NOT NULL DEFAULT 0.0,
    dias_sindicato          REAL    NOT NULL DEFAULT 1.0,
    dias_enfermedad         REAL    NOT NULL DEFAULT 0.45,
    dias_clima              REAL    NOT NULL DEFAULT 3.85,
    dias_arrastre           REAL    NOT NULL DEFAULT 0.0,
    dias_guardia            REAL    NOT NULL DEFAULT 0.0,
    dias_otros_no_lab       REAL    NOT NULL DEFAULT 5.0,
    imss_guarderias         REAL    NOT NULL DEFAULT 1.0,
    imss_retiro             REAL    NOT NULL DEFAULT 2.0,
    imss_riesgos            REAL    NOT NULL DEFAULT 7.58875,
    imss_invalidez          REAL    NOT NULL DEFAULT 1.75,
    imss_cesantia           REAL    NOT NULL DEFAULT 3.15,
    imss_enfermedad         REAL    NOT NULL DEFAULT 5.35365,
    infonavit               REAL    NOT NULL DEFAULT 5.0,
    impuesto_nomina         REAL    NOT NULL DEFAULT 0.0,
    otros_impuestos         REAL    NOT NULL DEFAULT 0.0,
    factor_fsr_calculado    REAL,
    fecha_calculo           TEXT,
    activo                  INTEGER NOT NULL DEFAULT 1,
    creado_por              INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en               TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por          INTEGER REFERENCES usuarios(id),
    modificado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(proyecto_id, clave)
);


-- =============================================================================
-- BLOQUE 5: ESTRUCTURA DEL PRESUPUESTO
-- Fuente de verdad jerárquica: campo wbs (PRE_WBS en OPUS).
-- El importador filtra _deleted=True antes de insertar.
-- Los totales se recalculan en Python bottom-up al editar.
-- El precio se resuelve desde insumos.costo_final o apu_matrices via insumo_id.
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

    -- Vínculo al catálogo de insumos (solo conceptos)
    insumo_id       INTEGER REFERENCES insumos(id),

    -- Nombre del nodo: para agrupadores es el nombre del capítulo;
    -- para conceptos se resuelve via JOIN a insumos.descripcion
    descripcion     TEXT    NOT NULL DEFAULT '',

    -- Medición (solo conceptos hoja)
    cantidad        REAL,
    formula         TEXT,   -- expresión opcional para calcular cantidad

    -- Única columna de valor monetario: para conceptos = cantidad × precio (desde APU o insumo),
    -- para capítulos = suma de hijos
    total           REAL    NOT NULL DEFAULT 0.0,

    -- Semáforo de confiabilidad: 0=sin revisar, 1=en revisión, 2=verificado, 3=cuestionado
    estado          INTEGER NOT NULL DEFAULT 0,

    -- Nota rápida inline
    notas_rapidas   TEXT,

    -- Fuera de presupuesto (conceptos extra que no forman parte del presupuesto legal)
    es_extra        INTEGER NOT NULL DEFAULT 0,

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

    -- Hash de descripción normalizada (uppercase + espacios colapsados).
    -- Llave funcional principal para búsqueda y deduplicación de insumos.
    -- Se genera al crear y se regenera junto con descripcion al editar.
    hash                TEXT,

    -- Identificación
    -- clave_opus: código original importado de OPUS (campo NOMBRE del DBF).
    -- Solo referencial — no participa en ninguna relación ni búsqueda interna.
    clave_opus          TEXT,
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
    costo_directo       REAL    NOT NULL DEFAULT 0.0,
    costo_final         REAL    NOT NULL DEFAULT 0.0,

    -- Mano de obra
    usar_hoja_fasar     INTEGER NOT NULL DEFAULT 0,
    factor_fsr          REAL,

    -- Trabajo (tipo_id = 128)
    -- 'subcontrato' incluye todos los recursos
    -- 'acarreo' contempla traslado de materiales
    -- 'destajo' incluye solo la ejecución
    tipo_trabajo        TEXT    CHECK(tipo_trabajo IN ('subcontrato', 'acarreo', 'destajo')),

    -- Datos adicionales (todos los tipos)
    fecha_precio        TEXT,
    peso_kg             REAL,
    comentarios         TEXT,

    -- Auditoría
    activo              INTEGER NOT NULL DEFAULT 1,
    creado_por          INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por      INTEGER REFERENCES usuarios(id),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now')),

    UNIQUE(proyecto_id, hash)
);

CREATE INDEX IF NOT EXISTS idx_insumos_proyecto   ON insumos(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_insumos_hash       ON insumos(proyecto_id, hash);
CREATE INDEX IF NOT EXISTS idx_insumos_tipo       ON insumos(tipo_id);
CREATE INDEX IF NOT EXISTS idx_insumos_clave_opus ON insumos(proyecto_id, clave_opus);
CREATE INDEX IF NOT EXISTS idx_insumos_familia    ON insumos(familia_id);
CREATE INDEX IF NOT EXISTS idx_insumos_subfamilia ON insumos(subfamilia_id);
CREATE INDEX IF NOT EXISTS idx_insumos_activo     ON insumos(activo);


-- =============================================================================
-- BLOQUE 7: APU (Análisis de Precio Unitario)
-- apu_matrices: desglose de insumos por concepto (ligado por matriz_id)
-- Los subtotales por tipo se calculan al vuelo en Python (no se persisten).
-- =============================================================================

-- Componentes del APU — matriz_id referencia al item padre (concepto del árbol
-- o insumo compuesto). El contexto de la llamada sabe cuál es.
CREATE TABLE IF NOT EXISTS apu_matrices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    matriz_id           INTEGER NOT NULL,
    insumo_id           INTEGER NOT NULL REFERENCES insumos(id),

    valor               REAL    NOT NULL DEFAULT 0.0,
    operador            TEXT    NOT NULL DEFAULT '*' CHECK(operador IN ('*', '/')),
    precio              REAL    NOT NULL DEFAULT 0.0,
    importe             REAL    NOT NULL DEFAULT 0.0,

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

-- =============================================================================
-- BLOQUE 8: FÓRMULAS Y VARIABLES
-- variables nombradas que pueden referenciarse desde formulas en apu_matrices o
-- estructura_presupuesto. Soporte recursivo con detección de ciclos.
-- =============================================================================

CREATE TABLE IF NOT EXISTS variables_formula (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    nombre          TEXT    NOT NULL,
    expresion       TEXT,
    valor           REAL,
    descripcion     TEXT,
    UNIQUE(proyecto_id, nombre)
);

CREATE INDEX IF NOT EXISTS idx_varf_proyecto ON variables_formula(proyecto_id);


-- =============================================================================
-- BLOQUE 8.1: INDIRECTOS
-- Gastos indirectos de campo y oficina. El total se calcula:
--   periodo_dias = 0  → total = importe × pct_participacion/100
--   periodo_dias > 0  → total = importe × (duracion_obra_dias / periodo_dias) × pct_participacion/100
-- =============================================================================

CREATE TABLE IF NOT EXISTS indirectos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id         INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    tipo                TEXT    NOT NULL CHECK(tipo IN ('campo', 'oficina')),
    categoria           TEXT,
    orden               INTEGER NOT NULL DEFAULT 0,
    concepto            TEXT,
    periodo_dias        REAL    NOT NULL DEFAULT 0.0,
    importe             REAL    NOT NULL DEFAULT 0.0,
    pct_participacion   REAL    NOT NULL DEFAULT 100.0,
    total               REAL    NOT NULL DEFAULT 0.0,
    activo              INTEGER NOT NULL DEFAULT 1,
    creado_en           TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_en       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_indirectos_proyecto ON indirectos(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_indirectos_tipo     ON indirectos(proyecto_id, tipo);


-- =============================================================================
-- BLOQUE 9: COLABORACIÓN
-- historial: base para Ctrl+Z colaborativo — ver DECISIONES_PENDIENTES.md FE-02
-- =============================================================================

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
    cambiado_en     TEXT    NOT NULL DEFAULT (datetime('now')),
    deshachado_en   TEXT    -- SRV-10: timestamp cuando se deshace (NULL = activo)
);

CREATE INDEX IF NOT EXISTS idx_historial_registro ON historial(tabla, registro_id);
CREATE INDEX IF NOT EXISTS idx_historial_sesion   ON historial(sesion);
CREATE INDEX IF NOT EXISTS idx_historial_usuario  ON historial(usuario_id);


-- =============================================================================
-- BLOQUE 10: VERSIÓN DEL ESQUEMA
-- =============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    aplicado_en TEXT    NOT NULL DEFAULT (datetime('now')),
    descripcion TEXT
);

INSERT OR IGNORE INTO schema_version (version, descripcion) VALUES
    (4, 'v4: costo_directo + FSR en insumos, apu_matrices con valor/operador, factores_sobrecosto, factores_fsr, variables_formula'),
    (5, 'v5: limpia proyectos (24 cols muertas), fusiona configuracion_proyecto, elimina apu_resumen_totales, crea indirectos'),
    (6, 'v6: elimina catfsr y fsr_minimo de insumos (FSR solo manual via factor_fsr)'),
    (7, 'v7: elimina tabla notas, salario_nominal, salario_real e indice_inegi de insumos'),
    (8, 'v8: generadores de obra — tablas generadores y generador_renglones'),
    (9, 'v9: generadores.cad_archivo_path — cada generador liga su propio DXF');


-- =============================================================================
-- BLOQUE 11: GENERADORES DE OBRA
-- Documentos de medición (ubicación × veces × largo × ancho × alto → subtotal).
-- Pueden existir solos (concepto_id = NULL) o vinculados a un concepto del
-- presupuesto. La sincronización de cantidad es automática vía DataService.
-- =============================================================================

CREATE TABLE IF NOT EXISTS generadores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    concepto_id     INTEGER REFERENCES estructura_presupuesto(id),  -- NULL = suelto
    nombre          TEXT    NOT NULL DEFAULT '',
    unidad          TEXT,
    cantidad_total  REAL    NOT NULL DEFAULT 0.0,   -- SUM(renglones activos)
    cad_archivo_path TEXT,  -- ruta del DXF ligado a este generador (cada uno tiene el suyo)
    notas           TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gen_proyecto ON generadores(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_gen_concepto ON generadores(concepto_id);

CREATE TABLE IF NOT EXISTS generador_renglones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    generador_id    INTEGER NOT NULL REFERENCES generadores(id) ON DELETE CASCADE,
    orden           INTEGER NOT NULL DEFAULT 0,

    eje             TEXT    NOT NULL DEFAULT '',
    tramo           TEXT    NOT NULL DEFAULT '',
    veces           REAL    NOT NULL DEFAULT 1,
    largo           REAL,
    ancho           REAL,
    alto            REAL,
    subtotal        REAL    NOT NULL DEFAULT 0.0,   -- veces × (largo|1) × (ancho|1) × (alto|1)

    origen          TEXT    NOT NULL DEFAULT 'manual' CHECK(origen IN ('manual', 'cad')),
    cad_archivo_id  INTEGER,
    cad_capa        TEXT,
    cad_tipo_medicion TEXT CHECK(cad_tipo_medicion IN
                        ('punto', 'linea', 'polilinea', 'area', 'contador')),
    cad_geometria   TEXT,   -- JSON

    notas           TEXT,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER NOT NULL DEFAULT 1 REFERENCES usuarios(id),
    creado_en       TEXT    NOT NULL DEFAULT (datetime('now')),
    modificado_por  INTEGER REFERENCES usuarios(id),
    modificado_en   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_genr_generador ON generador_renglones(generador_id);
