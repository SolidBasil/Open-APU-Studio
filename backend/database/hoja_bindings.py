"""
hoja_bindings.py
================
Capa de acceso a datos entre las hojas del sidebar (TreeTableWidget) y la
base de datos SQLite del proyecto (schema.sql).

Cada sub-pestaña del sidebar (TreeTableWidget) se
describe con una `HojaBinding`: qué tabla SQL le corresponde y cómo se lee/
escribe cada una de sus columnas. Con esa descripción, `cargar_hoja()` y
`guardar_fila()` sirven para CUALQUIER hoja sin código especial por tabla.

Tipos de columna:
    "texto" — columna directa de la tabla (texto o número).
    "check" — columna booleana (0/1), se edita como checkbox.
    "ref"   — columna FK: se muestra/edita por el nombre visible de la fila
              referenciada (nodos.etiqueta, secciones.nombre, etc.), no por
              su id interno.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


# =============================================================================
# DESCRIPCIÓN DE COLUMNAS Y HOJAS
# =============================================================================

@dataclass
class Col:
    columna: str                    # columna real en la tabla SQL de la hoja
    tipo: str = "texto"             # "texto" | "check" | "ref"
    ref_tabla: str | None = None    # tabla referenciada (solo tipo == "ref")
    ref_label: str = "etiqueta"     # columna visible de esa tabla ("etiqueta" o "nombre")
    numero: bool = False            # True -> se guarda como float (columnas REAL)


def T(columna, numero=False) -> Col:
    return Col(columna, "texto", numero=numero)


def CH(columna) -> Col:
    return Col(columna, "check")


def REF(columna, tabla, label="etiqueta") -> Col:
    return Col(columna, "ref", ref_tabla=tabla, ref_label=label)


@dataclass
class HojaBinding:
    tabla: str
    columnas: list[Col]
    fila_unica: bool = False   # True para peso_propio (siempre id=1, sin etiqueta)


# =============================================================================
# MAPEO (categoría, sub-pestaña) -> HojaBinding
# El orden de `columnas` debe calzar exactamente con ESTRUCTURA[cat][sub].
# =============================================================================

BINDINGS: dict[tuple[str, str], HojaBinding] = {

    # ── Nudos ──────────────────────────────────────────────────────────
    ("Nudos", "Coordenadas"): HojaBinding("nodos", [
        T("etiqueta"), T("x", numero=True), T("y", numero=True), T("z", numero=True),
    ]),
    ("Nudos", "Restricciones"): HojaBinding("nodos", [
        T("etiqueta"), CH("restr_ux"), CH("restr_uy"), CH("restr_uz"),
        CH("restr_rx"), CH("restr_ry"), CH("restr_rz"),
    ]),
    ("Nudos", "Resortes"): HojaBinding("nodos", [
        T("etiqueta"), T("resorte_kx", True), T("resorte_ky", True), T("resorte_kz", True),
        T("resorte_krx", True), T("resorte_kry", True), T("resorte_krz", True),
    ]),
    ("Nudos", "Diafragma de piso rígido"): HojaBinding("nodos", [
        T("etiqueta"), T("piso"), T("diafragma"),
    ]),
    ("Nudos", "Masas"): HojaBinding("nodos", [
        T("etiqueta"), T("masa_mx", True), T("masa_my", True), T("masa_mz", True),
    ]),
    ("Nudos", "Fuerzas"): HojaBinding("nodo_fuerzas", [
        REF("nodo_id", "nodos"),
        T("fx", True), T("fy", True), T("fz", True),
        T("mx", True), T("my", True), T("mz", True),
        REF("caso_id", "casos_carga", "nombre"),
    ]),
    ("Nudos", "Desplazamientos prescritos"): HojaBinding("nodo_desplazamientos_prescritos", [
        REF("nodo_id", "nodos"),
        T("dx", True), T("dy", True), T("dz", True),
        T("rx", True), T("ry", True), T("rz", True),
        REF("caso_id", "casos_carga", "nombre"),
    ]),

    # ── Miembros (Barras) ────────────────────────────────────────────────
    ("Miembros", "Conectividad"): HojaBinding("barras", [
        T("etiqueta"), REF("nodo_i_id", "nodos"), REF("nodo_j_id", "nodos"), T("descripcion"),
    ]),
    ("Miembros", "Conexiones de nudos"): HojaBinding("barras", [
        T("etiqueta"), T("condicion_i"), T("condicion_j"),
    ]),
    ("Miembros", "Secciones"): HojaBinding("barras", [
        T("etiqueta"), REF("seccion_id", "secciones", "nombre"),
    ]),
    ("Miembros", "Materiales"): HojaBinding("barras", [
        T("etiqueta"), REF("material_id", "materiales", "nombre"),
    ]),
    ("Miembros", "Ejes locales"): HojaBinding("barras", [
        T("etiqueta"), T("angulo_beta", True),
    ]),
    ("Miembros", "Punto cardinal"): HojaBinding("barras", [
        T("etiqueta"), T("punto_cardinal"),
    ]),
    ("Miembros", "Cacho rígido"): HojaBinding("barras", [
        T("etiqueta"), T("cacho_i", True), T("cacho_j", True),
    ]),
    ("Miembros", "Articulaciones"): HojaBinding("barras", [
        T("etiqueta"), T("articulacion_i"), T("articulacion_j"),
    ]),
    ("Miembros", "Comportamiento axial"): HojaBinding("barras", [
        T("etiqueta"), T("comportamiento_axial"),
    ]),
    ("Miembros", "Cargas sobre miembros"): HojaBinding("barra_cargas", [
        REF("barra_id", "barras"), T("tipo_carga"), T("magnitud", True), T("direccion"),
        REF("caso_id", "casos_carga", "nombre"),
    ]),
    ("Miembros", "Número de piso"): HojaBinding("barras", [
        T("etiqueta"), T("piso"),
    ]),

    # ── Placas ─────────────────────────────────────────────────────────
    ("Placas", "Conectividad"): HojaBinding("placas", [
        T("etiqueta"), REF("nodo1_id", "nodos"), REF("nodo2_id", "nodos"),
        REF("nodo3_id", "nodos"), REF("nodo4_id", "nodos"), T("descripcion"),
    ]),
    ("Placas", "Espesor"): HojaBinding("placas", [
        T("etiqueta"), T("espesor", True), T("tipo"),
    ]),
    ("Placas", "Material"): HojaBinding("placas", [
        T("etiqueta"), REF("material_id", "materiales", "nombre"),
    ]),
    ("Placas", "Ejes locales"): HojaBinding("placas", [
        T("etiqueta"), T("angulo_ejes", True),
    ]),
    ("Placas", "Apoyos intermedios"): HojaBinding("placa_apoyos_intermedios", [
        REF("placa_id", "placas"), REF("nodo_id", "nodos"),
    ]),
    ("Placas", "Cargas"): HojaBinding("placa_cargas", [
        REF("placa_id", "placas"), T("tipo_carga"), T("magnitud", True), T("direccion"),
        REF("caso_id", "casos_carga", "nombre"),
    ]),
    ("Placas", "Claros"): HojaBinding("placas", [
        T("etiqueta"), T("claro_x", True), T("claro_y", True),
    ]),
    ("Placas", "Interfaces"): HojaBinding("placas", [
        T("etiqueta"), T("interface"),
    ]),
    ("Placas", "Número de piso"): HojaBinding("placas", [
        T("etiqueta"), T("piso"),
    ]),
    ("Placas", "Factor de rigidez"): HojaBinding("placas", [
        T("etiqueta"), T("factor_rigidez", True),
    ]),

    # ── Área ───────────────────────────────────────────────────────────
    ("Área", "Nudos"): HojaBinding("areas", [
        T("etiqueta"), REF("nodo1_id", "nodos"), REF("nodo2_id", "nodos"),
        REF("nodo3_id", "nodos"), REF("nodo4_id", "nodos"),
    ]),
    ("Área", "Dirección de carga"): HojaBinding("areas", [
        T("etiqueta"), T("direccion_carga"),
    ]),
    ("Área", "Cargas"): HojaBinding("area_cargas", [
        REF("area_id", "areas"), T("magnitud", True), REF("caso_id", "casos_carga", "nombre"),
    ]),

    # ── Gen ────────────────────────────────────────────────────────────
    ("Gen", "Peso propio"): HojaBinding("peso_propio", [
        T("factor_x", True), T("factor_y", True), T("factor_z", True),
    ], fila_unica=True),
    ("Gen", "Aceleración de sismo"): HojaBinding("sismo_aceleracion", [
        REF("caso_id", "casos_carga", "nombre"), T("ax", True), T("ay", True), T("az", True),
    ]),
    ("Gen", "Espectro sísmico"): HojaBinding("sismo_espectro", [
        REF("caso_id", "casos_carga", "nombre"), T("periodo_s", True), T("sa_g", True),
    ]),

    # ── Catálogos ──────────────────────────────────────────────────────
    ("Catálogos", "Secciones"): HojaBinding("secciones", [
        T("nombre"), T("tipo"), T("area", True), T("iy", True), T("iz", True),
        T("j", True), T("b", True), T("h", True), T("d", True),
    ]),
    ("Catálogos", "Materiales"): HojaBinding("materiales", [
        T("nombre"), T("tipo"), T("E", True), T("G", True), T("poisson", True),
        T("peso_especifico", True), T("fy", True), T("fpc", True),
    ]),
    ("Catálogos", "Casos de carga"): HojaBinding("casos_carga", [
        T("nombre"), T("tipo"),
    ]),
}


# =============================================================================
# AUTO-ID — número autoincremental para la columna "etiqueta" de las
# tablas de elementos (Nudo/Miembro/Placa/Área). El usuario ya no la
# escribe a mano: se genera sola (1, 2, 3...) la primera vez que llena
# cualquier otra columna de una fila nueva. Cada tabla lleva su propio
# contador (un Nudo "3" y una Barra "3" no chocan, son tablas distintas).
# Los catálogos (secciones/materiales/casos_carga) NO entran aquí — su
# columna "nombre" sigue siendo texto libre.
# =============================================================================

TABLAS_AUTO_ID: set[str] = {"nodos", "barras", "placas", "areas"}


def siguiente_etiqueta(conn: sqlite3.Connection, tabla: str) -> str:
    """Genera la siguiente etiqueta autoincremental para `tabla`: "1", "2",
    "3"... (solo número, sin prefijo).

    Toma el número más alto ya usado y le suma 1, en vez de contar filas —
    así no se repiten etiquetas aunque se haya borrado alguna intermedia.
    """
    maximo = 0
    for (etiqueta,) in conn.execute(f"SELECT etiqueta FROM {tabla}"):
        if etiqueta and etiqueta.isdigit():
            maximo = max(maximo, int(etiqueta))
    return str(maximo + 1)


# =============================================================================
# CARGA / GUARDADO GENÉRICO
# =============================================================================

def cargar_hoja(conn: sqlite3.Connection, binding: HojaBinding) -> list[tuple[int, list[str]]]:
    """Lee todas las filas de una hoja. Devuelve [(id_fila, [valores_texto...]), ...].

    Las columnas "ref" ya vienen resueltas al nombre visible (JOIN), no al id.
    """
    if binding.fila_unica:
        fila = conn.execute(f"SELECT * FROM {binding.tabla} WHERE id = 1").fetchone()
        if fila is None:
            return []
        valores = [_texto(fila[c.columna]) for c in binding.columnas]
        return [(1, valores)]

    selects, joins = [], []
    for i, c in enumerate(binding.columnas):
        if c.tipo == "ref":
            alias = f"r{i}"
            joins.append(f"LEFT JOIN {c.ref_tabla} {alias} ON {alias}.id = {binding.tabla}.{c.columna}")
            selects.append(f"{alias}.{c.ref_label}")
        else:
            selects.append(f"{binding.tabla}.{c.columna}")

    sql = f"SELECT {binding.tabla}.id, {', '.join(selects)} FROM {binding.tabla} " + " ".join(joins)
    filas = conn.execute(sql).fetchall()
    return [(f[0], [_texto(v) for v in f[1:]]) for f in filas]


def guardar_fila(conn: sqlite3.Connection, binding: HojaBinding,
                  fila_id: int | None, valores: list[str]) -> tuple[int | None, str | None]:
    """Guarda una fila completa (INSERT si fila_id es None, UPDATE si no).

    Devuelve (id_resultante, None) si guardó bien, o (None, mensaje_error) si no
    (ej. una columna "ref" no encuentra el nombre escrito, o falta un dato
    obligatorio) — el llamador decide cómo mostrar el error, este módulo no
    conoce la UI.
    """
    if binding.fila_unica:
        columnas_sql, parametros = [], []
        for c, texto in zip(binding.columnas, valores):
            columnas_sql.append(c.columna)
            parametros.append(_a_numero(texto) if c.numero else (texto or None))
        set_clause = ", ".join(f"{c} = ?" for c in columnas_sql)
        conn.execute(f"UPDATE {binding.tabla} SET {set_clause} WHERE id = 1", parametros)
        conn.commit()
        return 1, None

    # Varias sub-pestañas pueden compartir la misma tabla ancha (ej.
    # Coordenadas y Restricciones son ambas `nodos`). Si la primera columna
    # es el propio nombre/etiqueta de la tabla (no una "ref" a otra tabla)
    # y ya existe una fila con ese valor, esto es una edición de esa fila
    # desde otra sub-pestaña, no una fila nueva -> UPDATE, no INSERT.
    if fila_id is None and binding.columnas and binding.columnas[0].tipo == "texto":
        etiqueta = (valores[0] or "").strip()
        if etiqueta:
            existente = conn.execute(
                f"SELECT id FROM {binding.tabla} WHERE {binding.columnas[0].columna} = ?",
                (etiqueta,),
            ).fetchone()
            if existente is not None:
                fila_id = existente["id"]

    columnas_sql, parametros = [], []
    for c, texto in zip(binding.columnas, valores):
        texto = (texto or "").strip()
        if c.tipo == "ref":
            if not texto:
                return None, f"'{c.columna}' es obligatorio"
            fila_ref = conn.execute(
                f"SELECT id FROM {c.ref_tabla} WHERE {c.ref_label} = ?", (texto,)
            ).fetchone()
            if fila_ref is None:
                return None, f"No existe '{texto}' en {c.ref_tabla}"
            columnas_sql.append(c.columna)
            parametros.append(fila_ref["id"])
        elif c.tipo == "check":
            columnas_sql.append(c.columna)
            parametros.append(1 if texto in ("1", "true", "True") else 0)
        else:
            columnas_sql.append(c.columna)
            if not texto:
                parametros.append(None)
            elif c.numero:
                num = _a_numero(texto)
                if num is None:
                    return None, f"'{texto}' no es un número válido"
                parametros.append(num)
            else:
                parametros.append(texto)

    try:
        if fila_id is None:
            placeholders = ", ".join(["?"] * len(columnas_sql))
            sql = f"INSERT INTO {binding.tabla} ({', '.join(columnas_sql)}) VALUES ({placeholders})"
            cur = conn.execute(sql, parametros)
            conn.commit()
            return cur.lastrowid, None
        else:
            set_clause = ", ".join(f"{c} = ?" for c in columnas_sql)
            sql = f"UPDATE {binding.tabla} SET {set_clause} WHERE id = ?"
            conn.execute(sql, parametros + [fila_id])
            conn.commit()
            return fila_id, None
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return None, str(e)


def eliminar_fila(conn: sqlite3.Connection, binding: HojaBinding, fila_id: int) -> None:
    conn.execute(f"DELETE FROM {binding.tabla} WHERE id = ?", (fila_id,))
    conn.commit()


# ── Helpers ──────────────────────────────────────────────────────────────

def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        # Sin ceros de más (3.0 -> "3", 3.5 -> "3.5")
        return f"{valor:g}"
    return str(valor)


def _a_numero(texto: str) -> float | None:
    try:
        return float(texto)
    except (TypeError, ValueError):
        return None
