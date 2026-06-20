from db.repos.base import RepoBase


class InsumoRepo(RepoBase):
    TABLA = "insumos"
    CAMPOS = ["clave", "tipo", "unidad", "precio", "descripcion",
              "descripcion_corta", "es_basico", "fecha_precio",
              "costo_materiales", "costo_mano_obra", "costo_herramienta",
              "costo_equipo", "costo_auxiliares"]

    def todos(self):
        return self._lista("SELECT * FROM insumos ORDER BY tipo, clave")

    def por_tipo(self, tipo):
        return self._lista("SELECT * FROM insumos WHERE tipo = ? ORDER BY clave", [tipo])

    def por_tipos(self, tipos):
        placeholders = ",".join("?" for _ in tipos)
        return self._lista(f"SELECT * FROM insumos WHERE tipo IN ({placeholders}) ORDER BY tipo, clave", list(tipos))

    def buscar(self, clave):
        return self._uno("SELECT * FROM insumos WHERE clave = ?", [clave])

    def insertar(self, datos):
        cols = ", ".join(self.CAMPOS)
        placeholders = ", ".join("?" for _ in self.CAMPOS)
        valores = [datos.get(c, None) for c in self.CAMPOS]
        self._ejecutar(f"INSERT OR REPLACE INTO {self.TABLA} ({cols}) VALUES ({placeholders})", valores)

    def tipos_disponibles(self):
        return self._lista("""
            SELECT t.id, t.nombre, COUNT(*) as total
            FROM tipos_insumo t
            LEFT JOIN insumos i ON i.tipo = t.id
            GROUP BY t.id
            ORDER BY t.id
        """)

    def total_por_tipo(self):
        return self._lista("""
            SELECT t.id as tipo, t.nombre, COUNT(*) as total
            FROM insumos i
            JOIN tipos_insumo t ON t.id = i.tipo
            GROUP BY i.tipo
            ORDER BY i.tipo
        """)
