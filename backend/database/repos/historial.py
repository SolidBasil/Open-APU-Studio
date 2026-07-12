"""
historial.py
============
Repositorio de historial de cambios — base del Ctrl+Z colaborativo.

SRV-09: cada escritura captura valor_anterior ANTES del UPDATE.
SRV-10: deshacer()/rehacer() restauran valores vía DataService (no SQL directo).

Tabla: historial (ver schema.sql)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from backend.database.repos.base import RepoBase


class HistorialRepo(RepoBase):
    TABLA = "historial"

    # ── SRV-09: Captura de estado anterior ─────────────────────────

    def capturar(self, tabla: str, registro_id: int, campo: str,
                 valor_anterior, valor_nuevo, usuario_id: int = 1,
                 sesion: str | None = None) -> None:
        """Registra un cambio en historial. Llamar ANTES del commit.

        sesion: UUID para agrupar cambios de una misma operación
                (ej. recálculo en cascada = muchos campos, un solo undo).
                Si es None, genera uno nuevo.
        """
        if sesion is None:
            sesion = str(uuid.uuid4())
        self._insert(self.TABLA, {
            "sesion":         sesion,
            "tabla":          tabla,
            "registro_id":    registro_id,
            "campo":          campo,
            "valor_anterior": str(valor_anterior) if valor_anterior is not None else None,
            "valor_nuevo":    str(valor_nuevo) if valor_nuevo is not None else None,
            "usuario_id":     usuario_id,
            "cambiado_en":    datetime.now().isoformat(),
        })

    # ── SRV-10: Deshacer / Rehacer ────────────────────────────────

    def ultima_sesion_usuario(self, usuario_id: int) -> str | None:
        """Devuelve la sesion UUID del último cambio NO deshecho de este usuario."""
        row = self._uno(
            "SELECT sesion FROM historial WHERE usuario_id = ? "
            "AND deshachado_en IS NULL "
            "ORDER BY id DESC LIMIT 1", (usuario_id,)
        )
        return row["sesion"] if row else None

    def ultima_sesion_deshecha(self, usuario_id: int) -> str | None:
        """Devuelve la sesion UUID del PRIMER cambio deshecho (FIFO: primero deshecho = primero a rehacer)."""
        row = self._uno(
            "SELECT sesion FROM historial WHERE usuario_id = ? "
            "AND deshachado_en IS NOT NULL "
            "ORDER BY id ASC LIMIT 1", (usuario_id,)
        )
        return row["sesion"] if row else None

    def marcar_deshachada(self, sesion: str) -> None:
        """Marca una sesión como deshecha (para poder rehacerla después)."""
        self._cursor.execute(
            "UPDATE historial SET deshachado_en = datetime('now') "
            "WHERE sesion = ?", (sesion,)
        )

    def desmarcar_sesion(self, sesion: str) -> None:
        """Des-marca una sesión deshecha (al rehacerla)."""
        self._cursor.execute(
            "UPDATE historial SET deshachado_en = NULL "
            "WHERE sesion = ?", (sesion,)
        )

    def limpiar_deshachadas(self, usuario_id: int) -> None:
        """Borra sesiones deshechas (nueva escritura invalida el redo stack)."""
        self._cursor.execute(
            "DELETE FROM historial WHERE usuario_id = ? "
            "AND deshachado_en IS NOT NULL", (usuario_id,)
        )

    def cambios_sesion(self, sesion: str) -> list[dict]:
        """Todos los cambios de una sesión, ordenados cronológicamente."""
        return self._lista(
            "SELECT * FROM historial WHERE sesion = ? ORDER BY id", (sesion,)
        )

    def invalidar_sesiones_usuario(self, usuario_id: int) -> int:
        """SRV-08: Borra el historial de OTROS usuarios cuando un usuario
        hace un recálculo que invalida sus cambios pendientes.

        Devuelve el número de registros eliminados.
        """
        self._cursor.execute(
            "DELETE FROM historial WHERE usuario_id = ?", (usuario_id,)
        )
        return self._cursor.rowcount

    def valor_campo(self, tabla: str, registro_id: int, campo: str):
        """Lee el valor actual de un campo específico de una tabla."""
        row = self._uno(
            f"SELECT {campo} FROM {tabla} WHERE id = ?", (registro_id,)
        )
        return row[campo] if row else None
