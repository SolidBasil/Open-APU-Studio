"""
formulas.py (repo)
===================
VariableFormulaRepo — CRUD de variables_formula (schema.sql Bloque 8).

Expone la interfaz estándar update()/insert()/delete()/buscar() que
espera DataService (ver data_service.py: repo.update(id, campos),
repo.insert(campos), repo.delete(id) vía eliminar()) — así el flujo pasa
por el mismo camino que cualquier otra entidad: validación de schema,
transacción, historial (undo/redo) y emisión de evento post-commit, sin
código especial. También significa que ya funciona vía HTTP sin tocar
server/servidor.py, porque /actualizar, /insertar y /eliminar son
genéricos por nombre de entidad.

La única razón para no usar los helpers _update()/_insert()/_delete()
de RepoBase tal cual es que esos asumen columnas `modificado_en`
(_update) y `activo` (_delete, soft-delete) que `variables_formula` no
tiene — es una tabla de catálogo simple, sin auditoría propia (el
historial de cambios ya lo cubre la tabla `historial` aparte). Por eso
aquí se escribe el SQL directo en vez de heredar ese comportamiento.

Uso:
    from backend.database.repos import VariableFormulaRepo
    repo = VariableFormulaRepo(db)
    repo.insert({"proyecto_id": 1, "nombre": "ancho_muro", "expresion": "3.5"})
    repo.por_proyecto(1)  # -> [{"nombre": "ancho_muro", ...}, ...]
"""

from .base import RepoBase

_CAMPOS_VALIDOS = {"proyecto_id", "nombre", "expresion", "valor", "descripcion"}


class VariableFormulaRepo(RepoBase):

    TABLA = "variables_formula"

    # ── Interfaz estándar (la que usa DataService) ──────────────────

    def update(self, registro_id: int, campos: dict) -> None:
        campos = {k: v for k, v in campos.items() if k in _CAMPOS_VALIDOS}
        if not campos:
            return
        set_clause = ", ".join(f"{k} = ?" for k in campos)
        valores = list(campos.values()) + [registro_id]
        self._cursor.execute(
            f"UPDATE variables_formula SET {set_clause} WHERE id = ?", valores
        )

    def insert(self, campos: dict) -> int:
        campos = {k: v for k, v in campos.items() if k in _CAMPOS_VALIDOS}
        cols = ", ".join(campos.keys())
        placeholders = ", ".join("?" for _ in campos)
        self._cursor.execute(
            f"INSERT INTO variables_formula ({cols}) VALUES ({placeholders})",
            list(campos.values()),
        )
        return self._cursor.lastrowid

    def delete(self, registro_id: int) -> None:
        """Hard delete — no hay columna `activo` en esta tabla, a
        diferencia de familias/subfamilias/insumos."""
        self._cursor.execute("DELETE FROM variables_formula WHERE id = ?", [registro_id])

    def buscar(self, registro_id: int) -> dict | None:
        return self._uno("SELECT * FROM variables_formula WHERE id = ?", [registro_id])

    # ── Consultas propias ────────────────────────────────────────────

    def por_proyecto(self, proyecto_id: int) -> list[dict]:
        """Todas las variables de un proyecto, ordenadas por nombre."""
        return self._lista(
            "SELECT * FROM variables_formula WHERE proyecto_id = ? ORDER BY nombre",
            [proyecto_id],
        )

    def buscar_por_nombre(self, proyecto_id: int, nombre: str) -> dict | None:
        return self._uno(
            "SELECT * FROM variables_formula WHERE proyecto_id = ? AND nombre = ?",
            [proyecto_id, nombre],
        )
