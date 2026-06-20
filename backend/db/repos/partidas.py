from backend.db.repos.base import RepoBase


class PartidaRepo(RepoBase):
    TABLA = "partidas"

    def todas(self):
        return self._lista("SELECT * FROM partidas ORDER BY nivel, orden")

    def hijos(self, padre_id=None):
        if padre_id is None:
            return self._lista("SELECT * FROM partidas WHERE padre_id IS NULL ORDER BY orden")
        return self._lista("SELECT * FROM partidas WHERE padre_id = ? ORDER BY orden", [padre_id])

    def buscar(self, id):
        return self._uno("SELECT * FROM partidas WHERE id = ?", [id])

    def insertar(self, datos):
        self._ejecutar(
            "INSERT INTO partidas (proyecto_id, padre_id, clave, nombre, orden, nivel) VALUES (?, ?, ?, ?, ?, ?)",
            [datos.get("proyecto_id", 1), datos.get("padre_id"),
             datos.get("clave"), datos.get("nombre"),
             datos.get("orden", 0), datos.get("nivel", 0)]
        )
        return self._cursor.lastrowid

    def arbol(self):
        todas = self.todas()
        arbol = []
        mapa = {}
        for p in todas:
            p["hijos"] = []
            mapa[p["id"]] = p
        for p in todas:
            pid = p["padre_id"]
            if pid and pid in mapa:
                mapa[pid]["hijos"].append(p)
            else:
                arbol.append(p)
        return arbol

    def limpiar(self):
        self._ejecutar("DELETE FROM partidas")

    def ultimo_orden(self, padre_id=None):
        if padre_id is None:
            row = self._uno("SELECT COALESCE(MAX(orden), 0) as ultimo FROM partidas WHERE padre_id IS NULL")
        else:
            row = self._uno("SELECT COALESCE(MAX(orden), 0) as ultimo FROM partidas WHERE padre_id = ?", [padre_id])
        return row["ultimo"] if row else 0
