import sqlite3
import os
from pathlib import Path


class DatabaseManager:
    _instance = None

    def __init__(self, db_path=None):
        self._conn = None
        self._db_path = None
        if db_path:
            self.open(db_path)

    def open(self, db_path):
        self.close()
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.row_factory = sqlite3.Row
        self._aplicar_migraciones()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
            self._db_path = None

    @property
    def conn(self):
        return self._conn

    @property
    def db_path(self):
        return self._db_path

    def _aplicar_migraciones(self):
        cursor = self._conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, aplicado_en TEXT NOT NULL DEFAULT (datetime('now')))")
        aplicadas = {row[0] for row in cursor.execute("SELECT version FROM schema_version").fetchall()}
        migraciones_dir = Path(__file__).parent / "migraciones"
        archivos = sorted(migraciones_dir.glob("*.sql"))
        for archivo in archivos:
            version = int(archivo.stem.split("_")[0])
            if version not in aplicadas:
                sql = archivo.read_text(encoding="utf-8")
                self._conn.executescript(sql)
                self._conn.commit()

    @classmethod
    def instancia(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def abrir(cls, db_path):
        inst = cls.instancia()
        inst.open(db_path)
        return inst

    @classmethod
    def cerrar(cls):
        inst = cls.instancia()
        inst.close()
