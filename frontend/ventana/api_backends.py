"""
api_backends.py
================
Backends de Api: separan la implementación local (SQLite directo) de la
implementación HTTP (vía servidor embebido) que hoy conviven mezcladas
como `if self._use_http: ... else: ...` dentro de cada método de Api.

Cada backend implementa el mismo conjunto de métodos que expone Api.
Api delega al backend activo en vez de repetir el if/else en cada método.

Migración en progreso — ver docs/DUPLICACION_Y_DEUDA.md. Por ahora cubre
FACTORES DE SOBRECOSTO e INSUMOS; el resto de Api sigue con el patrón
viejo hasta terminar la migración sección por sección.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from frontend.ventana.api import Api


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

    def proyecto_guardar(self, campos: dict) -> None:
        self._api._ds.actualizar("proyectos", self._api._pid, **campos)

    # ── APU ──────────────────────────────────────────────────────────
    # Los 5 métodos de escritura de apu_matrices (actualizar_operador,
    # agregar_componente, actualizar_valor, reasignar_componente,
    # actualizar_precio_componente) siguen con el patrón viejo
    # `if self._use_http:` inline dentro de Api — no se migraron a
    # _BackendLocal/_BackendHTTP en esta ronda porque ya funcionan en
    # ambos modos tal cual están. Solo la lectura compuesta (apu(),
    # resolver_matriz()) se migra aquí, porque es la única que combina
    # varias consultas en una sola respuesta (matriz_id + detalle +
    # enriquecimiento de UI) — el resto son CRUD de una fila.

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

                conceptos = conn.execute(
                    "SELECT id, formula FROM estructura_presupuesto "
                    "WHERE proyecto_id = ? AND formula IS NOT NULL AND formula != '' AND activo = 1",
                    [pid],
                ).fetchall()
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


class _BackendHTTP:
    """Implementación vía servidor embebido (ApiCliente)."""

    def __init__(self, api: "Api"):
        self._api = api

    # ── FACTORES DE SOBRECOSTO ──────────────────────────────────────

    def factores_sobrecosto_obtener(self) -> dict:
        return self._api._http().factores_sobrecosto_obtener()

    def factores_sobrecosto_guardar(self, valores: dict) -> float:
        from backend.database.event_bus import FactoresSobrecostoActualizados, ProyectoRecalculado
        factor = self._api._http().factores_sobrecosto_guardar(valores)
        self._api._ds.emitir(FactoresSobrecostoActualizados(self._api._pid, valores))
        self._api._http().recalcular()
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return factor

    # ── INSUMOS ──────────────────────────────────────────────────────

    def insumos(self, tipo_clave: str | None = None) -> list[dict]:
        return self._api._http().insumos(tipo=tipo_clave)

    def insumo_por_hash(self, hash_val: str) -> dict | None:
        return self._api._http().insumo_por_hash(hash_val)

    def recalcular_proyecto(self) -> dict:
        self._api._http().recalcular()
        from backend.database.event_bus import ProyectoRecalculado
        self._api._ds.emitir(ProyectoRecalculado(self._api._pid))
        return {}

    def rastrear_insumo(self, insumo_id: int) -> list[dict]:
        return self._api._http().rastrear(insumo_id)

    def proyecto_guardar(self, campos: dict) -> None:
        # "proyectos" ya es una entidad registrada en crear_registry() —
        # el /actualizar genérico la acepta sin necesitar ruta propia.
        self._api._http().actualizar("proyectos", self._api._pid, **campos)

    # ── VARIABLES DE FÓRMULA ─────────────────────────────────────────
    # Todas con endpoints dedicados: crear/actualizar necesitan la misma
    # validación de formato/duplicados/ciclo que el lado local (no se
    # puede confiar esa lógica solo al cliente), y variables_resueltas()
    # trabaja con Decimal, que no es JSON-serializable — el servidor lo
    # manda como string y aquí se reconstruye.

    def variables_listar(self) -> list[dict]:
        return self._api._http().variables_listar()

    def variables_crear(self, nombre: str, expresion: str, descripcion: str) -> int:
        return self._api._http().variables_crear(nombre, expresion, descripcion)

    def variables_actualizar(self, variable_id: int, campos: dict) -> None:
        self._api._http().variables_actualizar(variable_id, campos)

    def variables_eliminar(self, variable_id: int) -> dict:
        return self._api._http().variables_eliminar(variable_id)

    def variables_resueltas(self) -> dict:
        from decimal import Decimal
        crudo = self._api._http().variables_resueltas()
        return {k: Decimal(v) for k, v in crudo.items()}

    def formula_evaluar(self, expr: str):
        from decimal import Decimal
        return Decimal(self._api._http().formula_evaluar(expr))

    # ── APU ──────────────────────────────────────────────────────────

    def apu(self, nodo_id: int | None, insumo_id: int | None) -> dict | None:
        data = self._api._http().apu_completo(nodo_id, insumo_id)
        if data.get("matriz_id") is None:
            return None
        ids_con_apu = self._api.insumo_ids_con_apu()  # ya funciona en HTTP
        return _enriquecer_detalle_apu(data, ids_con_apu)

    def resolver_matriz(self, nodo_id: int | None, insumo_id: int | None) -> tuple[int | None, str]:
        # Reusa /apu_completo (trae más de lo necesario — detalle y
        # totales que aquí se descartan) en vez de agregar un endpoint
        # solo para esto. Es aceptable: el propio resolver_matriz() local
        # ya hace 2-3 queries por concepto sin batchear cuando se llama
        # en loop (ver explosion.py) — este no es menos eficiente que eso,
        # solo cambia dónde ocurre el costo.
        data = self._api._http().apu_completo(nodo_id, insumo_id)
        return data.get("matriz_id"), data.get("descripcion", "")

    # ── GENERADORES ──────────────────────────────────────────────────
    # crear/actualizar_cad reusan insertar()/actualizar() genéricos
    # ("generadores" ya es entidad registrada). El resto son operaciones
    # a medida (guardar_renglon_generador recalcula cantidad_total y
    # cascada, no es un CRUD de una fila) — endpoints dedicados.

    def generadores_por_concepto(self, concepto_id: int | None) -> list[dict]:
        return self._api._http().generadores_por_concepto(concepto_id)

    def generador_por_id(self, generador_id: int) -> dict | None:
        return self._api._http().generador_por_id(generador_id)

    def generador_crear(self, nombre: str, concepto_id: int | None, unidad: str | None) -> int:
        campos = {"proyecto_id": self._api._pid, "nombre": nombre, "concepto_id": concepto_id}
        if unidad:
            campos["unidad"] = unidad
        return self._api._http().insertar("generadores", **campos)

    def generador_actualizar_cad(self, generador_id: int, path: str | None) -> None:
        self._api._http().actualizar("generadores", generador_id, cad_archivo_path=path)

    def generador_renglones(self, generador_id: int) -> list[dict]:
        return self._api._http().generador_renglones(generador_id)

    def generador_renglon_guardar(self, generador_id: int, renglon_id: int | None, campos: dict) -> int:
        return self._api._http().generador_renglon_guardar(generador_id, renglon_id, campos)

    def generador_renglon_eliminar(self, renglon_id: int) -> None:
        self._api._http().generador_renglon_eliminar(renglon_id)

    def generador_mover_renglones(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool) -> bool:
        return self._api._http().generador_mover_renglones(ids, nuevo_generador_id, antes_de_id, copiar)

    # ── INDIRECTOS ───────────────────────────────────────────────────
    # guardar/insertar/eliminar reusan actualizar()/insertar()/eliminar()
    # genéricos de ApiCliente — "indirectos" ya es una entidad registrada
    # en crear_registry() (Hallazgo 1), así que el servidor la acepta tal
    # cual en /actualizar, /insertar, /eliminar sin necesitar rutas nuevas.
    # Solo las operaciones que NO son CRUD de una fila (lista con filtro,
    # cálculo masivo, plantilla, %CI→sobrecosto) necesitan endpoints
    # dedicados — igual que ya pasa con factores_sobrecosto_guardar().

    def indirectos_lista(self, tipo: str | None = None) -> list[dict]:
        return self._api._http().indirectos_lista(tipo)

    def indirectos_guardar(self, registro_id: int, campos: dict) -> None:
        self._api._http().actualizar("indirectos", registro_id, **campos)

    def indirectos_insertar(self, campos: dict) -> int:
        # Misma inyección que _BackendLocal — sin esto, un indirecto
        # agregado sin proyecto_id explícito viola el NOT NULL de la
        # columna server-side y el insert falla con 500 (encontrado por
        # el test de paridad local-vs-HTTP antes de dar esto por bueno).
        campos = dict(campos)
        campos.setdefault("proyecto_id", self._api._pid)
        return self._api._http().insertar("indirectos", **campos)

    def indirectos_eliminar(self, registro_id: int) -> None:
        self._api._http().eliminar("indirectos", registro_id)

    def indirectos_calcular_totales(self) -> dict:
        return self._api._http().indirectos_calcular_totales()

    def indirectos_cargar_plantilla(self, tipo: str) -> int:
        return self._api._http().indirectos_cargar_plantilla(tipo)

    def indirectos_aplicar_a_sobrecosto(self) -> dict:
        return self._api._http().indirectos_aplicar_a_sobrecosto()
