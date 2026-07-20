"""indirectos.py
Repositorio de gastos indirectos de campo y oficina.

Fórmula del total:
  periodo_dias = 0  → total = importe × pct_participacion/100
  periodo_dias > 0  → total = importe × (duracion_obra_dias / periodo_dias) × pct_participacion/100
"""
from .base import RepoBase


class IndirectoRepo(RepoBase):

    TABLA = "indirectos"

    def update(self, registro_id: int, campos: dict) -> None:
        return self._update(self.TABLA, registro_id, campos)

    def insert(self, campos: dict) -> int:
        return self._insert(self.TABLA, campos)

    def delete(self, registro_id: int) -> None:
        return self._delete(self.TABLA, registro_id)

    def todos(self, proyecto_id: int, tipo: str | None = None) -> list[dict]:
        """Lista indirectos de un proyecto, opcionalmente filtrados por tipo."""
        if tipo:
            return self._lista(
                "SELECT * FROM indirectos WHERE proyecto_id = ? AND tipo = ? AND activo = 1 ORDER BY orden",
                [proyecto_id, tipo],
            )
        return self._lista(
            "SELECT * FROM indirectos WHERE proyecto_id = ? AND activo = 1 ORDER BY tipo, orden",
            [proyecto_id],
        )

    def calcular_totales(self, proyecto_id: int) -> None:
        """Recalcula el campo 'total' de todos los indirectos del proyecto."""
        # Obtener duracion_obra_dias del proyecto
        row = self._uno(
            "SELECT duracion_obra_dias FROM proyectos WHERE id = ?",
            [proyecto_id],
        )
        duracion = float(row["duracion_obra_dias"] or 0) if row else 0.0

        # Calcular total para cada indirecto
        indirectos = self._lista(
            "SELECT id, periodo_dias, importe, pct_participacion FROM indirectos WHERE proyecto_id = ? AND activo = 1",
            [proyecto_id],
        )
        for ind in indirectos:
            periodo = float(ind["periodo_dias"] or 0)
            importe = float(ind["importe"] or 0)
            pct = float(ind["pct_participacion"] or 100)

            if periodo == 0:
                total = importe * (pct / 100)
            else:
                total = importe * (duracion / periodo) * (pct / 100)

            self._cursor.execute(
                "UPDATE indirectos SET total = ?, modificado_en = datetime('now') WHERE id = ?",
                (round(total, 2), ind["id"]),
            )

    def total_por_tipo(self, proyecto_id: int, tipo: str) -> float:
        """Suma de totales de indirectos de un tipo específico."""
        row = self._uno(
            "SELECT COALESCE(SUM(total), 0) AS suma FROM indirectos WHERE proyecto_id = ? AND tipo = ? AND activo = 1",
            [proyecto_id, tipo],
        )
        return float(row["suma"]) if row else 0.0


# =============================================================================
# PLANTILLAS
# =============================================================================

PLANTILLA_CAMPO = [
    # (categoria, concepto, periodo_dias, importe_default)
    # ── Personal ──
    ("Personal", "Residente de obra", 30, 0.0),
    ("Personal", "Superintendente", 30, 0.0),
    ("Personal", "Auxiliar de residente", 30, 0.0),
    ("Personal", "Supervisor de obra", 30, 0.0),
    ("Personal", "Supervisor de seguridad e higiene", 30, 0.0),
    ("Personal", "Topógrafo", 30, 0.0),
    ("Personal", "Auxiliar de topografía", 30, 0.0),
    ("Personal", "Laboratorista", 30, 0.0),
    ("Personal", "Almacenista", 30, 0.0),
    ("Personal", "Bodeguero", 30, 0.0),
    ("Personal", "Velador", 30, 0.0),
    ("Personal", "Chofer", 30, 0.0),
    ("Personal", "Personal de limpieza", 30, 0.0),
    # ── Instalaciones temporales ──
    ("Instalaciones temporales", "Oficina de obra", 30, 0.0),
    ("Instalaciones temporales", "Bodega de materiales", 30, 0.0),
    ("Instalaciones temporales", "Campamento", 30, 0.0),
    ("Instalaciones temporales", "Caseta de vigilancia", 30, 0.0),
    ("Instalaciones temporales", "Taller provisional", 30, 0.0),
    # ── Servicios ──
    ("Servicios", "Agua", 30, 0.0),
    ("Servicios", "Energía eléctrica", 30, 0.0),
    ("Servicios", "Internet", 30, 0.0),
    ("Servicios", "Telefonía", 30, 0.0),
    ("Servicios", "Sanitarios portátiles", 30, 0.0),
    ("Servicios", "Recolección de basura", 30, 0.0),
    ("Servicios", "Limpieza de obra", 30, 0.0),
    # ── Vehículos y equipo auxiliar ──
    ("Vehículos y equipo auxiliar", "Camioneta", 30, 0.0),
    ("Vehículos y equipo auxiliar", "Automóvil", 30, 0.0),
    ("Vehículos y equipo auxiliar", "Motocicleta", 30, 0.0),
    ("Vehículos y equipo auxiliar", "Combustible", 30, 0.0),
    ("Vehículos y equipo auxiliar", "Mantenimiento de vehículos", 30, 0.0),
    # ── Control de calidad ──
    ("Control de calidad", "Laboratorio de concreto", 30, 0.0),
    ("Control de calidad", "Laboratorio de mecánica de suelos", 30, 0.0),
    ("Control de calidad", "Topografía externa", 30, 0.0),
    ("Control de calidad", "Ensayes de materiales", 30, 0.0),
    # ── Logística ──
    ("Logística", "Fletes", 0, 0.0),
    ("Logística", "Acarreos", 0, 0.0),
    ("Logística", "Movilización de maquinaria", 0, 0.0),
    ("Logística", "Desmovilización de maquinaria", 0, 0.0),
    # ── Seguridad ──
    ("Seguridad", "Seguro de maquinaria", 365, 0.0),
    ("Seguridad", "Seguro de vehículos", 365, 0.0),
    ("Seguridad", "Fianza específica de obra", 0, 0.0),
    # ── Otros ──
    ("Otros", "Herramienta menor", 0, 0.0),
    ("Otros", "Equipo de protección personal", 0, 0.0),
    ("Otros", "Señalización temporal", 0, 0.0),
    ("Otros", "Gastos imprevistos de obra", 0, 0.0),
]

PLANTILLA_OFICINA = [
    # ── Dirección ──
    ("Dirección", "Director General", 30, 0.0),
    ("Dirección", "Gerente Técnico", 30, 0.0),
    ("Dirección", "Gerente Administrativo", 30, 0.0),
    ("Dirección", "Personal administrativo", 30, 0.0),
    ("Dirección", "Contador", 30, 0.0),
    ("Dirección", "Auxiliar contable", 30, 0.0),
    ("Dirección", "Recursos Humanos", 30, 0.0),
    ("Dirección", "Compras", 30, 0.0),
    ("Dirección", "Recepcionista", 30, 0.0),
    ("Dirección", "Auxiliar administrativo", 30, 0.0),
    ("Dirección", "Mensajería", 30, 0.0),
    # ── Oficina ──
    ("Oficina", "Renta de oficina", 30, 0.0),
    ("Oficina", "Agua", 30, 0.0),
    ("Oficina", "Energía eléctrica", 30, 0.0),
    ("Oficina", "Internet", 30, 0.0),
    ("Oficina", "Telefonía", 30, 0.0),
    ("Oficina", "Papelería", 30, 0.0),
    ("Oficina", "Impresiones", 30, 0.0),
    ("Oficina", "Artículos de limpieza", 30, 0.0),
    # ── Software y tecnología ──
    ("Software y tecnología", "Licencias de software", 365, 0.0),
    ("Software y tecnología", "Almacenamiento en la nube", 30, 0.0),
    ("Software y tecnología", "Dominio y hospedaje web", 365, 0.0),
    ("Software y tecnología", "Equipos de cómputo", 0, 0.0),
    ("Software y tecnología", "Mantenimiento de equipos", 30, 0.0),
    # ── Vehículos administrativos ──
    ("Vehículos administrativos", "Automóvil", 30, 0.0),
    ("Vehículos administrativos", "Camioneta", 30, 0.0),
    ("Vehículos administrativos", "Combustible", 30, 0.0),
    ("Vehículos administrativos", "Mantenimiento", 30, 0.0),
    # ── Asesorías ──
    ("Asesorías", "Asesoría jurídica", 30, 0.0),
    ("Asesorías", "Asesoría fiscal", 30, 0.0),
    ("Asesorías", "Auditorías", 0, 0.0),
    ("Asesorías", "Consultoría externa", 0, 0.0),
    # ── Seguros ──
    ("Seguros", "Seguro de oficina", 365, 0.0),
    ("Seguros", "Seguro de vehículos", 365, 0.0),
    ("Seguros", "Fianzas corporativas", 365, 0.0),
    # ── Gastos financieros ──
    ("Gastos financieros", "Comisiones bancarias", 30, 0.0),
    ("Gastos financieros", "Intereses", 30, 0.0),
    ("Gastos financieros", "Gastos por transferencias", 0, 0.0),
]
