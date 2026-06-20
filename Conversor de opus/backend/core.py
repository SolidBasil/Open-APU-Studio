"""
backend/core.py — TODA la lógica que no sabe nada de presentación.

Responsabilidades (de abajo hacia arriba):
  1. Leer DBF/FPT binario          -> read_dbf()
  2. Volcar un directorio a SQLite -> convert_directory()
  3. Validar integridad            -> run_default_checks()
  4. Construir el árbol de negocio -> build_budget_tree()

El frontend (HTML o PyQt) SOLO debe importar `build_budget_tree()` de aquí.
Nada en este archivo debe saber qué es un QTreeView o un <div>.
"""
import os
import struct
import sqlite3


# ════════════════════════════════════════════════════════════════
# 1) LECTURA BINARIA DBF / FPT
# ════════════════════════════════════════════════════════════════

def _read_memo_file(fpt_path):
    if not os.path.exists(fpt_path):
        return None, 512
    with open(fpt_path, "rb") as f:
        data = f.read()
    if len(data) < 8:
        return None, 512
    block_size = struct.unpack(">H", data[6:8])[0] or 512
    return data, block_size


def _get_memo_text(fpt_data, block_size, block_num, encoding="latin1"):
    if fpt_data is None or not block_num:
        return None
    offset = block_num * block_size
    if offset + 8 > len(fpt_data):
        return None
    _memo_type, length = struct.unpack(">II", fpt_data[offset:offset + 8])
    raw = fpt_data[offset + 8:offset + 8 + length]
    try:
        return raw.decode(encoding).rstrip("\x00")
    except UnicodeDecodeError:
        return raw.decode(encoding, errors="replace")


def _decode_field(raw, ftype, fdec, fpt_data, block_size, encoding):
    """Nunca lanza excepción: ante dato corrupto devuelve None (mejor un
    NULL que tronar toda la conversión por un registro mal grabado)."""
    try:
        if ftype == "C":
            return raw.decode(encoding, errors="replace").rstrip()
        if ftype in ("N", "F"):
            s = raw.decode("latin1").strip()
            if s in ("", ".", "-"):
                return None
            return float(s) if fdec else int(float(s))
        if ftype == "D":
            s = raw.decode("latin1").strip()
            return f"{s[0:4]}-{s[4:6]}-{s[6:8]}" if (len(s) == 8 and s.isdigit()) else None
        if ftype == "L":
            c = raw.decode("latin1")
            return True if c in "TtYy" else (False if c in "FfNn" else None)
        if ftype == "M":
            s = raw.decode("latin1").strip()
            return _get_memo_text(fpt_data, block_size, int(s), encoding) if (s.isdigit() and int(s)) else None
        return raw.decode(encoding, errors="replace").strip()
    except Exception:
        return None


def read_dbf(path, encoding="latin1"):
    """Lee un .DBF (+ su .FPT si existe). Devuelve (fields, records).
    fields: [(nombre, tipo, longitud, decimales), ...]
    records: [ {campo: valor, "_deleted": bool}, ... ]"""
    with open(path, "rb") as f:
        data = f.read()

    num_records = struct.unpack("<I", data[4:8])[0]
    header_size = struct.unpack("<H", data[8:10])[0]
    record_size = struct.unpack("<H", data[10:12])[0]

    fields = []
    pos = 32
    while pos < header_size - 1:
        chunk = data[pos:pos + 32]
        if len(chunk) < 32 or chunk[0] == 0x0D:
            break
        name = chunk[0:11].split(b"\x00")[0].decode("latin1")
        fields.append((name, chr(chunk[11]), chunk[16], chunk[17]))
        pos += 32

    fpt_data, block_size = _read_memo_file(os.path.splitext(path)[0] + ".FPT")

    records = []
    for i in range(num_records):
        rstart = header_size + i * record_size
        rec = data[rstart:rstart + record_size]
        if len(rec) < record_size:
            break
        row = {"_deleted": rec[0:1] == b"*"}
        fpos = 1
        for (name, ftype, flen, fdec) in fields:
            row[name] = _decode_field(rec[fpos:fpos + flen], ftype, fdec, fpt_data, block_size, encoding)
            fpos += flen
        records.append(row)

    return fields, records


# ════════════════════════════════════════════════════════════════
# 2) VOLCADO A SQLITE
# ════════════════════════════════════════════════════════════════

def _sqlite_type(ftype, fdec):
    if ftype in ("N", "F"):
        return "REAL" if fdec else "INTEGER"
    if ftype == "L":
        return "INTEGER"
    return "TEXT"


def _load_dbf_into_sqlite(dbf_path, conn, table_name, encoding="latin1"):
    fields, records = read_dbf(dbf_path, encoding=encoding)

    cols_ddl = ['"_deleted" INTEGER']
    col_names = ["_deleted"]
    for (name, ftype, _flen, fdec) in fields:
        cols_ddl.append(f'"{name}" {_sqlite_type(ftype, fdec)}')
        col_names.append(name)

    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(f'CREATE TABLE "{table_name}" ({", ".join(cols_ddl)})')

    placeholders = ",".join(["?"] * len(col_names))
    col_list = ",".join(f'"{c}"' for c in col_names)
    insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'

    rows = []
    for r in records:
        row = [int(r["_deleted"])]
        for (name, ftype, _flen, _fdec) in fields:
            v = r[name]
            row.append(int(v) if (ftype == "L" and isinstance(v, bool)) else v)
        rows.append(row)

    conn.executemany(insert_sql, rows)
    conn.commit()
    return len(records)


def convert_directory(upload_dir, out_db_path, verbose=True):
    """Convierte todos los .DBF de `upload_dir` a un único archivo SQLite,
    una tabla por archivo (mismo nombre, sin extensión)."""
    if os.path.exists(out_db_path):
        os.remove(out_db_path)
    conn = sqlite3.connect(out_db_path)

    dbf_files = sorted(f for f in os.listdir(upload_dir) if f.upper().endswith(".DBF"))
    if not dbf_files:
        raise FileNotFoundError(f"No se encontraron .DBF en {upload_dir}")

    for fn in dbf_files:
        table_name = os.path.splitext(fn)[0]
        try:
            n = _load_dbf_into_sqlite(os.path.join(upload_dir, fn), conn, table_name)
            if verbose:
                print(f"OK  {table_name}: {n} registros")
        except Exception as e:
            if verbose:
                print(f"ERROR {table_name}: {e}")

    conn.close()


# ════════════════════════════════════════════════════════════════
# 3) VALIDACIÓN DE INTEGRIDAD
# ════════════════════════════════════════════════════════════════

def run_default_checks(db_path):
    """Checks específicos de este proyecto (presupuesto D60JALISCOT).
    Ajustar nombres de tabla/columna si cambia el prefijo de la obra.

    GOTCHA importante: nunca usar un alias de 1 letra (ej. `c`) para
    COUNT(*) en este esquema — varias tablas (D60JALISCOTP) tienen
    columnas reales llamadas A,B,C,D,E,F y SQLite puede resolver el
    alias contra la columna real en vez del agregado, sin dar error."""
    conn = sqlite3.connect(db_path)

    dup_total = conn.execute(
        'SELECT PREFIJO,NOMBRE,COUNT(*) AS _dup_count FROM D60JALISCOTP '
        'GROUP BY PREFIJO,NOMBRE HAVING _dup_count > 1'
    ).fetchall()
    dup_activos = conn.execute(
        'SELECT PREFIJO,NOMBRE,COUNT(*) AS _dup_count FROM D60JALISCOTP '
        'WHERE _deleted=0 GROUP BY PREFIJO,NOMBRE HAVING _dup_count > 1'
    ).fetchall()

    activos = conn.execute('SELECT COUNT(*) FROM D60JALISCOT1 WHERE _deleted=0').fetchone()[0]
    huerfanos = conn.execute(
        'SELECT COUNT(*) FROM D60JALISCOT1 t WHERE t._deleted=0 AND t.PRE_IDPAD != -1 '
        'AND t.PRE_IDPAD NOT IN (SELECT PRE_ID FROM D60JALISCOT1 WHERE _deleted=0)'
    ).fetchone()[0]

    conn.close()
    return {
        "duplicados_totales_D60JALISCOTP": len(dup_total),
        "duplicados_activos_D60JALISCOTP": len(dup_activos),
        "nodos_activos_D60JALISCOT1": activos,
        "huerfanos_de_padre_borrado": huerfanos,
    }


# ════════════════════════════════════════════════════════════════
# 4) ÁRBOL DE NEGOCIO DEL PRESUPUESTO
# ════════════════════════════════════════════════════════════════

def _nearest_active_ancestor(pre_id, full_parent_map, active_ids):
    seen = set()
    pid = full_parent_map.get(pre_id, -1)
    while pid != -1 and pid not in active_ids:
        if pid in seen or pid not in full_parent_map:
            return -1
        seen.add(pid)
        pid = full_parent_map.get(pid, -1)
    return pid


def build_budget_tree(db_path):
    """Devuelve una lista de nodos raíz. Cada nodo:
        id, nivel, clave, desc, unidad, cantidad, precio, importe,
        es_capitulo, hijos: [...]

    Reglas de negocio aplicadas (ver ARQUITECTURA_CONVERSION.md):
      - Filtra siempre _deleted = 0, incluso dentro de los JOIN a catálogos.
      - Capítulo (PRE_COM='') -> descripción de D60JALISCOTA.DESC vía PRE_IDUNI.
      - Concepto (PRE_COM!='') -> descripción/unidad/precio de D60JALISCOTP
        vía (PREFIJO=32, NOMBRE=PRE_COM).
      - Importe = PRE_VOL * PRE_PRE en conceptos; PRE_PRE directo en capítulos.
      - Si el padre directo está borrado, se reconecta al ancestro activo
        más cercano subiendo por la cadena completa (incluye borrados).
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    full_parent_map = {
        row[0]: row[1] for row in conn.execute("SELECT PRE_ID, PRE_IDPAD FROM D60JALISCOT1")
    }

    rows = [dict(r) for r in conn.execute(
        """
        SELECT t1.PRE_ID, t1.PRE_IDPAD, t1.PRE_NIVEL, t1.PRE_COM, t1.PRE_VOL, t1.PRE_PRE,
               a.DESC as cap_desc,
               p.DESCRIPCIO as con_desc, p.UNIDAD as con_unidad
        FROM D60JALISCOT1 t1
        LEFT JOIN D60JALISCOTA a
               ON a.IDUNI = t1.PRE_IDUNI AND t1.PRE_COM = '' AND a._deleted = 0
        LEFT JOIN D60JALISCOTP p
               ON p.PREFIJO = 32 AND p.NOMBRE = t1.PRE_COM
              AND t1.PRE_COM != '' AND p._deleted = 0
        WHERE t1._deleted = 0
        ORDER BY t1.PRE_ID
        """
    )]
    conn.close()

    by_id = {r["PRE_ID"]: r for r in rows}
    active_ids = set(by_id.keys())

    children = {}
    for r in rows:
        idpad = r["PRE_IDPAD"]
        parent = idpad if (idpad == -1 or idpad in active_ids) \
            else _nearest_active_ancestor(r["PRE_ID"], full_parent_map, active_ids)
        children.setdefault(parent, []).append(r["PRE_ID"])

    def build_node(pre_id):
        r = by_id[pre_id]
        is_chapter = r["PRE_COM"] == ""
        desc = (r["cap_desc"] if is_chapter else r["con_desc"]) or "(sin descripción)"
        cantidad, precio = r["PRE_VOL"], r["PRE_PRE"]
        importe = precio if is_chapter else (cantidad or 0) * (precio or 0)
        return {
            "id": r["PRE_ID"],
            "nivel": r["PRE_NIVEL"],
            "clave": "" if is_chapter else r["PRE_COM"],
            "desc": desc,
            "unidad": "" if is_chapter else (r["con_unidad"] or ""),
            "cantidad": None if is_chapter else cantidad,
            "precio": None if is_chapter else precio,
            "importe": importe,
            "es_capitulo": is_chapter,
            "hijos": [build_node(cid) for cid in sorted(children.get(pre_id, []))],
        }

    return [build_node(rid) for rid in sorted(children.get(-1, []))]


def count_nodes(nodes):
    return sum(1 + count_nodes(n["hijos"]) for n in nodes)


def count_concepts(nodes):
    return sum((0 if n["es_capitulo"] else 1) + count_concepts(n["hijos"]) for n in nodes)
