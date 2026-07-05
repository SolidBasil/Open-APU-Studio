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
    api = Api(self._db.conn, self._db.db_path, proyecto_id=1,
              data_service=self._data_service)
    arbol   = api.presupuesto_arbol()
    apu     = api.apu(nodo_id=17)         # concepto del árbol (id en estructura_presupuesto)
    apu2    = api.apu(insumo_id=42)      # insumo compuesto
    filas,t = api.explotar(concepto_ids=[5,23], nivel="basico", tipos_ids=[1,2,4])
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.database.services.data_service import DataService

# ponytail: constante global — evita recrear el dict en cada llamada a apu()
_EMOJI = {1: "🧱", 2: "👷", 4: "🔧", 8: "🚜", 16: "⚙️", 32: "📄"}


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class Api:
    """Fachada de servicios para el frontend.

    Args:
        conn       — conexión SQLite activa del proyecto abierto
        db_path    — ruta al archivo .db (referencial; ya no la usa ningún
            método de esta clase desde Fase 4, se conserva por si algún
            flujo futuro la necesita — ver docs/ARQUITECTURA_SERVICIOS.md)
        proyecto_id — siempre 1 en la versión actual (monoproyecto por .db)
        data_service — DataService para escrituras. Obligatorio: todo write
            de esta fachada pasa por él (Fase 2 completa, ver
            docs/ARQUITECTURA_SERVICIOS.md).
    """

    def __init__(self, conn: sqlite3.Connection, db_path: str | Path,
                 proyecto_id: int = 1, data_service: DataService | None = None):
        if data_service is None:
            raise ValueError(
                "Api requiere un DataService. Ver _wire_servicios() en "
                "frontend/ventana/handlers/gestion_proyectos.py."
            )
        self._conn   = conn
        self._db_path = str(db_path)
        self._pid    = proyecto_id
        self._ds     = data_service

    def proyecto_actual_id(self) -> int:
        """Devuelve el ID del proyecto activo."""
        return self._pid

    # =========================================================================
    # PRESUPUESTO
    # =========================================================================

    def presupuesto_arbol(self) -> list[dict]:
        """Devuelve el árbol completo del presupuesto listo para poblar TablaArbol."""
        from backend.database.repos import NodoRepo
        return NodoRepo(self._conn).arbol(self._pid)

    def nodo_total(self, nodo_id: int) -> float:
        """Devuelve el total de un nodo del presupuesto."""
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        return (nodo.get("total") or 0) if nodo else 0

    def concepto_actualizar_cantidad(self, concepto_id: int, cantidad: float) -> None:
        """Actualiza la cantidad de un concepto y recalcula totales."""
        from backend.database.repos import NodoRepo
        from backend.database.event_bus import ProyectoRecalculado
        if cantidad < 0:
            raise ValueError("La cantidad no puede ser negativa")
        # El campo 'cantidad' se escribe y se notifica vía DataService.
        # Solo falta la cascada de totales hacia la raíz: es cálculo
        # derivado (no dato de usuario), no pasa por SchemaRegistry y
        # no dispara su propio evento semántico. ProyectoRecalculado
        # avisa a los widgets que los totales corriente arriba cambiaron
        # (Fase 3: reemplaza a _refrescar_tab_activa()).
        self._ds.actualizar("estructura_presupuesto", concepto_id, cantidad=cantidad)
        NodoRepo(self._conn).recalcular_desde(concepto_id)
        self._conn.commit()
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def nodo_descripcion_actual(self, nodo_id: int) -> str:
        """Devuelve la descripción visible actual de un nodo del árbol
        (propia si es capítulo, o la de su insumo ligado si es concepto).

        Uso: revertir una celda tras un ValueError de validación (ej.
        descripción duplicada) sin recargar todo el árbol.
        """
        from backend.database.repos import NodoRepo, InsumoRepo
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        if not nodo:
            return ""
        if nodo.get("insumo_id"):
            insumo = InsumoRepo(self._conn).buscar(nodo["insumo_id"])
            return (insumo or {}).get("descripcion", "") or ""
        return nodo.get("descripcion", "") or ""

    def concepto_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        """Actualiza la descripción del insumo ligado a un concepto.

        Reutiliza insumo_actualizar_descripcion() para no duplicar la
        lógica de regeneración de hash y verificación de colisión.
        """
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        if nodo and nodo.get("insumo_id"):
            self.insumo_actualizar_descripcion(nodo["insumo_id"], descripcion)

    def concepto_actualizar_unidad(self, nodo_id: int, unidad: str) -> None:
        """Actualiza la unidad de un concepto (escribe en insumos)."""
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        if nodo and nodo.get("insumo_id"):
            self._ds.actualizar("insumos", nodo["insumo_id"], unidad=unidad)

    def concepto_actualizar_pu(self, nodo_id: int, precio: float) -> None:
        """Actualiza P.U. solo para insumos básicos (sin APU propio)."""
        from backend.database.repos import NodoRepo, InsumoRepo, RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        if precio < 0:
            raise ValueError("El precio no puede ser negativo")
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        if not nodo or not nodo.get("insumo_id"):
            return
        insumo = InsumoRepo(self._conn).buscar(nodo["insumo_id"])
        if insumo and not insumo.get("es_compuesto"):
            self._ds.actualizar("insumos", nodo["insumo_id"],
                                costo_mn=precio, costo_directo=precio, costo_final=precio)
            # Recalc total de este concepto y hacia arriba
            NodoRepo(self._conn).actualizar_cantidad(
                nodo_id, nodo.get("cantidad", 0))
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
            self._ds.emitir(ProyectoRecalculado(self._pid))

    def agrupador_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        """Actualiza la descripción de un agrupador (capítulo)."""
        self._ds.actualizar("estructura_presupuesto", nodo_id, descripcion=descripcion)

    def todos_concepto_ids(self) -> list[int]:
        """Devuelve los ids de todos los conceptos activos del proyecto."""
        from backend.database.repos import NodoRepo
        return NodoRepo(self._conn).ids_por_tipo(self._pid, tipo="concepto")

    def conceptos_planos(self) -> list[dict]:
        """Lista plana de todos los conceptos con clave, descripción, unidad, cantidad, total."""
        from backend.database.repos import NodoRepo
        return NodoRepo(self._conn).todos(self._pid, tipo="concepto")

    # =========================================================================
    # APU
    # =========================================================================

    def apu(self, nodo_id: int | None = None, insumo_id: int | None = None) -> dict | None:
        """Devuelve el APU de un concepto del árbol (por nodo_id) o de un insumo
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
            id (pk de apu_matrices, usado como comp_id para editar
            operador/valor), tipo_emoji, tipo_nombre, tipo_id, insumo_id,
            descripcion, insumo_unidad, cantidad (desde valor/operador),
            precio, importe, es_compuesto, tiene_sub_apu
        """
        from backend.database.repos  import NodoRepo, InsumoRepo, ApuMatricesRepo

        # 1. Resolver matriz_id
        matriz_id, descripcion = self._resolver_matriz(nodo_id=nodo_id, insumo_id=insumo_id)
        if matriz_id is None:
            return None

        # 2. Obtener detalle
        data = ApuMatricesRepo(self._conn).con_detalle(matriz_id)

        # 3. Enriquecer filas
        ids_con_apu = self.insumo_ids_con_apu()

        detalle = []
        for r in data["detalle"]:
            tid   = r.get("tipo_id", 0)
            desc  = r.get("insumo_descripcion") or r.get("insumo_desc_corta") or ""
            tiene_sub = r.get("insumo_id") in ids_con_apu
            v = r.get("valor", 0) or 0
            op = r.get("operador", "*")
            detalle.append({
                "id":           r.get("id"),
                "tipo_emoji":   _EMOJI.get(tid, ""),
                "tipo_nombre":  r.get("tipo_nombre", ""),
                "tipo_id":      tid,
                "insumo_id":    r.get("insumo_id"),
                "descripcion":  f"▶ {desc}" if tiene_sub else desc,
                "insumo_unidad": r.get("insumo_unidad", ""),
                "valor":        v,
                "operador":     op,
                "cantidad":     v if op == "*" else (1.0 / v if v else 0.0),
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

    def apu_actualizar_operador(self, comp_id: int, operador: str) -> None:
        """Actualiza el operador (* o /) de un componente APU y recalcula en cascada."""
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        if operador not in ('*', '/'):
            raise ValueError("Operador debe ser '*' o '/'")
        self._ds.actualizar("apu_matrices", comp_id, operador=operador)
        RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def apu_actualizar_valor(self, comp_id: int, valor: float) -> None:
        """Actualiza la cantidad (columna Valor) de un componente APU y recalcula en cascada."""
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        if valor is None or valor < 0:
            raise ValueError("La cantidad no puede ser negativa")
        self._ds.actualizar("apu_matrices", comp_id, valor=valor)
        RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def apu_actualizar_precio_componente(self, insumo_id: int, precio: float) -> None:
        """Actualiza el Precio de un componente editado desde dentro de un APU.

        IMPORTANTE: esto NO escribe en apu_matrices.precio directamente.
        RecalculoRepo._sincronizar_precios_componentes() sobreescribe ese
        campo con insumos.costo_final en cada recálculo, así que un valor
        puesto ahí se perdería de inmediato. El precio real vive en el
        insumo del catálogo — igual que editarlo desde la pestaña de
        Insumos — así que reutiliza insumo_actualizar_precio() para que el
        cambio se propague a todo lo que use ese insumo, no solo a esta fila.
        """
        self.insumo_actualizar_precio(insumo_id, precio)

    def insumo_ids_con_apu(self) -> set[int]:
        """Conjunto de ids de insumos compuestos (tienen APU propio)."""
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._conn).ids_con_apu(self._pid)

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

    def recalcular_proyecto(self) -> dict:
        """Recalcula en cascada todo el presupuesto del proyecto abierto:
        costo de insumos compuestos → totales de conceptos → totales de
        capítulos. Útil tras editar precios o cantidades a mano.
        """
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        resultado = RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))
        return resultado

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

        Verifica antes de escribir que el hash nuevo no colisione con otro
        insumo del mismo proyecto. Si hay colisión, lanza ValueError con el
        id y descripción del insumo existente para que la UI informe al
        usuario. El hash es una llave de deduplicación interna, no un dato
        de dominio con reglas de SchemaRegistry, así que se calcula aquí y
        se envía como campo extra a DataService.actualizar().
        """
        from backend.database.repos import InsumoRepo
        from backend.database.repos.base import generar_hash
        descripcion = descripcion.strip()
        if not descripcion:
            raise ValueError("La descripción no puede estar vacía")
        nuevo_hash = generar_hash(descripcion)
        existente = InsumoRepo(self._conn).buscar_por_hash(nuevo_hash, self._pid)
        if existente and existente["id"] != insumo_id:
            raise ValueError(
                f"Ya existe un insumo con esa descripción: "
                f"[{existente['id']}] {existente['descripcion']}"
            )
        self._ds.actualizar("insumos", insumo_id, descripcion=descripcion, hash=nuevo_hash)

    def insumo_actualizar_precio(
        self, insumo_id: int, precio: float, usuario_id: int = 1
    ) -> None:
        """Actualiza el costo_mn y costo_final de un insumo y recalcula en cascada."""
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        if precio < 0:
            raise ValueError("El precio no puede ser negativo")
        self._ds.actualizar("insumos", insumo_id,
                            costo_mn=precio, costo_directo=precio, costo_final=precio)
        RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def insumo_actualizar_campo(
        self, insumo_id: int, campo: str, valor, usuario_id: int = 1
    ) -> None:
        """Actualiza un campo simple de un insumo del catálogo."""
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        self._ds.actualizar("insumos", insumo_id, **{campo: valor})
        if campo == "costo_final":
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
            self._ds.emitir(ProyectoRecalculado(self._pid))

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

        Genera el hash de deduplicación aquí, igual que
        insumo_actualizar_descripcion(): el hash es una llave interna, no
        un dato de dominio con reglas de SchemaRegistry, así que se calcula
        en la fachada y se envía como campo extra a DataService.insertar().
        Verifica colisión con otro insumo del proyecto antes de crear.
        """
        from backend.database.repos import InsumoRepo
        from backend.database.repos.base import generar_hash
        nuevo_hash = generar_hash(descripcion) if descripcion else None
        if nuevo_hash:
            existente = InsumoRepo(self._conn).buscar_por_hash(nuevo_hash, self._pid)
            if existente:
                raise ValueError(
                    f"Ya existe un insumo con esa descripción: "
                    f"[{existente['id']}] {existente['descripcion']}"
                )
        return self._ds.insertar(
            "insumos",
            proyecto_id=self._pid,
            tipo_id=tipo_id,
            descripcion=descripcion,
            descripcion_corta=descripcion_corta,
            unidad=unidad,
            costo_mn=costo,
            costo_directo=costo,
            costo_final=costo,
            es_compuesto=es_compuesto,
            hash=nuevo_hash,
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

    # =========================================================================
    # FACTORES DE SOBRECOSTO
    # =========================================================================

    def factores_sobrecosto_obtener(self) -> dict:
        """Devuelve los factores de sobrecosto del proyecto o dict vacío."""
        from backend.database.repos import FactoresSobrecostoRepo
        return FactoresSobrecostoRepo(self._conn).obtener(self._pid) or {}

    def factores_sobrecosto_calcular(
        self, pct_indirectos_campo=0, pct_indirectos_oficina=0,
        pct_financiamiento=0, pct_utilidad=0, pct_cargos_adicionales=0,
    ) -> float:
        """Calcula el factor_total sin persistir."""
        from backend.database.repos import FactoresSobrecostoRepo
        return FactoresSobrecostoRepo._calcular_factor(
            pct_indirectos_campo, pct_indirectos_oficina,
            pct_financiamiento, pct_utilidad, pct_cargos_adicionales,
        )

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        """Guarda los factores, calcula factor_total y recalcula en cascada.
        Devuelve el factor_total calculado.

        No pasa por DataService.actualizar() porque factor_total es un
        campo calculado por el propio repo antes de persistir (no encaja
        en el genérico columna=valor). Se usa DataService solo para emitir
        el evento semántico, vía el método `emitir()` documentado para
        este caso en ARQUITECTURA_SERVICIOS.md.
        """
        from backend.database.repos import FactoresSobrecostoRepo, RecalculoRepo
        from backend.database.event_bus import FactoresSobrecostoActualizados, ProyectoRecalculado
        factor = FactoresSobrecostoRepo(self._conn).guardar(self._pid, **valores)
        self._ds.emitir(FactoresSobrecostoActualizados(self._pid, valores))
        RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))
        return factor

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def _resolver_matriz(
        self, nodo_id: int | None = None, insumo_id: int | None = None
    ) -> tuple[int | None, str]:
        """Resuelve a un (matriz_id, descripcion).

        Pasa exactamente uno de los dos:
            nodo_id    — id del concepto en estructura_presupuesto (matriz_id positivo)
            insumo_id  — busca un insumo compuesto directamente por id (matriz_id negativo)

        Devuelve (None, '') si no existe o no tiene APU.
        """
        from backend.database.repos import NodoRepo, InsumoRepo, ApuMatricesRepo

        if nodo_id is not None:
            nodo = NodoRepo(self._conn).buscar(nodo_id)
            if not nodo or nodo.get("proyecto_id") != self._pid:
                return None, ""
            insumo_id_nodo = nodo.get("insumo_id")
            if insumo_id_nodo:
                insumo = InsumoRepo(self._conn).buscar(insumo_id_nodo)
                if insumo and insumo.get("es_compuesto"):
                    neg_id = -insumo["id"]
                    if ApuMatricesRepo(self._conn).por_matriz(neg_id):
                        return neg_id, nodo.get("descripcion") or ""
            matriz_id   = nodo["id"]
            descripcion = nodo.get("descripcion") or ""
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

    def unificar_matrices_apu(self) -> int:
        """Una sola matriz por APU (Fase de migración).

        La importación OPUS creaba DOS matrices para el mismo desglose:
        una para el concepto (matriz_id positivo) y otra para el insumo
        compuesto (matriz_id negativo). Esto causaba desfase de costos.

        Esta migra: para cada concepto con insumo compuesto que tenga
        matriz propia, redirige los componentes a la matriz del insumo
        compuesto y borra la matriz duplicada. Devuelve el número de
        conceptos migrados.
        """
        cur = self._conn.cursor()
        rows = cur.execute("""
            SELECT e.id AS cid, e.insumo_id
            FROM estructura_presupuesto e
            JOIN insumos i ON i.id = e.insumo_id
            WHERE e.proyecto_id = ? AND e.tipo = 'concepto' AND e.activo = 1
              AND i.es_compuesto = 1
        """, (self._pid,)).fetchall()

        migrados = 0
        for row in rows:
            cid  = row["cid"]
            iid  = row["insumo_id"]
            neg  = -iid

            n_conc = cur.execute(
                "SELECT COUNT(*) AS c FROM apu_matrices WHERE matriz_id = ?",
                (cid,),
            ).fetchone()["c"]
            if n_conc == 0:
                continue

            n_comp = cur.execute(
                "SELECT COUNT(*) AS c FROM apu_matrices WHERE matriz_id = ?",
                (neg,),
            ).fetchone()["c"]

            if n_comp == 0:
                cur.execute(
                    "UPDATE apu_matrices SET matriz_id = ? WHERE matriz_id = ?",
                    (neg, cid),
                )
            else:
                cur.execute("DELETE FROM apu_matrices WHERE matriz_id = ?", (cid,))
            migrados += 1

        if migrados:
            self._conn.commit()
        return migrados