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
                "frontend/ventana/mixins/gestion_proyectos.py."
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

        # Backends — contrato ToqueApiBackend (ver
        # frontend/ventana/api_backends.py y docs/ARQUITECTURA_SERVICIOS.md
        # Fases 0-4 completadas 2026-08-31). api.py es dispatcher puro (R2):
        # cada método público es `return self._backend.<metodo>(...)` sin
        # `if _use_http` por método.
        from frontend.ventana.api_backends import _BackendLocal, _BackendHTTP, ToqueApiBackend
        self._backend_local: ToqueApiBackend = _BackendLocal(self)
        self._backend_http: ToqueApiBackend = _BackendHTTP(self)
        assert isinstance(self._backend_local, ToqueApiBackend)
        assert isinstance(self._backend_http, ToqueApiBackend)

    @property
    def _backend(self) -> "ToqueApiBackend":
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
        return self._backend.presupuesto_arbol(extra=extra)

    def nodo_total(self, nodo_id: int) -> float:
        """Devuelve el total de un nodo del presupuesto."""
        return self._backend.nodo_total(nodo_id)

    def concepto_actualizar_cantidad(self, concepto_id: int, cantidad: float,
                                       formula: str | None = None) -> None:
        """Actualiza la cantidad y opcionalmente la fórmula de un concepto.

        Si se proporciona `formula`, se evalúa antes de guardar (valida
        que dé un resultado numérico). El resultado se guarda como
        `cantidad` y el texto de la fórmula se persiste en la columna
        `formula`. Si la evaluación falla, no se guarda nada (ValueError).
        """
        return self._backend.concepto_actualizar_cantidad(concepto_id, cantidad, formula)

    def concepto_reasignar_insumo(self, concepto_id: int, nuevo_insumo_id: int) -> None:
        """Reasigna un concepto a otro insumo del catálogo.

        Cambia el insumo_id del concepto, que ahora apuntará al nuevo
        insumo (descripción, unidad, precio se resuelven desde allí).
        Dispara recálculo completo del proyecto y reconstrucción del árbol.
        """
        return self._backend.concepto_reasignar_insumo(concepto_id, nuevo_insumo_id)

    def nodo_descripcion_actual(self, nodo_id: int) -> str:
        """Devuelve la descripción visible actual de un nodo del árbol
        (propia si es capítulo, o la de su insumo ligado si es concepto).

        Uso: revertir una celda tras un ValueError de validación (ej.
        descripción duplicada) sin recargar todo el árbol.
        """
        return self._backend.nodo_descripcion_actual(nodo_id)

    def concepto_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        """Actualiza la descripción del insumo ligado a un concepto.

        Reutiliza insumo_actualizar_descripcion() para no duplicar la
        lógica de regeneración de hash y verificación de colisión.
        """
        return self._backend.concepto_actualizar_descripcion(nodo_id, descripcion)

    def concepto_actualizar_unidad(self, nodo_id: int, unidad: str) -> None:
        """Actualiza la unidad de un concepto (escribe en insumos)."""
        return self._backend.concepto_actualizar_unidad(nodo_id, unidad)

    def agrupador_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        """Actualiza la descripción de un agrupador (capítulo)."""
        return self._backend.agrupador_actualizar_descripcion(nodo_id, descripcion)

    def eliminar_nodo(self, nodo_id: int) -> None:
        """Elimina (soft-delete) un nodo del presupuesto y recalcula en cascada."""
        return self._backend.eliminar_nodo(nodo_id)

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
        return self._backend.agregar_nodo(tipo, padre_id, descripcion, insumo_id,
                                           cantidad, orden, antes_de, es_extra)

    def todos_concepto_ids(self) -> list[int]:
        """Devuelve los ids de todos los conceptos activos del proyecto."""
        return self._backend.todos_concepto_ids()

    def conceptos_planos(self) -> list[dict]:
        """Lista plana de todos los conceptos con clave, descripción, unidad, cantidad, total."""
        return self._backend.conceptos_planos()

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
        return self._backend.apu_actualizar_operador(comp_id, operador)

    def apu_agregar_componente(self, matriz_id: int, insumo_id: int,
                                valor: float = 1.0, operador: str = "*") -> int:
        """Inserta un nuevo componente en el APU de una matriz y recalcula.

        Antes usaba repo.insert() directo, saltándose DataService — sin
        validación de SchemaRegistry ni historial (no deshacible con
        Ctrl+Z), mismo patrón de bug que el Hallazgo 1 original.
        Encontrado al migrar APU a la API HTTP (este método era el único
        de los 5 de escritura de APU sin soporte HTTP en absoluto)."""
        return self._backend.apu_agregar_componente(matriz_id, insumo_id, valor, operador)

    def apu_actualizar_valor(self, comp_id: int, valor: float,
                              formula: str | None = None) -> None:
        """Actualiza el valor y opcionalmente la fórmula de un componente APU.

        Si se proporciona `formula`, se evalúa antes de guardar.
        """
        return self._backend.apu_actualizar_valor(comp_id, valor, formula)

    def apu_reasignar_componente(self, comp_id: int, nuevo_insumo_id: int) -> None:
        """Reasigna el insumo de un componente dentro de un APU.

        Cambia el insumo_id del registro en apu_matrices. Dispara recálculo
        completo y todos los widgets suscritos se refrescan solos.
        """
        return self._backend.apu_reasignar_componente(comp_id, nuevo_insumo_id)

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
        return self._backend.apu_actualizar_precio_componente(insumo_id, precio)

    def insumo_ids_con_apu(self) -> set[int]:
        """Conjunto de ids de insumos compuestos (tienen APU propio)."""
        return self._backend.insumo_ids_con_apu()

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

    def reindexar_proyecto(self) -> None:
        """Recalcula wbs/nivel de TODO el árbol del proyecto abierto a partir
        de padre_id + orden (ver NodoRepo.reindexar()). Corrige numeración
        desactualizada — por ejemplo proyectos importados con una versión
        anterior de la app que dejaba el código crudo de OPUS (ej. "0101",
        "010203") en vez del formato "1.1", "1.1.3" que usa la numeración
        propia del presupuesto."""
        self._backend.reindexar_proyecto()

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
        return self._backend.explotar(concepto_ids, nivel, tipos_ids)

    def conceptos_bajo_nodo(self, nodo_id: int) -> list[int]:
        """IDs de todos los conceptos descendientes de un nodo (capítulo)."""
        return self._backend.conceptos_bajo_nodo(nodo_id)

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
        return self._backend.familias()

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
        return self._backend.familia_insertar(nombre)

    def subfamilias(self, familia_id: int) -> list[dict]:
        """Lista de subfamilias activas de una familia."""
        return self._backend.subfamilias(familia_id)

    def subfamilia_insertar(self, familia_id: int, nombre: str) -> int:
        """Inserta una nueva subfamilia dentro de una familia.

        Mismo motivo que `familia_insertar()`: pasa por `DataService` para
        que la escritura quede realmente confirmada en disco.
        """
        return self._backend.subfamilia_insertar(familia_id, nombre)

    # =========================================================================
    # MUTACIÓN DE INSUMOS
    # =========================================================================

    def insumo_actualizar_descripcion(
        self, insumo_id: int, descripcion: str, usuario_id: int = 1
    ) -> None:
        """Actualiza la descripción de un insumo y regenera su hash."""
        return self._backend.insumo_actualizar_descripcion(insumo_id, descripcion, usuario_id)

    def insumo_actualizar_precio(
        self, insumo_id: int, precio: float, usuario_id: int = 1
    ) -> None:
        """Actualiza el costo_directo de un insumo y recalcula en cascada."""
        return self._backend.insumo_actualizar_precio(insumo_id, precio, usuario_id)

    def insumo_actualizar_precios(
        self, insumo_id: int, costo_mn: float, costo_me: float, usuario_id: int = 1
    ) -> None:
        """Actualiza costo_mn y costo_me de un insumo y recalcula en cascada."""
        return self._backend.insumo_actualizar_precios(insumo_id, costo_mn, costo_me, usuario_id)

    def insumo_actualizar_campo(
        self, insumo_id: int, campo: str, valor, usuario_id: int = 1
    ) -> None:
        """Actualiza un campo simple de un insumo del catálogo."""
        return self._backend.insumo_actualizar_campo(insumo_id, campo, valor, usuario_id)

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
        """Crea un insumo nuevo desde la app (no importado)."""
        return self._backend.insumo_insertar(tipo_id, descripcion, descripcion_corta, unidad, costo, costo_me, es_compuesto, familia_id, subfamilia_id, usuario_id)

    def insumo_por_id(self, insumo_id: int) -> dict | None:
        """Devuelve el dict completo de un insumo por su id, o None si no existe."""
        return self._backend.insumo_por_id(insumo_id)

    def eliminar_insumo(self, insumo_id: int) -> None:
        """Elimina (soft-delete) un insumo del catálogo y recalcula en cascada."""
        return self._backend.eliminar_insumo(insumo_id)

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
        return self._backend.deshacer(usuario_id)

    def rehacer(self, usuario_id: int = 1) -> bool:
        """Rehace la última operación deshecha (SRV-10)."""
        return self._backend.rehacer(usuario_id)

    def iniciar_sesion_undo(self) -> str | None:
        """Agrupa todas las escrituras hechas hasta cerrar_sesion_undo() en
        una sola entrada de deshacer (SRV-09 'sesion')."""
        return self._backend.iniciar_sesion_undo()

    def cerrar_sesion_undo(self) -> None:
        """Cierra la sesión de deshacer agrupada abierta con iniciar_sesion_undo()."""
        return self._backend.cerrar_sesion_undo()

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
        return self._backend.unificar_matrices_apu()

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
        return self._backend.concepto_cantidad(concepto_id)

    def concepto_actualizar(self, concepto_id: int, **campos) -> None:
        return self._backend.concepto_actualizar(concepto_id, **campos)

    def campo_valor(self, tabla: str, campo: str, registro_id: int) -> dict | None:
        """Lee un campo concreto de una tabla. Devuelve registro completo o None."""
        return self._backend.campo_valor(tabla, campo, registro_id)
