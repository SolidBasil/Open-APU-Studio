"""
generador.py
============
Repositorio de generadores de obra y sus renglones.

CRUD completo + cálculo de subtotal y sincronización con el presupuesto.
"""

from typing import Any
from .base import RepoBase


class GeneradorRenglonRepo(RepoBase):
    """Repo mínimo solo para que el motor genérico de deshacer/rehacer
    (DataService.deshacer/rehacer, que hace repo.update(id, {campo:
    valor}) contra repo.TABLA) apunte a la tabla correcta. GeneradorRepo
    ya tiene toda la lógica real de renglones (arriba); su .TABLA es
    "generadores", no serviría para esto."""
    TABLA = "generador_renglones"


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

    def hermanos_de(self, generador_id: int) -> list[int]:
        """ids de todos los renglones activos de un generador, en su
        orden actual."""
        filas = self._lista(
            "SELECT id FROM generador_renglones "
            "WHERE generador_id = ? AND activo = 1 ORDER BY orden, id",
            [generador_id]
        )
        return [f["id"] for f in filas]

    def info_renglon(self, renglon_id: int) -> dict | None:
        """Devuelve {generador_id, orden} de un renglón, o None si no existe."""
        return self._uno(
            "SELECT generador_id, orden FROM generador_renglones WHERE id = ?",
            [renglon_id]
        )

    def mover_bloque(self, ids: list[int], nuevo_generador_id: int,
                      antes_de_id: int | None) -> None:
        """Reposiciona un bloque de renglones (ids, en el orden en que el
        usuario los arrastró) para que queden en nuevo_generador_id,
        insertados justo antes de antes_de_id (o al final si es None o
        ya no es uno de los renglones de ese generador).

        Usado por el drag and drop del generador: soltar dentro del
        mismo generador reordena; soltar en OTRO generador (otra
        pestaña abierta) lo mueve ahí. El llamador (DataService) es
        quien recalcula cantidad_total/concepto de los generadores
        afectados después — esto solo toca generador_id/orden."""
        ids_mover = set(ids)
        hermanos = [rid for rid in self.hermanos_de(nuevo_generador_id) if rid not in ids_mover]
        if antes_de_id is not None and antes_de_id in hermanos:
            idx = hermanos.index(antes_de_id)
        else:
            idx = len(hermanos)
        nuevo_orden = hermanos[:idx] + list(ids) + hermanos[idx:]
        self._cursor.executemany(
            "UPDATE generador_renglones SET generador_id = ?, orden = ? WHERE id = ?",
            [(nuevo_generador_id, pos + 1, rid) for pos, rid in enumerate(nuevo_orden)]
        )

    def duplicar_bloque(self, ids: list[int], nuevo_generador_id: int,
                         antes_de_id: int | None) -> list[int]:
        """Duplica un bloque de renglones como filas nuevas en
        nuevo_generador_id, en la posición indicada (ver mover_bloque).
        Devuelve los ids nuevos, en el mismo orden que `ids`. Usado por
        el drag and drop con Ctrl presionado: el original queda intacto."""
        nuevos = []
        for rid in ids:
            fila = self.buscar_renglon(rid)
            if not fila:
                continue
            datos = {k: v for k, v in fila.items()
                     if k not in ("id", "generador_id", "orden",
                                  "creado_en", "modificado_en", "modificado_por")}
            datos["generador_id"] = nuevo_generador_id
            datos["orden"] = 0  # posicionado de verdad por mover_bloque() justo después
            nuevos.append(self.insertar_renglon(datos))
        self.mover_bloque(nuevos, nuevo_generador_id, antes_de_id)
        return nuevos

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
