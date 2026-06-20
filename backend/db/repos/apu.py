from backend.db.repos.base import RepoBase


class ApuComponenteRepo(RepoBase):
    TABLA = "apu_componentes"

    def por_concepto(self, concepto_clave):
        return self._lista("SELECT * FROM apu_componentes WHERE concepto_clave = ?", [concepto_clave])

    def insertar(self, datos):
        self._ejecutar(
            "INSERT INTO apu_componentes (concepto_clave, insumo_clave, tipo_insumo, rendimiento, num_elementos, cantidad_total, precio_unitario, importe, formula) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [datos.get("concepto_clave"), datos.get("insumo_clave"),
             datos.get("tipo_insumo", 0), datos.get("rendimiento", 0),
             datos.get("num_elementos", 1), datos.get("cantidad_total", 0),
             datos.get("precio_unitario", 0), datos.get("importe", 0),
             datos.get("formula")]
        )

    def limpiar(self):
        self._ejecutar("DELETE FROM apu_componentes")


class ApuResumenRepo(RepoBase):
    TABLA = "apu_resumen"

    def por_concepto(self, concepto_clave):
        return self._uno("SELECT * FROM apu_resumen WHERE concepto_clave = ?", [concepto_clave])

    def todos(self):
        return self._lista("SELECT * FROM apu_resumen")

    def insertar(self, datos):
        self._ejecutar(
            "INSERT OR REPLACE INTO apu_resumen (concepto_clave, total_materiales, total_mano_obra, total_herramienta, total_equipo, total_auxiliares, total_subcontratos, indirectos, financiamiento, utilidad, precio_venta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [datos.get("concepto_clave"), datos.get("total_materiales", 0),
             datos.get("total_mano_obra", 0), datos.get("total_herramienta", 0),
             datos.get("total_equipo", 0), datos.get("total_auxiliares", 0),
             datos.get("total_subcontratos", 0), datos.get("indirectos", 0),
             datos.get("financiamiento", 0), datos.get("utilidad", 0),
             datos.get("precio_venta", 0)]
        )

    def limpiar(self):
        self._ejecutar("DELETE FROM apu_resumen")


class AuxiliarRepo(RepoBase):
    TABLA = "auxiliares"

    def todos(self):
        return self._lista("SELECT * FROM auxiliares")

    def insertar(self, datos):
        self._ejecutar(
            "INSERT INTO auxiliares (insumo_clave, tipo, cantidad, precio, importe) VALUES (?, ?, ?, ?, ?)",
            [datos.get("insumo_clave"), datos.get("tipo", 0),
             datos.get("cantidad", 0), datos.get("precio", 0),
             datos.get("importe", 0)]
        )

    def limpiar(self):
        self._ejecutar("DELETE FROM auxiliares")
