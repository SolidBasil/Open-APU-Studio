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
    apu     = api.apu(clave="0202002")  # concepto del árbol
    apu2    = api.apu(insumo_id=42)      # insumo compuesto
    filas,t = api.explotar(concepto_ids=[5,23], nivel="basico", tipos_ids=[1,2,4])
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


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
        from backend.database.core import build_budget_tree
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
        from backend.database.repos import ConceptoRepo
        return ConceptoRepo(self._conn).todos(self._pid)

    # =========================================================================
    # APU
    # =========================================================================

    def apu(self, clave: str | None = None, insumo_id: int | None = None) -> dict | None:
        """Devuelve el APU de un concepto del árbol (por clave) o de un insumo
        compuesto (por insumo_id). Pasa exactamente uno de los dos.

        Retorna:
            {
                "matriz_id":    int,
                "descripcion":  str,
                "detalle":      list[dict],   # filas del APU, listas para la tabla
                "totales":      dict | None,  # subtotales por tipo
            }
            o None si no hay APU asociado.

        Cada fila de detalle incluye:
            tipo_emoji, tipo_nombre, tipo_id, insumo_id, descripcion,
            insumo_unidad, cantidad, precio, importe, es_compuesto, tiene_sub_apu
        """
        from backend.database.repos  import NodoRepo, InsumoRepo, ApuMatricesRepo
        from backend.database.core   import get_apu

        # 1. Resolver matriz_id
        matriz_id, descripcion = self._resolver_matriz(clave=clave, insumo_id=insumo_id)
        if matriz_id is None:
            return None

        # 2. Obtener detalle
        data = get_apu(self._db_path, matriz_id)

        # 3. Fallback: APU negativo vacío → buscar APU positivo del árbol (solo aplica a conceptos)
        if not data.get("detalle") and matriz_id < 0 and clave:
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
        ids_con_apu = self.insumo_ids_con_apu()
        _EMOJI = {1: "🧱", 2: "👷", 4: "🔧", 8: "🚜", 16: "⚙️", 32: "📄"}

        detalle = []
        for r in data["detalle"]:
            tid   = r.get("tipo_id", 0)
            desc  = r.get("insumo_descripcion") or r.get("insumo_desc_corta") or ""
            tiene_sub = r.get("insumo_id") in ids_con_apu
            detalle.append({
                "tipo_emoji":   _EMOJI.get(tid, ""),
                "tipo_nombre":  r.get("tipo_nombre", ""),
                "tipo_id":      tid,
                "insumo_id":    r.get("insumo_id"),
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

    def insumo_es_compuesto(self, insumo_id: int) -> bool:
        """True si el insumo con ese id es compuesto (tiene APU propio)."""
        row = self._conn.execute("""
            SELECT es_compuesto FROM insumos
            WHERE id = ? AND proyecto_id = ? LIMIT 1
        """, (insumo_id, self._pid)).fetchone()
        return bool(row and row[0])

    def insumo_ids_con_apu(self) -> set[int]:
        """Conjunto de ids de insumos compuestos (tienen APU propio)."""
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id FROM insumos WHERE es_compuesto = 1 AND proyecto_id = ?",
            (self._pid,)
        )
        return {r[0] for r in cur.fetchall()}

    def claves_con_apu(self) -> set[str]:
        """Conjunto de claves (estructura_presupuesto) de conceptos con APU en el árbol.
        Nota: esto solo cubre conceptos del árbol, no insumos compuestos —
        para eso usar insumo_ids_con_apu().
        """
        cur = self._conn.cursor()
        cur.execute("""
            SELECT DISTINCT ep.clave FROM estructura_presupuesto ep
            JOIN apu_matrices am ON am.matriz_id = ep.id
            WHERE ep.proyecto_id = ? AND ep.clave IS NOT NULL
        """, (self._pid,))
        return {r[0] for r in cur.fetchall()}

    # =========================================================================
    # INSUMOS
    # =========================================================================

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        """Catálogo de insumos, opcionalmente filtrado por tipo (ej. 'material', 'mano_obra').
        Cada dict incluye todos los campos de InsumoRepo más familia y subfamilia.
        """
        from backend.database.repos import InsumoRepo
        repo = InsumoRepo(self._conn)
        return repo.por_tipo(self._pid, tipo_clave) if tipo_clave else repo.todos(self._pid)

    def insumos_con_matrices(self, tipo_clave: str | None = None) -> list[dict]:
        """Como insumos() pero filtra solo los que aparecen en al menos un APU."""
        ids = self.insumo_ids_con_apu()
        return [i for i in self.insumos(tipo_clave) if i.get("id") in ids]

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        """Devuelve las matrices (conceptos o compuestos) donde aparece un insumo.

        Cada fila:
            tipo_origen ('concepto' | 'compuesto'), matriz_clave, matriz_descripcion,
            matriz_wbs, cantidad, precio, importe
        """
        from backend.database.repos import InsumoRepo
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
        from backend.database.repos  import ExplosionRepo
        from frontend.ventana.widgets.ajustes import get_decimales_explosion

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
        from frontend.ventana.widgets.explosion import TIPOS_INSUMO, TIPO_ICONO
        tipo_nombre_map = {t[0]: t[1] for t in TIPOS_INSUMO}
        return ", ".join(
            f"{TIPO_ICONO.get(tid, '')} {tipo_nombre_map.get(tid, str(tid))}".strip()
            for tid in tipos_ids
        )

    # =========================================================================
    # MUTACIÓN DE INSUMOS
    # =========================================================================

    def insumo_actualizar_descripcion(
        self, insumo_id: int, descripcion: str, usuario_id: int = 1
    ) -> None:
        """Actualiza la descripción de un insumo y regenera su hash.

        Lanza ValueError si ya existe otro insumo con la misma descripción
        normalizada en el proyecto. El mensaje incluye el id y descripción
        del duplicado para que la UI lo muestre al usuario.
        """
        from backend.database.repos import InsumoRepo
        InsumoRepo(self._conn).actualizar_descripcion(
            insumo_id, descripcion, self._pid, usuario_id
        )

    def insumo_actualizar_precio(
        self, insumo_id: int, precio: float, usuario_id: int = 1
    ) -> None:
        """Actualiza el costo_mn y costo_final de un insumo."""
        from backend.database.repos import InsumoRepo
        InsumoRepo(self._conn).actualizar_precio(insumo_id, precio, usuario_id)

    def insumo_insertar(
        self,
        tipo_id: int,
        descripcion: str,
        descripcion_corta: str | None = None,
        unidad: str | None = None,
        costo: float = 0.0,
        es_compuesto: int = 0,
        usuario_id: int = 1,
    ) -> int:
        """Crea un insumo nuevo desde la app (no importado).

        Genera el hash automáticamente desde la descripción — es la llave
        funcional. clave_opus queda NULL (solo se llena al importar de OPUS).
        Lanza ValueError si ya existe un insumo con la misma descripción.
        Devuelve el id del insumo insertado.
        """
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._conn).insertar(
            proyecto_id       = self._pid,
            tipo_id           = tipo_id,
            descripcion       = descripcion,
            descripcion_corta = descripcion_corta,
            unidad            = unidad,
            costo             = costo,
            es_compuesto      = es_compuesto,
            usuario_id        = usuario_id,
        )

    def insumo_por_id(self, insumo_id: int) -> dict | None:
        """Devuelve el dict completo de un insumo por su id, o None si no existe."""
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._conn).buscar(insumo_id)

    # =========================================================================
    # GESTIÓN DE PROYECTOS
    # =========================================================================

    @staticmethod
    def proyectos_disponibles() -> list[str]:
        """Lista de nombres de proyectos (.db) disponibles en la carpeta de proyectos."""
        from backend.database.db import Rutas
        carpeta = Rutas.proyectos()
        if not carpeta.exists():
            return []
        return sorted(p.stem for p in carpeta.glob("*.db"))

    @staticmethod
    def abrir_carpeta_proyectos():
        """Abre la carpeta de proyectos en el explorador del sistema."""
        from backend.database.db import Rutas
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

    def _resolver_matriz(
        self, clave: str | None = None, insumo_id: int | None = None
    ) -> tuple[int | None, str]:
        """Resuelve a un (matriz_id, descripcion).

        Pasa exactamente uno de los dos:
            clave      — busca un concepto en el árbol del presupuesto (matriz_id positivo)
            insumo_id  — busca un insumo compuesto directamente por id (matriz_id negativo)

        Devuelve (None, '') si no existe o no tiene APU.
        """
        from backend.database.repos import NodoRepo, InsumoRepo, ApuMatricesRepo

        if clave is not None:
            nodo = NodoRepo(self._conn).buscar_por_clave(clave, proyecto_id=self._pid)
            if nodo:
                matriz_id   = nodo["id"]
                descripcion = nodo.get("descripcion") or nodo.get("descripcion_corta") or clave
                if ApuMatricesRepo(self._conn).por_matriz(matriz_id):
                    return matriz_id, descripcion
            return None, ""

        if insumo_id is not None:
            insumo = InsumoRepo(self._conn).buscar(insumo_id)
            if insumo and insumo.get("es_compuesto"):
                matriz_id   = -insumo["id"]
                descripcion = insumo.get("descripcion") or insumo.get("descripcion_corta") or ""
                return matriz_id, descripcion
            return None, ""

        return None, ""
