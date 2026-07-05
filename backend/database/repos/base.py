"""
base.py
=======
Clase base para todos los repositorios — Open APU Studio.

Escritura (no hacen commit, asumen transacción externa — ver
DataService/api.py, que envuelven cada llamada en Database.transaction()):
    _update(tabla, id, campos)
    _insert(tabla, campos) → int
    _delete(tabla, id)

Fase 4 (ver docs/ARQUITECTURA_SERVICIOS.md): se eliminaron los métodos
legados _ejecutar()/_muchos()/_actualizar_campo() — quedaron sin uso una
vez migrados todos los writes a DataService en Fase 2.
"""

from typing import Any

from backend.database.core import generar_hash  # noqa: F401


class RepoBase:
    def __init__(self, db_or_conn):
        """Inicializa el repositorio.

        Acepta Database (nuevo) o conn (legacy, deprecated).
        """
        # Soporte dual: Database o conn directo
        if hasattr(db_or_conn, 'conn'):
            self._db = db_or_conn
            self._conn = db_or_conn.conn
        else:
            self._db = None
            self._conn = db_or_conn
        self._cursor = self._conn.cursor()

    # ── Lectura ──────────────────────────────────────────────────────

    def _uno(self, sql, params=None):
        """SELECT → primera fila como dict, o None."""
        row = self._cursor.execute(sql, params or []).fetchone()
        return dict(row) if row else None

    def _lista(self, sql, params=None):
        """SELECT → lista de dicts."""
        return [dict(r) for r in self._cursor.execute(sql, params or []).fetchall()]

    def buscar(self, registro_id: int) -> dict | None:
        """SELECT genérico por id usando self.TABLA. Los repos específicos
        pueden sobreescribir con JOINs enriquecidos."""
        row = self._cursor.execute(
            f"SELECT * FROM {self.TABLA} WHERE id = ?", (registro_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Escritura (sin commit — la transacción la controla el servicio) ──

    def _update(self, tabla: str, registro_id: int, campos: dict[str, Any]) -> None:
        """UPDATE genérico. No hace commit (asume transacción externa)."""
        if not campos:
            return
        set_clause = ", ".join(f"{k} = ?" for k in campos)
        valores = list(campos.values()) + [registro_id]
        self._cursor.execute(
            f"UPDATE {tabla} SET {set_clause}, "
            f"modificado_en = datetime('now') WHERE id = ?",
            valores
        )

    def _insert(self, tabla: str, campos: dict[str, Any]) -> int:
        """INSERT genérico. No hace commit. Devuelve lastrowid."""
        cols = ", ".join(campos.keys())
        placeholders = ", ".join("?" for _ in campos)
        self._cursor.execute(
            f"INSERT INTO {tabla} ({cols}) VALUES ({placeholders})",
            list(campos.values())
        )
        return self._cursor.lastrowid

    def _delete(self, tabla: str, registro_id: int) -> None:
        """Soft-delete genérico. No hace commit."""
        self._update(tabla, registro_id, {"activo": 0})
