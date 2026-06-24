"""
importar.py
===========
Importa un proyecto OPUS 2010 (archivos .DBF) al esquema SQLite
de Open APU Studio.

Detecta automáticamente el prefijo del proyecto y el formato de archivos
(sufijos clásicos EGP/EGF/EGN o numéricos P/F/N/1/A).

Reglas:
  1. Todo registro con _deleted=True se ignora antes de cualquier procesamiento.
  2. La jerarquía se reconstruye por PRE_WBS (truncado de derecha a izquierda).
     Ver SCHEMA.md sección "Decisiones de diseño — jerarquía por WBS".
  3. Los importes (PRE_VOL × PRE_PRE) se materializan al insertar.
  4. Los subtotales de capítulos se calculan bottom-up al final.
  5. Toda referencia a catálogos también filtra _deleted=False.
  6. PRE_IDPAD del *1.DBF NO se usa para resolver padres (pertenece a otra
     tabla de OPUS y sus valores coinciden con PRE_ID solo por azar).

Archivos DBF que lee:
  *P.DBF   — Catálogo de insumos (materiales, MO, equipo, etc.)
  *F.DBF   — Fórmulas/APU: componentes de cada concepto o insumo compuesto
  *N.DBF   — Resúmenes de APU por concepto (totales por tipo de costo)
  *X.DBF   — EGX: relación de insumos compuestos (obsoleto en v3, usamos es_compuesto)
  *Z.DBF   — Configuración del proyecto (horas/día, tasas)
  *I.DBF   — Renglones de sobrecostos (pie de precios)
  *1.DBF   — Árbol jerárquico del presupuesto (formato numérico)
  *A.DBF   — Nombres de unidades/agrupadores para el árbol

Uso:
    from backend.importar import importar

    stats = importar(
        carpeta  = "C:/OPUSCMS/Obras/D60JALISCOT",
        db_path  = "D60JALISCOT.db",
        nombre   = "Vivienda D60 Jalisco"   # opcional
    )
"""

import sqlite3
import sys
import uuid
from pathlib import Path

from backend.db import Database

try:
    from dbfread import DBF
except ImportError:
    raise ImportError("Instala dbfread:  pip install dbfread")


# =============================================================================
# UTILIDADES
# =============================================================================

# ── convertir a float con valor por defecto ──
def _f(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── convertir a string limpio con valor por defecto ──
def _s(val, default=""):
    if val is None:
        return default
    return str(val).strip()


# ── leer archivo DBF filtrando registros borrados ──
def _leer_dbf(ruta: Path, encoding="latin-1") -> list[dict]:
    """Lee un .DBF devolviendo solo registros activos (_deleted=False)."""
    if not ruta or not ruta.exists():
        return []
    for enc in [encoding, "cp850", "latin-1"]:
        try:
            tabla   = DBF(str(ruta), encoding=enc, load=True)
            activos = [dict(r) for r in tabla if not r.get("_deleted", False)]
            borrados = sum(1 for r in tabla if r.get("_deleted", False))
            print(f"  ✓ {ruta.name}: {len(activos)} activos / {borrados} borrados")
            return activos
        except Exception as e:
            last_err = e
    print(f"  ✗ {ruta.name}: {last_err}")
    return []


# =============================================================================
# DETECCIÓN DEL PROYECTO
# =============================================================================

_SUFIJOS = {
    "clasico":  {"P":"EGP","F":"EGF","N":"EGN","X":"EGX","Z":"EGZ","I":"EGI"},
    "numerico": {"P":"P",  "F":"F",  "N":"N",  "X":"X",  "Z":"Z",  "I":"I",
                 "1":"1",  "A":"A"},
}


# ── detectar prefijo y formato del proyecto ──
def _detectar(carpeta: Path) -> tuple[str, str]:
    """Devuelve (prefijo, formato) — 'clasico' o 'numerico'."""
    for f in sorted(carpeta.glob("*EGP.DBF")) + sorted(carpeta.glob("*egp.dbf")):
        return f.stem[:-3], "clasico"
    cont = {}
    for f in carpeta.glob("*.DBF"):
        for s in ["1", "P", "F", "N"]:
            if f.stem.upper().endswith(s):
                p = f.stem[:-len(s)]
                cont[p] = cont.get(p, 0) + 1
    if cont:
        return max(cont, key=cont.get), "numerico"
    raise ValueError(f"No se encontraron archivos OPUS en {carpeta}")


# ── resolver ruta de archivo DBF por sufijo ──
def _ruta_dbf(carpeta: Path, prefijo: str, formato: str, clave: str) -> Path | None:
    sufijo = _SUFIJOS[formato].get(clave, "")
    for nombre in [f"{prefijo}{sufijo}.DBF", f"{prefijo}{sufijo}.dbf"]:
        r = carpeta / nombre
        if r.exists():
            return r
    return None


# =============================================================================
# JERARQUÍA — ALGORITMO WBS
# =============================================================================

# ── determinar padre truncando WBS de derecha a izquierda ──
def _padre_por_wbs(wbs: str, wbs_a_id: dict) -> int | None:
    """
    Trunca PRE_WBS de derecha a izquierda hasta encontrar un nodo activo.
    Fuente de verdad de la jerarquía — ver SCHEMA.md.

    OPUS asigna WBS de forma jerárquica: 1, 11, 111, 11101…
    Truncando el último carácter o grupo se obtiene el WBS del padre.
    Ej: 11101 → 1110 (no existe) → 111 (existe, es el padre).

    wbs_a_id se construye a medida que se procesan nodos (orden WBS ascendente),
    por lo que el padre siempre está en el dict cuando se procesa un hijo.
    """
    if not wbs or len(wbs) <= 1:
        return None
    codigo = wbs[:-1]
    while codigo:
        if codigo in wbs_a_id:
            return wbs_a_id[codigo]
        codigo = codigo[:-1]
    return None


# =============================================================================
# TIPO DE INSUMO
# =============================================================================

# ── bit de mayor peso del prefijo OPUS → id de tipo de insumo ──
def _tipo_id(prefijo: int) -> int:
    """Bit de mayor peso del campo PREFIJO de OPUS → id de tipos_insumo."""
    p = int(prefijo or 0)
    for bit in [128, 64, 32, 16, 8, 4, 2, 1]:
        if p & bit:
            return bit
    return 1


# =============================================================================
# IMPORTACIÓN PRINCIPAL
# =============================================================================

def importar(carpeta: str, db_path: str, nombre: str | None = None) -> dict:
    """
    Importa un proyecto OPUS al SQLite de Open APU Studio.

    Args:
        carpeta:  Ruta a la carpeta con los archivos .DBF
        db_path:  Ruta del archivo .db de destino (se crea si no existe)
        nombre:   Nombre del proyecto (default: se infiere del prefijo)

    Returns:
        Dict con estadísticas: estructura_presupuesto, insumos, apu_matrices, apu_resumen_totales, etc.
    """
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise ValueError(f"Carpeta no válida: {carpeta}")

    print(f"\n=== Importando proyecto ===")
    prefijo, formato = _detectar(carpeta)
    print(f"  Prefijo : {prefijo!r}")
    print(f"  Formato : {formato}")

    nombre_proyecto = nombre or f"Proyecto {prefijo}"
    sesion = str(__import__('uuid').uuid4())  # agrupa cambios de esta importación

    # Abrir DB (aplica schema.sql automáticamente si es nueva)
    db  = Database.abrir(db_path)
    con = db.conn
    cur = con.cursor()

    # ── Leer DBFs ────────────────────────────────────────────────────────
    print("\nLeyendo archivos DBF...")

    def dbf(clave):
        r = _ruta_dbf(carpeta, prefijo, formato, clave)
        return _leer_dbf(r) if r else []

    regs_p = dbf("P")
    regs_f = dbf("F")
    regs_n = dbf("N")
    regs_x = dbf("X")
    regs_z = dbf("Z")
    regs_i = dbf("I")
    regs_1 = dbf("1")
    regs_a = dbf("A")

    # ── Proyecto ─────────────────────────────────────────────────────────
    print("\nInsertando...")
    cfg = regs_z[0] if regs_z else {}

    cur.execute("""
        INSERT INTO proyectos
            (nombre, clave_opus, moneda_nombre, moneda_simbolo,
             moneda_abrev, iva_porcentaje, creado_por)
        VALUES (?, ?, 'Peso mexicano', '$', 'MXN', 16.0, 1)
    """, (nombre_proyecto, prefijo))
    proyecto_id = cur.lastrowid

    cur.execute("""
        INSERT INTO configuracion_proyecto
            (proyecto_id, horas_dia, tasa_seguro, tasa_interes)
        VALUES (?, ?, ?, ?)
    """, (proyecto_id, _f(cfg.get("HORASDIA"), 8),
          _f(cfg.get("SEGURO")), _f(cfg.get("TASA_INTER"))))

    con.commit()
    print(f"  → proyecto '{nombre_proyecto}' (id={proyecto_id})")

    # ── Pie de precios ────────────────────────────────────────────────────
    for r in regs_i:
        cur.execute("""
            INSERT INTO sobrecostos
                (proyecto_id, orden, variable, descripcion, formula,
                 porcentaje_mn, porcentaje_me, suma_en_total,
                 es_egreso_financ, es_ingreso_financ, se_imprime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (proyecto_id, int(_f(r.get("RENGLON"))),
              _s(r.get("VAR")), _s(r.get("DESC1") or r.get("DESC")),
              _s(r.get("FORMULA")), _f(r.get("PORCMN") or r.get("PORC")),
              _f(r.get("PORCME")),
              1 if r.get("SE_SUMA") else 0,
              1 if r.get("ES_EGRE") else 0,
              1 if r.get("ES_INGR") else 0,
              1 if r.get("SE_IMPR") else 0))
    con.commit()
    print(f"  → sobrecostos: {len(regs_i)}")

    # ── Familias y subfamilias ────────────────────────────────────────────
    # Se recopilan los valores únicos de FAMILIA y SUBFAMILIA del catálogo
    # antes de insertar insumos, para poder resolver familia_id y subfamilia_id.
    #
    # FUERA DE ALCANCE (documentado):
    #   - INDICE (INEGI): clasificación para escalatorias de gobierno
    #   - INDICE_1 al INDICE_6: variables para fórmulas de costo personalizadas
    #   - FORMULA_MN / FORMULA_ME: fórmulas de costo en moneda nacional/extranjera
    #   - Subtotales por tipo (MATERIALES, MANO_DEO, etc.): se recalculan desde APU

    familia_id_por_nombre:    dict[str, int] = {}
    subfamilia_id_por_nombre: dict[tuple, int] = {}  # (familia, subfamilia) → id

    # Nombres alternativos del campo FAMILIA en distintas versiones de OPUS
    _FAM_KEYS  = ["ELE_FAM",  "FAMILIA",  "FAM",  "FAMILIAS", "GRP"]
    _SFAM_KEYS = ["ELE_SFAM", "SUBFAMILIA", "SFAM", "SUBGRUP", "SUBGRUPO"]

    for r in regs_p:
        fam = next((_s(r.get(k)) for k in _FAM_KEYS if _s(r.get(k))), "")
        sub = next((_s(r.get(k)) for k in _SFAM_KEYS if _s(r.get(k))), "")
        if fam and fam not in familia_id_por_nombre:
            cur.execute("""
                INSERT OR IGNORE INTO familias (nombre) VALUES (?)
            """, (fam,))
            cur.execute("SELECT id FROM familias WHERE nombre = ?", (fam,))
            row = cur.fetchone()
            if row:
                familia_id_por_nombre[fam] = row["id"]
        if fam and sub and (fam, sub) not in subfamilia_id_por_nombre:
            fam_id = familia_id_por_nombre.get(fam)
            if fam_id:
                cur.execute("""
                    INSERT OR IGNORE INTO subfamilias (familia_id, nombre) VALUES (?, ?)
                """, (fam_id, sub))
                cur.execute("""
                    SELECT id FROM subfamilias WHERE familia_id = ? AND nombre = ?
                """, (fam_id, sub))
                row = cur.fetchone()
                if row:
                    subfamilia_id_por_nombre[(fam, sub)] = row["id"]

    con.commit()
    n_familias    = len(familia_id_por_nombre)
    n_subfamilias = len(subfamilia_id_por_nombre)
    if n_familias:
        print(f"  → familias: {n_familias}  |  subfamilias: {n_subfamilias}")

    # ── Insumos ───────────────────────────────────────────────────────────
    # Campos importados: clave, tipo, descripcion, unidad, precio, basico,
    #                    fecha, es_compuesto, fsr (salario_real para MO),
    #                    clave_usuario, peso_kg, familia_id, subfamilia_id
    #                    comentarios → tabla notas
    insumo_id_por_clave: dict[str, int] = {}
    notas_insumos: list[tuple] = []  # (insumo_id, texto) — se insertan al final
    n_compuestos = 0

    # Items que aparecen como padres en *F.DBF tienen APU → es_compuesto=1
    padres_con_apu = {_s(r.get("NOMBRE")) for r in regs_f if _s(r.get("NOMBRE"))}

    for r in regs_p:
        clave = _s(r.get("NOMBRE"))
        if not clave:
            continue

        fam = _s(r.get("ELE_FAM") or r.get("FAMILIA") or r.get("FAM"))
        sub = _s(r.get("ELE_SFAM") or r.get("SUBFAMILIA") or r.get("SFAM"))
        familia_id    = familia_id_por_nombre.get(fam) if fam else None
        subfamilia_id = subfamilia_id_por_nombre.get((fam, sub)) if (fam and sub) else None

        # es_compuesto: bit 32 en PREFIJO o presente como padre en *F.DBF
        # (cuadrillas con PREFIJO=2 pero con APU propio entran por esta segunda)
        prefijo      = int(r.get("PREFIJO") or 0)
        es_compuesto = 1 if ((prefijo & 32) or clave in padres_con_apu) else 0
        if es_compuesto:
            n_compuestos += 1

        # FSR (Factor Salario Real) — solo aplica a mano de obra (tipo_id=2)
        fsr           = _f(r.get("FSR") or r.get("FASAR"))
        salario_real  = _f(r.get("PRECIO")) * fsr if fsr else None

        comentario = _s(r.get("COMENTARIO") or r.get("COMEN") or r.get("MEMO"))

        cur.execute("""
            INSERT OR IGNORE INTO insumos
                (proyecto_id, clave, tipo_id, descripcion, descripcion_corta,
                 unidad, costo_mn, costo_final, es_basico, es_compuesto,
                 fecha_precio, clave_usuario, peso_kg,
                 familia_id, subfamilia_id,
                 salario_real, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            proyecto_id,
            clave,
            _tipo_id(prefijo),
            _s(r.get("DESCRIPCIO") or r.get("DESCRIPCION")),
            _s(r.get("DESCCORTA")),
            _s(r.get("UNIDAD")),
            _f(r.get("PRECIO")),
            _f(r.get("PRECIO")),
            1 if _s(r.get("BASICO")).upper() == "S" else 0,
            es_compuesto,
            _s(r.get("FECHA")),
            _s(r.get("CLAVE_USU") or r.get("CLVUSUARIO") or r.get("CLV_USU")),
            _f(r.get("PESO")) or None,
            familia_id,
            subfamilia_id,
            salario_real,
        ))

        cur.execute("""
            SELECT id FROM insumos WHERE proyecto_id = ? AND clave = ?
        """, (proyecto_id, clave))
        row = cur.fetchone()
        if row:
            insumo_id = row["id"]
            insumo_id_por_clave[clave] = insumo_id
            if comentario:
                notas_insumos.append((insumo_id, comentario))

    con.commit()
    print(f"  → insumos: {len(insumo_id_por_clave)}")

    # Comentarios de insumos → tabla notas (ligados al primer concepto que los use)
    # NOTA: Las notas de insumos se guardan como texto plano con la clave del insumo.
    # En una versión futura se puede ligar a un concepto específico.
    if notas_insumos:
        for insumo_id, texto in notas_insumos:
            cur.execute("""
                INSERT INTO historial
                    (sesion, tabla, registro_id, campo, valor_anterior, valor_nuevo, usuario_id)
                VALUES (?, 'insumos', ?, 'comentario', NULL, ?, 1)
            """, (sesion, insumo_id, texto))
        con.commit()
        print(f"  → comentarios de insumos: {len(notas_insumos)}")

    # ── Árbol ─────────────────────────────────────────────────────────────
    if formato == "numerico":
        nodo_id_sqlite = _arbol_numerico(
            con, cur, proyecto_id, regs_1, regs_a, regs_p)
    else:
        nodo_id_sqlite = _arbol_clasico(
            con, cur, proyecto_id, regs_f, regs_p)

    con.commit()
    print(f"  → estructura_presupuesto: {len(nodo_id_sqlite)}")

    # ── APU NODOS (sintéticos para insumos compuestos fuera del árbol) ─────
    insumo_por_clave = {_s(r.get("NOMBRE")): r for r in regs_p if _s(r.get("NOMBRE"))}

    cur.execute("SELECT clave FROM estructura_presupuesto WHERE proyecto_id = ? AND clave IS NOT NULL",
                (proyecto_id,))
    claves_existentes = {r["clave"] for r in cur.fetchall()}

    # apu_auxiliares eliminado — insumos compuestos ya están en insumos (es_compuesto=1)

    # ── APU matrices (componentes del APU) ──────────────────────────────
    # Lookup de conceptos del árbol por clave
    cur.execute("""
        SELECT clave, id FROM estructura_presupuesto
        WHERE proyecto_id = ? AND clave IS NOT NULL
    """, (proyecto_id,))
    clave_a_conceptos: dict[str, list[int]] = {}
    for r in cur.fetchall():
        clave_a_conceptos.setdefault(r["clave"], []).append(r["id"])

    # Lookup de insumos compuestos por clave (es_compuesto=1)
    # Reemplaza el lookup de apu_auxiliares que fue eliminado
    cur.execute("""
        SELECT clave, id FROM insumos
        WHERE proyecto_id = ? AND es_compuesto = 1
    """, (proyecto_id,))
    clave_a_insumos_compuestos: dict[str, list[int]] = {}
    for r in cur.fetchall():
        clave_a_insumos_compuestos.setdefault(r["clave"], []).append(r["id"])

    n_comp       = 0
    n_skip_padre = 0
    n_skip_ins   = 0

    for r in regs_f:
        concepto_clave = _s(r.get("NOMBRE"))
        insumo_clave   = _s(r.get("COMPONENTE"))
        insumo_id      = insumo_id_por_clave.get(insumo_clave)
        if not insumo_id:
            n_skip_ins += 1
            continue

        # Buscar el padre primero en el árbol, luego en insumos compuestos
        padres = clave_a_conceptos.get(concepto_clave, [])
        es_comp = False
        if not padres:
            padres = clave_a_insumos_compuestos.get(concepto_clave, [])
            es_comp = True
        if not padres:
            n_skip_padre += 1
            continue

        for pid in padres:
            mid = -pid if es_comp else pid
            cur.execute("""
                INSERT INTO apu_matrices
                    (matriz_id, insumo_id, rendimiento, cantidad,
                     precio, formula, orden, creado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (mid, insumo_id,
                  _f(r.get("RENDTO")), _f(r.get("CANTIDAD")),
                  _f(r.get("COSTO")),
                  _s(r.get("EXPRESION") or r.get("MEMOCAD")),
                  int(_f(r.get("CLAVENUM")))))
            n_comp += 1

    con.commit()
    msg = f"  → apu_matrices: {n_comp}"
    if n_skip_padre: msg += f"  |  {n_skip_padre} sin padre"
    if n_skip_ins:   msg += f"  |  {n_skip_ins} sin insumo"
    print(msg)

        # ── APU resumen totales ──────────────────────────────────────────────
    n_tot        = 0
    n_skip_tot   = 0
    for r in regs_n:
        conceptos_ids = clave_a_conceptos.get(_s(r.get("NOMBRE")), [])
        if not conceptos_ids:
            n_skip_tot += 1
            continue
        cd = sum(_f(r.get(k)) for k in ["MM","OO","HH","EE","AA","SUBCONT"])
        for cid in conceptos_ids:
            cur.execute("""
                INSERT OR REPLACE INTO apu_resumen_totales
                    (matriz_id, materiales, mano_obra, herramienta, equipo,
                     auxiliares, subcontratos, costo_directo,
                     indirectos_pct, financiamiento_pct, utilidad_pct, precio_venta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, _f(r.get("MM")), _f(r.get("OO")),
                  _f(r.get("HH")), _f(r.get("EE")), _f(r.get("AA")),
                  _f(r.get("SUBCONT")), cd, _f(r.get("INDIRECTOS")),
                  _f(r.get("FINANCIA")), _f(r.get("UTILIDAD")), _f(r.get("PP"))))
            n_tot += 1

    con.commit()
    msg = f"  → apu_resumen_totales: {n_tot}"
    if n_skip_tot: msg += f"  |  {n_skip_tot} sin concepto"
    print(msg)

        # NOTA: tabla auxiliares (*EGX.DBF) eliminada del schema v2.
    # Los insumos compuestos usan es_compuesto=1 en insumos + apu_matrices.

        # ── Subtotales bottom-up ──────────────────────────────────────────────
    print("  → Recalculando subtotales...")
    _recalcular_subtotales(con, proyecto_id)

    cur.execute("""
        UPDATE proyectos SET total_obra = (
            SELECT COALESCE(SUM(subtotal), 0) FROM estructura_presupuesto
            WHERE proyecto_id = ? AND padre_id IS NULL AND activo = 1
        ) WHERE id = ?
    """, (proyecto_id, proyecto_id))
    con.commit()

    # ── Verificación post-import ────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*) FROM estructura_presupuesto ep
        LEFT JOIN apu_matrices ac ON ac.matriz_id = ep.id
        WHERE ep.proyecto_id = ? AND ep.tipo = 'concepto' AND ep.activo = 1
          AND ac.id IS NULL
    """, (proyecto_id,))
    sin_apu = cur.fetchone()[0]
    if sin_apu:
        print(f"  ⚠  {sin_apu} conceptos sin componentes APU")

    stats = {
        "proyecto_id": proyecto_id,
        "nodos":       len(nodo_id_sqlite),
        "insumos":     len(insumo_id_por_clave),
        "apu_matrices":          n_comp,
        "apu_resumen_totales":   n_tot,
        "insumos_compuestos":    n_compuestos,
        "sobrecostos":           len(regs_i),
    }
    print("\n--- Resumen ---")
    for k, v in stats.items():
        print(f"  {k:<15}: {v}")

    Database.cerrar()
    return stats


# =============================================================================
# ÁRBOL — FORMATO NUMÉRICO (*1 + *A)
# =============================================================================

# ── construir árbol desde formato numérico ──
def _arbol_numerico(con, cur, proyecto_id, regs_1, regs_a, regs_p) -> dict:
    nombres = {int(r["IDUNI"]): r for r in regs_a if r.get("IDUNI") is not None}
    egp     = {_s(r.get("NOMBRE")): r for r in regs_p if _s(r.get("NOMBRE"))}

    nodos_ord  = sorted(regs_1, key=lambda r: _s(r.get("PRE_WBS")))
    activos_id = {int(r.get("PRE_ID") or 0) for r in nodos_ord}

    nodo_id_sqlite: dict[int, int] = {}
    wbs_a_sqlite:   dict[str, int] = {}
    stats = {"wbs": 0, "sin_resolver": 0}

    for r in nodos_ord:
        pre_id    = int(r.get("PRE_ID")  or 0)
        pre_idpad = int(r.get("PRE_IDPAD") or -1)
        wbs       = _s(r.get("PRE_WBS"))
        nivel     = int(r.get("PRE_NIVEL") or 0)
        pre_com   = _s(r.get("PRE_COM"))
        pre_iduni = int(r.get("PRE_IDUNI") or -1)

        # Resolver padre — WBS truncation is the only reliable method.
        # PRE_IDPAD values come from a different OPUS table and are NOT
        # valid PRE_ID references (they only happen to overlap sometimes).
        if pre_idpad == -1:
            padre_id = None
        else:
            padre_id = _padre_por_wbs(wbs, wbs_a_sqlite)
        if padre_id is None:
            stats["sin_resolver"] += 1
        else:
            stats["wbs"] += 1

        # Descripción según tipo
        es_concepto = bool(pre_com)
        if es_concepto:
            rec  = egp.get(pre_com, {})
            desc = _s(rec.get("DESCRIPCIO") or rec.get("DESCCORTA"))
            desc_corta = _s(rec.get("DESCCORTA"))
            unidad     = _s(rec.get("UNIDAD"))
            cantidad   = _f(r.get("PRE_VOL"))
            pu         = _f(r.get("PRE_PRE"))
        else:
            rec  = nombres.get(pre_iduni, {})
            desc = _s(rec.get("DESC") or rec.get("DESCRIPCION") or rec.get("DESCCORTA"))
            desc_corta = _s(rec.get("DESCCORTA") or rec.get("DESC"))
            unidad = cantidad = pu = None

        cur.execute("""
            INSERT INTO estructura_presupuesto
                (proyecto_id, padre_id, wbs, nivel, orden, tipo,
                 clave, descripcion, descripcion_corta, unidad,
                 cantidad, precio_unitario, subtotal, estado, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, 1)
        """, (proyecto_id, padre_id, wbs, nivel,
              int(wbs[-2:]) if len(wbs) >= 2 else 0,
              "concepto" if es_concepto else "capitulo",
              pre_com if es_concepto else None,
              desc, desc_corta, unidad, cantidad, pu))

        sid = cur.lastrowid
        nodo_id_sqlite[pre_id] = sid
        if wbs:
            wbs_a_sqlite[wbs] = sid

    print(f"    WBS: {stats['wbs']}  |  "
          f"Sin resolver: {stats['sin_resolver']}")
    con.commit()
    return nodo_id_sqlite


# =============================================================================
# ÁRBOL — FORMATO CLÁSICO (*EGF con PREF=16)
# =============================================================================

# ── construir árbol desde formato clásico ──
def _arbol_clasico(con, cur, proyecto_id, regs_f, regs_p) -> dict:
    from collections import defaultdict

    egp       = {_s(r.get("NOMBRE")): r for r in regs_p if _s(r.get("NOMBRE"))}
    conceptos = sorted(
        [r for r in regs_f if int(r.get("PREF") or 0) == 16],
        key=lambda r: int(_f(r.get("CLAVENUM")))
    )
    caps = defaultdict(list)
    for r in conceptos:
        caps[int(_f(r.get("CLAVENUM")) // 100)].append(r)

    nodo_id_sqlite = {}
    for orden_cap, cap in enumerate(sorted(caps), start=1):
        wbs_cap = str(orden_cap)
        cur.execute("""
            INSERT INTO estructura_presupuesto
                (proyecto_id, padre_id, wbs, nivel, orden, tipo,
                 clave, descripcion, descripcion_corta, subtotal, estado, creado_por)
            VALUES (?, NULL, ?, 1, ?, 'capitulo', ?, ?, ?, 0, 1, 1)
        """, (proyecto_id, wbs_cap, orden_cap, str(cap),
              f"Capítulo {cap}" if cap else "Generales",
              f"Cap. {cap}"))
        cap_id = cur.lastrowid
        nodo_id_sqlite[f"cap_{cap}"] = cap_id

        for i, r in enumerate(caps[cap], start=1):
            clave = _s(r.get("NOMBRE"))
            rec   = egp.get(clave, {})
            cur.execute("""
                INSERT INTO estructura_presupuesto
                    (proyecto_id, padre_id, wbs, nivel, orden, tipo,
                     clave, descripcion, descripcion_corta,
                     unidad, cantidad, precio_unitario,
                     subtotal, estado, creado_por)
                VALUES (?, ?, ?, 2, ?, 'concepto', ?, ?, ?, ?, ?, ?, 0, 1, 1)
            """, (proyecto_id, cap_id, f"{wbs_cap}{i:02d}", i, clave,
                  _s(rec.get("DESCRIPCIO") or rec.get("DESCCORTA")),
                  _s(rec.get("DESCCORTA")),
                  _s(rec.get("UNIDAD")),
                  _f(r.get("NOELE")), _f(r.get("COSTO"))))
            nodo_id_sqlite[clave] = cur.lastrowid

    con.commit()
    return nodo_id_sqlite


# =============================================================================
# SUBTOTALES BOTTOM-UP
# =============================================================================

# ── recalcular subtotales de capítulos desde hojas hacia raíz ──
def _recalcular_subtotales(con, proyecto_id: int):
    cur = con.cursor()
    cur.execute("""
        SELECT MAX(nivel) FROM estructura_presupuesto WHERE proyecto_id = ? AND activo = 1
    """, (proyecto_id,))
    max_nivel = cur.fetchone()[0] or 0

    for nivel in range(max_nivel, -1, -1):
        cur.execute("""
            UPDATE estructura_presupuesto SET
                subtotal = (
                    SELECT COALESCE(SUM(
                        CASE WHEN tipo = 'concepto'
                             THEN COALESCE(importe, 0)
                             ELSE COALESCE(subtotal, 0)
                        END
                    ), 0)
                    FROM estructura_presupuesto h
                    WHERE h.padre_id = estructura_presupuesto.id AND h.activo = 1
                ),
                modificado_en = datetime('now')
            WHERE proyecto_id = ? AND nivel = ?
              AND tipo = 'capitulo' AND activo = 1
        """, (proyecto_id, nivel))
    con.commit()


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Importar proyecto OPUS a SQLite")
    parser.add_argument("carpeta",       help="Carpeta con los .DBF del proyecto")
    parser.add_argument("db",            help="Ruta del .db de destino")
    parser.add_argument("--nombre", "-n", default=None, help="Nombre del proyecto")
    args = parser.parse_args()
    importar(args.carpeta, args.db, args.nombre)
