"""
db.py
=====
Gestión de la conexión SQLite, carpeta de datos del usuario
y aplicación automática del esquema.

Estructura de carpetas en el sistema del usuario:
    Windows: C:/Users/<usuario>/AppData/Local/Open APU Studio/
    Linux:   ~/.local/share/Open APU Studio/
    macOS:   ~/Library/Application Support/Open APU Studio/
    ├── config.json       ← preferencias de la app
    ├── proyectos/        ← archivos .db de cada proyecto
    └── logs/             ← log de errores e importaciones

Uso:
    from backend.database.db import Rutas, Database

    # Rutas del sistema
    db_path = Rutas.proyectos() / "D60JALISCOT.db"

    # Abrir un proyecto
    db = Database.abrir(db_path)
    conn = db.conn
    db.close()
"""

# ── imports / platformdirs ──
import json
import logging
import sqlite3
import shutil
import sys
import threading
from pathlib import Path

if getattr(sys, "frozen", False):
    # Exe empaquetado (PyInstaller): datos del usuario en AppData.
    try:
        import platformdirs
        _BASE = Path(platformdirs.user_data_dir("Open APU Studio", "OpenAPU"))
    except ImportError:
        _BASE = Path(__file__).resolve().parent.parent.parent / "datos_usuario"
else:
    # En desarrollo (corriendo desde el repo) los datos viven SIEMPRE en
    # <repo>/datos_usuario, sin importar si platformdirs está instalado.
    # Antes el try/except lo decidía, y al añadir platformdirs a
    # requirements.txt el app cambió de carpeta de golpe: las obras dejaron
    # de aparecer (estaban en datos_usuario, no en AppData).
    _BASE = Path(__file__).resolve().parent.parent.parent / "datos_usuario"


# =============================================================================
# RUTAS DEL SISTEMA
# =============================================================================

def _copiar_plantillas_incluidas(destino: Path):
    """Copia las plantillas .tex incluidas en el proyecto a la carpeta del usuario.
    Solo copia si la carpeta destino está vacía (primera ejecución).
    """
    if any(destino.iterdir()):
        return
    bundled = Path(__file__).parent.parent / "exportar" / "informe_pdf" / "latex" / "templates"
    if bundled.exists():
        for f in bundled.iterdir():
            if f.suffix == ".tex":
                shutil.copy2(f, destino / f.name)

class Rutas:
    """
    Centraliza todas las rutas de datos del usuario.
    Crea las carpetas si no existen al primer acceso.
    """

    @staticmethod
    def base() -> Path:
        """Carpeta raíz de datos del usuario."""
        _BASE.mkdir(parents=True, exist_ok=True)
        return _BASE

    @staticmethod
    def proyectos() -> Path:
        """Carpeta donde se guardan los archivos .db de proyectos."""
        p = _BASE / "proyectos"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def logs() -> Path:
        """Carpeta de logs de importación y errores."""
        p = _BASE / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def config_path() -> Path:
        """Ruta al archivo de configuración de la app."""
        return _BASE / "config.json"

    @staticmethod
    def templates() -> Path:
        """Carpeta donde se almacenan las plantillas LaTeX del usuario.
        En primera ejecución se copian desde las incluidas en el proyecto.
        """
        p = _BASE / "templates"
        p.mkdir(parents=True, exist_ok=True)
        _copiar_plantillas_incluidas(p)
        return p

    @staticmethod
    def reportes() -> Path:
        """Carpeta donde se guardan los .tex y .pdf generados."""
        p = _BASE / "reportes"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def listar_proyectos() -> list[Path]:
        """Devuelve la lista de archivos .db disponibles, ordenados por fecha."""
        return sorted(
            Rutas.proyectos().glob("*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,   # más reciente primero
        )

    @staticmethod
    def db_proyecto(nombre: str) -> Path:
        """
        Devuelve la ruta al .db de un proyecto dado su nombre.
        Ejemplo: Rutas.db_proyecto("D60JALISCOT") → .../proyectos/D60JALISCOT.db
        """
        return Rutas.proyectos() / f"{nombre.strip()}.db"


# =============================================================================
# CONFIGURACIÓN DE LA APP
# =============================================================================

class Config:
    """
    Lee y escribe preferencias en config.json.
    Valores disponibles: tema_modo, tema_acento, ultimo_proyecto.

    Uso:
        Config.get("tema_acento", "azul")
        Config.set("ultimo_proyecto", "D60JALISCOT")
    """

    _cache: dict | None = None

    # ── cargar configuración desde JSON ──
    @classmethod
    def _cargar(cls) -> dict:
        """Carga config.json desde disco al caché de clase; retorna dict vacío si no existe o está corrupto."""
        if cls._cache is not None:
            return cls._cache
        ruta = Rutas.config_path()
        if ruta.exists():
            try:
                cls._cache = json.loads(ruta.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                cls._cache = {}
        else:
            cls._cache = {}
        return cls._cache

    # ── leer valor de configuración ──
    @classmethod
    def get(cls, clave: str, default=None):
        """Lee valor de configuración por clave; devuelve default si no existe."""
        return cls._cargar().get(clave, default)

    # ── guardar valor de configuración ──
    @classmethod
    def set(cls, clave: str, valor):
        """Persiste par clave/valor en config.json y actualiza el caché."""
        datos = cls._cargar()
        datos[clave] = valor
        Rutas.config_path().write_text(
            json.dumps(datos, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        cls._cache = datos  # sincroniza caché para que get() vea el valor nuevo

    @classmethod
    def ultimo_proyecto(cls) -> Path | None:
        """Devuelve la ruta al último proyecto abierto, o None si no existe."""
        nombre = cls.get("ultimo_proyecto")
        if not nombre:
            return None
        ruta = Rutas.db_proyecto(nombre)
        return ruta if ruta.exists() else None

    @classmethod
    def guardar_ultimo_proyecto(cls, db_path: str | Path):
        """Guarda el nombre del último proyecto abierto."""
        cls.set("ultimo_proyecto", Path(db_path).stem)


# =============================================================================
# CONEXIÓN A LA BASE DE DATOS
# =============================================================================

class Database:
    """Gestiona la conexión SQLite activa de un proyecto.

    Cada instancia controla su propia conexión. No hay singleton — el
    caller es responsable de guardar la referencia y cerrarla cuando
    ya no se necesite.

    Uso:
        db = Database.abrir(db_path)
        conn = db.conn
        db.close()
    """

    def __init__(self, db_path=None):
        """Database vacía o que abre conexión si se pasa db_path."""
        self._conn    = None
        self._db_path = None
        # Profundidad de transaction() anidados (ver _TransactionContext):
        # solo el nivel externo commitea/rollbackea de verdad.
        self._tx_depth = 0
        self._tx_lock  = threading.Lock()
        if db_path:
            self._abrir(db_path)

    # ── Conexión ──────────────────────────────────────────────────────────

    # ── abrir conexión a SQLite ──
    def _abrir(self, db_path: str | Path, check_same_thread: bool = True):
        """Abre (o reabre) conexión SQLite, aplica pragmas y schema, guarda como último proyecto.

        check_same_thread=False es necesario en el servidor HTTP (ver
        server/servidor.py): FastAPI corre los endpoints síncronos en un
        thread pool, así que la misma conexión puede terminar accedida
        desde threads distintos entre un request y otro. El driver
        sqlite3 de Python solo prohíbe esto por default como salvavidas
        — no lo hace seguro por sí solo. Quien pase check_same_thread=False
        es responsable de serializar el acceso con un lock (el servidor
        ya lo hace, uno por proyecto — ver `_proyectos[nombre]["lock"]`).
        La app de escritorio nunca necesita esto (un solo hilo, el del
        loop de eventos de Qt) y se queda con el default seguro.
        """
        self.close()
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=check_same_thread)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.row_factory = sqlite3.Row
        self._aplicar_schema()
        Config.guardar_ultimo_proyecto(db_path)
        return self

    # ── cerrar conexión SQLite ──
    def close(self):
        """Cierra la conexión activa y limpia el estado."""
        if self._conn:
            self._conn.close()
            self._conn    = None
            self._db_path = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Conexión SQLite activa (solo lectura)."""
        return self._conn

    @property
    def db_path(self) -> str:
        """Ruta del archivo .db abierto (solo lectura)."""
        return self._db_path

    # ── Schema ────────────────────────────────────────────────────────────

    def _aplicar_schema(self):
        """Aplica schema.sql completo. Crea tablas si no existen.
        Para proyectos viejos: agrega columnas nuevas y migra datos de
        configuracion_proyecto antes de que se elimine la tabla.
        """
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"No se encontró el schema en {schema_path}")

        # Migración v5: copiar configuracion_proyecto a proyectos ANTES del schema
        self._migrar_v5()

        sql = schema_path.read_text(encoding="utf-8")
        self._conn.executescript(sql)

        # SRV-10: agregar columna deshachado_en a historial si falta (proyectos viejos)
        try:
            self._conn.execute(
                "ALTER TABLE historial ADD COLUMN deshachado_en TEXT"
            )
        except sqlite3.OperationalError:
            pass  # columna ya existe
        # v6: columna es_extra para conceptos fuera de presupuesto
        try:
            self._conn.execute(
                "ALTER TABLE estructura_presupuesto ADD COLUMN es_extra INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # columna ya existe
        # Asegurar que registros viejos tengan es_extra = 0
        try:
            self._conn.execute(
                "UPDATE estructura_presupuesto SET es_extra = 0 WHERE es_extra IS NULL"
            )
        except sqlite3.OperationalError:
            pass  # columna es_extra aún no existe en este punto de la migración
        # v7: columna modificado_en en familias/subfamilias. RepoBase._update()
        # siempre escribe "modificado_en = datetime('now')" en cualquier
        # UPDATE genérico, pero estas dos tablas no la tenían en el schema
        # original. Antes esto era inalcanzable porque nada llamaba a
        # actualizar()/deshacer() sobre "familias"/"subfamilias" (no había
        # UI de edición ni historial de creación); se volvió alcanzable al
        # corregir el Hallazgo 3 (insertar() ahora captura historial de
        # creación para TODA entidad, así que deshacer crear una familia
        # nueva pasó a ejecutar un UPDATE real) — encontrado por el smoke
        # test de esa corrección antes de llegar a producción.
        for tabla in ("familias", "subfamilias"):
            try:
                self._conn.execute(
                    f"ALTER TABLE {tabla} ADD COLUMN modificado_en TEXT"
                )
            except sqlite3.OperationalError:
                pass  # columna ya existe
        # v9: generadores.cad_archivo_path — cada generador liga su propio
        # DXF. FALTABA esta migración (bug real: quedó solo en schema.sql,
        # nunca se agregó aquí) — cualquier proyecto creado antes de v9
        # rompía con "no such column: cad_archivo_path" en cuanto se
        # intentaba abrir/ligar un DXF a un generador.
        try:
            self._conn.execute(
                "ALTER TABLE generadores ADD COLUMN cad_archivo_path TEXT"
            )
        except sqlite3.OperationalError:
            pass  # columna ya existe
        # v10: cad_campo en generador_renglones — a qué celda (veces/largo/
        # ancho/alto) apunta una medición CAD, para saber cuál sobrescribir
        # al editar sus nodos (ver VisorCadWidget._finalizar_edicion_medicion).
        # Proyectos con generador_renglones creada antes de v10 no la tienen.
        try:
            self._conn.execute(
                "ALTER TABLE generador_renglones ADD COLUMN cad_campo TEXT"
            )
        except sqlite3.OperationalError:
            pass  # columna ya existe
        # v11: cad_origen_archivo en generador_renglones — nombre del DXF
        # del que salió la medición (además de sus coordenadas). Un
        # generador solo liga UN dxf a la vez (cad_archivo_path), así que
        # si más adelante se reemplaza por otro archivo, sin este dato no
        # quedaría registro de en qué plano se midió originalmente cada
        # renglón — solo puntos sueltos sin poder decir "esto salió del
        # plano X.dxf".
        try:
            self._conn.execute(
                "ALTER TABLE generador_renglones ADD COLUMN cad_origen_archivo TEXT"
            )
        except sqlite3.OperationalError:
            pass  # columna ya existe
        # v12: cad_medidas en generador_renglones — JSON con UNA medición
        # independiente POR CELDA (veces/largo/ancho/alto), cada una con
        # su propio tipo/puntos/archivo. Las columnas anteriores
        # (cad_tipo_medicion/cad_geometria/cad_campo/cad_origen_archivo)
        # solo alcanzaban para UNA medición por renglón entero — medir
        # Ancho después de Largo pisaba esas mismas columnas y borraba
        # el trazo de Largo. Se dejan esas columnas (legacy) para poder
        # seguir leyendo renglones medidos antes de v12.
        try:
            self._conn.execute(
                "ALTER TABLE generador_renglones ADD COLUMN cad_medidas TEXT"
            )
        except sqlite3.OperationalError:
            pass  # columna ya existe
        self._conn.commit()

    def _migrar_v5(self):
        """Migración v5: agrega columnas nuevas a proyectos y migra datos
        de configuracion_proyecto (que se fusiona en proyectos).
        """
        cur = self._conn.cursor()

        # Verificar si la tabla antigua existe
        try:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='configuracion_proyecto'")
            tiene_cfg = cur.fetchone() is not None
        except sqlite3.OperationalError:
            tiene_cfg = False

        # Columnas a agregar (solo si no existen)
        columnas_nuevas = [
            # Fusionadas desde configuracion_proyecto
            ("horas_dia", "REAL NOT NULL DEFAULT 8.0"),
            ("tasa_seguro", "REAL NOT NULL DEFAULT 0.0"),
            ("tasa_interes", "REAL NOT NULL DEFAULT 0.0"),
            ("capturar_rendimientos", "INTEGER NOT NULL DEFAULT 0"),
            ("unidad_cantidad_agrup", "INTEGER NOT NULL DEFAULT 0"),
            # Ubicación de la obra
            ("obra_domicilio", "TEXT"),
            ("obra_ciudad", "TEXT"),
            ("obra_estado", "TEXT"),
            ("obra_cp", "TEXT"),
            ("obra_pais", "TEXT DEFAULT 'México'"),
            ("obra_latitud", "REAL"),
            ("obra_longitud", "REAL"),
            ("obra_descripcion", "TEXT"),
            # Contacto
            ("contacto_nombre", "TEXT"),
            ("contacto_cargo", "TEXT"),
            ("contacto_email", "TEXT"),
            ("contacto_tel", "TEXT"),
            # Constructora
            ("constructora_nombre", "TEXT"),
            ("constructora_rfc", "TEXT"),
            ("constructora_domicilio", "TEXT"),
            ("constructora_ciudad", "TEXT"),
            ("constructora_estado", "TEXT"),
            ("constructora_cp", "TEXT"),
            ("constructora_pais", "TEXT DEFAULT 'México'"),
            ("constructora_tel", "TEXT"),
            ("constructora_email", "TEXT"),
            ("constructora_sitio_web", "TEXT"),
            ("constructora_logo_path", "TEXT"),
            # Moneda extranjera
            ("moneda_ext_nombre", "TEXT"),
            ("moneda_ext_simbolo", "TEXT"),
            ("moneda_ext_abrev", "TEXT"),
            ("tipo_cambio", "REAL NOT NULL DEFAULT 1.0"),
            # Programa de obra
            ("duracion_obra_dias", "INTEGER"),
            # Reportes
            ("reporte_responsable", "TEXT"),
            ("reporte_version", "TEXT DEFAULT '1.0'"),
            ("reporte_observaciones", "TEXT"),
            ("reporte_fecha", "TEXT"),
        ]

        for col, typedef in columnas_nuevas:
            try:
                cur.execute(f"ALTER TABLE proyectos ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass  # columna ya existe

        # Copiar datos de configuracion_proyecto si existe
        if tiene_cfg:
            try:
                cur.execute("""
                    UPDATE proyectos SET
                        horas_dia = COALESCE((SELECT horas_dia FROM configuracion_proyecto WHERE proyecto_id = proyectos.id), 8.0),
                        tasa_seguro = COALESCE((SELECT tasa_seguro FROM configuracion_proyecto WHERE proyecto_id = proyectos.id), 0.0),
                        tasa_interes = COALESCE((SELECT tasa_interes FROM configuracion_proyecto WHERE proyecto_id = proyectos.id), 0.0),
                        capturar_rendimientos = COALESCE((SELECT capturar_rendimientos FROM configuracion_proyecto WHERE proyecto_id = proyectos.id), 0),
                        unidad_cantidad_agrup = COALESCE((SELECT unidad_cantidad_agrup FROM configuracion_proyecto WHERE proyecto_id = proyectos.id), 0)
                """)
                cur.execute("DROP TABLE IF EXISTS configuracion_proyecto")
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # tabla configuracion_proyecto ya no existe

        # Eliminar tabla apu_resumen_totales si existe (v5 la elimina)
        try:
            cur.execute("DROP TABLE IF EXISTS apu_resumen_totales")
            self._conn.commit()
        except sqlite3.OperationalError as e:
            # DROP TABLE IF EXISTS no debería fallar por ausencia de la tabla;
            # si llega aquí es un error real de sqlite — se deja registro.
            logging.getLogger(__name__).warning("No se pudo eliminar apu_resumen_totales: %s", e)

    # ── Instanciación ────────────────────────────────────────────────

    @classmethod
    def abrir(cls, db_path: str | Path, check_same_thread: bool = True) -> "Database":
        """Crea una nueva instancia de Database y abre conexión al .db.

        check_same_thread=False: ver docstring de _abrir() — solo lo
        necesita el servidor HTTP, que debe pasarlo junto con un lock
        propio para serializar el acceso desde su thread pool.
        """
        inst = cls()
        inst._abrir(db_path, check_same_thread=check_same_thread)
        return inst

    # ── Transacciones ────────────────────────────────────────────────

    def transaction(self):
        """Context manager: abre transacción, commitea al salir, rollback si falla.

        Soporta anidado (los writes de DataService abren su propio nivel
        dentro del nivel del caller): los niveles internos usan SAVEPOINT y
        solo el nivel EXTERNO commitea (o hace rollback total si falla).
        Sin esto, el servidor HTTP —que nunca llama a conn.commit()
        directo— acumulaba todo en una transacción implícita abierta:
        sus lecturas veían los writes pero el archivo no, otros procesos
        recibían "database is locked" y al reiniciar se perdía todo.

        Uso:
            with db.transaction():
                repo.update(id, campos)
                registro = repo.buscar(id)
            # ← COMMIT aquí (solo si es el nivel externo). Si excepción → ROLLBACK.
        """
        return _TransactionContext(self)


# ── Context manager de transacciones ──────────────────────────────

class _TransactionContext:
    """Context manager para transacciones SQLite (anidables).

    Cada nivel abre un SAVEPOINT (mismo nombre en todos los niveles —
    SQLite los apila y RELEASE/ROLLBACK TO siempre resuelven al más
    reciente). Solo el nivel externo toca la transacción implícita:
    COMMIT al salir limpio, ROLLBACK total si hubo excepción.
    """

    def __init__(self, db: "Database"):
        self._db   = db
        self._conn = db.conn

    def __enter__(self):
        with self._db._tx_lock:
            self._db._tx_depth += 1
        self._conn.execute("SAVEPOINT _sp_data_service")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self._conn.execute("ROLLBACK TO SAVEPOINT _sp_data_service")
                self._conn.execute("RELEASE SAVEPOINT _sp_data_service")
            else:
                self._conn.execute("RELEASE SAVEPOINT _sp_data_service")
        finally:
            with self._db._tx_lock:
                self._db._tx_depth -= 1
                externo = self._db._tx_depth == 0
            if externo:
                if exc_type is not None:
                    self._conn.rollback()
                elif self._conn.in_transaction:
                    self._conn.commit()
        return False  # No suprime excepciones
