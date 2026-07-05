"""catalogos.py
Repositorios de catálogos auxiliares: familias, subfamilias y notas.
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

    def insertar(self, nombre):
        """Inserta una nueva familia."""
        return self._insert("familias", {"nombre": nombre})


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

    def insertar(self, familia_id, nombre):
        """Inserta una nueva subfamilia dentro de una familia."""
        return self._insert("subfamilias", {"familia_id": familia_id, "nombre": nombre})


# =============================================================================
# NOTAS
# =============================================================================

class NotaRepo(RepoBase):

    TABLA = "notas"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def por_nodo(self, concepto_id):
        """Devuelve las notas de un nodo ordenadas por fecha descendente."""
        return self._lista("""
            SELECT n.*, u.nombre AS autor
            FROM notas n
            JOIN usuarios u ON u.id = n.usuario_id
            WHERE n.concepto_id = ?
            ORDER BY n.creado_en DESC
        """, [concepto_id])

    def insertar(self, concepto_id, texto, usuario_id=1):
        """Inserta una nota en un nodo."""
        return self._insert("notas", {
            "concepto_id": concepto_id,
            "usuario_id": usuario_id,
            "texto": texto,
        })

    def resolver(self, nota_id):
        """Marca una nota como resuelta."""
        self._update("notas", nota_id, {"resuelta": 1})

    def abiertas(self, proyecto_id):
        """Devuelve las notas no resueltas de un proyecto."""
        return self._lista("""
            SELECT n.*, u.nombre AS autor,
                   ep.wbs, ep.descripcion_corta
            FROM notas n
            JOIN usuarios u              ON u.id  = n.usuario_id
            JOIN estructura_presupuesto ep ON ep.id = n.concepto_id
            WHERE ep.proyecto_id = ? AND n.resuelta = 0
            ORDER BY n.creado_en DESC
        """, [proyecto_id])


# =============================================================================
# EXPLOSIÓN DE INSUMOS
# =============================================================================
