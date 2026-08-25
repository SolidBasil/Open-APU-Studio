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
    from decimal import Decimal
    from backend.database.services.data_service import DataService

# ponytail: constante global — evita recrear el dict en cada llamada a apu()
from frontend.ventana.tipos_insumo import ICONO_SVG as _TIPO_ICONO_SVG


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
                 proyecto_id: int = 1, data_service: DataService | None = None,
                 servidor_url: str | None = None,
                 ensure_server=None):
        if data_service is None:
            raise ValueError(
                "Api requiere un DataService. Ver _wire_servicios() en "
                "frontend/ventana/handlers/gestion_proyectos.py."
            )
        self._conn   = conn
        self._db_path = str(db_path)
        self._pid    = proyecto_id
        self._ds     = data_service
        # ensure_server: callable que arranca el servidor bajo demanda y
        # devuelve la URL. Se usa en lazy start — el servidor solo arranca
        # cuando un método HTTP es invocado por primera vez.
        self._ensure_server = ensure_server
        self._use_http = servidor_url is not None
        self._servidor_url = servidor_url
        self._nombre_proyecto = Path(db_path).stem
        self._cliente = None
        if servidor_url:
            from frontend.ventana.api_cliente import ApiCliente
            self._cliente = ApiCliente(servidor_url, self._nombre_proyecto)

        # Backends (migración en progreso, ver api_backends.py): por ahora
        # solo la sección FACTORES DE SOBRECOSTO delega aquí; el resto de
        # Api sigue con el patrón "if self._use_http" método por método.
        from frontend.ventana.api_backends import _BackendLocal, _BackendHTTP
        self._backend_local = _BackendLocal(self)
        self._backend_http  = _BackendHTTP(self)

    @property
    def _backend(self):
        """Backend activo. Es una property (no un valor fijo) porque
        _use_http puede promoverse a True a medio uso — ver _http()."""
        return self._backend_http if self._use_http else self._backend_local

    def proyecto_actual_id(self) -> int:
        """Devuelve el ID del proyecto activo."""
        return self._pid

    def _http(self):
        """Devuelve el cliente HTTP, arrancando el servidor bajo demanda."""
        if self._cliente is not None:
            return self._cliente
        url = self._ensure_server() if self._ensure_server else None
        if not url:
            raise RuntimeError("Servidor no disponible")
        from frontend.ventana.api_cliente import ApiCliente
        self._cliente = ApiCliente(url, self._nombre_proyecto)
        self._use_http = True
        return self._cliente

    # =========================================================================
    # PRESUPUESTO
    # =========================================================================

    def presupuesto_arbol(self, extra: bool = False) -> list[dict]:
        """Devuelve el árbol del presupuesto (es_extra=0) o extra (es_extra=1)."""
        if self._use_http:
            return self._http().arbol(extra=extra)
        from backend.database.repos import NodoRepo
        return NodoRepo(self._conn).arbol(self._pid, extra=extra)

    def nodo_total(self, nodo_id: int) -> float:
        """Devuelve el total de un nodo del presupuesto."""
        if self._use_http:
            nodo = self._http().buscar("estructura_presupuesto", nodo_id)
            return (nodo.get("total") or 0) if nodo else 0
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        return (nodo.get("total") or 0) if nodo else 0

    def concepto_actualizar_cantidad(self, concepto_id: int, cantidad: float,
                                      formula: str | None = None) -> None:
        """Actualiza la cantidad y opcionalmente la fórmula de un concepto.

        Si se proporciona `formula`, se evalúa antes de guardar (valida
        que dé un resultado numérico). El resultado se guarda como
        `cantidad` y el texto de la fórmula se persiste en la columna
        `formula`. Si la evaluación falla, no se guarda nada (ValueError).
        """
        from backend.database.event_bus import ProyectoRecalculado
        if cantidad < 0:
            raise ValueError("La cantidad no puede ser negativa")
        if formula is not None and formula.strip():
            from backend.formulas import evaluar_formula, ErrorFormula
            try:
                resuelta = evaluar_formula(formula.strip(), self.variables_resueltas())
                cantidad = float(resuelta)
            except ErrorFormula as e:
                raise ValueError(str(e))
        else:
            formula = None
        if self._use_http:
            campos = {"cantidad": cantidad}
            if formula is not None:
                campos["formula"] = formula
            self._http().actualizar("estructura_presupuesto", concepto_id, **campos)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import NodoRepo
        with self._ds.transaccion():
            campos = {"cantidad": cantidad}
            if formula is not None:
                campos["formula"] = formula
            self._ds.actualizar("estructura_presupuesto", concepto_id, **campos)
            NodoRepo(self._conn).recalcular_desde(concepto_id)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def concepto_reasignar_insumo(self, concepto_id: int, nuevo_insumo_id: int) -> None:
        """Reasigna un concepto a otro insumo del catálogo.

        Cambia el insumo_id del concepto, que ahora apuntará al nuevo
        insumo (descripción, unidad, precio se resuelven desde allí).
        Dispara recálculo completo del proyecto y reconstrucción del árbol.
        """
        from backend.database.event_bus import ProyectoRecalculado
        if self._use_http:
            self._http().actualizar("estructura_presupuesto", concepto_id,
                                      insumo_id=nuevo_insumo_id)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.actualizar("estructura_presupuesto", concepto_id,
                                 insumo_id=nuevo_insumo_id)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def nodo_descripcion_actual(self, nodo_id: int) -> str:
        """Devuelve la descripción visible actual de un nodo del árbol
        (propia si es capítulo, o la de su insumo ligado si es concepto).

        Uso: revertir una celda tras un ValueError de validación (ej.
        descripción duplicada) sin recargar todo el árbol.
        """
        if self._use_http:
            nodo = self._http().buscar("estructura_presupuesto", nodo_id)
            if not nodo:
                return ""
            if nodo.get("insumo_id"):
                insumo = self._http().buscar("insumos", nodo["insumo_id"])
                return (insumo or {}).get("descripcion", "") or ""
            return nodo.get("descripcion", "") or ""
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
        if self._use_http:
            nodo = self._http().buscar("estructura_presupuesto", nodo_id)
        else:
            from backend.database.repos import NodoRepo
            nodo = NodoRepo(self._conn).buscar(nodo_id)
        if nodo and nodo.get("insumo_id"):
            self.insumo_actualizar_descripcion(nodo["insumo_id"], descripcion)

    def concepto_actualizar_unidad(self, nodo_id: int, unidad: str) -> None:
        """Actualiza la unidad de un concepto (escribe en insumos)."""
        if self._use_http:
            nodo = self._http().buscar("estructura_presupuesto", nodo_id)
            if nodo and nodo.get("insumo_id"):
                self._http().actualizar("insumos", nodo["insumo_id"], unidad=unidad)
                from backend.database.event_bus import InsumoActualizado
                registro = self._http().buscar("insumos", nodo["insumo_id"]) or {}
                self._ds.emitir(InsumoActualizado(nodo["insumo_id"], {"unidad": unidad}, registro))
            return
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._conn).buscar(nodo_id)
        if nodo and nodo.get("insumo_id"):
            self._ds.actualizar("insumos", nodo["insumo_id"], unidad=unidad)

    def agrupador_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        """Actualiza la descripción de un agrupador (capítulo)."""
        if self._use_http:
            self._http().actualizar("estructura_presupuesto", nodo_id, descripcion=descripcion)
            return
        self._ds.actualizar("estructura_presupuesto", nodo_id, descripcion=descripcion)

    def eliminar_nodo(self, nodo_id: int) -> None:
        """Elimina (soft-delete) un nodo del presupuesto y recalcula en cascada."""
        from backend.database.event_bus import ProyectoRecalculado
        if self._use_http:
            self._http().eliminar("estructura_presupuesto", nodo_id)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.eliminar("estructura_presupuesto", nodo_id)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def agregar_nodo(
        self, tipo: str, padre_id: int | None = None,
        descripcion: str = "", insumo_id: int | None = None,
        cantidad: float | None = None, orden: float | None = None,
        antes_de: int | None = None, es_extra: bool = False,
    ) -> int:
        """Inserta un nodo nuevo en el presupuesto (o extra) y recalcula.

        Args:
            tipo: 'concepto' o 'capitulo'
            padre_id: id del padre (None = raíz)
            descripcion: texto (capítulo) o vacío (concepto)
            insumo_id: vínculo a catálogo (solo conceptos)
            cantidad: cantidad inicial (solo conceptos)
            orden: posición explícita (None = al final)
            antes_de: id del nodo hermano justo después del nuevo
            es_extra: True para nodos fuera de presupuesto

        Returns:
            id del nodo insertado
        """
        from backend.database.event_bus import ProyectoRecalculado

        if self._use_http:
            if orden is None and antes_de is not None:
                ref = self._http().buscar("estructura_presupuesto", antes_de)
                if ref:
                    orden = ref["orden"] - 0.5
            if orden is None:
                orden = self._http().proximo_orden(padre_id)
            nuevo_id = self._http().insertar("estructura_presupuesto", **{
                "proyecto_id": self._pid, "padre_id": padre_id, "wbs": "",
                "nivel": 0, "tipo": tipo, "descripcion": descripcion or "",
                "orden": orden, "insumo_id": insumo_id, "cantidad": cantidad,
                "total": 0.0, "es_extra": 1 if es_extra else 0,
                "estado": 0, "activo": 1, "creado_por": 1,
            })
            self._http().reindexar()
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return nuevo_id

        from backend.database.repos import NodoRepo, RecalculoRepo
        repo = NodoRepo(self._conn)
        if orden is None and antes_de is not None:
            ref = repo.buscar(antes_de)
            if ref:
                orden = ref["orden"] - 0.5
        if orden is None:
            orden = repo.proximo_orden(self._pid, padre_id)
        with self._ds.transaccion():
            nuevo_id = repo.insert({
                "proyecto_id": self._pid,
                "padre_id":    padre_id,
                "wbs":         "",
                "nivel":       0,
                "tipo":        tipo,
                "descripcion": descripcion or "",
                "orden":       orden,
                "insumo_id":   insumo_id,
                "cantidad":    cantidad,
                "total":       0.0,
                "es_extra":    1 if es_extra else 0,
                "estado":      0,
                "activo":      1,
                "creado_por":  1,
            })
            repo.reindexar(self._pid)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))
        return nuevo_id

    def todos_concepto_ids(self) -> list[int]:
        """Devuelve los ids de todos los conceptos activos del proyecto."""
        if self._use_http:
            return self._http().todos_concepto_ids()
        from backend.database.repos import NodoRepo
        return NodoRepo(self._conn).ids_por_tipo(self._pid, tipo="concepto")

    def conceptos_planos(self) -> list[dict]:
        """Lista plana de todos los conceptos con clave, descripción, unidad, cantidad, total."""
        if self._use_http:
            return self._http().conceptos_planos()
        from backend.database.repos import NodoRepo
        return NodoRepo(self._conn).todos(self._pid, tipo="concepto")

    # =========================================================================
    # VARIABLES DE FÓRMULA
    # =========================================================================

    def variables_listar(self) -> list[dict]:
        """Todas las variables del proyecto."""
        return self._backend.variables_listar()

    def variables_crear(self, nombre: str, expresion: str = "",
                        descripcion: str = "") -> int:
        """Crea una variable. Valida nombre duplicado."""
        return self._backend.variables_crear(nombre, expresion, descripcion)

    def variables_actualizar(self, variable_id: int, **campos) -> None:
        """Actualiza expresión, descripción o nombre de una variable.
        Rechaza cambios que creen ciclos en el conjunto completo.

        Si cambia 'nombre', valida formato y duplicados igual que
        variables_crear() — antes esto no se validaba aquí: si el nuevo
        nombre coincidía con el de otra variable existente, el diccionario
        interno de resolución de ciclos las mezclaba (una sobrescribe a la
        otra en el dict) en vez de rechazar el cambio con un error claro.
        Encontrado al construir la UI de variables (N3 del seguimiento) —
        antes era inalcanzable porque nada llamaba a esta función con un
        'nombre' nuevo.
        """
        self._backend.variables_actualizar(variable_id, campos)

    def variables_eliminar(self, variable_id: int) -> dict:
        """Elimina una variable, sustituyendo antes su último valor
        conocido en cualquier fórmula que la referencie: otras variables
        (`variables_formula.expresion`), cantidades de conceptos
        (`estructura_presupuesto.formula`) y valores de componentes APU
        (`apu_matrices.formula`).

        Antes de este fix, borrar una variable dejaba esas fórmulas
        referenciando un nombre inexistente sin ningún aviso — la próxima
        vez que alguien reeditara esa celda (o algo disparara una
        reevaluación), fallaba con "variable no definida" sin que el
        usuario supiera por qué. `sustituir_variable_eliminada()` ya
        existía en backend/formulas.py pero ningún flujo real la invocaba
        (ver Hallazgo 5 de la auditoría).

        Devuelve un resumen {"variables": [...], "conceptos": [...],
        "componentes_apu": [...]} con lo que se reescribió, para que la
        UI pueda avisar al usuario qué se vio afectado.
        """
        return self._backend.variables_eliminar(variable_id)

    def variables_resueltas(self) -> dict[str, 'Decimal']:
        """Resuelve todas las variables del proyecto en orden de
        dependencias. Devuelve {nombre: Decimal}.
        Lanza ValueError si hay ciclo o variable indefinida."""
        return self._backend.variables_resueltas()

    def formula_evaluar(self, expr: str) -> 'Decimal':
        """Evalúa una expresión contra las variables del proyecto.
        Devuelve Decimal. Lanza ValueError con mensaje legible."""
        return self._backend.formula_evaluar(expr)

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
            operador/valor), tipo_icono, tipo_nombre, tipo_id, insumo_id,
            descripcion, insumo_unidad, cantidad (desde valor/operador),
            precio, importe, es_compuesto, tiene_sub_apu, formula,
            creado_en, modificado_en
        """
        return self._backend.apu(nodo_id, insumo_id)

    def apu_actualizar_operador(self, comp_id: int, operador: str) -> None:
        """Actualiza el operador (* o /) de un componente APU y recalcula en cascada."""
        from backend.database.event_bus import ProyectoRecalculado
        if operador not in ('*', '/'):
            raise ValueError("Operador debe ser '*' o '/'")
        if self._use_http:
            self._http().actualizar("apu_matrices", comp_id, operador=operador)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.actualizar("apu_matrices", comp_id, operador=operador)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def apu_agregar_componente(self, matriz_id: int, insumo_id: int,
                                valor: float = 1.0, operador: str = "*") -> int:
        """Inserta un nuevo componente en el APU de una matriz y recalcula.

        Antes usaba repo.insert() directo, saltándose DataService — sin
        validación de SchemaRegistry ni historial (no deshacible con
        Ctrl+Z), mismo patrón de bug que el Hallazgo 1 original.
        Encontrado al migrar APU a la API HTTP (este método era el único
        de los 5 de escritura de APU sin soporte HTTP en absoluto)."""
        from backend.database.event_bus import ProyectoRecalculado
        from backend.database.repos import ApuMatricesRepo
        orden = ApuMatricesRepo(self._conn).proximo_orden(matriz_id)
        campos = {
            "matriz_id": matriz_id, "insumo_id": insumo_id,
            "valor": valor, "operador": operador,
            "precio": 0.0, "orden": orden, "formula": None,
        }
        if self._use_http:
            nuevo_id = self._http().insertar("apu_matrices", **campos)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return nuevo_id
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            nuevo_id = self._ds.insertar("apu_matrices", **campos)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))
        return nuevo_id

    def apu_actualizar_valor(self, comp_id: int, valor: float,
                              formula: str | None = None) -> None:
        """Actualiza el valor y opcionalmente la fórmula de un componente APU.

        Si se proporciona `formula`, se evalúa antes de guardar.
        """
        from backend.database.event_bus import ProyectoRecalculado
        if valor is None or valor < 0:
            raise ValueError("La cantidad no puede ser negativa")
        if formula is not None and formula.strip():
            from backend.formulas import evaluar_formula, ErrorFormula
            try:
                resuelta = evaluar_formula(formula.strip(), self.variables_resueltas())
                valor = float(resuelta)
            except ErrorFormula as e:
                raise ValueError(str(e))
        else:
            formula = None
        if self._use_http:
            if valor == 0:
                comp = self._http().buscar("apu_matrices", comp_id)
                if comp and comp["operador"] == "/":
                    raise ValueError("La cantidad no puede ser cero con operador división (división por cero)")
            campos = {"valor": valor}
            if formula is not None:
                campos["formula"] = formula
            self._http().actualizar("apu_matrices", comp_id, **campos)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import ApuMatricesRepo, RecalculoRepo
        if valor == 0:
            comp = ApuMatricesRepo(self._conn).buscar(comp_id)
            if comp and comp["operador"] == "/":
                raise ValueError("La cantidad no puede ser cero con operador división (división por cero)")
        with self._ds.transaccion():
            campos = {"valor": valor}
            if formula is not None:
                campos["formula"] = formula
            self._ds.actualizar("apu_matrices", comp_id, **campos)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def apu_reasignar_componente(self, comp_id: int, nuevo_insumo_id: int) -> None:
        """Reasigna el insumo de un componente dentro de un APU.

        Cambia el insumo_id del registro en apu_matrices. Dispara recálculo
        completo y todos los widgets suscritos se refrescan solos.
        """
        from backend.database.event_bus import ProyectoRecalculado
        if self._use_http:
            self._http().actualizar("apu_matrices", comp_id, insumo_id=nuevo_insumo_id)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.actualizar("apu_matrices", comp_id, insumo_id=nuevo_insumo_id)
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
        if self._use_http:
            return set(self._http().insumos_con_apu())
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._conn).ids_con_apu(self._pid)

    # =========================================================================
    # INSUMOS
    # =========================================================================

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        """Catálogo de insumos, opcionalmente filtrado por tipo (ej. 'material', 'mano_obra').
        Cada dict incluye todos los campos de InsumoRepo más familia y subfamilia.
        """
        return self._backend.insumos(tipo_clave)

    def insumos_con_matrices(self, tipo_clave: str | None = None) -> list[dict]:
        """Como insumos() pero filtra solo los que aparecen en al menos un APU."""
        ids = self.insumo_ids_con_apu()
        return [i for i in self.insumos(tipo_clave) if i.get("id") in ids]

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        """Busca un insumo por su hash dentro del proyecto activo."""
        return self._backend.insumo_por_hash(hash_val)

    def recalcular_proyecto(self) -> dict:
        """Recalcula en cascada todo el presupuesto del proyecto abierto:
        costo de insumos compuestos → totales de conceptos → totales de
        capítulos. Útil tras editar precios o cantidades a mano.
        """
        return self._backend.recalcular_proyecto()

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        """Devuelve las matrices (conceptos o compuestos) donde aparece un insumo.

        Cada fila:
            tipo_origen ('concepto' | 'compuesto'), matriz_clave, matriz_descripcion,
            matriz_wbs, cantidad, precio, importe
        """
        return self._backend.rastrear_insumo(insumo_id)

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
        if self._use_http:
            return self._http().explotar(concepto_ids, nivel, tipos_ids)
        from backend.database.repos  import ExplosionRepo

        return ExplosionRepo(self._conn).calcular(
            proyecto_id  = self._pid,
            concepto_ids = concepto_ids,
            nivel        = nivel,
            tipos_ids    = tipos_ids,
        )

    def conceptos_bajo_nodo(self, nodo_id: int) -> list[int]:
        """IDs de todos los conceptos descendientes de un nodo (capítulo)."""
        if self._use_http:
            desc = self._http().descendientes(nodo_id)
            return [d["id"] for d in desc if d.get("tipo") == "concepto"]
        from backend.database.repos import NodoRepo
        descendientes = NodoRepo(self._conn).descendientes(nodo_id)
        return [d["id"] for d in descendientes if d.get("tipo") == "concepto"]

    def resumen_tipos_explosion(self, tipos_ids: list[int]) -> str:
        """Genera el string de tipos para el encabezado de la pestaña de explosión.
        Ej: 'Materiales, Mano de obra, Herramienta'
        """
        from frontend.ventana.widgets.explosion import TIPOS_INSUMO
        tipo_nombre_map = {t[0]: t[1] for t in TIPOS_INSUMO}
        return ", ".join(
            tipo_nombre_map.get(tid, str(tid))
            for tid in tipos_ids
        )

    # =========================================================================
    # CATÁLOGOS (FAMILIAS / SUBFAMILIAS)
    # =========================================================================

    def familias(self) -> list[dict]:
        """Lista de familias activas del proyecto."""
        if self._use_http:
            return self._http().familias()
        from backend.database.repos import FamiliaRepo
        return FamiliaRepo(self._conn).todas()

    def familia_insertar(self, nombre: str) -> int:
        """Inserta una nueva familia.

        Pasa por `DataService.insertar()` (no por `FamiliaRepo` directo):
        el repo no commitea por sí solo, y sin el `SAVEPOINT`/`RELEASE` de
        `DataService` la fila quedaba en una transacción implícita abierta
        que `Database.close()` descarta al hacer `conn.close()` sin
        commit — si nada más escribía en la misma sesión antes de cerrar,
        la familia recién creada desaparecía sin ningún error visible.
        Emite `NodoInsertado(id, "familias", None)`; los widgets ya
        filtran por `evento.tipo`, así que no reaccionan a esto.
        """
        if self._use_http:
            return self._http().insertar("familias", nombre=nombre)
        return self._ds.insertar("familias", nombre=nombre)

    def subfamilias(self, familia_id: int) -> list[dict]:
        """Lista de subfamilias activas de una familia."""
        if self._use_http:
            return self._http().subfamilias(familia_id)
        from backend.database.repos import SubfamiliaRepo
        return SubfamiliaRepo(self._conn).por_familia(familia_id)

    def subfamilia_insertar(self, familia_id: int, nombre: str) -> int:
        """Inserta una nueva subfamilia dentro de una familia.

        Mismo motivo que `familia_insertar()`: pasa por `DataService` para
        que la escritura quede realmente confirmada en disco.
        """
        if self._use_http:
            return self._http().insertar("subfamilias", familia_id=familia_id, nombre=nombre)
        return self._ds.insertar("subfamilias", familia_id=familia_id, nombre=nombre)

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
        from backend.database.core import generar_hash
        descripcion = descripcion.strip()
        if not descripcion:
            raise ValueError("La descripción no puede estar vacía")
        nuevo_hash = generar_hash(descripcion)
        if self._use_http:
            existente = self._http().insumo_por_hash(nuevo_hash)
            if existente and existente["id"] != insumo_id:
                raise ValueError(
                    f"Ya existe un insumo con esa descripción: "
                    f"[{existente['id']}] {existente['descripcion']}"
                )
            self._http().actualizar("insumos", insumo_id, descripcion=descripcion, hash=nuevo_hash)
            from backend.database.event_bus import InsumoActualizado
            registro = self._http().buscar("insumos", insumo_id) or {}
            self._ds.emitir(InsumoActualizado(insumo_id, {"descripcion": descripcion, "hash": nuevo_hash}, registro))
            return
        from backend.database.repos import InsumoRepo
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
        """Actualiza el costo_directo de un insumo y recalcula en cascada.

        costo_final se calcula en recalcular_proyecto como
        costo_directo × factor_sobrecosto — no se escribe aquí.
        """
        from backend.database.event_bus import ProyectoRecalculado
        if precio < 0:
            raise ValueError("El precio no puede ser negativo")
        if self._use_http:
            self._http().actualizar("insumos", insumo_id,
                costo_mn=precio, costo_directo=precio)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.actualizar("insumos", insumo_id,
                                costo_mn=precio, costo_directo=precio)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def insumo_actualizar_precios(
        self, insumo_id: int, costo_mn: float, costo_me: float, usuario_id: int = 1
    ) -> None:
        """Actualiza costo_mn y costo_me de un insumo y recalcula en cascada.

        costo_directo = costo_mn (precio base). costo_final se calcula
        en recalcular_proyecto (costo_directo × factor_sobrecosto).
        """
        from backend.database.event_bus import ProyectoRecalculado
        if costo_mn < 0 or costo_me < 0:
            raise ValueError("Los precios no pueden ser negativos")
        if self._use_http:
            self._http().actualizar("insumos", insumo_id,
                costo_mn=costo_mn, costo_directo=costo_mn,
                costo_me=costo_me)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.actualizar("insumos", insumo_id,
                                costo_mn=costo_mn, costo_directo=costo_mn,
                                costo_me=costo_me)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    def insumo_actualizar_campo(
        self, insumo_id: int, campo: str, valor, usuario_id: int = 1
    ) -> None:
        """Actualiza un campo simple de un insumo del catálogo.

        `DataService.actualizar()` ya emite `InsumoActualizado` por su
        cuenta — eso basta para que la fila del insumo se refresque. Solo
        cuando el campo cambiado es `costo_final` hay que además recalcular
        en cascada (afecta compuestos que lo referencian y los totales del
        árbol) y avisar con `ProyectoRecalculado`. Emitir ese evento sin
        haber corrido el recálculo hacía que los widgets suscritos (árbol,
        insumos) repoblaran creyendo que hay totales nuevos que no existen
        — además de ser trabajo desperdiciado, con historial multiusuario
        (ver SRV-08 en docs/DECISIONES_MULTIUSUARIO.md) dispararía la
        invalidación cruzada de la pila de undo de otros usuarios por un
        cambio que nunca tocó ningún total.

        Con `servidor_url` configurado (Fase 4/5), va por HTTP vía
        `ApiCliente` — incluyendo `costo_final`, ahora que el servidor
        expone `/recalcular` (Fase 5); ya no hace falta la excepción
        local que tenía en Fase 4. El servidor emite sus propios eventos
        en SU EventBus (otro proceso), que no llegan aquí; sin WebSocket
        todavía (SRV-05, Fase 7), el propio cliente que hizo el cambio
        emite el evento LOCAL tras la respuesta HTTP exitosa.
        """
        from backend.database.event_bus import InsumoActualizado, ProyectoRecalculado

        if not self._use_http:
            from backend.database.repos import RecalculoRepo
            with self._ds.transaccion():
                self._ds.actualizar("insumos", insumo_id, **{campo: valor})
                if campo == "costo_final":
                    RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
            if campo == "costo_final":
                self._ds.emitir(ProyectoRecalculado(self._pid))
            return

        self._http().actualizar("insumos", insumo_id, **{campo: valor})
        registro = self._http().buscar("insumos", insumo_id) or {}
        self._ds.emitir(InsumoActualizado(insumo_id, {campo: valor}, registro))
        if campo == "costo_final":
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))

    def insumo_insertar(
        self,
        tipo_id: int,
        descripcion: str,
        descripcion_corta: str | None = None,
        unidad: str | None = None,
        costo: float = 0.0,
        costo_me: float = 0.0,
        es_compuesto: int = 0,
        familia_id: int | None = None,
        subfamilia_id: int | None = None,
        usuario_id: int = 1,
    ) -> int:
        """Crea un insumo nuevo desde la app (no importado).

        Genera el hash de deduplicación aquí, igual que
        insumo_actualizar_descripcion(): el hash es una llave interna, no
        un dato de dominio con reglas de SchemaRegistry, así que se calcula
        en la fachada y se envía como campo extra a DataService.insertar().
        Verifica colisión con otro insumo del proyecto antes de crear.
        """
        from backend.database.core import generar_hash
        nuevo_hash = generar_hash(descripcion) if descripcion else None
        if self._use_http:
            if nuevo_hash:
                existente = self._http().insumo_por_hash(nuevo_hash)
                if existente:
                    raise ValueError(
                        f"Ya existe un insumo con esa descripción: "
                        f"[{existente['id']}] {existente['descripcion']}"
                    )
            campos = dict(
                proyecto_id=self._pid, tipo_id=tipo_id, descripcion=descripcion,
                descripcion_corta=descripcion_corta, unidad=unidad,
                costo_mn=costo, costo_me=costo_me, costo_directo=costo,
                costo_final=costo, es_compuesto=es_compuesto, hash=nuevo_hash,
            )
            if familia_id is not None:
                campos["familia_id"] = familia_id
            if subfamilia_id is not None:
                campos["subfamilia_id"] = subfamilia_id
            return self._http().insertar("insumos", **campos)

        from backend.database.repos import InsumoRepo
        if nuevo_hash:
            existente = InsumoRepo(self._conn).buscar_por_hash(nuevo_hash, self._pid)
            if existente:
                raise ValueError(
                    f"Ya existe un insumo con esa descripción: "
                    f"[{existente['id']}] {existente['descripcion']}"
                )
        campos = dict(
            proyecto_id=self._pid,
            tipo_id=tipo_id,
            descripcion=descripcion,
            descripcion_corta=descripcion_corta,
            unidad=unidad,
            costo_mn=costo,
            costo_me=costo_me,
            costo_directo=costo,
            costo_final=costo,
            es_compuesto=es_compuesto,
            hash=nuevo_hash,
        )
        if familia_id is not None:
            campos["familia_id"] = familia_id
        if subfamilia_id is not None:
            campos["subfamilia_id"] = subfamilia_id
        return self._ds.insertar("insumos", **campos)

    def insumo_por_id(self, insumo_id: int) -> dict | None:
        """Devuelve el dict completo de un insumo por su id, o None si no existe."""
        if self._use_http:
            return self._http().buscar("insumos", insumo_id)
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._conn).buscar(insumo_id)

    def eliminar_insumo(self, insumo_id: int) -> None:
        """Elimina (soft-delete) un insumo del catálogo y recalcula en cascada."""
        from backend.database.event_bus import ProyectoRecalculado
        if self._use_http:
            self._http().eliminar("insumos", insumo_id)
            self._http().recalcular()
            self._ds.emitir(ProyectoRecalculado(self._pid))
            return
        from backend.database.repos import RecalculoRepo
        with self._ds.transaccion():
            self._ds.eliminar("insumos", insumo_id)
            RecalculoRepo(self._conn).recalcular_proyecto(self._pid)
        self._ds.emitir(ProyectoRecalculado(self._pid))

    # =========================================================================
    # GESTIÓN DE PROYECTOS
    # =========================================================================

    def proyecto_leer(self) -> dict:
        """Devuelve todos los campos editables del proyecto actual."""
        from backend.database.repos import ProyectoRepo
        reg = ProyectoRepo(self._conn).buscar(self._pid)
        return dict(reg) if reg else {}

    def proyecto_guardar(self, campos: dict) -> None:
        """Persiste los campos editados del proyecto.

        Antes escribía directo vía ProyectoRepo.update(), sin pasar por
        DataService — sin validación de SchemaRegistry, sin historial
        (no deshacible con Ctrl+Z), y sin comitear (dependía de que el
        caller hiciera commit a mano). Mismo patrón que tenía indirectos
        antes del fix del Hallazgo 1 — ver hallazgo N1 del seguimiento.

        Delega a self._backend (no llama a self._ds directo) para
        funcionar igual en modo local y HTTP — encontrado como bug real
        al migrar indirectos a HTTP: sin esto, en modo HTTP escribía en
        silencio a la BD local del proceso (irrelevante) en vez de
        hablarle al servidor, y la duración de obra nunca llegaba donde
        el servidor la necesita para calcular indirectos.
        """
        self._backend.proyecto_guardar(campos)

    # =========================================================================
    # FACTORES DE SOBRECOSTO
    # =========================================================================

    def factores_sobrecosto_obtener(self) -> dict:
        """Devuelve los factores de sobrecosto del proyecto o dict vacío."""
        return self._backend.factores_sobrecosto_obtener()

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
        return self._backend.factores_sobrecosto_guardar(valores)

    # =========================================================================
    # INDIRECTOS
    # =========================================================================

    def indirectos_lista(self, tipo: str | None = None) -> list[dict]:
        """Lista indirectos del proyecto, opcionalmente filtrados por tipo."""
        return self._backend.indirectos_lista(tipo)

    def indirectos_guardar(self, registro_id: int, campos: dict) -> None:
        """Actualiza un indirecto existente.

        Pasa por DataService (Fase 2, ver docs/ARQUITECTURA_SERVICIOS.md):
        valida contra SchemaRegistry, captura historial (Ctrl+Z) y emite
        IndirectoActualizado — antes de este fix esta escritura se saltaba
        las tres cosas (ver Hallazgo 1 de la auditoría funcional)."""
        self._backend.indirectos_guardar(registro_id, campos)

    def indirectos_insertar(self, campos: dict) -> int:
        """Inserta un indirecto nuevo. Devuelve el id.

        Inyecta proyecto_id si el caller no lo trae — sin esto, un
        indirecto agregado a mano (botón "+ Agregar", no plantilla)
        quedaba con proyecto_id NULL y desaparecía de indirectos_lista().

        insertar() genérico solo emite NodoInsertado (pensado para el
        árbol de presupuesto); emitimos IndirectoActualizado aparte para
        que un futuro panel de indirectos/sobrecostos pueda refrescarse
        igual que con actualizar()/eliminar()."""
        return self._backend.indirectos_insertar(campos)

    def indirectos_eliminar(self, registro_id: int) -> None:
        """Elimina (soft-delete) un indirecto."""
        self._backend.indirectos_eliminar(registro_id)

    def indirectos_calcular_totales(self) -> dict:
        """Recalcula el campo 'total' de todos los indirectos del proyecto.

        No encaja en el genérico actualizar()/insertar() (es un UPDATE
        masivo, no de una sola fila) — mismo caso que
        factores_sobrecosto_guardar. Se envuelve en una transacción propia
        y se emite el evento a mano vía DataService.emitir().

        Devuelve el resultado de IndirectoRepo.calcular_totales():
        {"duracion_obra_dias": float, "afectados_por_duracion_faltante": [ids]}
        — la UI puede usar "afectados_por_duracion_faltante" para avisar
        que hay indirectos calculando total=0 por falta de capturar la
        duración de obra del proyecto (Hallazgo 7 de la auditoría)."""
        return self._backend.indirectos_calcular_totales()

    def indirectos_cargar_plantilla(self, tipo: str) -> int:
        """Carga items de plantilla que no existan ya. Devuelve cuántos insertó."""
        return self._backend.indirectos_cargar_plantilla(tipo)

    def indirectos_aplicar_a_sobrecosto(self) -> dict:
        """Traslada los totales de indirectos (campo + oficina) a
        factores_sobrecosto como %CI, y recalcula el presupuesto en cascada.

        Fórmula (RLOPSRM Cap. Sexto Art. 214-219 / metodología estándar de
        precios unitarios):
            %CI = Total de Indirectos / Costo Directo Total del proyecto × 100
        calculado por separado para campo y oficina, porque
        factores_sobrecosto guarda ambos valores en columnas independientes.

        Antes de este método no existía ninguna conexión entre el desglose
        itemizado de `indirectos` y el porcentaje que de verdad entra en la
        cascada de sobrecosto — ver Hallazgo 1/12 de la auditoría: el
        usuario podía llenar plantillas de indirectos con total aparente
        sin que eso afectara el presupuesto final.

        Devuelve un dict con los porcentajes aplicados y las bases usadas,
        para que la UI pueda mostrar de dónde salió cada número.
        Lanza ValueError si el costo directo del proyecto es 0 (nada que
        capturar de qué prorratear el %CI).
        """
        return self._backend.indirectos_aplicar_a_sobrecosto()

    # =========================================================================
    # SRV-10: DESHACER / REHACER
    # =========================================================================

    def deshacer(self, usuario_id: int = 1) -> bool:
        """Deshace la última operación del usuario (SRV-10)."""
        if self._use_http:
            return self._http().deshacer(usuario_id)
        return self._ds.deshacer(usuario_id, proyecto_id=self._pid)

    def rehacer(self, usuario_id: int = 1) -> bool:
        """Rehace la última operación deshecha (SRV-10)."""
        if self._use_http:
            return self._http().rehacer(usuario_id)
        return self._ds.rehacer(usuario_id, proyecto_id=self._pid)

    def iniciar_sesion_undo(self) -> str | None:
        """Agrupa todas las escrituras hechas hasta cerrar_sesion_undo() en
        una sola entrada de deshacer (SRV-09 'sesion'). Pensado para
        operaciones que tocan varios campos/filas a la vez, como el pegado
        multi-celda, para que Ctrl+Z las revierta de un solo golpe en vez
        de una por una.

        Nota: en modo servidor (_use_http) todavía no hay agrupación de
        sesión entre requests — cada campo pegado queda como una entrada
        de deshacer independiente hasta que SRV-10 se extienda al cliente
        HTTP. No falla, solo no agrupa.
        """
        if self._use_http:
            return None
        return self._ds.iniciar_sesion()

    def cerrar_sesion_undo(self) -> None:
        """Cierra la sesión de deshacer agrupada abierta con iniciar_sesion_undo()."""
        if not self._use_http:
            self._ds.cerrar_sesion()

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def resolver_matriz(
        self, nodo_id: int | None = None, insumo_id: int | None = None
    ) -> tuple[int | None, str]:
        """Resuelve a un (matriz_id, descripcion).

        Pasa exactamente uno de los dos:
            nodo_id    — id del concepto en estructura_presupuesto (matriz_id positivo)
            insumo_id  — busca un insumo compuesto directamente por id (matriz_id negativo)

        Devuelve (None, '') si no existe o no tiene APU.
        """
        return self._backend.resolver_matriz(nodo_id, insumo_id)

    def unificar_matrices_apu(self) -> int:
        """Una sola matriz por APU (Fase de migración).

        La importación OPUS creaba DOS matrices para el mismo desglose:
        una para el concepto (matriz_id positivo) y otra para el insumo
        compuesto (matriz_id negativo). Esto causaba desfase de costos.

        Esta migra: para cada concepto con insumo compuesto que tenga
        matriz propia, redirige los componentes a la matriz del insumo
        compuesto y borra la matriz duplicada. Devuelve el número de
        conceptos migrados.

        Corre en cada apertura/importación de proyecto (ver
        `_wire_servicios()`/`_on_abrir_proyecto()` en
        `frontend/ventana/handlers/gestion_proyectos.py`), así que si no
        hay nada que migrar debe ser barato y no debe tocar la UI.

        Excepción deliberada al patrón HTTP de Fase 5: se queda en el
        camino local (`self._conn` directo) en vez de migrar a
        `ApiCliente`. No es un verbo CRUD (insertar/actualizar/eliminar/
        recalcular) sino una operación de mantenimiento en lote sobre
        `apu_matrices`, y corre ANTES de que el resto de la sesión toque
        ese proyecto — mismo archivo, misma conexión que ya se abre en
        `_wire_servicios()` para wireear todo lo demás. Moverla a un
        endpoint dedicado es posible (mismo patrón que `/recalcular` o
        `/factores_sobrecosto`) pero no aporta nada mientras corra en el
        mismo proceso que abre el archivo; revisar si esto cambia cuando
        el modelo de apertura de proyectos deje de ser "un archivo, una
        conexión directa del cliente" (Fase 9).
        """
        from backend.database.repos import ApuMatricesRepo
        from backend.database.event_bus import ProyectoRecalculado

        repo = ApuMatricesRepo(self._conn)
        candidatos = repo.conceptos_con_insumo_compuesto(self._pid)

        migrados = 0
        with self._ds.transaccion():
            for row in candidatos:
                cid = row["cid"]
                neg = -row["insumo_id"]

                if repo.contar_por_matriz(cid) == 0:
                    continue  # el concepto no tiene matriz propia, nada que unificar

                if repo.contar_por_matriz(neg) == 0:
                    repo.redirigir_matriz(origen=cid, destino=neg)
                else:
                    repo.eliminar_matriz(cid)
                migrados += 1

        if migrados:
            self._ds.emitir(ProyectoRecalculado(self._pid))
        return migrados

    # =========================================================================
    # GENERADORES DE OBRA
    # =========================================================================

    def generadores_por_concepto(self, concepto_id: int | None) -> list[dict]:
        """Generadores vinculados a un concepto, o sueltos si concepto_id es None."""
        return self._backend.generadores_por_concepto(concepto_id)

    def generador_por_id(self, generador_id: int) -> dict | None:
        return self._backend.generador_por_id(generador_id)

    def generador_crear(self, nombre: str = "", concepto_id: int | None = None,
                        unidad: str | None = None) -> int:
        """Crea un generador vacío. Devuelve su id."""
        return self._backend.generador_crear(nombre, concepto_id, unidad)

    def generador_actualizar_cad(self, generador_id: int, path: str | None) -> None:
        """Liga (o desliga, con None) un archivo DXF a este generador —
        persiste la ruta para que se recargue sola la próxima vez que se
        abra la pestaña de este generador."""
        self._backend.generador_actualizar_cad(generador_id, path)

    def generador_renglones(self, generador_id: int) -> list[dict]:
        return self._backend.generador_renglones(generador_id)

    def generador_renglon_guardar(self, generador_id: int,
                                  renglon_id: int | None = None,
                                  **campos) -> int:
        return self._backend.generador_renglon_guardar(generador_id, renglon_id, campos)

    def generador_renglon_eliminar(self, renglon_id: int) -> None:
        self._backend.generador_renglon_eliminar(renglon_id)

    def generador_mover_renglones(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool) -> bool:
        """Mueve o copia (Ctrl) un bloque de renglones a otro generador,
        o reordena si nuevo_generador_id es el mismo — ver drag and drop
        de TablaGenerador (widgets/generador.py)."""
        return self._backend.generador_mover_renglones(ids, nuevo_generador_id, antes_de_id, copiar)

    def concepto_cantidad(self, concepto_id: int) -> float:
        from backend.database.repos.presupuesto import NodoRepo
        row = NodoRepo(self._conn).buscar(concepto_id)
        return float(row["cantidad"]) if row and row.get("cantidad") else 0.0

    def concepto_actualizar(self, concepto_id: int, **campos) -> None:
        self._ds.actualizar("estructura_presupuesto", concepto_id, **campos)

    def campo_valor(self, tabla: str, campo: str, registro_id: int) -> dict | None:
        """Lee un campo concreto de una tabla. Devuelve registro completo o None."""
        from backend.database.repos import NodoRepo, ApuMatricesRepo, InsumoRepo
        repos = {
            "estructura_presupuesto": NodoRepo,
            "apu_matrices": ApuMatricesRepo,
            "insumos": InsumoRepo,
        }
        cls = repos.get(tabla)
        if not cls:
            return None
        return cls(self._conn).buscar(registro_id)
