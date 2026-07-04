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
    Database.cerrar()
"""

# ── imports / platformdirs ──
import json
import sqlite3
import shutil
from pathlib import Path

try:
    import platformdirs
    _BASE = Path(platformdirs.user_data_dir("Open APU Studio", "OpenAPU"))
except ImportError:
    # Fallback si platformdirs no está instalado — carpeta junto al ejecutable
    _BASE = Path(__file__).parent.parent / "datos_usuario"


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
    """
    Gestiona la conexión SQLite activa.
    Singleton — una sola conexión abierta a la vez.
    Aplica schema.sql automáticamente si la DB es nueva.
    """

    _instancia = None

    def __init__(self, db_path=None):
        """Database vacía o que abre conexión si se pasa db_path."""
        self._conn    = None
        self._db_path = None
        if db_path:
            self._abrir(db_path)

    # ── Conexión ──────────────────────────────────────────────────────────

    # ── abrir conexión a SQLite ──
    def _abrir(self, db_path: str | Path):
        """Abre (o reabre) conexión SQLite, aplica pragmas y schema, guarda como último proyecto."""
        self._cerrar()
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.row_factory = sqlite3.Row
        self._aplicar_schema()
        Config.guardar_ultimo_proyecto(db_path)
        return self

    # ── cerrar conexión SQLite ──
    def _cerrar(self):
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
        """Aplica schema.sql completo. Crea tablas si no existen."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"No se encontró el schema en {schema_path}")
        sql = schema_path.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    # ── Singleton ─────────────────────────────────────────────────────────

    @classmethod
    def instancia(cls) -> "Database":
        """Singleton: devuelve la instancia única de Database, creándola si no existe."""
        if cls._instancia is None:
            cls._instancia = cls()
        return cls._instancia

    @classmethod
    def abrir(cls, db_path: str | Path) -> "Database":
        """Método de clase: obtiene singleton y abre conexión al .db."""
        inst = cls.instancia()
        inst._abrir(db_path)
        return inst

    @classmethod
    def cerrar(cls):
        """Método de clase: cierra la conexión activa desde el singleton."""
        cls.instancia()._cerrar()

    # ── Transacciones ────────────────────────────────────────────────

    def transaction(self):
        """Context manager: abre transacción, commitea al salir, rollback si falla.

        Uso:
            with db.transaction():
                repo.update(id, campos)
                registro = repo.buscar(id)
            # ← COMMIT aquí. Si excepción → ROLLBACK.
        """
        return _TransactionContext(self._conn)


# ── Context manager de transacciones ──────────────────────────────

class _TransactionContext:
    """Context manager para transacciones SQLite. Commitea al salir, rollback si falla."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def __enter__(self):
        self._conn.execute("SAVEPOINT _sp_data_service")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self._conn.execute("ROLLBACK TO SAVEPOINT _sp_data_service")
        else:
            self._conn.execute("RELEASE SAVEPOINT _sp_data_service")
        return False  # No suprime excepciones
