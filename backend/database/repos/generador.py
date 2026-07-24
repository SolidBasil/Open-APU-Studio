"""
generador.py
============
Repositorio de generadores de obra y sus renglones.

CRUD completo + cálculo de subtotal y sincronización con el presupuesto.
"""

from typing import Any
from .base import RepoBase


class GeneradorRepo(RepoBase):
    TABLA = "generadores"

    # ── Generadores ─────────────────────────────────────────────────

    def listar_por_concepto(self, proyecto_id: int,
                            concepto_id: int | None) -> list[dict]:
        """Generadores vinculados a un concepto, o sueltos si concepto_id es None."""
        if concepto_id is None:
            return self._lista(
                "SELECT * FROM generadores WHERE proyecto_id = ? "
                "AND concepto_id IS NULL AND activo = 1 ORDER BY nombre",
                (proyecto_id,),
            )
        return self._lista(
            "SELECT * FROM generadores WHERE proyecto_id = ? "
            "AND concepto_id = ? AND activo = 1 ORDER BY nombre",
            (proyecto_id, concepto_id),
        )

    def buscar(self, generador_id: int) -> dict | None:
        return self._uno(
            "SELECT * FROM generadores WHERE id = ?", (generador_id,)
        )

    def insert(self, campos: dict[str, Any]) -> int:
        return self._insert("generadores", campos)

    def update(self, registro_id: int, campos: dict[str, Any]) -> None:
        self._update("generadores", registro_id, campos)

    def delete(self, registro_id: int) -> None:
        self._update("generadores", registro_id, {"activo": 0})
        # Desactivar renglones hijos
        self._conn.execute(
            "UPDATE generador_renglones SET activo = 0 "
            "WHERE generador_id = ?", (registro_id,)
        )

    # ── Renglones ───────────────────────────────────────────────────

    def listar_renglones(self, generador_id: int) -> list[dict]:
        return self._lista(
            "SELECT * FROM generador_renglones "
            "WHERE generador_id = ? AND activo = 1 ORDER BY orden",
            (generador_id,),
        )

    def buscar_renglon(self, renglon_id: int) -> dict | None:
        return self._uno(
            "SELECT * FROM generador_renglones WHERE id = ?",
            (renglon_id,),
        )

    def insertar_renglon(self, campos: dict[str, Any]) -> int:
        return self._insert("generador_renglones", campos)

    def actualizar_renglon(self, renglon_id: int, campos: dict[str, Any]) -> None:
        self._update("generador_renglones", renglon_id, campos)

    def eliminar_renglon(self, renglon_id: int) -> None:
        self._update("generador_renglones", renglon_id, {"activo": 0})

    # ── Cálculos ────────────────────────────────────────────────────

    @staticmethod
    def calcular_subtotal(veces: float, largo: float | None,
                          ancho: float | None, alto: float | None) -> float:
        """subtotal = veces × (largo o 1) × (ancho o 1) × (alto o 1)"""
        return veces * (largo or 1.0) * (ancho or 1.0) * (alto or 1.0)

    def recalcular_cantidad_total(self, generador_id: int) -> float:
        """Recalcula generadores.cantidad_total = SUM(subtotal) de renglones activos."""
        row = self._cursor.execute(
            "SELECT COALESCE(SUM(subtotal), 0) AS total "
            "FROM generador_renglones WHERE generador_id = ? AND activo = 1",
            (generador_id,),
        ).fetchone()
        total = float(row["total"])
        self._update("generadores", generador_id, {"cantidad_total": total})
        return total

    def recalcular_concepto(self, concepto_id: int) -> float:
        """Recalcula estructura_presupuesto.cantidad = SUM(cantidad_total) de
        todos los generadores activos enlazados a ese concepto.
        Devuelve la nueva cantidad."""
        row = self._cursor.execute(
            "SELECT COALESCE(SUM(cantidad_total), 0) AS total "
            "FROM generadores WHERE concepto_id = ? AND activo = 1",
            (concepto_id,),
        ).fetchone()
        cantidad = float(row["total"])
        self._cursor.execute(
            "UPDATE estructura_presupuesto SET cantidad = ?, "
            "modificado_en = datetime('now') WHERE id = ?",
            (cantidad, concepto_id),
        )
        return cantidad

    def conceptos_afectados(self, generador_id: int,
                            nuevo_concepto_id: int | None) -> list[int]:
        """Devuelve los concepto_id que cambian al reasignar un generador:
        el viejo (si existía) y el nuevo (si se provee)."""
        actual = self._cursor.execute(
            "SELECT concepto_id FROM generadores WHERE id = ?",
            (generador_id,),
        ).fetchone()
        ids = set()
        if actual and actual["concepto_id"] is not None:
            ids.add(actual["concepto_id"])
        if nuevo_concepto_id is not None:
            ids.add(nuevo_concepto_id)
        return list(ids)
