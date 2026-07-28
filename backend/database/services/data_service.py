"""
data_service.py
===============
Servicio único de escritura para Open APU Studio.

Coordina: validar → transacción → repo → commit → evento.

Ningún servicio conoce SQL. Ningún repositorio conoce eventos.
Los eventos se emiten después del COMMIT exitoso.
"""

from __future__ import annotations

import uuid
from typing import Any, TYPE_CHECKING

from backend.database.event_bus import (
    EventBus, Evento,
    InsumoActualizado, ConceptoActualizado, ApuComponenteActualizado,
    FactoresSobrecostoActualizados, NodoInsertado, NodoEliminado,
    ProyectoRecalculado, GeneradorActualizado, VariableFormulaActualizada,
)
from backend.database.schema_registry import SchemaRegistry
from backend.database.exceptions import (
    DataServiceError, ValidationError, RepositoryError,
)

if TYPE_CHECKING:
    from backend.database.db import Database
    from backend.database.services.repository_registry import RepositoryRegistry


# Mapa de entidad → clase de evento para operaciones de actualización
_EVENTO_POR_ENTIDAD: dict[str, type[Evento]] = {
    "insumos": InsumoActualizado,
    "estructura_presupuesto": ConceptoActualizado,
    "apu_matrices": ApuComponenteActualizado,
    "factores_sobrecosto": FactoresSobrecostoActualizados,
    "variables_formula": VariableFormulaActualizada,
}

# Tablas con columna 'activo' (soft-delete). Usado por deshacer()/rehacer()
# para las entradas CAMPO_CREADO (ver historial.py): en estas tablas,
# deshacer una fila creada la soft-elimina y rehacer la revive. En tablas
# SIN esta columna (ej. apu_matrices — sus componentes se identifican por
# fila, no tienen estado activo/inactivo) no hay forma de "ocultarla" sin
# borrarla de verdad, así que deshacer ahí es un DELETE físico — y por lo
# tanto irreversible: no hay nada que rehacer.
_TABLAS_CON_SOFT_DELETE = {"estructura_presupuesto", "generador_renglones"}


class DataService:
    """Servicio único de escritura.

    Args:
        db: Database del proyecto abierto
        registry: RepositoryRegistry con los repos ya registrados
        event_bus: EventBus para notificar cambios
    """

    def __init__(self, db: Database, registry: RepositoryRegistry,
                 event_bus: EventBus):
        self._db = db
        self._registry = registry
        self._schema = SchemaRegistry()
        self._event_bus = event_bus
        self._sesion: str | None = None  # SRV-09: sesión activa para agrupar

    # ── SRV-09: Sesión de undo ──────────────────────────────────────

    def iniciar_sesion(self) -> str:
        """Genera una nueva sesión UUID para agrupar cambios de undo."""
        self._sesion = str(uuid.uuid4())
        return self._sesion

    def cerrar_sesion(self):
        """Cierra la sesión activa."""
        self._sesion = None

    # ── Actualizar ──────────────────────────────────────────────────

    def actualizar(self, entidad: str, registro_id: int,
                   usuario_id: int = 1, limpiar_redo: bool = True,
                   **campos: Any) -> None:
        """Actualiza campos de un registro y emite evento post-commit.

        SRV-09: captura valor_anterior de cada campo modificado en
        historial ANTES del UPDATE, dentro de la misma transacción.

        usuario_id: id del usuario que realiza la operación (SRV-06).
        limpiar_redo: True = limpia sesiones deshechas (nueva escritura
                      invalida redo). Poner False en recálculos internos
                      o durante deshacer/rehacer.
        """
        try:
            self._schema.validate(entidad, campos)
        except ValidationError:
            raise
        except Exception as e:
            raise DataServiceError(str(e)) from e

        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                # SRV-09: leer valores ANTES del UPDATE
                from backend.database.repos.historial import HistorialRepo
                h_repo = HistorialRepo(self._db.conn)
                # SRV-10: nueva escritura invalida el redo stack
                if limpiar_redo:
                    h_repo.limpiar_deshachadas(usuario_id)
                sesion = self._sesion or str(uuid.uuid4())
                for campo, nuevo_valor in campos.items():
                    viejo = h_repo.valor_campo(entidad, registro_id, campo)
                    if str(viejo) != str(nuevo_valor):
                        h_repo.capturar(
                            tabla=entidad, registro_id=registro_id,
                            campo=campo, valor_anterior=viejo,
                            valor_nuevo=nuevo_valor, usuario_id=usuario_id,
                            sesion=sesion,
                        )
                repo.update(registro_id, campos)
                registro = repo.buscar(registro_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        evento = self._evento(entidad, registro_id, campos, registro)
        self._event_bus.emit(evento)

    # ── Insertar ────────────────────────────────────────────────────

    def insertar(self, entidad: str, usuario_id: int = 1, **campos: Any) -> int:
        """Inserta un registro y emite evento post-commit.

        Retorna: id del registro insertado.
        usuario_id: id del usuario que realiza la operación (SRV-06).
        """
        try:
            self._schema.validate(entidad, campos)
        except ValidationError:
            raise
        except Exception as e:
            raise DataServiceError(str(e)) from e

        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                registro_id = repo.insert(campos)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(NodoInsertado(registro_id, entidad, campos.get("padre_id")))
        return registro_id

    # ── Eliminar ────────────────────────────────────────────────────

    def eliminar(self, entidad: str, registro_id: int,
                 usuario_id: int = 1, limpiar_redo: bool = True) -> None:
        """Elimina (soft-delete) un registro y emite evento post-commit.

        SRV-09: captura en historial el valor anterior del campo 'activo'
        ANTES del soft-delete, igual que actualizar() — así Ctrl+Z puede
        deshacer un eliminar_nodo/eliminar_insumo (antes de este fix,
        _delete() escribía directo con _update() sin pasar por
        HistorialRepo.capturar() y el borrado no quedaba en el historial).

        Si la tabla no tiene columna 'activo' (hard-delete real, ej.
        variables_formula) no hay nada que capturar: ese borrado sigue
        sin ser deshacible, porque no queda fila para revertir.

        usuario_id: id del usuario que realiza la operación (SRV-06).
        limpiar_redo: True = limpia sesiones deshechas (nueva escritura
                      invalida redo). Poner False en llamadas internas.
        """
        from backend.database.repos.historial import HistorialRepo

        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                h_repo = HistorialRepo(self._db.conn)
                if limpiar_redo:
                    h_repo.limpiar_deshachadas(usuario_id)
                sesion = self._sesion or str(uuid.uuid4())

                try:
                    viejo = h_repo.valor_campo(entidad, registro_id, "activo")
                except Exception:
                    viejo = None  # tabla sin columna 'activo' (hard-delete)

                repo.delete(registro_id)

                if viejo is not None:
                    h_repo.capturar(
                        tabla=entidad, registro_id=registro_id,
                        campo="activo", valor_anterior=viejo, valor_nuevo=0,
                        usuario_id=usuario_id, sesion=sesion,
                    )
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(NodoEliminado(registro_id, entidad))

    # ── Transacciones compuestas (write + recalc + commit atómico) ───

    def transaccion(self):
        """Context manager para agrupar escritura + recálculo en una
        transacción atómica. El caller pone aquí la escritura principal
        (vía actualizar/insertar/eliminar) y el recálculo; el commit
        ocurre al salir del bloque, y los eventos se emiten después.

        Uso típico desde api.py:
            with self._ds.transaccion():
                self._ds.actualizar(...)
                RecalculoRepo(conn).recalcular_proyecto(pid)
            self._ds.emitir(ProyectoRecalculado(pid))
        """
        return self._db.transaction()

    # ── SRV-10: Deshacer / Rehacer ─────────────────────────────────

    def _recalcular_generadores_tocados(self, cambios: list[dict]) -> None:
        """Tras deshacer/rehacer, generador_renglones.generador_id/orden ya
        quedaron restaurados como simples valores de campo — pero
        generadores.cantidad_total y estructura_presupuesto.cantidad son
        cachés derivados (SUM de renglones) que el motor genérico de
        deshacer/rehacer no sabe que debe recalcular, porque no conoce el
        significado de esas tablas. Sin esto, deshacer un movimiento entre
        generadores deja ambos lados con una cantidad_total desactualizada
        (ver GeneradorRepo.recalcular_cantidad_total/recalcular_concepto,
        que sí se llaman al mover/copiar normalmente vía
        mover_renglones_generador())."""
        from backend.database.repos.generador import GeneradorRepo
        gen_ids = set()
        for c in cambios:
            if c["tabla"] != "generador_renglones":
                continue
            if c["campo"] == "generador_id":
                for v in (c.get("valor_anterior"), c.get("valor_nuevo")):
                    if v is not None:
                        try:
                            gen_ids.add(int(float(v)))
                        except (ValueError, TypeError):
                            pass
            else:
                # CAMPO_CREADO u otro campo (ej. "orden"): el generador
                # actual del renglón (tras aplicar el cambio) también
                # puede necesitar recalcularse.
                gen_repo_tmp = GeneradorRepo(self._db.conn)
                fila = gen_repo_tmp.buscar_renglon(c["registro_id"])
                if fila:
                    gen_ids.add(fila["generador_id"])
        if not gen_ids:
            return
        gen_repo = GeneradorRepo(self._db.conn)
        for gid in gen_ids:
            gen_repo.recalcular_cantidad_total(gid)
            gen = gen_repo.buscar(gid)
            if gen and gen.get("concepto_id"):
                gen_repo.recalcular_concepto(gen["concepto_id"])

    def deshacer(self, usuario_id: int = 1,
                  proyecto_id: int | None = None) -> bool:
        """Deshace la última operación del usuario.

        Lee la última sesión no deshecha, invierte cada campo
        (valor_nuevo → valor_anterior) escribiendo directo al repo,
        la marca como deshecha (para poder rehacerla), recalcula
        y limpia el redo stack de otras sesiones.

        proyecto_id: se infiere del primer cambio si no se provee.
        Devuelve True si había algo que deshacer.
        """
        from backend.database.repos.historial import HistorialRepo, CAMPO_CREADO
        from backend.database.repos import RecalculoRepo

        h_repo = HistorialRepo(self._db.conn)
        sesion = h_repo.ultima_sesion_usuario(usuario_id)
        if not sesion:
            return False

        cambios = h_repo.cambios_sesion(sesion)
        if not cambios:
            return False

        # Inferir proyecto_id del primer cambio si no se dio.
        # Ojo: NO usar repo_tmp.buscar() aquí — casi todos los repos lo
        # sobreescriben para filtrar "WHERE activo = 1", así que si el
        # cambio a deshacer es justo un eliminar_nodo/eliminar_insumo (el
        # registro está soft-deleted en este momento) buscar() no lo
        # encontraría y pid caería siempre al fallback 1, recalculando el
        # proyecto equivocado. Se consulta la tabla directo, sin filtro.
        pid = proyecto_id
        if pid is None:
            for c in cambios:
                repo_tmp = self._registry.obtener(c["tabla"])
                reg = repo_tmp._uno(f"SELECT * FROM {c['tabla']} WHERE id = ?", [c["registro_id"]])
                if reg and "proyecto_id" in reg:
                    pid = reg["proyecto_id"]
                    break
            if pid is None:
                pid = 1  # fallback

        with self._db.transaction():
            for c in cambios:
                repo = self._registry.obtener(c["tabla"])
                if c["campo"] == CAMPO_CREADO:
                    # Esta fila se creó en esta sesión (ver
                    # HistorialRepo.capturar_creado) — deshacer la borra,
                    # no restaura un valor de campo. Soft-delete si la
                    # tabla lo soporta; si no (ver _TABLAS_CON_SOFT_DELETE),
                    # DELETE físico — sin redo posible para esta entrada.
                    if c["tabla"] in _TABLAS_CON_SOFT_DELETE:
                        repo.update(c["registro_id"], {"activo": 0})
                    else:
                        # repo.delete() asume una columna 'activo' (soft-delete
                        # genérico de RepoBase) que esta tabla no tiene —
                        # DELETE físico directo.
                        self._db.conn.execute(
                            f"DELETE FROM {c['tabla']} WHERE id = ?", [c["registro_id"]]
                        )
                    continue
                valor = c["valor_anterior"]
                if valor is None:
                    continue
                if c["tabla"] in ("insumos", "estructura_presupuesto", "apu_matrices", "generador_renglones"):
                    try:
                        valor = float(valor)
                    except (ValueError, TypeError):
                        pass
                repo.update(c["registro_id"], {c["campo"]: valor})

            # Marcar como deshecha (redo stack). NO limpiar aquí:
            # limpiar_deshachadas solo corre en actualizar() cuando
            # el usuario hace una escritura nueva (invalida redo).
            h_repo.marcar_deshachada(sesion)
            self._recalcular_generadores_tocados(cambios)
            RecalculoRepo(self._db.conn).recalcular_proyecto(pid)

        self._event_bus.emit(ProyectoRecalculado(pid))
        return True

    def rehacer(self, usuario_id: int = 1,
                proyecto_id: int | None = None) -> bool:
        """Rehace la última operación deshecha del usuario.

        Busca la última sesión deshecha, re-aplica valor_nuevo de cada
        cambio (restaurando el valor original), la des-marca, recalcula.

        Devuelve True si había algo que rehacer.
        """
        from backend.database.repos.historial import HistorialRepo, CAMPO_CREADO
        from backend.database.repos import RecalculoRepo

        h_repo = HistorialRepo(self._db.conn)
        sesion = h_repo.ultima_sesion_deshecha(usuario_id)
        if not sesion:
            return False

        cambios = h_repo.cambios_sesion(sesion)
        if not cambios:
            return False

        pid = proyecto_id
        if pid is None:
            for c in cambios:
                repo_tmp = self._registry.obtener(c["tabla"])
                reg = repo_tmp._uno(f"SELECT * FROM {c['tabla']} WHERE id = ?", [c["registro_id"]])
                if reg and "proyecto_id" in reg:
                    pid = reg["proyecto_id"]
                    break
            if pid is None:
                pid = 1

        with self._db.transaction():
            for c in cambios:
                repo = self._registry.obtener(c["tabla"])
                if c["campo"] == CAMPO_CREADO:
                    # Redo de una fila creada: revivirla, solo posible si
                    # la tabla tiene soft-delete — si el deshacer fue un
                    # DELETE físico (ver deshacer()), la fila ya no existe
                    # y no hay nada que revivir.
                    if c["tabla"] in _TABLAS_CON_SOFT_DELETE:
                        repo.update(c["registro_id"], {"activo": 1})
                    continue
                valor = c["valor_nuevo"]
                if valor is None:
                    continue
                if c["tabla"] in ("insumos", "estructura_presupuesto", "apu_matrices", "generador_renglones"):
                    try:
                        valor = float(valor)
                    except (ValueError, TypeError):
                        pass
                repo.update(c["registro_id"], {c["campo"]: valor})

            h_repo.desmarcar_sesion(sesion)
            self._recalcular_generadores_tocados(cambios)
            RecalculoRepo(self._db.conn).recalcular_proyecto(pid)

        self._event_bus.emit(ProyectoRecalculado(pid))
        return True

    def emitir(self, evento: Evento) -> None:
        """Emite un evento ya construido por el caller.

        Uso: operaciones que no encajan en actualizar/insertar/eliminar
        genéricos (ej. factores_sobrecosto, donde el propio repo calcula
        `factor_total` antes de persistir). El caller sigue siendo
        responsable de su propia transacción/commit; esto solo evita que
        el código externo tenga que tocar el EventBus interno de la
        instancia directamente.
        """
        self._event_bus.emit(evento)

    # ── Generadores de obra ─────────────────────────────────────────

    def guardar_renglon_generador(self, generador_id: int,
                                  usuario_id: int = 1,
                                  renglon_id: int | None = None,
                                  **campos) -> int:
        """Inserta o actualiza un renglón de generador.

        Recalcula cantidad_total del generador y, si tiene concepto_id,
        la cantidad del concepto en el presupuesto. Emite GeneradorActualizado.
        """
        from backend.database.repos.generador import GeneradorRepo
        from backend.database.repos.recalculo import RecalculoRepo

        gen_repo = GeneradorRepo(self._db.conn)

        # Para ediciones inline solo llega el campo que cambió (ej. sólo
        # "ancho"). Si el subtotal se calculara nada más con `campos`, los
        # campos ausentes se tratarían como veces=1 / largo=ancho=alto=None,
        # y el subtotal terminaba siendo literalmente el único valor editado
        # en vez de la multiplicación real. Por eso, al actualizar un
        # renglón existente, se completan los campos faltantes con lo que
        # ya está guardado en la BD antes de calcular.
        existente = gen_repo.buscar_renglon(renglon_id) if renglon_id else None

        def _campo(nombre, default=None):
            if nombre in campos:
                return campos[nombre]
            if existente is not None:
                return existente.get(nombre, default)
            return default

        veces = float(_campo("veces", 1) or 1)
        largo = _campo("largo")
        ancho = _campo("ancho")
        alto = _campo("alto")
        campos["subtotal"] = GeneradorRepo.calcular_subtotal(
            veces,
            float(largo) if largo is not None else None,
            float(ancho) if ancho is not None else None,
            float(alto) if alto is not None else None,
        )

        conceptos_ids = []
        proyecto_id = None

        try:
            with self._db.transaction():
                if renglon_id:
                    gen_repo.actualizar_renglon(renglon_id, campos)
                else:
                    campos["generador_id"] = generador_id
                    renglon_id = gen_repo.insertar_renglon(campos)

                # Recalcular cantidad_total del generador
                gen_repo.recalcular_cantidad_total(generador_id)

                # Recalcular concepto(s) afectado(s)
                gen = gen_repo.buscar(generador_id)
                if gen and gen.get("concepto_id"):
                    cid = gen["concepto_id"]
                    gen_repo.recalcular_concepto(cid)
                    conceptos_ids.append(cid)
                    proyecto_id = gen["proyecto_id"]
                    # Propagar total (cantidad × precio) hacia capítulos padres
                    RecalculoRepo(self._db.conn).recalcular_proyecto(proyecto_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(GeneradorActualizado(
            generador_id=generador_id,
            conceptos_ids=conceptos_ids,
        ))
        if conceptos_ids:
            from backend.database.repos import NodoRepo
            nodo_repo = NodoRepo(self._db.conn)
            for cid in conceptos_ids:
                registro = nodo_repo.buscar(cid)
                if registro:
                    from backend.database.event_bus import ConceptoActualizado
                    self._event_bus.emit(ConceptoActualizado(
                        concepto_id=cid,
                        cambios={"cantidad", "total"},
                        registro=registro,
                    ))
        if proyecto_id is not None:
            self._event_bus.emit(ProyectoRecalculado(proyecto_id))
        return renglon_id

    def eliminar_renglon_generador(self, renglon_id: int,
                                   usuario_id: int = 1) -> None:
        """Elimina un renglón y recalcula sync."""
        from backend.database.repos.generador import GeneradorRepo
        from backend.database.repos.recalculo import RecalculoRepo

        gen_repo = GeneradorRepo(self._db.conn)
        rn = gen_repo.buscar_renglon(renglon_id)
        if not rn:
            return

        generador_id = rn["generador_id"]
        conceptos_ids = []
        proyecto_id = None

        try:
            with self._db.transaction():
                gen_repo.eliminar_renglon(renglon_id)
                gen_repo.recalcular_cantidad_total(generador_id)

                gen = gen_repo.buscar(generador_id)
                if gen and gen.get("concepto_id"):
                    cid = gen["concepto_id"]
                    gen_repo.recalcular_concepto(cid)
                    conceptos_ids.append(cid)
                    proyecto_id = gen["proyecto_id"]
                    RecalculoRepo(self._db.conn).recalcular_proyecto(proyecto_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(GeneradorActualizado(
            generador_id=generador_id,
            conceptos_ids=conceptos_ids,
        ))
        if conceptos_ids:
            from backend.database.repos import NodoRepo
            nodo_repo = NodoRepo(self._db.conn)
            for cid in conceptos_ids:
                registro = nodo_repo.buscar(cid)
                if registro:
                    from backend.database.event_bus import ConceptoActualizado
                    self._event_bus.emit(ConceptoActualizado(
                        concepto_id=cid,
                        cambios={"cantidad", "total"},
                        registro=registro,
                    ))
        if proyecto_id is not None:
            self._event_bus.emit(ProyectoRecalculado(proyecto_id))

    def mover_renglones_generador(self, ids: list[int], nuevo_generador_id: int,
                                   antes_de_id: int | None, copiar: bool,
                                   usuario_id: int = 1) -> bool:
        """Mueve o copia (Ctrl) un bloque de renglones a nuevo_generador_id,
        insertados justo antes de antes_de_id (o al final si es None) —
        usado por el drag and drop entre pestañas de Generadores (ver
        TablaGenerador.dropEvent). Si nuevo_generador_id es el mismo
        generador de origen, esto simplemente reordena.

        Recalcula cantidad_total de AMBOS generadores involucrados (si
        mover cambia de generador) y la cantidad de sus conceptos
        vinculados, en caso de tenerlos — igual alcance que
        eliminar_renglon_generador()/guardar_renglon_generador()."""
        from backend.database.repos.generador import GeneradorRepo
        from backend.database.repos.recalculo import RecalculoRepo
        from backend.database.repos.historial import HistorialRepo
        import uuid as _uuid

        if not ids:
            return False
        gen_repo = GeneradorRepo(self._db.conn)
        h_repo = HistorialRepo(self._db.conn)
        h_repo.limpiar_deshachadas(usuario_id)
        sesion = str(_uuid.uuid4())

        generadores_afectados = set()
        for rid in ids:
            info = gen_repo.info_renglon(rid)
            if info:
                generadores_afectados.add(info["generador_id"])
        generadores_afectados.add(nuevo_generador_id)

        try:
            with self._db.transaction():
                if not copiar:
                    viejos = {rid: gen_repo.info_renglon(rid) for rid in ids}
                    gen_repo.mover_bloque(ids, nuevo_generador_id, antes_de_id)
                    nuevos = {rid: gen_repo.info_renglon(rid) for rid in ids}
                    for rid in ids:
                        viejo, nuevo = viejos.get(rid), nuevos.get(rid)
                        if not viejo or not nuevo:
                            continue
                        if viejo["generador_id"] != nuevo["generador_id"]:
                            h_repo.capturar(tabla="generador_renglones", registro_id=rid,
                                             campo="generador_id", valor_anterior=viejo["generador_id"],
                                             valor_nuevo=nuevo["generador_id"], usuario_id=usuario_id,
                                             sesion=sesion)
                        if viejo["orden"] != nuevo["orden"]:
                            h_repo.capturar(tabla="generador_renglones", registro_id=rid,
                                             campo="orden", valor_anterior=viejo["orden"],
                                             valor_nuevo=nuevo["orden"], usuario_id=usuario_id,
                                             sesion=sesion)
                else:
                    nuevos_ids = gen_repo.duplicar_bloque(ids, nuevo_generador_id, antes_de_id)
                    for nid in nuevos_ids:
                        h_repo.capturar_creado("generador_renglones", nid,
                                                usuario_id=usuario_id, sesion=sesion)

                conceptos_ids = []
                proyecto_id = None
                for gid in generadores_afectados:
                    gen_repo.recalcular_cantidad_total(gid)
                    gen = gen_repo.buscar(gid)
                    if gen and gen.get("concepto_id"):
                        cid = gen["concepto_id"]
                        gen_repo.recalcular_concepto(cid)
                        conceptos_ids.append(cid)
                        proyecto_id = gen["proyecto_id"]
                if proyecto_id is not None:
                    RecalculoRepo(self._db.conn).recalcular_proyecto(proyecto_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        for gid in generadores_afectados:
            self._event_bus.emit(GeneradorActualizado(
                generador_id=gid, conceptos_ids=conceptos_ids,
            ))
        if conceptos_ids:
            from backend.database.repos import NodoRepo
            nodo_repo = NodoRepo(self._db.conn)
            for cid in conceptos_ids:
                registro = nodo_repo.buscar(cid)
                if registro:
                    from backend.database.event_bus import ConceptoActualizado
                    self._event_bus.emit(ConceptoActualizado(
                        concepto_id=cid, cambios={"cantidad", "total"}, registro=registro,
                    ))
        if proyecto_id is not None:
            self._event_bus.emit(ProyectoRecalculado(proyecto_id))
        return True

    def reasignar_generador(self, generador_id: int,
                            nuevo_concepto_id: int | None,
                            usuario_id: int = 1) -> None:
        """Cambia el concepto vinculado a un generador y recalcula ambos."""
        from backend.database.repos.generador import GeneradorRepo
        from backend.database.repos.recalculo import RecalculoRepo

        gen_repo = GeneradorRepo(self._db.conn)
        afectados = gen_repo.conceptos_afectados(generador_id, nuevo_concepto_id)
        proyecto_id = None

        try:
            with self._db.transaction():
                gen_repo.update(generador_id, {"concepto_id": nuevo_concepto_id})
                for cid in afectados:
                    gen_repo.recalcular_concepto(cid)
                if afectados:
                    gen = gen_repo.buscar(generador_id)
                    if gen:
                        proyecto_id = gen["proyecto_id"]
                        RecalculoRepo(self._db.conn).recalcular_proyecto(proyecto_id)
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(GeneradorActualizado(
            generador_id=generador_id,
            conceptos_ids=afectados,
        ))
        if afectados:
            from backend.database.repos import NodoRepo
            nodo_repo = NodoRepo(self._db.conn)
            for cid in afectados:
                registro = nodo_repo.buscar(cid)
                if registro:
                    from backend.database.event_bus import ConceptoActualizado
                    self._event_bus.emit(ConceptoActualizado(
                        concepto_id=cid,
                        cambios={"cantidad", "total"},
                        registro=registro,
                    ))
        if proyecto_id is not None:
            self._event_bus.emit(ProyectoRecalculado(proyecto_id))

    # ── Helpers internos ────────────────────────────────────────────

    def _evento(self, entidad: str, id: int, cambios: dict,
                registro: dict | None) -> Evento:
        """Resuelve el tipo de evento según la entidad."""
        tipo = _EVENTO_POR_ENTIDAD.get(entidad)
        if tipo is None:
            return Evento()
        if entidad == "factores_sobrecosto":
            return tipo(proyecto_id=id, registro=registro)
        return tipo(id, cambios, registro)
