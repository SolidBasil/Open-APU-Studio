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
    ProyectoRecalculado, GeneradorActualizado,
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
}


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
                 usuario_id: int = 1) -> None:
        """Elimina (soft-delete) un registro y emite evento post-commit.
        usuario_id: id del usuario que realiza la operación (SRV-06).
        """
        repo = self._registry.obtener(entidad)
        try:
            with self._db.transaction():
                repo.delete(registro_id)
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
        from backend.database.repos.historial import HistorialRepo
        from backend.database.repos import RecalculoRepo

        h_repo = HistorialRepo(self._db.conn)
        sesion = h_repo.ultima_sesion_usuario(usuario_id)
        if not sesion:
            return False

        cambios = h_repo.cambios_sesion(sesion)
        if not cambios:
            return False

        # Inferir proyecto_id del primer cambio si no se dio
        pid = proyecto_id
        if pid is None:
            for c in cambios:
                repo_tmp = self._registry.obtener(c["tabla"])
                reg = repo_tmp.buscar(c["registro_id"])
                if reg and "proyecto_id" in reg:
                    pid = reg["proyecto_id"]
                    break
            if pid is None:
                pid = 1  # fallback

        with self._db.transaction():
            for c in cambios:
                valor = c["valor_anterior"]
                if valor is None:
                    continue
                if c["tabla"] in ("insumos", "estructura_presupuesto", "apu_matrices"):
                    try:
                        valor = float(valor)
                    except (ValueError, TypeError):
                        pass
                repo = self._registry.obtener(c["tabla"])
                repo.update(c["registro_id"], {c["campo"]: valor})

            # Marcar como deshecha (redo stack). NO limpiar aquí:
            # limpiar_deshachadas solo corre en actualizar() cuando
            # el usuario hace una escritura nueva (invalida redo).
            h_repo.marcar_deshachada(sesion)
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
        from backend.database.repos.historial import HistorialRepo
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
                reg = repo_tmp.buscar(c["registro_id"])
                if reg and "proyecto_id" in reg:
                    pid = reg["proyecto_id"]
                    break
            if pid is None:
                pid = 1

        with self._db.transaction():
            for c in cambios:
                valor = c["valor_nuevo"]
                if valor is None:
                    continue
                if c["tabla"] in ("insumos", "estructura_presupuesto", "apu_matrices"):
                    try:
                        valor = float(valor)
                    except (ValueError, TypeError):
                        pass
                repo = self._registry.obtener(c["tabla"])
                repo.update(c["registro_id"], {c["campo"]: valor})

            h_repo.desmarcar_sesion(sesion)
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

        # Calcular subtotal antes de persistir
        veces = float(campos.get("veces", 1))
        largo = campos.get("largo")
        ancho = campos.get("ancho")
        alto = campos.get("alto")
        campos["subtotal"] = GeneradorRepo.calcular_subtotal(
            veces,
            float(largo) if largo is not None else None,
            float(ancho) if ancho is not None else None,
            float(alto) if alto is not None else None,
        )

        conceptos_ids = []

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
                    # Propagar total (cantidad × precio) hacia capítulos padres
                    RecalculoRepo(self._db.conn).recalcular_proyecto(
                        gen["proyecto_id"]
                    )
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(GeneradorActualizado(
            generador_id=generador_id,
            conceptos_ids=conceptos_ids,
        ))
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

        try:
            with self._db.transaction():
                gen_repo.eliminar_renglon(renglon_id)
                gen_repo.recalcular_cantidad_total(generador_id)

                gen = gen_repo.buscar(generador_id)
                if gen and gen.get("concepto_id"):
                    cid = gen["concepto_id"]
                    gen_repo.recalcular_concepto(cid)
                    conceptos_ids.append(cid)
                    RecalculoRepo(self._db.conn).recalcular_proyecto(
                        gen["proyecto_id"]
                    )
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(GeneradorActualizado(
            generador_id=generador_id,
            conceptos_ids=conceptos_ids,
        ))

    def reasignar_generador(self, generador_id: int,
                            nuevo_concepto_id: int | None,
                            usuario_id: int = 1) -> None:
        """Cambia el concepto vinculado a un generador y recalcula ambos."""
        from backend.database.repos.generador import GeneradorRepo
        from backend.database.repos.recalculo import RecalculoRepo

        gen_repo = GeneradorRepo(self._db.conn)
        afectados = gen_repo.conceptos_afectados(generador_id, nuevo_concepto_id)

        try:
            with self._db.transaction():
                gen_repo.update(generador_id, {"concepto_id": nuevo_concepto_id})
                for cid in afectados:
                    gen_repo.recalcular_concepto(cid)
                if afectados:
                    gen = gen_repo.buscar(generador_id)
                    if gen:
                        RecalculoRepo(self._db.conn).recalcular_proyecto(
                            gen["proyecto_id"]
                        )
        except Exception as e:
            raise RepositoryError(str(e)) from e

        self._event_bus.emit(GeneradorActualizado(
            generador_id=generador_id,
            conceptos_ids=afectados,
        ))

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
