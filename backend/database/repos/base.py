"""
base.py
=======
Clase base para todos los repositorios — Open APU Studio.
"""

from backend.database.core import generar_hash  # noqa: F401 — reexportado para repos que lo usan


class RepoBase:
    def __init__(self, conn):
        """Inicializa el repositorio con una conexión SQLite."""
        self._conn   = conn
        self._cursor = conn.cursor()

    def _uno(self, sql, params=None):
        """Ejecuta una consulta y devuelve la primera fila como dict, o None."""
        row = self._cursor.execute(sql, params or []).fetchone()
        return dict(row) if row else None

    def _lista(self, sql, params=None):
        """Ejecuta una consulta y devuelve todas las filas como lista de dicts."""
        return [dict(r) for r in self._cursor.execute(sql, params or []).fetchall()]

    def _ejecutar(self, sql, params=None):
        """Ejecuta una sentencia INSERT/UPDATE/DELETE y hace commit."""
        self._cursor.execute(sql, params or [])
        self._conn.commit()
        return self._cursor.lastrowid

    def _muchos(self, sql, seq):
        """Ejecuta una inserción masiva con executemany y hace commit."""
        self._cursor.executemany(sql, seq)
        self._conn.commit()
