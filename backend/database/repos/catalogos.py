"""catalogos.py
Repositorios de catálogos auxiliares: familias y subfamilias.
"""
from .base import RepoBase

class FamiliaRepo(RepoBase):

    TABLA = "familias"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def todas(self):
        """Devuelve todas las familias activas ordenadas por nombre."""
        return self._lista("SELECT * FROM familias WHERE activo = 1 ORDER BY nombre")

    def buscar(self, familia_id):
        """Busca una familia por su ID."""
        return self._uno("SELECT * FROM familias WHERE id = ?", [familia_id])


class SubfamiliaRepo(RepoBase):

    TABLA = "subfamilias"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def por_familia(self, familia_id):
        """Devuelve las subfamilias activas de una familia."""
        return self._lista("""
            SELECT * FROM subfamilias
            WHERE familia_id = ? AND activo = 1
            ORDER BY nombre
        """, [familia_id])

    def buscar(self, subfamilia_id):
        """Busca una subfamilia por su ID."""
        return self._uno("SELECT * FROM subfamilias WHERE id = ?", [subfamilia_id])
