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
   4. Los totales de capítulos se calculan bottom-up al final.
  5. Toda referencia a catálogos también filtra _deleted=False.
  6. PRE_IDPAD del *1.DBF NO se usa para resolver padres (pertenece a otra
     tabla de OPUS y sus valores coinciden con PRE_ID solo por azar).

Archivos DBF que lee:
  *P.DBF   — Catálogo de insumos (materiales, MO, equipo, etc.)
  *F.DBF   — Fórmulas/APU: componentes de cada concepto o insumo compuesto
  *N.DBF   — Resúmenes de APU por concepto (totales por tipo de costo)
  *Z.DBF   — Configuración del proyecto (horas/día, tasas)
  *C.DBF   — Carátula del proyecto (factores de sobrecosto)
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

from backend.database.core import generar_hash
from backend.database.db import Database

try:
    from dbfread import DBF
except ImportError:
    raise ImportError("Instala dbfread:  pip install dbfread")


# =============================================================================
# UTILIDADES
# =============================================================================

# ── convertir a float con valor por defecto ──
def _f(val, default=0.0):
    """Convierte valor a float; devuelve default si es None o no convertible."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── convertir a string limpio con valor por defecto ──
def _s(val, default=""):
    """Convierte valor a string con strip; devuelve default si es None."""
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
            print(f"  [OK] {ruta.name}: {len(activos)} activos / {borrados} borrados")
            return activos
        except Exception as e:
            last_err = e
    print(f"  [FALLO] {ruta.name}: {last_err}")
    return []


# =============================================================================
# DETECCIÓN DEL PROYECTO
# =============================================================================

_SUFIJOS = {
    "clasico":  {"P":"EGP","F":"EGF","N":"EGN","X":"EGX","Z":"EGZ","I":"EGI","C":"EGC"},
    "numerico": {"P":"P",  "F":"F",  "N":"N",  "X":"X",  "Z":"Z",  "I":"I",
                 "1":"1",  "A":"A",  "C":"C"},
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
    """Resuelve la ruta completa a un archivo DBF dado su sufijo (P, F, N, etc.), probando mayúsculas y minúsculas."""
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

def importar(
    carpeta: str,
    db_path: str,
    nombre: str | None = None,
    cerrar_al_terminar: bool = False,
) -> dict:
    """
    Importa un proyecto OPUS al SQLite de Open APU Studio.

    Args:
        carpeta:            Ruta a la carpeta con los archivos .DBF
        db_path:            Ruta del archivo .db de destino (se crea si no existe)
        nombre:             Nombre del proyecto (default: se infiere del prefijo)
        cerrar_al_terminar: Si True, cierra la conexion al final (util en CLI/tests).
                            Si False (default), deja la DB abierta para que el
                            frontend pueda seguir usandola sin reconectar.

    Returns:
        Dict con estadisticas: estructura_presupuesto, insumos, apu_matrices, etc.
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
        """Lee archivo DBF por sufijo (P, F, N, etc.) desde la carpeta del proyecto."""
        r = _ruta_dbf(carpeta, prefijo, formato, clave)
        return _leer_dbf(r) if r else []

    regs_p = dbf("P")
    regs_f = dbf("F")
    regs_n = dbf("N")
    regs_z = dbf("Z")
    regs_c = dbf("C")
    regs_1 = dbf("1")
    regs_a = dbf("A")

    # ── Proyecto ─────────────────────────────────────────────────────────
    print("\nInsertando...")
    cfg = regs_z[0] if regs_z else {}

    cur.execute("""
        INSERT INTO proyectos
            (nombre, clave_opus, moneda_nombre, moneda_simbolo,
             moneda_abrev, iva_porcentaje,
             horas_dia, tasa_seguro, tasa_interes, creado_por)
        VALUES (?, ?, 'Peso mexicano', '$', 'MXN', 16.0, ?, ?, ?, 1)
    """, (nombre_proyecto, prefijo,
          _f(cfg.get("HORASDIA"), 8),
          _f(cfg.get("SEGURO")),
          _f(cfg.get("TASA_INTER"))))
    proyecto_id = cur.lastrowid

    con.commit()
    print(f"  → proyecto '{nombre_proyecto}' (id={proyecto_id})")

    # ── Factores de sobrecosto (desde *C.DBF) ──────────────────────────
    from backend.database.repos.proyecto import FactoresSobrecostoRepo
    sobrecosto_repo = FactoresSobrecostoRepo(con)
    cfg_c = regs_c[0] if regs_c else {}
    sobrecosto_repo.guardar(
        proyecto_id,
        pct_indirectos_campo   = _f(cfg_c.get("OBRPIND")),
        pct_indirectos_oficina = _f(cfg_c.get("OBRPIND2")),
        pct_financiamiento     = _f(cfg_c.get("OBRPFIN")),
        pct_utilidad           = _f(cfg_c.get("OBRPUTI")),
        pct_cargos_adicionales = _f(cfg_c.get("OBRPCAD")),
    )
    con.commit()
    n_sobrecosto = 1 if cfg_c else 0
    print(f"  → factores de sobrecosto: {'importados' if cfg_c else 'defaults (sin *C.DBF)'}")

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

    # Nombres alternativos del campo FAMILIA/GRUPO en distintas versiones de OPUS
    # (ELE_GRUPO es el nombre real en *P.DBF para proyectos numericos;
    #  ELE_FAM suele aparecer en formatos clásicos)
    _FAM_KEYS  = ["ELE_FAM",  "FAMILIA",  "FAM",  "FAMILIAS", "GRP", "ELE_GRUPO"]
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
    #                    fecha, es_compuesto, factor_fsr,
    #                    clave_usuario, peso_kg, familia_id, subfamilia_id
    #                    comentarios → tabla notas
    insumo_id_por_clave:   dict[str, int] = {}
    insumo_tipo_por_clave: dict[str, int] = {}  # tipo_id para decidir operador en apu_matrices
    notas_insumos: list[tuple] = []  # (insumo_id, texto) — se insertan al final
    n_compuestos = 0

    # Items que aparecen como padres en *F.DBF tienen APU → es_compuesto=1
    padres_con_apu = {_s(r.get("NOMBRE")) for r in regs_f if _s(r.get("NOMBRE"))}

    for r in regs_p:
        clave = _s(r.get("NOMBRE"))
        if not clave:
            continue

        fam = next((_s(r.get(k)) for k in _FAM_KEYS if _s(r.get(k))), "")
        sub = next((_s(r.get(k)) for k in _SFAM_KEYS if _s(r.get(k))), "")
        familia_id    = familia_id_por_nombre.get(fam) if fam else None
        subfamilia_id = subfamilia_id_por_nombre.get((fam, sub)) if (fam and sub) else None

        # es_compuesto: bit 32 en PREFIJO o presente como padre en *F.DBF
        # (cuadrillas con PREFIJO=2 pero con APU propio entran por esta segunda)
        prefijo      = int(r.get("PREFIJO") or 0)
        es_compuesto = 1 if ((prefijo & 32) or clave in padres_con_apu) else 0
        if es_compuesto:
            n_compuestos += 1

        # FSR (Factor Salario Real) — solo aplica a mano de obra (tipo_id=2)
        fsr = _f(r.get("FSR") or r.get("FASAR"))

        comentario = _s(r.get("COMENTARIO") or r.get("COMEN") or r.get("MEMO"))

        _desc = _s(r.get("DESCRIPCIO") or r.get("DESCRIPCION"))
        _hash = generar_hash(_desc) if _desc else None

        # Resolver duplicados ANTES de insertar.
        # Caso normal (hash no nulo): UNIQUE(proyecto_id, hash) ya protegería,
        # pero se verifica aquí también para evitar dos SELECT distintos.
        # Caso especial (hash nulo): SQLite nunca activa UNIQUE entre NULLs,
        # así que sin esta verificación manual se duplicaría en cada reimportación.
        # Se usa clave_opus como respaldo de deduplicación en ese caso, ya que
        # dentro de un mismo archivo OPUS es única.
        if _hash is not None:
            cur.execute("""
                SELECT id, tipo_id FROM insumos WHERE proyecto_id = ? AND hash = ?
            """, (proyecto_id, _hash))
        else:
            cur.execute("""
                SELECT id, tipo_id FROM insumos
                WHERE proyecto_id = ? AND hash IS NULL AND clave_opus = ?
            """, (proyecto_id, clave))
        ya_existe = cur.fetchone()

        if not ya_existe:
            tipo_id = _tipo_id(prefijo)
            precio = _f(r.get("PRECIO"))
            if tipo_id == 2:
                costo_mn = _f(r.get("PBASEMN")) or (precio / fsr if fsr else precio)
                costo_final = costo_mn * fsr if fsr else costo_mn
            else:
                costo_mn = _f(r.get("PRECIOMN")) or precio
                costo_final = costo_mn
            costo_me = _f(r.get("PRECIOME")) or 0.0
            costo_directo = costo_mn  # base sin FSR; FSR se aplica en recálculo
            cur.execute("""
                INSERT INTO insumos
                    (proyecto_id, clave_opus, tipo_id, descripcion, descripcion_corta,
                     unidad, costo_mn, costo_me, costo_directo, costo_final, es_compuesto,
                     fecha_precio, clave_usuario, peso_kg,
                     familia_id, subfamilia_id,
                     factor_fsr, hash, creado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                proyecto_id,
                clave,
                tipo_id,
                _desc,
                _s(r.get("DESCCORTA")),
                _s(r.get("UNIDAD")),
                costo_mn,
                costo_me,
                costo_directo,
                costo_final,
                es_compuesto,
                _s(r.get("FECHA")),
                _s(r.get("CLAVE_USU") or r.get("CLVUSUARIO") or r.get("CLV_USU")),
                _f(r.get("PESO")) or None,
                familia_id,
                subfamilia_id,
                fsr or None,
                _hash,
            ))
        else:
            tipo_id = ya_existe["tipo_id"]

        cur.execute("""
            SELECT id FROM insumos
            WHERE proyecto_id = ?
              AND (hash = ? OR (hash IS NULL AND ? IS NULL AND clave_opus = ?))
        """, (proyecto_id, _hash, _hash, clave))
        row = cur.fetchone()
        if row:
            insumo_id = row["id"]
            insumo_id_por_clave[clave]   = insumo_id
            insumo_tipo_por_clave[clave] = tipo_id
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
        nodo_id_sqlite, clave_a_conceptos = _arbol_numerico(
            con, cur, proyecto_id, regs_1, regs_a, regs_p)
    else:
        nodo_id_sqlite, clave_a_conceptos = _arbol_clasico(
            con, cur, proyecto_id, regs_f, regs_p)

    con.commit()
    print(f"  → estructura_presupuesto: {len(nodo_id_sqlite)}")

    # Deja wbs/nivel canónicos desde el primer momento, derivados de
    # padre_id + orden (ver NodoRepo.reindexar). Robusto ante cualquier
    # inconsistencia menor del propio importador (ej. PRE_WBS sin resolver).
    from backend.database.repos import NodoRepo
    NodoRepo(con).reindexar(proyecto_id)
    con.commit()

    # ── Vincular insumo_id en estructura_presupuesto ──────────────────────
    # clave_a_conceptos mapea clave_opus → [ep_id, ...]. Para cada concepto
    # del árbol se busca el insumo correspondiente por clave_opus y se escribe
    # insumo_id en la fila de estructura_presupuesto.
    n_vinculados   = 0
    n_sin_insumo   = 0
    for clave_opus, ep_ids in clave_a_conceptos.items():
        insumo_id = insumo_id_por_clave.get(clave_opus)
        if not insumo_id:
            n_sin_insumo += len(ep_ids)
            continue
        for ep_id in ep_ids:
            cur.execute("""
                UPDATE estructura_presupuesto
                SET insumo_id = ?
                WHERE id = ?
            """, (insumo_id, ep_id))
            n_vinculados += 1
    con.commit()
    msg = f"  → insumo_id vinculados: {n_vinculados}"
    if n_sin_insumo:
        msg += f"  |  {n_sin_insumo} sin insumo en catálogo"
    print(msg)

    # Recalcular total de conceptos usando precio real del insumo (costo_final)
    # PRE_PRE del DBF puede ser un valor desactualizado; el precio vigente vive
    # en insumos.costo_final y ahora está accesible vía el insumo_id vinculado.
    from backend.database.repos import RecalculoRepo
    RecalculoRepo(con).recalcular_totales_conceptos(proyecto_id)
    con.commit()
    print(f"  → totales de conceptos recalculados con precio real del insumo")

    # ── APU NODOS (sintéticos para insumos compuestos fuera del árbol) ─────
    insumo_por_clave = {_s(r.get("NOMBRE")): r for r in regs_p if _s(r.get("NOMBRE"))}

    # apu_auxiliares eliminado — insumos compuestos ya están en insumos (es_compuesto=1)

    # ── APU matrices (componentes del APU) ──────────────────────────────

    # Lookup de insumos compuestos por clave (es_compuesto=1)
    # Reemplaza el lookup de apu_auxiliares que fue eliminado.
    # clave_opus es la clave original de OPUS (mismo NOMBRE que usan los
    # registros de componentes COMPONENTE en regs_f) — sigue siendo necesaria
    # aquí solo como llave de cruce *durante* la importación, en memoria.
    cur.execute("""
        SELECT clave_opus AS clave, id FROM insumos
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

        # Insertar en TODOS los padres que correspondan:
        # — conceptos del árbol (matriz_id positivo)
        # — insumos compuestos del catálogo (matriz_id negativo)
        # Un mismo concepto_clave puede aparecer en ambas listas si es
        # a la vez concepto del presupuesto e insumo compuesto reutilizable.
        padres_arbol  = [(pid, False) for pid in clave_a_conceptos.get(concepto_clave, [])]
        padres_comp   = [(pid, True)  for pid in clave_a_insumos_compuestos.get(concepto_clave, [])]
        todos_padres  = padres_arbol + padres_comp

        if not todos_padres:
            n_skip_padre += 1
            continue

        for pid, es_comp in todos_padres:
            mid     = -pid if es_comp else pid
            es_mo   = insumo_tipo_por_clave.get(insumo_clave, 0) == 2
            operador = '/' if es_mo else '*'
            valor = _f(r.get("RENDTO")) if es_mo else _f(r.get("CANTIDAD"))
            formula = _s(r.get("EXPRESION") or r.get("MEMOCAD"))
            if operador == '/' and formula:
                formula = f"1/{formula}"
            cur.execute("""
                INSERT INTO apu_matrices
                    (matriz_id, insumo_id, valor, operador,
                     precio, formula, orden, creado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (mid, insumo_id,
                  valor,
                  operador,
                  _f(r.get("COSTO")),
                  formula,
                  int(_f(r.get("CLAVENUM")))))
            n_comp += 1

    con.commit()
    msg = f"  → apu_matrices: {n_comp}"
    if n_skip_padre: msg += f"  |  {n_skip_padre} sin padre"
    if n_skip_ins:   msg += f"  |  {n_skip_ins} sin insumo"
    print(msg)

    # ponytail: apu_resumen_totales eliminado — subtotales se calculan al vuelo

    # ── Totales bottom-up ──────────────────────────────────────────
    print("  → Recalculando totales...")
    _recalcular_totales(con, proyecto_id)

    cur.execute("""
        UPDATE proyectos SET total_obra = (
            SELECT COALESCE(SUM(total), 0) FROM estructura_presupuesto
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
        "insumos_compuestos":    n_compuestos,
        "factores_sobrecosto":   n_sobrecosto,
    }
    print("\n--- Resumen ---")
    for k, v in stats.items():
        print(f"  {k:<15}: {v}")

    if cerrar_al_terminar:
        db.close()
    return stats


# =============================================================================
# ÁRBOL — FORMATO NUMÉRICO (*1 + *A)
# =============================================================================

# ── construir árbol desde formato numérico ──
def _arbol_numerico(con, cur, proyecto_id, regs_1, regs_a, regs_p) -> dict:
    """Construye el árbol del presupuesto desde el formato numérico OPUS (*1.DBF + *A.DBF + *P.DBF)."""
    nombres = {int(r["IDUNI"]): r for r in regs_a if r.get("IDUNI") is not None}
    egp     = {_s(r.get("NOMBRE")): r for r in regs_p if _s(r.get("NOMBRE"))}

    nodos_ord  = sorted(regs_1, key=lambda r: _s(r.get("PRE_WBS")))
    activos_id = {int(r.get("PRE_ID") or 0) for r in nodos_ord}

    nodo_id_sqlite: dict[int, int] = {}
    wbs_a_sqlite:   dict[str, int] = {}
    clave_nodo_ids: dict[str, list[int]] = {}
    stats = {"wbs": 0, "sin_resolver": 0}

    for r in nodos_ord:
        pre_id    = int(r.get("PRE_ID")  or 0)
        pre_idpad = int(r.get("PRE_IDPAD") or -1)
        wbs       = _s(r.get("PRE_WBS"))
        nivel     = int(r.get("PRE_NIVEL") or 0)
        pre_com   = _s(r.get("PRE_COM"))
        pre_iduni = int(r.get("PRE_IDUNI") or -1)

        # El primer registro de *1.DBF es un nodo raíz interno de OPUS (nivel=0,
        # sin PRE_COM, sin descripción real) que no corresponde a ningún capítulo
        # del presupuesto. Se omite para no generar una fila vacía en la UI.
        if nivel == 0 and not pre_com:
            continue

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

        total = cantidad * pu if es_concepto and cantidad and pu else 0
        formula_pres = _s(r.get("PRE_EXP")) or None
        cur.execute("""
            INSERT INTO estructura_presupuesto
                (proyecto_id, padre_id, wbs, nivel, orden, tipo,
                 insumo_id, descripcion, cantidad, formula, total, estado, creado_por)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
        """, (proyecto_id, padre_id, wbs, nivel,
              int(wbs[-2:]) if len(wbs) >= 2 else 0,
              "concepto" if es_concepto else "capitulo",
              None,  # insumo_id: se vincula posteriormente
              desc,
              cantidad,
              formula_pres,
              total))

        sid = cur.lastrowid
        nodo_id_sqlite[pre_id] = sid
        if es_concepto and pre_com:
            clave_nodo_ids.setdefault(pre_com, []).append(sid)
        if wbs:
            wbs_a_sqlite[wbs] = sid

    print(f"    WBS: {stats['wbs']}  |  "
          f"Sin resolver: {stats['sin_resolver']}")
    con.commit()
    return nodo_id_sqlite, clave_nodo_ids


# =============================================================================
# ÁRBOL — FORMATO CLÁSICO (*EGF con PREF=16)
# =============================================================================

# ── construir árbol desde formato clásico ──
def _arbol_clasico(con, cur, proyecto_id, regs_f, regs_p) -> dict:
    """Construye el árbol del presupuesto desde el formato clásico OPUS (*EGF + *EGP)."""
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
                 descripcion, total, estado, creado_por)
            VALUES (?, NULL, ?, 1, ?, 'capitulo', ?, 0, 1, 1)
        """, (proyecto_id, wbs_cap, orden_cap,
              f"Capítulo {cap}" if cap else "Generales"))
        cap_id = cur.lastrowid
        nodo_id_sqlite[f"cap_{cap}"] = cap_id

        for i, r in enumerate(caps[cap], start=1):
            clave = _s(r.get("NOMBRE"))
            rec   = egp.get(clave, {})
            cantidad = _f(r.get("NOELE"))
            pu       = _f(r.get("COSTO"))
            total    = cantidad * pu if cantidad and pu else 0
            formula_pres = (_s(r.get("EXPRESION")) or _s(r.get("PRE_EXP"))) or None
            cur.execute("""
                INSERT INTO estructura_presupuesto
                    (proyecto_id, padre_id, wbs, nivel, orden, tipo,
                     insumo_id, descripcion, cantidad, formula, total, estado, creado_por)
                VALUES (?, ?, ?, 2, ?, 'concepto', ?, ?, ?, ?, ?, 1, 1)
            """, (proyecto_id, cap_id, f"{wbs_cap}{i:02d}", i,
                  None,  # insumo_id
                  _s(rec.get("DESCRIPCIO") or rec.get("DESCCORTA")),
                  cantidad, formula_pres, total))
            nodo_id_sqlite[clave] = cur.lastrowid

    con.commit()
    return nodo_id_sqlite, nodo_id_sqlite


# =============================================================================
# SUBTOTALES BOTTOM-UP
# =============================================================================
# ── recalcular totales de capítulos desde hojas hacia raíz ──
def _recalcular_totales(con, proyecto_id: int):
    """Recalcula totales de capítulos bottom-up desde el nivel más profundo hacia la raíz."""
    from backend.database.repos import RecalculoRepo
    RecalculoRepo(con).recalcular_totales_capitulos(proyecto_id)
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
    importar(args.carpeta, args.db, args.nombre, cerrar_al_terminar=True)
