"""
opensees_repo.py
=================
Wrapper de OpenSeesPy con el mismo espíritu que backend/database/repos/*.py:
el frontend nunca llama a `ops.*` directamente, solo a este repo.

Responsabilidades:
    - Construir un modelo de ejemplo (pórtico 3D) para probar la interfaz.
    - Correr análisis (gravedad).
    - Exponer nodos/elementos/reacciones como dataclasses simples,
      listos para tablas (TreeTableWidget) y para el viewport 3D (PyVista).

Uso:
    from backend.motor import OpenSeesRepo

    repo = OpenSeesRepo()
    repo.construir_modelo_ejemplo(niveles=3, bahias_x=2, bahias_y=2)
    repo.analizar()
    nodos = repo.obtener_nodos()
    elementos = repo.obtener_elementos()
"""

from __future__ import annotations

import os
# El runtime Fortran (Intel) que trae openseespy en Windows instala su
# propio manejador de eventos de consola, que a veces interpreta un clic
# o cambio de foco en PowerShell como si fuera Ctrl+C y aborta el proceso
# entero con "forrtl: error (200)". Esto lo desactiva — debe fijarse ANTES
# de importar openseespy.
os.environ.setdefault("FOR_DISABLE_CONSOLE_CTRL_HANDLER", "1")

from dataclasses import dataclass, field

import openseespy.opensees as ops


# =============================================================================
# MODELOS DE DATOS (para tablas y viewport)
# =============================================================================

@dataclass
class Nodo:
    tag: int
    x: float
    y: float
    z: float
    restringido: bool = False
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    rz: float = 0.0
    rx_reac: float = 0.0
    ry_reac: float = 0.0
    rz_reac: float = 0.0

    @property
    def coord(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def coord_deformada(self) -> tuple[float, float, float]:
        return (self.x + self.dx, self.y + self.dy, self.z + self.dz)


@dataclass
class Elemento:
    tag: int
    tipo: str                       # "columna" | "viga"
    nodo_i: int
    nodo_j: int
    axial: float = 0.0              # N (+ tracción / - compresión) extremo i
    corte_y: float = 0.0
    corte_z: float = 0.0
    momento_y: float = 0.0
    momento_z: float = 0.0


@dataclass
class ResultadoModelo:
    nodos: list[Nodo] = field(default_factory=list)
    elementos: list[Elemento] = field(default_factory=list)
    analizado: bool = False


# =============================================================================
# REPO
# =============================================================================

class OpenSeesRepo:
    """Encapsula el dominio OpenSees activo en memoria (proceso único, sin BD)."""

    # Secciones/material genéricos para el modelo de ejemplo (unidades: m, kN)
    E_CONCRETO = 2.5e7        # kN/m2
    G_CONCRETO = 1.0e7
    COL_A, COL_IZ, COL_IY, COL_J = 0.16, 0.00213, 0.00213, 0.00360   # 0.4x0.4 m
    VIGA_A, VIGA_IZ, VIGA_IY, VIGA_J = 0.09, 0.00108, 0.00047, 0.00135  # 0.3x0.3m aprox

    def __init__(self):
        self._construido = False
        self._analizado = False
        self._nodos_tags: list[int] = []
        self._elementos: dict[int, tuple[str, int, int]] = {}  # tag -> (tipo, i, j)
        self._nodos_restringidos: set[int] = set()

    # ------------------------------------------------------------------ #
    # CONSTRUCCIÓN DE MODELO DE EJEMPLO
    # ------------------------------------------------------------------ #

    def construir_modelo_ejemplo(self, niveles: int = 3, bahias_x: int = 2,
                                  bahias_y: int = 2, hx: float = 5.0,
                                  hy: float = 5.0, hz: float = 3.0) -> None:
        """Genera un edificio aporticado regular en 3D: (bahias_x+1) x (bahias_y+1)
        columnas por nivel, vigas en X e Y en cada piso, base empotrada.
        Sirve como dataset de prueba para la interfaz (tablas + viewport).
        """
        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        self._nodos_tags = []
        self._elementos = {}
        self._nodos_restringidos = set()

        nx, ny = bahias_x + 1, bahias_y + 1

        def tag_nodo(nivel: int, i: int, j: int) -> int:
            return nivel * (nx * ny) + i * ny + j + 1

        # ── Nodos ──────────────────────────────────────────────────────
        for nivel in range(niveles + 1):
            z = nivel * hz
            for i in range(nx):
                x = i * hx
                for j in range(ny):
                    y = j * hy
                    t = tag_nodo(nivel, i, j)
                    ops.node(t, x, y, z)
                    self._nodos_tags.append(t)
                    if nivel == 0:
                        ops.fix(t, 1, 1, 1, 1, 1, 1)
                        self._nodos_restringidos.add(t)

        # ── Transformaciones geométricas ─────────────────────────────
        ops.geomTransf('Linear', 1, 1, 0, 0)   # columnas (vector local z aux)
        ops.geomTransf('Linear', 2, 0, 0, 1)   # vigas en X
        ops.geomTransf('Linear', 3, 0, 0, 1)   # vigas en Y

        ele_tag = 1

        # ── Columnas ───────────────────────────────────────────────────
        for nivel in range(1, niveles + 1):
            for i in range(nx):
                for j in range(ny):
                    n_inf = tag_nodo(nivel - 1, i, j)
                    n_sup = tag_nodo(nivel, i, j)
                    ops.element('elasticBeamColumn', ele_tag, n_inf, n_sup,
                                self.COL_A, self.E_CONCRETO, self.G_CONCRETO,
                                self.COL_J, self.COL_IY, self.COL_IZ, 1)
                    self._elementos[ele_tag] = ('columna', n_inf, n_sup)
                    ele_tag += 1

        # ── Vigas dirección X ────────────────────────────────────────
        for nivel in range(1, niveles + 1):
            for j in range(ny):
                for i in range(nx - 1):
                    n1 = tag_nodo(nivel, i, j)
                    n2 = tag_nodo(nivel, i + 1, j)
                    ops.element('elasticBeamColumn', ele_tag, n1, n2,
                                self.VIGA_A, self.E_CONCRETO, self.G_CONCRETO,
                                self.VIGA_J, self.VIGA_IY, self.VIGA_IZ, 2)
                    self._elementos[ele_tag] = ('viga', n1, n2)
                    ele_tag += 1

        # ── Vigas dirección Y ────────────────────────────────────────
        for nivel in range(1, niveles + 1):
            for i in range(nx):
                for j in range(ny - 1):
                    n1 = tag_nodo(nivel, i, j)
                    n2 = tag_nodo(nivel, i, j + 1)
                    ops.element('elasticBeamColumn', ele_tag, n1, n2,
                                self.VIGA_A, self.E_CONCRETO, self.G_CONCRETO,
                                self.VIGA_J, self.VIGA_IY, self.VIGA_IZ, 3)
                    self._elementos[ele_tag] = ('viga', n1, n2)
                    ele_tag += 1

        # ── Cargas: gravedad (nodal, hacia -Z) + empuje lateral en X ───
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        for nivel in range(1, niveles + 1):
            for i in range(nx):
                for j in range(ny):
                    t = tag_nodo(nivel, i, j)
                    fx = 5.0 * nivel      # empuje lateral creciente con la altura
                    ops.load(t, fx, 0.0, -20.0, 0.0, 0.0, 0.0)

        self._construido = True
        self._analizado = False

    # ------------------------------------------------------------------ #
    # CONSTRUCCIÓN DESDE LA BASE DE DATOS DEL PROYECTO
    # ------------------------------------------------------------------ #

    def construir_desde_db(self, conn) -> list[str]:
        """Construye el modelo REAL de OpenSees a partir de la BD del
        proyecto (nodos, barras, secciones, materiales, restricciones y
        cargas nodales) — reemplaza a construir_modelo_ejemplo() como
        fuente del modelo que usan el viewport y el análisis.

        `conn` es una sqlite3.Connection con row_factory = sqlite3.Row
        (ver backend/database/db.py).

        Devuelve una lista de avisos (barra sin sección/material -> se
        usaron valores por defecto, referencias rotas, modelo sin cargas,
        etc.) para que el llamador los muestre donde le convenga (barra de
        estado). Lista vacía = todo capturado correctamente.
        """
        avisos: list[str] = []

        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        self._nodos_tags = []
        self._elementos = {}
        self._nodos_restringidos = set()

        filas_nodos = conn.execute(
            "SELECT id, etiqueta, x, y, z, restr_ux, restr_uy, restr_uz, "
            "restr_rx, restr_ry, restr_rz FROM nodos"
        ).fetchall()
        if not filas_nodos:
            self._construido = False
            self._analizado = False
            return ["El proyecto no tiene nudos capturados (hoja Nudos → Coordenadas)."]

        id_a_tag: dict[int, int] = {}
        coords: dict[int, tuple[float, float, float]] = {}
        for tag, fila in enumerate(filas_nodos, start=1):
            id_a_tag[fila["id"]] = tag
            x, y, z = fila["x"] or 0.0, fila["y"] or 0.0, fila["z"] or 0.0
            ops.node(tag, x, y, z)
            coords[tag] = (x, y, z)
            self._nodos_tags.append(tag)

            restrs = [fila[c] or 0 for c in
                      ("restr_ux", "restr_uy", "restr_uz",
                       "restr_rx", "restr_ry", "restr_rz")]
            if any(restrs):
                ops.fix(tag, *[1 if r else 0 for r in restrs])
                self._nodos_restringidos.add(tag)

        filas_barras = conn.execute(
            "SELECT b.id, b.etiqueta, b.nodo_i_id, b.nodo_j_id, "
            "s.area AS area, s.iy AS iy, s.iz AS iz, s.j AS jj, "
            "m.E AS E, m.G AS G "
            "FROM barras b "
            "LEFT JOIN secciones s ON s.id = b.seccion_id "
            "LEFT JOIN materiales m ON m.id = b.material_id"
        ).fetchall()
        if not filas_barras:
            avisos.append("El proyecto no tiene barras capturadas (hoja Miembros → Conectividad); solo se muestran nudos.")

        # geomTransf: una por cada vector de referencia distinto que haga
        # falta (columnas verticales -> referencia en X; todo lo demás ->
        # referencia en Z), se cachean para no repetir geomTransf iguales.
        transf_cache: dict[tuple, int] = {}
        siguiente_transf = 1

        def transf_para(vec_xz: tuple) -> int:
            nonlocal siguiente_transf
            if vec_xz not in transf_cache:
                ops.geomTransf('Linear', siguiente_transf, *vec_xz)
                transf_cache[vec_xz] = siguiente_transf
                siguiente_transf += 1
            return transf_cache[vec_xz]

        avisos_seccion = False
        ele_tag = 1
        for fila in filas_barras:
            ni = id_a_tag.get(fila["nodo_i_id"])
            nj = id_a_tag.get(fila["nodo_j_id"])
            if ni is None or nj is None:
                avisos.append(f"Barra '{fila['etiqueta']}' referencia un nudo inexistente; se omitió.")
                continue

            area = fila["area"] or self.VIGA_A
            iy = fila["iy"] or self.VIGA_IY
            iz = fila["iz"] or self.VIGA_IZ
            j_ = fila["jj"] or self.VIGA_J
            e = fila["E"] or self.E_CONCRETO
            g = fila["G"] or self.G_CONCRETO
            if not fila["area"] or not fila["E"]:
                avisos_seccion = True

            p_i, p_j = coords[ni], coords[nj]
            vertical = (abs(p_i[0] - p_j[0]) < 1e-9 and abs(p_i[1] - p_j[1]) < 1e-9)
            vec_xz = (1.0, 0.0, 0.0) if vertical else (0.0, 0.0, 1.0)
            transf = transf_para(vec_xz)

            ops.element('elasticBeamColumn', ele_tag, ni, nj,
                        area, e, g, j_, iy, iz, transf)
            self._elementos[ele_tag] = ("columna" if vertical else "viga", ni, nj)
            ele_tag += 1

        if avisos_seccion:
            avisos.append("Una o más barras no tienen sección/material asignado (hoja Miembros → Secciones/Materiales); se usaron valores por defecto.")

        # ── Cargas nodales — todos los casos de carga capturados se suman
        # en un único patrón estático (no hay todavía combinaciones ni
        # pasos de carga por caso; ver Gen → Casos de carga a futuro). ──
        filas_cargas = conn.execute(
            "SELECT nodo_id, fx, fy, fz, mx, my, mz FROM nodo_fuerzas"
        ).fetchall()
        ops.timeSeries('Linear', 1)
        ops.pattern('Plain', 1, 1)
        hay_carga = False
        for fila in filas_cargas:
            tag = id_a_tag.get(fila["nodo_id"])
            if tag is None:
                continue
            vals = [fila[c] or 0.0 for c in ("fx", "fy", "fz", "mx", "my", "mz")]
            if any(vals):
                ops.load(tag, *vals)
                hay_carga = True
        if not hay_carga:
            avisos.append("El modelo no tiene cargas nodales capturadas (hoja Nudos → Fuerzas); el análisis dará desplazamientos en cero.")

        # ⚠️ Cargas distribuidas sobre miembros (barra_cargas) todavía no
        # se aplican al motor — pendiente (requiere eleLoad por tramo).

        self._construido = True
        self._analizado = False
        return avisos

    def tiene_modelo(self) -> bool:
        """True si hay un modelo construido con al menos un nudo."""
        return self._construido and bool(self._nodos_tags)

    # ------------------------------------------------------------------ #
    # ANÁLISIS
    # ------------------------------------------------------------------ #

    def analizar(self) -> bool:
        """Análisis estático lineal simple. Devuelve True si convergió."""
        if not self._construido:
            raise RuntimeError("Primero llama a construir_modelo_ejemplo().")

        ops.system('BandGeneral')
        ops.numberer('RCM')
        ops.constraints('Plain')
        ops.integrator('LoadControl', 1.0)
        ops.algorithm('Linear')
        ops.analysis('Static')
        ok = ops.analyze(1)

        self._analizado = (ok == 0)
        return self._analizado

    # ------------------------------------------------------------------ #
    # LECTURA DE RESULTADOS
    # ------------------------------------------------------------------ #

    def obtener_nodos(self) -> list[Nodo]:
        nodos = []
        for t in self._nodos_tags:
            x, y, z = ops.nodeCoord(t)
            n = Nodo(tag=t, x=x, y=y, z=z, restringido=t in self._nodos_restringidos)
            if self._analizado:
                disp = ops.nodeDisp(t)
                n.dx, n.dy, n.dz, n.rx, n.ry, n.rz = disp
                if t in self._nodos_restringidos:
                    reac = ops.nodeReaction(t)
                    n.rx_reac, n.ry_reac, n.rz_reac = reac[0], reac[1], reac[2]
            nodos.append(n)
        return nodos

    def obtener_elementos(self) -> list[Elemento]:
        elementos = []
        for tag, (tipo, ni, nj) in self._elementos.items():
            el = Elemento(tag=tag, tipo=tipo, nodo_i=ni, nodo_j=nj)
            if self._analizado:
                try:
                    fuerzas = ops.eleForce(tag)  # [N,Vy,Vz,T,My,Mz] extremo i ... extremo j
                    el.axial     = fuerzas[0]
                    el.corte_y   = fuerzas[1]
                    el.corte_z   = fuerzas[2]
                    el.momento_y = fuerzas[4]
                    el.momento_z = fuerzas[5]
                except Exception:
                    pass
            elementos.append(el)
        return elementos

    def resultado_completo(self) -> ResultadoModelo:
        return ResultadoModelo(
            nodos=self.obtener_nodos(),
            elementos=self.obtener_elementos(),
            analizado=self._analizado,
        )
