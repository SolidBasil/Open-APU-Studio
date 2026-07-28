"""apu.py
Repositorios de matrices APU — subtotales se calculan al vuelo.
"""
from .base import RepoBase
from .recalculo import RecalculoRepo, _RESUMEN_DEFAULT


class ApuMatricesRepo(RepoBase):
    """Componentes del APU: desglose de insumos por concepto o insumo compuesto.
    matriz_id unificado: positivo para nodos del árbol, negativo para insumos compuestos.
    """

    TABLA = "apu_matrices"

    def proximo_orden(self, matriz_id: int) -> int:
        row = self._uno(
            "SELECT COALESCE(MAX(orden), 0) + 1 AS prox FROM apu_matrices WHERE matriz_id = ?",
            [matriz_id],
        )
        return row["prox"] if row else 1

    def hermanos_de(self, matriz_id: int) -> list[int]:
        """ids de todos los componentes de una matriz, en su orden actual."""
        filas = self._lista(
            "SELECT id FROM apu_matrices WHERE matriz_id = ? ORDER BY orden, id",
            [matriz_id]
        )
        return [f["id"] for f in filas]

    def info_componente(self, comp_id: int) -> dict | None:
        """Devuelve {matriz_id, orden} de un componente, o None si no existe."""
        return self._uno(
            "SELECT matriz_id, orden FROM apu_matrices WHERE id = ?", [comp_id]
        )

    def mover_bloque(self, ids: list[int], nueva_matriz_id: int,
                      antes_de_id: int | None) -> None:
        """Reposiciona un bloque de componentes (ids, en el orden en que
        el usuario los arrastró) para que queden en nueva_matriz_id,
        insertados justo antes de antes_de_id (o al final si es None o ya
        no es uno de los componentes de esa matriz).

        A diferencia de NodoRepo.mover_bloque (Presupuesto), aquí no hace
        falta la técnica de "hueco"/orden_tras: una matriz normalmente
        tiene pocos componentes, así que simplemente se renumera todo el
        grupo destino de 1 en 1 tras insertar el bloque en su lugar.

        Usado por el drag and drop del desglose de APU: soltar dentro de
        la misma matriz reordena; soltar en OTRA matriz (otra pestaña de
        APU abierta) mueve el componente ahí."""
        ids_mover = set(ids)
        hermanos = [cid for cid in self.hermanos_de(nueva_matriz_id) if cid not in ids_mover]
        if antes_de_id is not None and antes_de_id in hermanos:
            idx = hermanos.index(antes_de_id)
        else:
            idx = len(hermanos)
        nuevo_orden = hermanos[:idx] + list(ids) + hermanos[idx:]
        self._cursor.executemany(
            "UPDATE apu_matrices SET matriz_id = ?, orden = ? WHERE id = ?",
            [(nueva_matriz_id, pos + 1, cid) for pos, cid in enumerate(nuevo_orden)]
        )

    def duplicar_bloque(self, ids: list[int], nueva_matriz_id: int,
                         antes_de_id: int | None) -> list[int]:
        """Duplica un bloque de componentes como filas nuevas en
        nueva_matriz_id, en la posición indicada (ver mover_bloque).
        Devuelve los ids nuevos, en el mismo orden que `ids`.

        Usado por el drag and drop del desglose de APU con Ctrl
        presionado: a diferencia de mover_bloque, el/los componente(s)
        original(es) quedan intactos donde estaban."""
        nuevos = []
        for cid in ids:
            fila = self.buscar(cid)
            if not fila:
                continue
            datos = {k: v for k, v in fila.items()
                     if k not in ("id", "matriz_id", "orden", "importe",
                                  "creado_en", "modificado_en", "modificado_por")}
            datos["matriz_id"] = nueva_matriz_id
            datos["orden"] = self.proximo_orden(nueva_matriz_id)
            nuevos.append(self.insert(datos))
        self.mover_bloque(nuevos, nueva_matriz_id, antes_de_id)
        return nuevos

    def por_matriz(self, matriz_id):
        """Devuelve los componentes del APU de una matriz (concepto o compuesto)."""
        return self._lista("""
            SELECT ac.*,
                   i.descripcion       AS insumo_descripcion,
                   i.descripcion_corta AS insumo_desc_corta,
                   i.unidad            AS insumo_unidad,
                   t.clave             AS tipo_clave,
                   t.nombre            AS tipo_nombre,
                   t.id                AS tipo_id
            FROM apu_matrices ac
            JOIN insumos i      ON i.id = ac.insumo_id
            JOIN tipos_insumo t ON t.id = i.tipo_id
            WHERE ac.matriz_id = ?
            ORDER BY ac.orden
        """, [matriz_id])

    def conceptos_con_insumo_compuesto(self, proyecto_id: int) -> list[dict]:
        """Conceptos del árbol cuyo insumo es compuesto (es_compuesto=1)."""
        return self._lista("""
            SELECT ep.id AS cid, ep.insumo_id
            FROM estructura_presupuesto ep
            JOIN insumos i ON i.id = ep.insumo_id
            WHERE ep.proyecto_id = ? AND i.es_compuesto = 1
        """, [proyecto_id])

    def contar_por_matriz(self, matriz_id: int) -> int:
        """Filas en apu_matrices para un matriz_id dado."""
        row = self._uno(
            "SELECT COUNT(*) AS n FROM apu_matrices WHERE matriz_id = ?",
            [matriz_id],
        )
        return row["n"] if row else 0

    def redirigir_matriz(self, origen: int, destino: int) -> None:
        """Mueve todos los componentes de apu_matrices de origen a destino."""
        self._conn.execute(
            "UPDATE apu_matrices SET matriz_id = ? WHERE matriz_id = ?",
            [destino, origen],
        )

    def eliminar_matriz(self, matriz_id: int) -> None:
        """Borra todos los componentes de apu_matrices de un matriz_id."""
        self._conn.execute(
            "DELETE FROM apu_matrices WHERE matriz_id = ?", [matriz_id]
        )

    def con_detalle(self, matriz_id: int) -> dict:
        """Devuelve el APU completo de una matriz (concepto o insumo compuesto):
        componentes con su insumo enriquecido + totales por tipo (al vuelo).

        Returns:
            {
                "detalle":  list[dict],   # componentes con insumo completo
                "totales":  dict | None,  # subtotales por tipo calculados al vuelo
            }
        """
        detalle = self._lista("""
            SELECT
                ad.id,
                ad.orden,
                ad.valor,
                ad.operador,
                ad.precio,
                CASE WHEN ad.operador = '*' THEN ad.valor * ad.precio ELSE ad.precio / ad.valor END AS importe,
                ad.formula,
                ad.creado_en,
                ad.modificado_en,
                i.es_compuesto      AS insumo_es_compuesto,
                i.id                AS insumo_id,
                i.descripcion       AS insumo_descripcion,
                i.descripcion_corta AS insumo_desc_corta,
                i.unidad            AS insumo_unidad,
                t.clave             AS tipo_clave,
                t.nombre            AS tipo_nombre,
                t.id                AS tipo_id
            FROM apu_matrices ad
            JOIN insumos i      ON i.id  = ad.insumo_id
            JOIN tipos_insumo t ON t.id  = i.tipo_id
            WHERE ad.matriz_id = ?
            ORDER BY ad.orden
        """, [matriz_id])

        # ponytail: calcular resumen al vuelo en vez de leer de apu_resumen_totales
        proyecto_id = self._obtener_proyecto_id(matriz_id)
        if proyecto_id is not None:
            rc = RecalculoRepo(self._conn)
            totales = rc.calcular_resumen(proyecto_id, matriz_id)
        else:
            totales = _RESUMEN_DEFAULT.copy()

        return {"detalle": detalle, "totales": totales}

    def _obtener_proyecto_id(self, matriz_id: int) -> int | None:
        """Resuelve proyecto_id desde matriz_id (positivo=árbol, negativo=compuesto)."""
        if matriz_id > 0:
            row = self._uno(
                "SELECT proyecto_id FROM estructura_presupuesto WHERE id = ?",
                [matriz_id],
            )
        else:
            row = self._uno(
                "SELECT proyecto_id FROM insumos WHERE id = ?",
                [-matriz_id],
            )
        return row["proyecto_id"] if row else None


# =============================================================================
# APU RESUMEN (antes: apu_totales)
# =============================================================================
# ponytail: eliminado — los subtotales se calculan al vuelo en memoria
