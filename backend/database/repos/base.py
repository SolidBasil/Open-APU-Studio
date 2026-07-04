"""
base.py
=======
Clase base para todos los repositorios — Open APU Studio.

Métodos nuevos (no hacen commit, asumen transacción externa):
    _update(tabla, id, campos)
    _insert(tabla, campos) → int
    _delete(tabla, id)

Método legado (DEPRECATED, hace commit):
    _ejecutar(sql, params)
"""

import warnings
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

    def buscar(self, tabla: str, registro_id: int) -> dict | None:
        """SELECT genérico por id. Los repos específicos pueden sobreescribir con JOINs."""
        row = self._cursor.execute(
            f"SELECT * FROM {tabla} WHERE id = ?", (registro_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Escritura (nuevos, sin commit) ──────────────────────────────

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

    # ── Métodos legados (DEPRECATED) ─────────────────────────────────

    def _ejecutar(self, sql, params=None):
        """DEPRECATED: hace commit(). Solo usar en código no migrado."""
        warnings.warn(
            "_ejecutar() está deprecado. Usa _update/_insert/_delete con transacción externa.",
            DeprecationWarning, stacklevel=2
        )
        self._cursor.execute(sql, params or [])
        self._conn.commit()
        return self._cursor.lastrowid

    def _muchos(self, sql, seq):
        """DEPRECATED: executemany + commit."""
        warnings.warn(
            "_muchos() está deprecado. Usa transacción externa.",
            DeprecationWarning, stacklevel=2
        )
        self._cursor.executemany(sql, seq)
        self._conn.commit()

    def _actualizar_campo(self, tabla, registro_id, campo, valor,
                          campos_permitidos, usuario_id=1):
        """DEPRECATED: actualiza un campo con whitelist."""
        warnings.warn(
            "_actualizar_campo() está deprecado. Usa DataService.actualizar().",
            DeprecationWarning, stacklevel=2
        )
        if campo not in campos_permitidos:
            raise ValueError(f"Campo '{campo}' no es editable en {tabla}")
        self._ejecutar(f"""
            UPDATE {tabla} SET {campo} = ?,
                modificado_por = ?, modificado_en = datetime('now')
            WHERE id = ?
        """, [valor, usuario_id, registro_id])
