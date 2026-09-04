"""
api_backends.py
================
Backends de Api: separan la implementación local (SQLite directo) de la
implementación HTTP (vía servidor embebido) que hoy conviven mezcladas
como `if self._use_http: ... else: ...` dentro de cada método de Api.

Cada backend implementa el mismo conjunto de métodos que expone Api.
Api delega al backend activo en vez de repetir el if/else en cada método.

Contrato normativo: ToqueApiBackend (Protocol, 66 métodos) — ver
docs/ARQUITECTURA_SERVICIOS.md R1-R9. Fases 0,2,3 completadas 2026-08-31
(api.py dispatcher, ApiCliente 7 transporte); Fase 4 WS ProyectoRecalculado
completada; Fase 1 (quitar ds.emitir duplicado) desbloqueada y opcional.

Actualizado: 2026-08-31 05:00 (hora local)
"""
from __future__ import annotations

import httpx
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from frontend.ventana.api import Api


@runtime_checkable
class ToqueApiBackend(Protocol):
    """Contrato que cumplen _BackendLocal y _BackendHTTP.

    Reglas de firma (obligatorias para TODO método nuevo, ver
    docs/ARQUITECTURA_SERVICIOS.md §3-§4):
    - Parámetros por id (int), nunca por texto/clave.
    - Retornos JSON-serializables: dict | list[dict] | int | float | str | bool | None.
      Decimal se transfiere como str y se reconstruye en el lado HTTP.
    - Sin azúcar de kwargs en la firma: campos explícitos.

    Lista viva — crece al migrar cada sección (Fase 2). Los ~31 métodos
    de abajo ya delegan; los ~40 con `if self._use_http:` inline en api.py
    se incorporan aquí al migrarlos sección por sección.
    """

    # ── FACTORES DE SOBRECOSTO ──────────────────────────────────
    def factores_sobrecosto_obtener(self) -> dict: ...
    def factores_sobrecosto_guardar(self, valores: dict) -> float: ...

    # ── INSUMOS / RECÁLCULO / RASTREO ───────────────────────────
    def insumos(self, tipo_clave: str | None = None) -> list[dict]: ...
    def insumos_con_matrices(self, tipo_clave: str | None = None) -> list[dict]: ...
    def insumo_por_hash(self, hash_val: str) -> dict | None: ...
    def recalcular_proyecto(self) -> dict: ...
    def reindexar_proyecto(self) -> None: ...
    def rastrear_insumo(self, insumo_id: int) -> list[dict]: ...
    def proyecto_guardar(self, campos: dict) -> None: ...
    def proyecto_leer(self) -> dict: ...

    # ── VARIABLES DE FÓRMULA ────────────────────────────────────
    def variables_listar(self) -> list[dict]: ...
    def variables_crear(self, nombre: str, expresion: str, descripcion: str) -> int: ...
    def variables_actualizar(self, variable_id: int, campos: dict) -> None: ...
    def variables_eliminar(self, variable_id: int) -> dict: ...
    def variables_resueltas(self) -> dict: ...
    def formula_evaluar(self, expr: str): ...

    # ── APU ─────────────────────────────────────────────────────
    def apu(self, nodo_id: int | None, insumo_id: int | None) -> dict | None: ...
    def resolver_matriz(self, nodo_id: int | None, insumo_id: int | None) -> tuple[int | None, str]: ...
    def apu_actualizar_operador(self, comp_id: int, operador: str) -> None: ...
    def apu_agregar_componente(self, matriz_id: int, insumo_id: int,
                                valor: float = 1.0, operador: str = "*") -> int: ...
    def apu_actualizar_valor(self, comp_id: int, valor: float,
                              formula: str | None = None) -> None: ...
    def apu_reasignar_componente(self, comp_id: int, nuevo_insumo_id: int) -> None: ...
    def apu_actualizar_precio_componente(self, insumo_id: int, precio: float) -> None: ...
    def insumo_ids_con_apu(self) -> set[int]: ...

    # ── GENERADORES ─────────────────────────────────────────────
    def generadores_por_concepto(self, concepto_id: int | None) -> list[dict]: ...
    def generador_por_id(self, generador_id: int) -> dict | None: ...
    def generador_crear(self, nombre: str, concepto_id: int | None, unidad: str | None) -> int: ...
    def generador_actualizar_cad(self, generador_id: int, path: str | None) -> None: ...
    def generador_renglones(self, generador_id: int) -> list[dict]: ...
    def generador_renglon_guardar(self, generador_id: int, renglon_id: int | None, campos: dict) -> int: ...
    def generador_renglon_eliminar(self, renglon_id: int) -> None: ...
    def generador_mover_renglones(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool) -> bool: ...
    def generador_reasignar(self, generador_id: int,
                            nuevo_concepto_id: int | None,
                            usuario_id: int = 1) -> None: ...

    # ── INDIRECTOS ──────────────────────────────────────────────
    def indirectos_lista(self, tipo: str | None = None) -> list[dict]: ...
    def indirectos_guardar(self, registro_id: int, campos: dict) -> None: ...
    def indirectos_insertar(self, campos: dict) -> int: ...
    def indirectos_eliminar(self, registro_id: int) -> None: ...
    def indirectos_calcular_totales(self) -> dict: ...
    def indirectos_cargar_plantilla(self, tipo: str) -> int: ...
    def indirectos_aplicar_a_sobrecosto(self) -> dict: ...

    # ── PRESUPUESTO ─────────────────────────────────────────────
    def presupuesto_arbol(self, extra: bool = False) -> list[dict]: ...
    def nodo_total(self, nodo_id: int) -> float: ...
    def concepto_actualizar_cantidad(self, concepto_id: int, cantidad: float,
                                      formula: str | None = None) -> None: ...
    def concepto_reasignar_insumo(self, concepto_id: int, nuevo_insumo_id: int) -> None: ...
    def nodo_descripcion_actual(self, nodo_id: int) -> str: ...
    def concepto_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None: ...
    def concepto_actualizar_unidad(self, nodo_id: int, unidad: str) -> None: ...
    def agrupador_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None: ...
    def eliminar_nodo(self, nodo_id: int) -> None: ...
    def agregar_nodo(self, tipo: str, padre_id: int | None = None,
                      descripcion: str = "", insumo_id: int | None = None,
                      cantidad: float | None = None, orden: float | None = None,
                      antes_de: int | None = None, es_extra: bool = False) -> int: ...
    def todos_concepto_ids(self) -> list[int]: ...
    def conceptos_planos(self) -> list[dict]: ...

    # ── EXPLOSIÓN ───────────────────────────────────────────────
    def explotar(self, concepto_ids: list[int], nivel: str, tipos_ids: list[int]) -> tuple[list[dict], float]: ...
    def conceptos_bajo_nodo(self, nodo_id: int) -> list[int]: ...

    # ── CATÁLOGOS (FAMILIAS / SUBFAMILIAS) ──────────────────────
    def familias(self) -> list[dict]: ...
    def familia_insertar(self, nombre: str) -> int: ...
    def subfamilias(self, familia_id: int) -> list[dict]: ...
    def subfamilia_insertar(self, familia_id: int, nombre: str) -> int: ...

    # ── INSUMOS (MUTACIÓN) ──────────────────────────────────────
    def insumo_actualizar_descripcion(self, insumo_id: int, descripcion: str, usuario_id: int = 1) -> None: ...
    def insumo_actualizar_precio(self, insumo_id: int, precio: float, usuario_id: int = 1) -> None: ...
    def insumo_actualizar_precios(self, insumo_id: int, costo_mn: float, costo_me: float, usuario_id: int = 1) -> None: ...
    def insumo_actualizar_campo(self, insumo_id: int, campo: str, valor, usuario_id: int = 1) -> None: ...
    def insumo_insertar(self, tipo_id: int, descripcion: str, descripcion_corta: str | None = None,
                         unidad: str | None = None, costo: float = 0.0, costo_me: float = 0.0,
                         es_compuesto: int = 0, familia_id: int | None = None,
                         subfamilia_id: int | None = None, usuario_id: int = 1) -> int: ...
    def insumo_por_id(self, insumo_id: int) -> dict | None: ...
    def eliminar_insumo(self, insumo_id: int) -> None: ...

    # ── UNDO / SESIÓN ───────────────────────────────────────────
    def deshacer(self, usuario_id: int = 1) -> bool: ...
    def rehacer(self, usuario_id: int = 1) -> bool: ...
    def iniciar_sesion_undo(self) -> str | None: ...
    def cerrar_sesion_undo(self) -> None: ...

    # ── CICLO DE VIDA REMOTO ──────────────────────────────────────
    def descargar_proyecto(self) -> bool: ...
    def estadisticas_proyecto(self) -> dict: ...

    # ── ADJUNTOS (Fase E: CAD remoto) ───────────────────────────────
    def adjuntos_listar(self) -> list[str]: ...
    def adjunto_guardar(self, filename: str, contenido: bytes) -> None: ...
    def adjunto_leer(self, filename: str) -> bytes | None: ...

    # ── HELPERS LOCALES ─────────────────────────────────────────
    def concepto_cantidad(self, concepto_id: int) -> float: ...
    def concepto_actualizar(self, concepto_id: int, **campos) -> None: ...
    def campo_valor(self, tabla: str, campo: str, registro_id: int) -> dict | None: ...
    def unificar_matrices_apu(self) -> int: ...


def _enriquecer_detalle_apu(data: dict, ids_con_apu: set[int]) -> dict:
    """Enriquece las filas crudas de con_detalle()/apu_completo() con lo
    que necesita la tabla de la UI (tipo_icono, cantidad calculada,
    tiene_sub_apu). Es lógica de presentación, no de negocio — vive aquí
    (compartida) en vez de duplicarse dentro de cada backend, y en vez de
    vivir en el servidor (que no debería saber de íconos SVG del cliente)."""
    from frontend.ventana.tipos_insumo import ICONO_SVG as _TIPO_ICONO_SVG

    if data.get("matriz_id") is None:
        return None

    detalle = []
    for r in data["detalle"]:
        tid  = r.get("tipo_id", 0)
        desc = r.get("insumo_descripcion") or r.get("insumo_desc_corta") or ""
        tiene_sub = r.get("insumo_id") in ids_con_apu
        v  = r.get("valor", 0) or 0
        op = r.get("operador", "*")
        detalle.append({
            "id":            r.get("id"),
            "tipo_icono":    _TIPO_ICONO_SVG.get(tid, "file-text"),
            "tipo_nombre":   r.get("tipo_nombre", ""),
            "tipo_id":       tid,
            "insumo_id":     r.get("insumo_id"),
            "descripcion":   desc,
            "insumo_unidad": r.get("insumo_unidad", ""),
            "valor":         v,
            "operador":      op,
            "cantidad":      v if op == "*" else (1.0 / v if v else 0.0),
            "precio":        r.get("precio", 0),
            "importe":       r.get("importe", 0),
            "es_compuesto":  r.get("insumo_es_compuesto", 0),
            "tiene_sub_apu": tiene_sub,
            "formula":       r.get("formula"),
            "creado_en":     r.get("creado_en"),
            "modificado_en": r.get("modificado_en"),
        })

    return {
        "matriz_id":   data["matriz_id"],
        "descripcion": data["descripcion"],
        "detalle":     detalle,
        "totales":     data.get("totales"),
    }


class _BackendLocal:
    """Implementación local (SQLite directo vía DataService/repos)."""

    def __init__(self, api: "Api"):
        self._api = api

    # ── FACTORES DE SOBRECOSTO ──────────────────────────────────────

    def factores_sobrecosto_obtener(self) -> dict:
        from backend.database.repos import FactoresSobrecostoRepo
        return FactoresSobrecostoRepo(self._api._conn).obtener(self._api._pid) or {}

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        from backend.database.event_bus import FactoresSobrecostoActualizados, ProyectoRecalculado
        from backend.database.repos import FactoresSobrecostoRepo, RecalculoRepo
        with self._api._ds.transaccion():
            factor = FactoresSobrecostoRepo(self._api._conn).guardar(self._api._pid, **valores)
            self._api._ds.emitir(FactoresSobrecostoActualizados(self._api._pid, valores))
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return factor

    # ── INSUMOS ──────────────────────────────────────────────────────

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        from backend.database.repos import InsumoRepo
        repo = InsumoRepo(self._api._conn)
        return repo.por_tipo(self._api._pid, tipo_clave) if tipo_clave else repo.todos(self._api._pid)

    def insumos_con_matrices(self, tipo_clave: str | None = None) -> list[dict]:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).con_matrices(self._api._pid, tipo_clave)

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).buscar_por_hash(hash_val, self._api._pid)

    def recalcular_proyecto(self) -> dict:
        from backend.database.repos import RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        with self._api._ds.transaccion():
            resultado = RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return resultado

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).donde_se_usa(insumo_id)

    def reindexar_proyecto(self) -> None:
        """Recalcula wbs/nivel de todo el árbol desde padre_id+orden (ver
        NodoRepo.reindexar()). Útil para proyectos con wbs desactualizado
        (ej. importados con una versión anterior que dejaba el código
        crudo de OPUS en vez de "1.1", "1.1.3"…)."""
        from backend.database.repos import NodoRepo
        from backend.database.event_bus import ProyectoRecalculado
        with self._api._ds.transaccion():
            NodoRepo(self._api._conn).reindexar(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def proyecto_guardar(self, campos: dict) -> None:
        self._api._ds.actualizar("proyectos", self._api._pid, **campos)

    def proyecto_leer(self) -> dict:
        from backend.database.repos import ProyectoRepo
        reg = ProyectoRepo(self._api._conn).buscar(self._api._pid)
        return dict(reg) if reg else {}

    # ── APU ──────────────────────────────────────────────────────────

    def resolver_matriz(self, nodo_id: int | None, insumo_id: int | None) -> tuple[int | None, str]:
        from backend.database.repos import NodoRepo, InsumoRepo, ApuMatricesRepo
        conn = self._api._conn

        if nodo_id is not None:
            nodo = NodoRepo(conn).buscar(nodo_id)
            if not nodo or nodo.get("proyecto_id") != self._api._pid:
                return None, ""
            insumo_id_nodo = nodo.get("insumo_id")
            if insumo_id_nodo:
                insumo = InsumoRepo(conn).buscar(insumo_id_nodo)
                if insumo and insumo.get("es_compuesto"):
                    neg_id = -insumo["id"]
                    if ApuMatricesRepo(conn).por_matriz(neg_id):
                        return neg_id, nodo.get("descripcion") or ""
            matriz_id = nodo["id"]
            descripcion = nodo.get("descripcion") or ""
            if ApuMatricesRepo(conn).por_matriz(matriz_id):
                return matriz_id, descripcion
            return None, ""

        if insumo_id is not None:
            insumo = InsumoRepo(conn).buscar(insumo_id)
            if insumo and insumo.get("es_compuesto"):
                matriz_id = -insumo["id"]
                descripcion = insumo.get("descripcion") or insumo.get("descripcion_corta") or ""
                return matriz_id, descripcion
            return None, ""

        return None, ""

    def apu_actualizar_operador(self, comp_id: int, operador: str) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        if operador not in ('*', '/'):
            raise ValueError("Operador debe ser '*' o '/'")
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.actualizar("apu_matrices", comp_id, operador=operador)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def apu_agregar_componente(self, matriz_id: int, insumo_id: int,
                                valor: float = 1.0, operador: str = "*") -> int:
        # Lógica única en DataService (Fase B R1).
        return self._api._ds.apu_agregar_componente(
            matriz_id, insumo_id, valor, operador,
            proyecto_id=self._api._pid)

    def apu_actualizar_valor(self, comp_id: int, valor: float,
                              formula: str | None = None) -> None:
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
        from backend.database.repos import ApuMatricesRepo, RecalculoRepo
        if valor == 0:
            comp = ApuMatricesRepo(self._api._conn).buscar(comp_id)
            if comp and comp["operador"] == "/":
                raise ValueError("La cantidad no puede ser cero con operador división (división por cero)")
        with self._api._ds.transaccion():
            campos = {"valor": valor}
            if formula is not None:
                campos["formula"] = formula
            self._api._ds.actualizar("apu_matrices", comp_id, **campos)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def apu_reasignar_componente(self, comp_id: int, nuevo_insumo_id: int) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.actualizar("apu_matrices", comp_id, insumo_id=nuevo_insumo_id)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def apu_actualizar_precio_componente(self, insumo_id: int, precio: float) -> None:
        # No escribe en apu_matrices.precio (lo sobreescribe el recálculo);
        # delega en el insumo — la vía canónica.
        self._api.insumo_actualizar_precio(insumo_id, precio)

    def insumo_ids_con_apu(self) -> set[int]:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).ids_con_apu(self._api._pid)

    # ── VARIABLES DE FÓRMULA ─────────────────────────────────────────

    def variables_listar(self) -> list[dict]:
        from backend.database.repos import VariableFormulaRepo
        return VariableFormulaRepo(self._api._conn).por_proyecto(self._api._pid)

    def variables_crear(self, nombre: str, expresion: str, descripcion: str) -> int:
        import re
        if not re.match(r'^[A-Za-z_]\w*$', nombre):
            raise ValueError(
                f"'{nombre}' no es un nombre de variable válido. "
                "Debe empezar con letra o _ y contener solo letras, dígitos o _."
            )
        from backend.database.repos import VariableFormulaRepo
        existente = VariableFormulaRepo(self._api._conn).buscar_por_nombre(self._api._pid, nombre)
        if existente:
            raise ValueError(f"Ya existe una variable con el nombre '{nombre}'")
        return self._api._ds.insertar(
            "variables_formula", proyecto_id=self._api._pid,
            nombre=nombre, expresion=expresion, descripcion=descripcion,
        )

    def variables_actualizar(self, variable_id: int, campos: dict) -> None:
        from backend.database.repos import VariableFormulaRepo
        repo = VariableFormulaRepo(self._api._conn)

        if "nombre" in campos:
            import re
            nuevo_nombre = campos["nombre"]
            if not re.match(r'^[A-Za-z_]\w*$', nuevo_nombre):
                raise ValueError(
                    f"'{nuevo_nombre}' no es un nombre de variable válido. "
                    "Debe empezar con letra o _ y contener solo letras, dígitos o _."
                )
            duplicado = repo.buscar_por_nombre(self._api._pid, nuevo_nombre)
            if duplicado and duplicado["id"] != variable_id:
                raise ValueError(f"Ya existe una variable con el nombre '{nuevo_nombre}'")

        if "expresion" in campos or "nombre" in campos:
            todas = repo.por_proyecto(self._api._pid)
            nuevas = {}
            for v in todas:
                key = v["nombre"]
                val = campos.get("expresion") if v["id"] == variable_id and "expresion" in campos else v.get("expresion", "")
                key_nuevo = campos.get("nombre") if v["id"] == variable_id and "nombre" in campos else key
                nuevas[key_nuevo] = val
            from backend.formulas import resolver_variables, ErrorFormula
            try:
                resolver_variables(nuevas)
            except ErrorFormula as e:
                raise ValueError(str(e))

        self._api._ds.actualizar("variables_formula", variable_id, **campos)

    def variables_eliminar(self, variable_id: int) -> dict:
        from decimal import Decimal
        from backend.database.repos import VariableFormulaRepo, ApuMatricesRepo, RecalculoRepo
        from backend.database.event_bus import ProyectoRecalculado
        from backend.formulas import (
            nombres_referenciados, sustituir_variable_eliminada,
            resolver_variables, evaluar_formula, ErrorFormula,
        )

        conn = self._api._conn
        pid = self._api._pid
        ds = self._api._ds

        repo = VariableFormulaRepo(conn)
        variable = repo.buscar(variable_id)
        if variable is None:
            raise ValueError(f"No existe la variable con id {variable_id}")
        nombre = variable["nombre"]

        todas = repo.por_proyecto(pid)
        expresiones = {v["nombre"]: v["expresion"] or "" for v in todas}
        try:
            resueltas = resolver_variables(expresiones)
            ultimo_valor = resueltas.get(nombre, Decimal(0))
            puede_sustituir = True
        except ErrorFormula:
            resueltas = {}
            ultimo_valor = None
            puede_sustituir = False

        afectadas: dict = {
            "variables": [], "conceptos": [], "componentes_apu": [],
            "omitido_por_error_previo": not puede_sustituir,
        }

        def _referencia(expr: str) -> bool:
            try:
                return nombre in nombres_referenciados(expr)
            except ErrorFormula:
                return False

        with ds.transaccion():
            if puede_sustituir:
                for v in todas:
                    if v["id"] == variable_id:
                        continue
                    expr = v["expresion"] or ""
                    if expr.strip() and _referencia(expr):
                        nueva_expr = sustituir_variable_eliminada(expr, nombre, ultimo_valor)
                        ds.actualizar("variables_formula", v["id"], expresion=nueva_expr)
                        afectadas["variables"].append(v["nombre"])

                from backend.database.repos import NodoRepo
                conceptos = NodoRepo(conn).con_formula_por_proyecto(pid)
                for row in conceptos:
                    if not _referencia(row["formula"]):
                        continue
                    nueva_formula = sustituir_variable_eliminada(row["formula"], nombre, ultimo_valor)
                    campos = {"formula": nueva_formula}
                    try:
                        campos["cantidad"] = float(evaluar_formula(nueva_formula, resueltas))
                    except ErrorFormula:
                        pass
                    ds.actualizar("estructura_presupuesto", row["id"], **campos)
                    afectadas["conceptos"].append(row["id"])

                for row in ApuMatricesRepo(conn).con_formula_por_proyecto(pid):
                    if not _referencia(row["formula"]):
                        continue
                    nueva_formula = sustituir_variable_eliminada(row["formula"], nombre, ultimo_valor)
                    campos = {"formula": nueva_formula}
                    try:
                        campos["valor"] = float(evaluar_formula(nueva_formula, resueltas))
                    except ErrorFormula:
                        pass
                    ds.actualizar("apu_matrices", row["id"], **campos)
                    afectadas["componentes_apu"].append(row["id"])

            ds.eliminar("variables_formula", variable_id)

            if afectadas["conceptos"] or afectadas["componentes_apu"]:
                RecalculoRepo(conn).recalcular_proyecto(pid)

        if afectadas["conceptos"] or afectadas["componentes_apu"]:
            ds.emitir(ProyectoRecalculado(pid))
        return afectadas

    def variables_resueltas(self) -> dict:
        from backend.database.repos import VariableFormulaRepo
        from backend.formulas import resolver_variables, ErrorFormula
        variables = {
            v["nombre"]: v["expresion"] or ""
            for v in VariableFormulaRepo(self._api._conn).por_proyecto(self._api._pid)
        }
        try:
            return resolver_variables(variables)
        except ErrorFormula as e:
            raise ValueError(str(e))

    def formula_evaluar(self, expr: str):
        from backend.formulas import evaluar_formula, ErrorFormula
        try:
            return evaluar_formula(expr, self.variables_resueltas())
        except ErrorFormula as e:
            raise ValueError(str(e))

    def apu(self, nodo_id: int | None, insumo_id: int | None) -> dict | None:
        from backend.database.repos import ApuMatricesRepo
        matriz_id, descripcion = self.resolver_matriz(nodo_id, insumo_id)
        if matriz_id is None:
            return None
        data = ApuMatricesRepo(self._api._conn).con_detalle(matriz_id)
        ids_con_apu = self._api.insumo_ids_con_apu()
        return _enriquecer_detalle_apu(
            {"matriz_id": matriz_id, "descripcion": descripcion, **data},
            ids_con_apu,
        )

    # ── GENERADORES ──────────────────────────────────────────────────

    def generadores_por_concepto(self, concepto_id: int | None) -> list[dict]:
        from backend.database.repos.generador import GeneradorRepo
        return GeneradorRepo(self._api._conn).listar_por_concepto(self._api._pid, concepto_id)

    def generador_por_id(self, generador_id: int) -> dict | None:
        from backend.database.repos.generador import GeneradorRepo
        return GeneradorRepo(self._api._conn).buscar(generador_id)

    def generador_crear(self, nombre: str, concepto_id: int | None, unidad: str | None) -> int:
        campos = {"proyecto_id": self._api._pid, "nombre": nombre, "concepto_id": concepto_id}
        if unidad:
            campos["unidad"] = unidad
        return self._api._ds.insertar("generadores", **campos)

    def generador_actualizar_cad(self, generador_id: int, path: str | None) -> None:
        self._api._ds.actualizar("generadores", generador_id, cad_archivo_path=path)

    def generador_renglones(self, generador_id: int) -> list[dict]:
        from backend.database.repos.generador import GeneradorRepo
        return GeneradorRepo(self._api._conn).listar_renglones(generador_id)

    def generador_renglon_guardar(self, generador_id: int, renglon_id: int | None, campos: dict) -> int:
        return self._api._ds.guardar_renglon_generador(
            generador_id, renglon_id=renglon_id, **campos
        )

    def generador_renglon_eliminar(self, renglon_id: int) -> None:
        self._api._ds.eliminar_renglon_generador(renglon_id)

    def generador_mover_renglones(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool) -> bool:
        return self._api._ds.mover_renglones_generador(ids, nuevo_generador_id, antes_de_id, copiar)

    def generador_reasignar(self, generador_id: int,
                            nuevo_concepto_id: int | None,
                            usuario_id: int = 1) -> None:
        self._api._ds.reasignar_generador(generador_id, nuevo_concepto_id, usuario_id)

    # ── INDIRECTOS ───────────────────────────────────────────────────

    def indirectos_lista(self, tipo: str | None = None) -> list[dict]:
        from backend.database.repos import IndirectoRepo
        return IndirectoRepo(self._api._conn).todos(self._api._pid, tipo)

    def indirectos_guardar(self, registro_id: int, campos: dict) -> None:
        self._api._ds.actualizar("indirectos", registro_id, **campos)

    def indirectos_insertar(self, campos: dict) -> int:
        from backend.database.event_bus import IndirectoActualizado
        campos = dict(campos)
        campos.setdefault("proyecto_id", self._api._pid)
        nuevo_id = self._api._ds.insertar("indirectos", **campos)
        self._api._ds.emitir(IndirectoActualizado(self._api._pid))
        return nuevo_id

    def indirectos_eliminar(self, registro_id: int) -> None:
        from backend.database.event_bus import IndirectoActualizado
        self._api._ds.eliminar("indirectos", registro_id)
        self._api._ds.emitir(IndirectoActualizado(self._api._pid))

    def indirectos_calcular_totales(self) -> dict:
        from backend.database.repos import IndirectoRepo
        from backend.database.event_bus import IndirectoActualizado
        with self._api._ds.transaccion():
            resultado = IndirectoRepo(self._api._conn).calcular_totales(self._api._pid)
        self._api._ds.emitir(IndirectoActualizado(self._api._pid))
        return resultado

    def indirectos_cargar_plantilla(self, tipo: str) -> int:
        from backend.database.repos import IndirectoRepo, PLANTILLA_CAMPO, PLANTILLA_OFICINA
        from backend.database.event_bus import IndirectoActualizado
        plantilla = PLANTILLA_CAMPO if tipo == "campo" else PLANTILLA_OFICINA
        existentes = {
            (i["concepto"], i["categoria"])
            for i in IndirectoRepo(self._api._conn).todos(self._api._pid, tipo)
        }
        orden = 0
        insertados = 0
        with self._api._ds.transaccion():
            for cat, concepto, periodo, importe in plantilla:
                orden += 1
                if (concepto, cat) not in existentes:
                    self._api._ds.insertar(
                        "indirectos",
                        proyecto_id=self._api._pid,
                        tipo=tipo,
                        categoria=cat,
                        orden=orden,
                        concepto=concepto,
                        periodo_dias=periodo,
                        importe=importe,
                        pct_participacion=100.0,
                        total=0.0,
                        activo=1,
                        limpiar_redo=(insertados == 0),
                    )
                    insertados += 1
        if insertados:
            self._api._ds.emitir(IndirectoActualizado(self._api._pid))
        return insertados

    def indirectos_aplicar_a_sobrecosto(self) -> dict:
        from backend.database.repos import IndirectoRepo, FactoresSobrecostoRepo
        from backend.database.event_bus import IndirectoActualizado

        repo = IndirectoRepo(self._api._conn)
        with self._api._ds.transaccion():
            resultado_totales = repo.calcular_totales(self._api._pid)

        costo_directo = repo.costo_directo_total(self._api._pid)
        total_campo = repo.total_por_tipo(self._api._pid, "campo")
        total_oficina = repo.total_por_tipo(self._api._pid, "oficina")

        if costo_directo <= 0:
            raise ValueError(
                "No se puede calcular el %CI: el costo directo del "
                "presupuesto es 0. Captura conceptos con insumo y "
                "cantidad antes de aplicar los indirectos a los "
                "sobrecostos."
            )

        pct_campo = round(total_campo / costo_directo * 100, 4)
        pct_oficina = round(total_oficina / costo_directo * 100, 4)

        actuales = FactoresSobrecostoRepo(self._api._conn).obtener(self._api._pid) or {}
        valores = {
            "pct_indirectos_campo": pct_campo,
            "pct_indirectos_oficina": pct_oficina,
            "pct_financiamiento": actuales.get("pct_financiamiento") or 0,
            "pct_utilidad": actuales.get("pct_utilidad") or 0,
            "pct_cargos_adicionales": actuales.get("pct_cargos_adicionales") or 0,
        }
        # self._api.factores_sobrecosto_guardar() (no self._api._backend
        # directo) para que respete el backend activo del Api completo —
        # en la práctica siempre coincide con éste (_BackendLocal), pero
        # así no hay que asumirlo.
        factor_total = self._api.factores_sobrecosto_guardar(valores)

        self._api._ds.emitir(IndirectoActualizado(self._api._pid))
        return {
            "pct_indirectos_campo": pct_campo,
            "pct_indirectos_oficina": pct_oficina,
            "costo_directo_total": costo_directo,
            "total_indirectos_campo": total_campo,
            "total_indirectos_oficina": total_oficina,
            "factor_total": factor_total,
            "duracion_obra_dias": resultado_totales["duracion_obra_dias"],
            "afectados_por_duracion_faltante": resultado_totales["afectados_por_duracion_faltante"],
        }

    # ── PRESUPUESTO ────────────────────────────────────────────────

    def presupuesto_arbol(self, extra: bool = False) -> list[dict]:
        from backend.database.repos import NodoRepo
        return NodoRepo(self._api._conn).arbol(self._api._pid, extra=extra)

    def nodo_total(self, nodo_id: int) -> float:
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._api._conn).buscar(nodo_id)
        return (nodo.get("total") or 0) if nodo else 0

    def concepto_actualizar_cantidad(self, concepto_id: int, cantidad: float,
                                      formula: str | None = None) -> None:
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
        from backend.database.repos import NodoRepo
        with self._api._ds.transaccion():
            campos = {"cantidad": cantidad}
            if formula is not None:
                campos["formula"] = formula
            self._api._ds.actualizar("estructura_presupuesto", concepto_id, **campos)
            NodoRepo(self._api._conn).recalcular_desde(concepto_id)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def concepto_reasignar_insumo(self, concepto_id: int, nuevo_insumo_id: int) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.actualizar("estructura_presupuesto", concepto_id,
                                      insumo_id=nuevo_insumo_id)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def nodo_descripcion_actual(self, nodo_id: int) -> str:
        from backend.database.repos import NodoRepo, InsumoRepo
        nodo = NodoRepo(self._api._conn).buscar(nodo_id)
        if not nodo:
            return ""
        if nodo.get("insumo_id"):
            insumo = InsumoRepo(self._api._conn).buscar(nodo["insumo_id"])
            return (insumo or {}).get("descripcion", "") or ""
        return nodo.get("descripcion", "") or ""

    def concepto_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._api._conn).buscar(nodo_id)
        if nodo and nodo.get("insumo_id"):
            # Reutiliza la lógica de insumo (hash/colisión) a través de Api
            # para no duplicarla aquí. Api la delegará al backend activo.
            self._api.insumo_actualizar_descripcion(nodo["insumo_id"], descripcion)

    def concepto_actualizar_unidad(self, nodo_id: int, unidad: str) -> None:
        from backend.database.repos import NodoRepo
        nodo = NodoRepo(self._api._conn).buscar(nodo_id)
        if nodo and nodo.get("insumo_id"):
            self._api._ds.actualizar("insumos", nodo["insumo_id"], unidad=unidad)

    def agrupador_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        self._api._ds.actualizar("estructura_presupuesto", nodo_id, descripcion=descripcion)

    def eliminar_nodo(self, nodo_id: int) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.eliminar("estructura_presupuesto", nodo_id)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def agregar_nodo(self, tipo: str, padre_id: int | None = None,
                      descripcion: str = "", insumo_id: int | None = None,
                      cantidad: float | None = None, orden: float | None = None,
                      antes_de: int | None = None, es_extra: bool = False) -> int:
        # Lógica única en DataService (Fase B R1).
        return self._api._ds.agregar_nodo(
            self._api._pid, tipo, padre_id, descripcion, insumo_id,
            cantidad, orden, antes_de, es_extra)

    def todos_concepto_ids(self) -> list[int]:
        from backend.database.repos import NodoRepo
        return NodoRepo(self._api._conn).ids_por_tipo(self._api._pid, tipo="concepto")

    def conceptos_planos(self) -> list[dict]:
        from backend.database.repos import NodoRepo
        return NodoRepo(self._api._conn).todos(self._api._pid, tipo="concepto")

    # ── EXPLOSIÓN ──────────────────────────────────────────────────

    def explotar(self, concepto_ids: list[int], nivel: str, tipos_ids: list[int]) -> tuple[list[dict], float]:
        from backend.database.repos import ExplosionRepo
        return ExplosionRepo(self._api._conn).calcular(
            proyecto_id=self._api._pid,
            concepto_ids=concepto_ids,
            nivel=nivel,
            tipos_ids=tipos_ids,
        )

    def conceptos_bajo_nodo(self, nodo_id: int) -> list[int]:
        from backend.database.repos import NodoRepo
        descendientes = NodoRepo(self._api._conn).descendientes(nodo_id)
        return [d["id"] for d in descendientes if d.get("tipo") == "concepto"]

    # ── CATÁLOGOS (FAMILIAS / SUBFAMILIAS) ─────────────────────────

    def familias(self) -> list[dict]:
        from backend.database.repos import FamiliaRepo
        return FamiliaRepo(self._api._conn).todas()

    def familia_insertar(self, nombre: str) -> int:
        return self._api._ds.insertar("familias", nombre=nombre)

    def subfamilias(self, familia_id: int) -> list[dict]:
        from backend.database.repos import SubfamiliaRepo
        return SubfamiliaRepo(self._api._conn).por_familia(familia_id)

    def subfamilia_insertar(self, familia_id: int, nombre: str) -> int:
        return self._api._ds.insertar("subfamilias", familia_id=familia_id, nombre=nombre)

    # ── INSUMOS (MUTACIÓN) ─────────────────────────────────────

    def insumo_actualizar_descripcion(self, insumo_id: int, descripcion: str, usuario_id: int = 1) -> None:
        from backend.database.core import generar_hash
        descripcion = descripcion.strip()
        if not descripcion:
            raise ValueError("La descripción no puede estar vacía")
        nuevo_hash = generar_hash(descripcion)
        from backend.database.repos import InsumoRepo
        existente = InsumoRepo(self._api._conn).buscar_por_hash(nuevo_hash, self._api._pid)
        if existente and existente["id"] != insumo_id:
            raise ValueError(
                f"Ya existe un insumo con esa descripción: "
                f"[{existente['id']}] {existente['descripcion']}"
            )
        self._api._ds.actualizar("insumos", insumo_id, usuario_id=usuario_id,
                                  descripcion=descripcion, hash=nuevo_hash)

    def insumo_actualizar_precio(self, insumo_id: int, precio: float, usuario_id: int = 1) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        if precio < 0:
            raise ValueError("El precio no puede ser negativo")
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.actualizar("insumos", insumo_id, usuario_id=usuario_id,
                                      costo_mn=precio, costo_directo=precio)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def insumo_actualizar_precios(self, insumo_id: int, costo_mn: float, costo_me: float, usuario_id: int = 1) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        if costo_mn < 0 or costo_me < 0:
            raise ValueError("Los precios no pueden ser negativos")
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.actualizar("insumos", insumo_id, usuario_id=usuario_id,
                                      costo_mn=costo_mn, costo_directo=costo_mn,
                                      costo_me=costo_me)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def insumo_actualizar_campo(self, insumo_id: int, campo: str, valor, usuario_id: int = 1) -> None:
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.actualizar("insumos", insumo_id, usuario_id=usuario_id, **{campo: valor})
            if campo == "costo_final":
                RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        if campo == "costo_final":
            from backend.database.event_bus import ProyectoRecalculado
            self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    def insumo_insertar(self, tipo_id: int, descripcion: str, descripcion_corta: str | None = None,
                         unidad: str | None = None, costo: float = 0.0, costo_me: float = 0.0,
                         es_compuesto: int = 0, familia_id: int | None = None,
                         subfamilia_id: int | None = None, usuario_id: int = 1) -> int:
        from backend.database.core import generar_hash
        nuevo_hash = generar_hash(descripcion) if descripcion else None
        from backend.database.repos import InsumoRepo
        if nuevo_hash:
            existente = InsumoRepo(self._api._conn).buscar_por_hash(nuevo_hash, self._api._pid)
            if existente:
                raise ValueError(
                    f"Ya existe un insumo con esa descripción: "
                    f"[{existente['id']}] {existente['descripcion']}"
                )
        campos = dict(
            proyecto_id=self._api._pid,
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
        return self._api._ds.insertar("insumos", usuario_id=usuario_id, **campos)

    def insumo_por_id(self, insumo_id: int) -> dict | None:
        from backend.database.repos import InsumoRepo
        return InsumoRepo(self._api._conn).buscar(insumo_id)

    def eliminar_insumo(self, insumo_id: int) -> None:
        from backend.database.event_bus import ProyectoRecalculado
        from backend.database.repos import RecalculoRepo
        with self._api._ds.transaccion():
            self._api._ds.eliminar("insumos", insumo_id)
            RecalculoRepo(self._api._conn).recalcular_proyecto(self._api._pid)
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))

    # ── UNDO / SESIÓN ──────────────────────────────────────────

    def deshacer(self, usuario_id: int = 1) -> bool:
        return self._api._ds.deshacer(usuario_id, proyecto_id=self._api._pid)

    def rehacer(self, usuario_id: int = 1) -> bool:
        return self._api._ds.rehacer(usuario_id, proyecto_id=self._api._pid)

    def iniciar_sesion_undo(self) -> str | None:
        return self._api._ds.iniciar_sesion()

    def cerrar_sesion_undo(self) -> None:
        self._api._ds.cerrar_sesion()

    # ── CICLO DE VIDA REMOTO ────────────────────────────────────

    def descargar_proyecto(self) -> bool:
        # Local: nada que liberar (la conexión la administra la ventana).
        return True

    def estadisticas_proyecto(self) -> dict:
        from backend.database.repos.diagnostico import DiagnosticoRepo
        return DiagnosticoRepo(self._api._conn).estadisticas(self._api._pid)

    # ── ADJUNTOS (Fase E: CAD remoto) ──────────────────────────
    # En local es FS directo al sidecar (misma convención que el mixin).

    def _adjuntos_dir(self):
        from pathlib import Path
        from backend.database.db import Rutas
        base = Path(self._api._db_path).stem
        d = Rutas.proyectos() / f"{base}_adjuntos"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def adjuntos_listar(self) -> list[str]:
        d = self._adjuntos_dir()
        return sorted(p.name for p in d.iterdir() if p.is_file())

    def adjunto_guardar(self, filename: str, contenido: bytes) -> None:
        import os
        (self._adjuntos_dir() / os.path.basename(filename)).write_bytes(contenido)

    def adjunto_leer(self, filename: str) -> bytes | None:
        import os
        ruta = self._adjuntos_dir() / os.path.basename(filename)
        return ruta.read_bytes() if ruta.is_file() else None

    # ── HELPERS LOCALES ────────────────────────────────────────

    def concepto_cantidad(self, concepto_id: int) -> float:
        from backend.database.repos.presupuesto import NodoRepo
        row = NodoRepo(self._api._conn).buscar(concepto_id)
        return float(row["cantidad"]) if row and row.get("cantidad") else 0.0

    def concepto_actualizar(self, concepto_id: int, **campos) -> None:
        self._api._ds.actualizar("estructura_presupuesto", concepto_id, **campos)

    def campo_valor(self, tabla: str, campo: str, registro_id: int) -> dict | None:
        from backend.database.repos import NodoRepo, ApuMatricesRepo, InsumoRepo
        repos = {
            "estructura_presupuesto": NodoRepo,
            "apu_matrices": ApuMatricesRepo,
            "insumos": InsumoRepo,
        }
        cls = repos.get(tabla)
        if not cls:
            return None
        return cls(self._api._conn).buscar(registro_id)

    def unificar_matrices_apu(self) -> int:
        # Lógica única en DataService (R1) — también la usan el servidor
        # y la apertura de proyecto.
        return self._api._ds.unificar_matrices_apu(self._api._pid)


class _BackendHTTP:
    """Implementación vía servidor embebido (ApiCliente)."""

    def __init__(self, api: "Api"):
        self._api = api
        # Fase D: token de sesión undo en red (None = sin sesión).
        self._sesion_token: str | None = None

    # ── FACTORES DE SOBRECOSTO ──────────────────────────────────────

    def factores_sobrecosto_obtener(self) -> dict:
        return self._api._http()._get("/factores_sobrecosto")

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        # El endpoint ya recalcula en servidor (Fase B: quita 2do recalc redundante).
        r = self._api._http()._post("/factores_sobrecosto", json={"valores": valores})
        return r["factor_total"]

    # ── INSUMOS ──────────────────────────────────────────────────────

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        params = {}
        if tipo_clave:
            params["tipo"] = tipo_clave
        return self._api._http()._get("/insumos", params=params)

    def insumos_con_matrices(self, tipo_clave: str | None = None) -> list[dict]:
        params = {}
        if tipo_clave:
            params["tipo"] = tipo_clave
        return self._api._http()._get("/insumos_con_matrices", params=params)

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        try:
            return self._api._http()._get(f"/insumo_por_hash/{hash_val}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def recalcular_proyecto(self) -> dict:
        self._api._http().recalcular()
        return {}

    def reindexar_proyecto(self) -> None:
        self._api._http().reindexar()

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        return self._api._http()._get(f"/rastrear/{insumo_id}")

    def proyecto_guardar(self, campos: dict) -> None:
        # "proyectos" ya es una entidad registrada en crear_registry() —
        # el /actualizar genérico la acepta sin necesitar ruta propia.
        self._api._http().actualizar("proyectos", self._api._pid, **campos, sesion_token=self._sesion_token)

    def proyecto_leer(self) -> dict:
        return self._api._http()._get("/proyecto")

    # ── VARIABLES DE FÓRMULA ─────────────────────────────────────────
    # Todas con endpoints dedicados: crear/actualizar necesitan la misma
    # validación de formato/duplicados/ciclo que el lado local (no se
    # puede confiar esa lógica solo al cliente), y variables_resueltas()
    # trabaja con Decimal, que no es JSON-serializable — el servidor lo
    # manda como string y aquí se reconstruye.

    def variables_listar(self) -> list[dict]:
        return self._api._http()._get("/variables")

    def variables_crear(self, nombre: str, expresion: str, descripcion: str) -> int:
        # Fase D: 422→ValueError lo traduce ApiCliente._post (R5).
        r = self._api._http()._post("/variables", json={
            "nombre": nombre, "expresion": expresion, "descripcion": descripcion,
        })
        return r["id"]

    def variables_actualizar(self, variable_id: int, campos: dict) -> None:
        self._api._http()._post(f"/variables/{variable_id}", json={"campos": campos})

    def variables_eliminar(self, variable_id: int) -> dict:
        return self._api._http()._post(f"/variables/{variable_id}/eliminar")

    def variables_resueltas(self) -> dict:
        from decimal import Decimal
        crudo = self._api._http()._get("/variables/resueltas")
        return {k: Decimal(v) for k, v in crudo.items()}

    def formula_evaluar(self, expr: str):
        from decimal import Decimal
        r = self._api._http()._post("/variables/evaluar", json={"expresion": expr})
        return Decimal(r["resultado"])

    # ── APU ──────────────────────────────────────────────────────────

    def apu(self, nodo_id: int | None, insumo_id: int | None) -> dict | None:
        params = {}
        if nodo_id is not None:
            params["nodo_id"] = nodo_id
        if insumo_id is not None:
            params["insumo_id"] = insumo_id
        data = self._api._http()._get("/apu_completo", params=params)
        if data.get("matriz_id") is None:
            return None
        ids_con_apu = self._api.insumo_ids_con_apu()
        return _enriquecer_detalle_apu(data, ids_con_apu)

    def resolver_matriz(self, nodo_id: int | None, insumo_id: int | None) -> tuple[int | None, str]:
        params = {}
        if nodo_id is not None:
            params["nodo_id"] = nodo_id
        if insumo_id is not None:
            params["insumo_id"] = insumo_id
        data = self._api._http()._get("/apu_completo", params=params)
        return data.get("matriz_id"), data.get("descripcion", "")

    def apu_actualizar_operador(self, comp_id: int, operador: str) -> None:
        if operador not in ('*', '/'):
            raise ValueError("Operador debe ser '*' o '/'")
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "apu_matrices", "registro_id": comp_id,
            "campos": {"operador": operador}})

    def apu_agregar_componente(self, matriz_id: int, insumo_id: int,
                                valor: float = 1.0, operador: str = "*") -> int:
        # Fase B: orden + insert + recalc atómicos en servidor.
        r = self._api._http()._post("/apu/agregar_componente", json={
            "sesion_token": self._sesion_token,
            "matriz_id": matriz_id, "insumo_id": insumo_id,
            "valor": valor, "operador": operador})
        return r["id"]

    def apu_actualizar_valor(self, comp_id: int, valor: float,
                              formula: str | None = None) -> None:
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
        if valor == 0:
            comp = self._api._http().buscar("apu_matrices", comp_id)
            if comp and comp["operador"] == "/":
                raise ValueError("La cantidad no puede ser cero con operador división (división por cero)")
        campos = {"valor": valor}
        if formula is not None:
            campos["formula"] = formula
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "apu_matrices", "registro_id": comp_id, "campos": campos})

    def apu_reasignar_componente(self, comp_id: int, nuevo_insumo_id: int) -> None:
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "apu_matrices", "registro_id": comp_id,
            "campos": {"insumo_id": nuevo_insumo_id}})

    def apu_actualizar_precio_componente(self, insumo_id: int, precio: float) -> None:
        self._api.insumo_actualizar_precio(insumo_id, precio)

    def insumo_ids_con_apu(self) -> set[int]:
        return set(self._api._http()._get("/insumos_con_apu"))

    # ── GENERADORES ──────────────────────────────────────────────────
    # crear/actualizar_cad reusan insertar()/actualizar() genéricos
    # ("generadores" ya es entidad registrada). El resto son operaciones
    # a medida (guardar_renglon_generador recalcula cantidad_total y
    # cascada, no es un CRUD de una fila) — endpoints dedicados.

    def generadores_por_concepto(self, concepto_id: int | None) -> list[dict]:
        params = {}
        if concepto_id is not None:
            params["concepto_id"] = concepto_id
        return self._api._http()._get("/generadores", params=params)

    def generador_por_id(self, generador_id: int) -> dict | None:
        return self._api._http()._get(f"/generadores/{generador_id}")

    def generador_crear(self, nombre: str, concepto_id: int | None, unidad: str | None) -> int:
        campos = {"proyecto_id": self._api._pid, "nombre": nombre, "concepto_id": concepto_id}
        if unidad:
            campos["unidad"] = unidad
        return self._api._http().insertar("generadores", **campos, sesion_token=self._sesion_token)

    def generador_actualizar_cad(self, generador_id: int, path: str | None) -> None:
        self._api._http().actualizar("generadores", generador_id, cad_archivo_path=path, sesion_token=self._sesion_token)

    def generador_renglones(self, generador_id: int) -> list[dict]:
        return self._api._http()._get(f"/generadores/{generador_id}/renglones")

    def generador_renglon_guardar(self, generador_id: int, renglon_id: int | None, campos: dict) -> int:
        r = self._api._http()._post(
            f"/generadores/{generador_id}/renglon",
            json={"renglon_id": renglon_id, "campos": campos},
        )
        return r["renglon_id"]

    def generador_renglon_eliminar(self, renglon_id: int) -> None:
        self._api._http()._post(f"/generadores/renglon/{renglon_id}/eliminar")

    def generador_mover_renglones(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool) -> bool:
        r = self._api._http()._post(
            "/generadores/mover_renglones",
            json={"ids": ids, "nuevo_generador_id": nuevo_generador_id, "antes_de_id": antes_de_id, "copiar": copiar},
        )
        return r["ok"]

    def generador_reasignar(self, generador_id: int,
                            nuevo_concepto_id: int | None,
                            usuario_id: int = 1) -> None:
        # Endpoint propio: ds.reasignar_generador recalcula ambos conceptos
        # y captura historial — no es un CRUD de fila simple.
        self._api._http()._post(
            f"/generadores/{generador_id}/reasignar",
            json={"concepto_id": nuevo_concepto_id, "usuario_id": usuario_id},
        )

    # ── INDIRECTOS ───────────────────────────────────────────────────
    # guardar/insertar/eliminar reusan actualizar()/insertar()/eliminar()
    # genéricos de ApiCliente — "indirectos" ya es una entidad registrada
    # en crear_registry() (Hallazgo 1), así que el servidor la acepta tal
    # cual en /actualizar, /insertar, /eliminar sin necesitar rutas nuevas.
    # Solo las operaciones que NO son CRUD de una fila (lista con filtro,
    # cálculo masivo, plantilla, %CI→sobrecosto) necesitan endpoints
    # dedicados — igual que ya pasa con factores_sobrecosto_guardar().

    def indirectos_lista(self, tipo: str | None = None) -> list[dict]:
        params = {}
        if tipo:
            params["tipo"] = tipo
        return self._api._http()._get("/indirectos", params=params)

    def indirectos_guardar(self, registro_id: int, campos: dict) -> None:
        self._api._http().actualizar("indirectos", registro_id, **campos, sesion_token=self._sesion_token)

    def indirectos_insertar(self, campos: dict) -> int:
        # Misma inyección que _BackendLocal — sin esto, un indirecto
        # agregado sin proyecto_id explícito viola el NOT NULL de la
        # columna server-side y el insert falla con 500 (encontrado por
        # el test de paridad local-vs-HTTP antes de dar esto por bueno).
        campos = dict(campos)
        campos.setdefault("proyecto_id", self._api._pid)
        return self._api._http().insertar("indirectos", **campos, sesion_token=self._sesion_token)

    def indirectos_eliminar(self, registro_id: int) -> None:
        self._api._http().eliminar("indirectos", registro_id, sesion_token=self._sesion_token)

    def indirectos_calcular_totales(self) -> dict:
        return self._api._http()._post("/indirectos/calcular_totales")

    def indirectos_cargar_plantilla(self, tipo: str) -> int:
        r = self._api._http()._post("/indirectos/cargar_plantilla", json={"tipo": tipo})
        return r["insertados"]

    def indirectos_aplicar_a_sobrecosto(self) -> dict:
        return self._api._http()._post("/indirectos/aplicar_a_sobrecosto")

    # ── PRESUPUESTO ────────────────────────────────────────────────

    def presupuesto_arbol(self, extra: bool = False) -> list[dict]:
        return self._api._http()._get("/arbol", params={"extra": extra})

    def nodo_total(self, nodo_id: int) -> float:
        nodo = self._api._http().buscar("estructura_presupuesto", nodo_id)
        return (nodo.get("total") or 0) if nodo else 0

    def concepto_actualizar_cantidad(self, concepto_id: int, cantidad: float,
                                      formula: str | None = None) -> None:
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
        campos = {"cantidad": cantidad}
        if formula is not None:
            campos["formula"] = formula
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "estructura_presupuesto", "registro_id": concepto_id, "campos": campos})

    def concepto_reasignar_insumo(self, concepto_id: int, nuevo_insumo_id: int) -> None:
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "estructura_presupuesto", "registro_id": concepto_id,
            "campos": {"insumo_id": nuevo_insumo_id}})

    def nodo_descripcion_actual(self, nodo_id: int) -> str:
        nodo = self._api._http().buscar("estructura_presupuesto", nodo_id)
        if not nodo:
            return ""
        if nodo.get("insumo_id"):
            insumo = self._api._http().buscar("insumos", nodo["insumo_id"])
            return (insumo or {}).get("descripcion", "") or ""
        return nodo.get("descripcion", "") or ""

    def concepto_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        nodo = self._api._http().buscar("estructura_presupuesto", nodo_id)
        if nodo and nodo.get("insumo_id"):
            self._api.insumo_actualizar_descripcion(nodo["insumo_id"], descripcion)

    def concepto_actualizar_unidad(self, nodo_id: int, unidad: str) -> None:
        nodo = self._api._http().buscar("estructura_presupuesto", nodo_id)
        if nodo and nodo.get("insumo_id"):
            self._api._http().actualizar("insumos", nodo["insumo_id"], unidad=unidad, sesion_token=self._sesion_token)
    
    def agrupador_actualizar_descripcion(self, nodo_id: int, descripcion: str) -> None:
        self._api._http().actualizar("estructura_presupuesto", nodo_id, descripcion=descripcion, sesion_token=self._sesion_token)

    def eliminar_nodo(self, nodo_id: int) -> None:
        self._api._http()._post("/eliminar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "estructura_presupuesto", "registro_id": nodo_id})

    def agregar_nodo(self, tipo: str, padre_id: int | None = None,
                      descripcion: str = "", insumo_id: int | None = None,
                      cantidad: float | None = None, orden: float | None = None,
                      antes_de: int | None = None, es_extra: bool = False) -> int:
        # Fase B: orden + insert + reindex + recalc atómicos en servidor.
        r = self._api._http()._post("/agregar_nodo", json={
            "sesion_token": self._sesion_token,
            "tipo": tipo, "padre_id": padre_id, "descripcion": descripcion or "",
            "insumo_id": insumo_id, "cantidad": cantidad, "orden": orden,
            "antes_de": antes_de, "es_extra": es_extra})
        return r["id"]

    def todos_concepto_ids(self) -> list[int]:
        return self._api._http()._get("/todos_concepto_ids")

    def conceptos_planos(self) -> list[dict]:
        return self._api._http()._get("/conceptos_planos")

    # ── EXPLOSIÓN ──────────────────────────────────────────────────

    def explotar(self, concepto_ids: list[int], nivel: str, tipos_ids: list[int]) -> tuple[list[dict], float]:
        r = self._api._http()._post("/explotar", json={
            "concepto_ids": concepto_ids,
            "nivel": nivel,
            "tipos_ids": tipos_ids,
        })
        return r["filas"], r["total"]

    def conceptos_bajo_nodo(self, nodo_id: int) -> list[int]:
        desc = self._api._http()._get(f"/descendientes/{nodo_id}")
        return [d["id"] for d in desc if d.get("tipo") == "concepto"]

    # ── CATÁLOGOS (FAMILIAS / SUBFAMILIAS) ─────────────────────────

    def familias(self) -> list[dict]:
        return self._api._http()._get("/familias")

    def familia_insertar(self, nombre: str) -> int:
        return self._api._http().insertar("familias", nombre=nombre, sesion_token=self._sesion_token)

    def subfamilias(self, familia_id: int) -> list[dict]:
        return self._api._http()._get(f"/subfamilias/{familia_id}")

    def subfamilia_insertar(self, familia_id: int, nombre: str) -> int:
        return self._api._http().insertar("subfamilias", familia_id=familia_id, nombre=nombre, sesion_token=self._sesion_token)

    # ── INSUMOS (MUTACIÓN) ─────────────────────────────────────

    def insumo_actualizar_descripcion(self, insumo_id: int, descripcion: str, usuario_id: int = 1) -> None:
        from backend.database.core import generar_hash
        descripcion = descripcion.strip()
        if not descripcion:
            raise ValueError("La descripción no puede estar vacía")
        nuevo_hash = generar_hash(descripcion)
        existente = self.insumo_por_hash(nuevo_hash)
        if existente and existente["id"] != insumo_id:
            raise ValueError(
                f"Ya existe un insumo con esa descripción: "
                f"[{existente['id']}] {existente['descripcion']}"
            )
        self._api._http().actualizar("insumos", insumo_id, descripcion=descripcion, hash=nuevo_hash, sesion_token=self._sesion_token, usuario_id=usuario_id)

    def insumo_actualizar_precio(self, insumo_id: int, precio: float, usuario_id: int = 1) -> None:
        if precio < 0:
            raise ValueError("El precio no puede ser negativo")
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "insumos", "registro_id": insumo_id,
            "usuario_id": usuario_id,
            "campos": {"costo_mn": precio, "costo_directo": precio}})

    def insumo_actualizar_precios(self, insumo_id: int, costo_mn: float, costo_me: float, usuario_id: int = 1) -> None:
        if costo_mn < 0 or costo_me < 0:
            raise ValueError("Los precios no pueden ser negativos")
        self._api._http()._post("/actualizar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "insumos", "registro_id": insumo_id,
            "usuario_id": usuario_id,
            "campos": {"costo_mn": costo_mn, "costo_directo": costo_mn, "costo_me": costo_me}})

    def insumo_actualizar_campo(self, insumo_id: int, campo: str, valor, usuario_id: int = 1) -> None:
        if campo == "costo_final":
            self._api._http()._post("/actualizar_y_recalcular", json={
                "sesion_token": self._sesion_token,
                "entidad": "insumos", "registro_id": insumo_id,
                "usuario_id": usuario_id, "campos": {campo: valor}})
        else:
            self._api._http().actualizar("insumos", insumo_id, **{campo: valor}, sesion_token=self._sesion_token, usuario_id=usuario_id)
    
    def insumo_insertar(self, tipo_id: int, descripcion: str, descripcion_corta: str | None = None,
                         unidad: str | None = None, costo: float = 0.0, costo_me: float = 0.0,
                         es_compuesto: int = 0, familia_id: int | None = None,
                         subfamilia_id: int | None = None, usuario_id: int = 1) -> int:
        from backend.database.core import generar_hash
        nuevo_hash = generar_hash(descripcion) if descripcion else None
        if nuevo_hash:
            existente = self.insumo_por_hash(nuevo_hash)
            if existente:
                raise ValueError(
                    f"Ya existe un insumo con esa descripción: "
                    f"[{existente['id']}] {existente['descripcion']}"
                )
        campos = dict(
            proyecto_id=self._api._pid, tipo_id=tipo_id, descripcion=descripcion,
            descripcion_corta=descripcion_corta, unidad=unidad,
            costo_mn=costo, costo_me=costo_me, costo_directo=costo,
            costo_final=costo, es_compuesto=es_compuesto, hash=nuevo_hash,
        )
        if familia_id is not None:
            campos["familia_id"] = familia_id
        if subfamilia_id is not None:
            campos["subfamilia_id"] = subfamilia_id
        return self._api._http().insertar("insumos", **campos, sesion_token=self._sesion_token, usuario_id=usuario_id)

    def insumo_por_id(self, insumo_id: int) -> dict | None:
        return self._api._http().buscar("insumos", insumo_id)

    def eliminar_insumo(self, insumo_id: int) -> None:
        self._api._http()._post("/eliminar_y_recalcular", json={
            "sesion_token": self._sesion_token,
            "entidad": "insumos", "registro_id": insumo_id})

    # ── UNDO / SESIÓN ──────────────────────────────────────────

    def deshacer(self, usuario_id: int = 1) -> bool:
        r = self._api._http()._post("/deshacer", json={"usuario_id": usuario_id})
        return r["ok"]

    def rehacer(self, usuario_id: int = 1) -> bool:
        r = self._api._http()._post("/rehacer", json={"usuario_id": usuario_id})
        return r["ok"]

    def iniciar_sesion_undo(self) -> str | None:
        # Fase D: el servidor agrupa los writes con este token en una
        # sola entrada de deshacer (igual que ds.iniciar_sesion en local).
        r = self._api._http()._post("/sesion/iniciar", json={})
        self._sesion_token = r.get("token")
        return self._sesion_token

    def cerrar_sesion_undo(self) -> None:
        if self._sesion_token is not None:
            try:
                self._api._http()._post("/sesion/cerrar",
                                        json={"token": self._sesion_token})
            except Exception:
                pass
            self._sesion_token = None

    # ── CICLO DE VIDA REMOTO ────────────────────────────────────

    def descargar_proyecto(self) -> bool:
        """Pide al servidor liberar la entrada del proyecto (cierra su
        conexión SQLite). Best-effort: si el servidor ya no está, igual
        se considera descargado. Idempotente en el servidor."""
        try:
            r = self._api._http()._post("/descargar", json={})
            return bool(r.get("ok", False))
        except Exception:
            return True

    def estadisticas_proyecto(self) -> dict:
        return self._api._http()._get("/estadisticas")

    # ── ADJUNTOS (Fase E: CAD remoto) ──────────────────────────
    # Misma firma que local (sidecar dir): el mixin no bifurca.

    def adjuntos_listar(self) -> list[str]:
        return self._api._http()._get("/adjuntos")

    def adjunto_guardar(self, filename: str, contenido: bytes) -> None:
        import os
        self._api._http().subir_archivo(
            "/adjuntos/subir", os.path.basename(filename), contenido)

    def adjunto_leer(self, filename: str) -> bytes | None:
        import os
        import httpx
        try:
            return self._api._http().descargar_archivo(
                f"/adjuntos/{os.path.basename(filename)}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ── HELPERS LOCALES ────────────────────────────────────────

    def concepto_cantidad(self, concepto_id: int) -> float:
        nodo = self._api._http().buscar("estructura_presupuesto", concepto_id)
        return float(nodo["cantidad"]) if nodo and nodo.get("cantidad") else 0.0

    def concepto_actualizar(self, concepto_id: int, **campos) -> None:
        self._api._http().actualizar("estructura_presupuesto", concepto_id, **campos, sesion_token=self._sesion_token)

    def campo_valor(self, tabla: str, campo: str, registro_id: int) -> dict | None:
        # buscar es genérico para las 3 tablas; campo se ignora aquí (se lee registro completo)
        return self._api._http().buscar(tabla, registro_id)

    def unificar_matrices_apu(self) -> int:
        # Lógica única en DataService (Fase A) — el endpoint es transporte.
        # El servidor además la corre solo al cargar el proyecto.
        r = self._api._http()._post("/unificar_matrices")
        return r["migrados"]
