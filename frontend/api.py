"""
api.py
======
Capa de servicio entre el frontend y el backend de Open APU Studio.

Responsabilidad: recibir peticiones del frontend en términos de dominio
(clave, proyecto_id, nivel de explosión…), coordinar los repos y core
necesarios, y devolver datos listos para que los widgets los rendericen
sin necesidad de conocer SQL ni repos.

Reglas:
- Nunca importa widgets de PySide6 — es agnóstico a la UI.
- Nunca escribe SQL directamente — delega a repos y core.
- Devuelve siempre tipos Python estándar: dict, list, str, int, float, None.
- Todos los métodos reciben `conn` (sqlite3.Connection) como primer argumento
  para que la ventana principal administre el ciclo de vida de la conexión.

Uso típico desde ventana.py:
    from frontend.api import Api
    api = Api(self._db.conn, self._db.db_path, proyecto_id=1)
    arbol   = api.presupuesto_arbol()
    apu     = api.apu(clave="0202002")
    filas,t = api.explotar(concepto_ids=[5,23], nivel="basico", tipos_ids=[1,2,4])
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing  import Any


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class Api:
    """Fachada de servicios para el frontend.

    Args:
        conn       — conexión SQLite activa del proyecto abierto
        db_path    — ruta al archivo .db (necesaria para get_apu de core)
        proyecto_id — siempre 1 en la versión actual (monoproyecto por .db)
    """

    def __init__(self, conn: sqlite3.Connection, db_path: str | Path, proyecto_id: int = 1):
        self._conn   = conn
        self._db_path = str(db_path)
        self._pid    = proyecto_id

    # =========================================================================
    # PRESUPUESTO
    # =========================================================================

    def presupuesto_arbol(self) -> list[dict]:
        """Devuelve el árbol completo del presupuesto listo para poblar TablaArbol."""
        from backend.core import build_budget_tree
        return build_budget_tree(self._db_path)

    def todos_concepto_ids(self) -> list[int]:
        """Devuelve los ids de todos los conceptos activos del proyecto."""
        rows = self._conn.execute("""
            SELECT id FROM estructura_presupuesto
            WHERE proyecto_id = ? AND tipo = 'concepto' AND activo = 1
        """, (self._pid,)).fetchall()
        return [r[0] for r in rows]

    def conceptos_planos(self) -> list[dict]:
        """Lista plana de todos los conceptos con clave, descripción, unidad, cantidad, precio, importe."""
        from backend.repos import ConceptoRepo
        return ConceptoRepo(self._conn).todos(self._pid)

    # =========================================================================
    # APU
    # =========================================================================

    def apu(self, clave: str) -> dict | None:
        """Devuelve el APU de un concepto o insumo compuesto por clave.

        Retorna:
            {
                "matriz_id":    int,
                "descripcion":  str,
                "detalle":      list[dict],   # filas del APU, listas para la tabla
                "totales":      dict | None,  # subtotales por tipo
            }
            o None si la clave no tiene APU asociado.

        Cada fila de detalle incluye:
            tipo_emoji, tipo_nombre, tipo_id, insumo_clave, descripcion,
            insumo_unidad, cantidad, precio, importe, es_compuesto, tiene_sub_apu
        """
        from backend.repos  import NodoRepo, InsumoRepo, ApuMatricesRepo
        from backend.core   import get_apu

        # 1. Resolver matriz_id
        matriz_id, descripcion = self._resolver_matriz(clave)
        if matriz_id is None:
            return None

        # 2. Obtener detalle
        data = get_apu(self._db_path, matriz_id)

        # 3. Fallback: APU negativo vacío → buscar APU positivo del árbol
        if not data.get("detalle") and matriz_id < 0:
            ep = self._conn.execute("""
                SELECT id FROM estructura_presupuesto
                WHERE clave = ? AND proyecto_id = ? AND tipo = 'concepto'
                LIMIT 1
            """, (clave, self._pid)).fetchone()
            if ep:
                data = get_apu(self._db_path, ep[0])

        if not data.get("detalle"):
            return None

        # 4. Enriquecer filas
        claves_con_apu = self.claves_con_apu()
        _EMOJI = {1: "🧱", 2: "👷", 4: "🔧", 8: "🚜", 16: "⚙️", 32: "📄"}

        detalle = []
        for r in data["detalle"]:
            tid   = r.get("tipo_id", 0)
            desc  = r.get("insumo_descripcion") or r.get("insumo_desc_corta") or ""
            tiene_sub = r.get("insumo_clave") in claves_con_apu
            detalle.append({
                "tipo_emoji":   _EMOJI.get(tid, ""),
                "tipo_nombre":  r.get("tipo_nombre", ""),
                "tipo_id":      tid,
                "insumo_clave": r.get("insumo_clave", ""),
                "descripcion":  f"▶ {desc}" if tiene_sub else desc,
                "insumo_unidad": r.get("insumo_unidad", ""),
                "cantidad":     r.get("cantidad", 0),
                "precio":       r.get("precio", 0),
                "importe":      r.get("importe", 0),
                "es_compuesto": r.get("insumo_es_compuesto", 0),
                "tiene_sub_apu": tiene_sub,
            })

        return {
            "matriz_id":   matriz_id,
            "descripcion": descripcion,
            "detalle":     detalle,
            "totales":     data.get("totales"),
        }

    def insumo_es_compuesto(self, clave: str) -> bool:
        """True si el insumo con esa clave es compuesto (tiene APU propio)."""
        row = self._conn.execute("""
            SELECT es_compuesto FROM insumos
            WHERE clave = ? AND proyecto_id = ? LIMIT 1
        """, (clave, self._pid)).fetchone()
        return bool(row and row[0])

    def claves_con_apu(self) -> set[str]:
        """Conjunto de claves de insumos compuestos y conceptos con APU en el árbol."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT clave FROM insumos WHERE es_compuesto = 1 AND proyecto_id = ?",
            (self._pid,)
        )
        claves = {r[0] for r in cur.fetchall()}
        cur.execute("""
            SELECT DISTINCT ep.clave FROM estructura_presupuesto ep
            JOIN apu_matrices am ON am.matriz_id = ep.id
            WHERE ep.proyecto_id = ? AND ep.clave IS NOT NULL
        """, (self._pid,))
        claves |= {r[0] for r in cur.fetchall()}
        return claves

    # =========================================================================
    # INSUMOS
    # =========================================================================

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        """Catálogo de insumos, opcionalmente filtrado por tipo (ej. 'material', 'mano_obra').
        Cada dict incluye todos los campos de InsumoRepo más familia y subfamilia.
        """
        from backend.repos import InsumoRepo
        repo = InsumoRepo(self._conn)
        return repo.por_tipo(self._pid, tipo_clave) if tipo_clave else repo.todos(self._pid)

    def insumos_con_matrices(self, tipo_clave: str | None = None) -> list[dict]:
        """Como insumos() pero filtra solo los que aparecen en al menos un APU."""
        claves = self.claves_con_apu()
        return [i for i in self.insumos(tipo_clave) if i.get("clave") in claves]

    def insumo_por_clave(self, clave: str) -> dict | None:
        """Devuelve el dict del insumo con esa clave, o None si no existe."""
        from backend.repos import InsumoRepo
        return InsumoRepo(self._conn).buscar_por_clave(clave, proyecto_id=self._pid)

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        """Devuelve las matrices (conceptos o compuestos) donde aparece un insumo.

        Cada fila:
            tipo_origen ('concepto' | 'compuesto'), matriz_clave, matriz_descripcion,
            matriz_wbs, cantidad, precio, importe
        """
        from backend.repos import InsumoRepo
        return InsumoRepo(self._conn).donde_se_usa(insumo_id)

    # =========================================================================
    # EXPLOSIÓN DE INSUMOS
    # =========================================================================

    def explotar(
        self,
        concepto_ids: list[int],
        nivel: str,
        tipos_ids: list[int],
    ) -> tuple[list[dict], float]:
        """Calcula la explosión de insumos para los conceptos dados.

        Lee la precisión de decimales desde Config automáticamente.

        Args:
            concepto_ids — ids de estructura_presupuesto a explotar
            nivel        — 'basico' | 'compuesto' | 'primer_nivel'
            tipos_ids    — lista de tipo_id a incluir (1=Mat,2=MO,4=Herr,8=Eq…)

        Returns:
            (filas, total_global)
            filas — list[dict] con tipo_id, tipo_nombre, clave, descripcion,
                    unidad, cantidad_total, pu, total, pct, pct_mo
        """
        from backend.repos  import ExplosionRepo
        from frontend.widgets.ajustes import get_decimales_explosion

        decimales = get_decimales_explosion()
        return ExplosionRepo(self._conn).calcular(
            proyecto_id  = self._pid,
            concepto_ids = concepto_ids,
            nivel        = nivel,
            tipos_ids    = tipos_ids,
            decimales    = decimales,
        )

    def resumen_tipos_explosion(self, tipos_ids: list[int]) -> str:
        """Genera el string de tipos para el encabezado de la pestaña de explosión.
        Ej: '🧱 Materiales, 👷 Mano de obra, 🔧 Herramienta'
        """
        from frontend.widgets.explosion import TIPOS_INSUMO, TIPO_ICONO
        tipo_nombre_map = {t[0]: t[1] for t in TIPOS_INSUMO}
        return ", ".join(
            f"{TIPO_ICONO.get(tid, '')} {tipo_nombre_map.get(tid, str(tid))}".strip()
            for tid in tipos_ids
        )

    # =========================================================================
    # GESTIÓN DE PROYECTOS
    # =========================================================================

    @staticmethod
    def proyectos_disponibles() -> list[str]:
        """Lista de nombres de proyectos (.db) disponibles en la carpeta de proyectos."""
        from backend.db import Rutas
        carpeta = Rutas.proyectos()
        if not carpeta.exists():
            return []
        return sorted(p.stem for p in carpeta.glob("*.db"))

    @staticmethod
    def abrir_carpeta_proyectos():
        """Abre la carpeta de proyectos en el explorador del sistema."""
        from backend.db import Rutas
        import subprocess, sys
        carpeta = Rutas.proyectos()
        carpeta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(carpeta)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(carpeta)])
        else:
            subprocess.Popen(["xdg-open", str(carpeta)])

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def _resolver_matriz(self, clave: str) -> tuple[int | None, str]:
        """Resuelve la clave a un (matriz_id, descripcion).

        Primero busca en el árbol del presupuesto (matriz_id positivo).
        Si no, busca en insumos compuestos (matriz_id negativo).
        Devuelve (None, '') si no existe.
        """
        from backend.repos import NodoRepo, InsumoRepo, ApuMatricesRepo

        nodo = NodoRepo(self._conn).buscar_por_clave(clave, proyecto_id=self._pid)
        if nodo:
            matriz_id   = nodo["id"]
            descripcion = nodo.get("descripcion") or nodo.get("descripcion_corta") or clave
            # Verificar que tiene APU
            if ApuMatricesRepo(self._conn).por_matriz(matriz_id):
                return matriz_id, descripcion

        insumo = InsumoRepo(self._conn).buscar_por_clave(clave, proyecto_id=self._pid)
        if insumo and insumo.get("es_compuesto"):
            matriz_id   = -insumo["id"]
            descripcion = insumo.get("descripcion") or insumo.get("descripcion_corta") or clave
            return matriz_id, descripcion

        return None, ""
