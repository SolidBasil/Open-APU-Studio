from db.repos.base import RepoBase


class ConceptoRepo(RepoBase):
    TABLA = "conceptos"

    def todos(self):
        return self._lista("SELECT * FROM conceptos ORDER BY partida_id, orden")

    def por_partida(self, partida_id):
        return self._lista("SELECT * FROM conceptos WHERE partida_id = ? ORDER BY orden", [partida_id])

    def buscar(self, id):
        return self._uno("SELECT * FROM conceptos WHERE id = ?", [id])

    def buscar_por_clave(self, clave):
        return self._uno("SELECT * FROM conceptos WHERE clave = ?", [clave])

    def insertar(self, datos):
        self._ejecutar(
            "INSERT INTO conceptos (proyecto_id, partida_id, clave, orden, cantidad, precio_unitario, importe, unidad, descripcion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [datos.get("proyecto_id", 1), datos.get("partida_id"),
             datos.get("clave"), datos.get("orden", 0),
             datos.get("cantidad", 1), datos.get("precio_unitario", 0),
             datos.get("importe", 0), datos.get("unidad"),
             datos.get("descripcion")]
        )
        return self._cursor.lastrowid

    def limpiar(self):
        self._ejecutar("DELETE FROM conceptos")
