"""
cdx.py — FoxPro CDX (Compound Index) writer.

Replicates the VFP CDX format: master B-tree → tag info pages → tag B-trees.
Used by exportar.py to create valid indexes for OPUS CMS.
"""

import struct
import os
import re


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _ceil_div(a, b):
    return (a + b - 1) // b


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _bits_for(v: int) -> int:
    if v < 1:
        return 1
    return v.bit_length()


# ---------------------------------------------------------------------------
# Leaf page construction (compact VFP CDX format)
# ---------------------------------------------------------------------------

def make_leaf_header(num_keys: int, key_len: int, max_recno: int,
                     is_root: bool = True, left_peer: int = -1,
                     right_peer: int = -1) -> tuple[bytes, dict]:
    """Build 24-byte compact leaf header."""
    attrs = 2  # compact leaf
    if is_root:
        attrs |= 1

    recno_bits = _bits_for(max_recno)
    dupe_bits  = _bits_for(key_len)
    trail_bits = _bits_for(key_len)
    recduptrail = _ceil_div(recno_bits + dupe_bits + trail_bits, 8)
    recduptrail = max(recduptrail, 1)

    recno_mask = (1 << recno_bits) - 1
    dupe_mask  = (1 << dupe_bits)  - 1
    trail_mask = (1 << trail_bits) - 1

    est_headers = recduptrail * num_keys
    est_keys    = key_len * num_keys
    free = max(488 - est_headers - est_keys, 0)

    # 24-byte compact leaf header (VFP CDX format)
    hdr = struct.pack('<HHiiHBBBBBBH',
        free, num_keys,
        left_peer, right_peer,
        attrs,
        recno_bits, dupe_bits, trail_bits, recduptrail, trail_bits,
        0,          # reserved byte → padded to uint16 to hit 24 bytes
        max_recno & 0xFFFF,
    )
    # Patch bytes 20-23 with full uint32 max_recno
    hdr = hdr[:20] + struct.pack('<I', max_recno)

    params = dict(
        reclen=recno_bits,
        duplen=dupe_bits,
        traillen=trail_bits,
        recduptrail=recduptrail,
        max_recno=max_recno,
    )
    return hdr, params


def pack_entry_header(recno: int, dupe: int, trail: int,
                      reclen: int, duplen: int, traillen: int,
                      nbytes: int) -> bytes:
    val = recno | (dupe << reclen) | (trail << (reclen + duplen))
    return val.to_bytes(nbytes, 'little')


def build_compact_leaf(key_len: int,
                       entries: list[tuple[bytes, int]],
                       is_root: bool = True) -> bytes | None:
    """
    Build a single 512-byte compact leaf page.
    Returns None if entries don't fit (caller should split).
    Returns empty leaf if entries == [].
    """
    n = len(entries)

    if n == 0:
        hdr, _ = make_leaf_header(0, key_len, 1, is_root)
        return hdr + b'\x00' * (512 - len(hdr))

    max_recno = max(r for _, r in entries)
    _, p = make_leaf_header(n, key_len, max_recno, is_root)
    recduptrail = p['recduptrail']

    hdr_bytes         = 24
    entry_header_bytes = recduptrail * n
    max_key_bytes     = key_len * n
    total_est         = hdr_bytes + entry_header_bytes + max_key_bytes

    if total_est >= 512:
        # Too many entries to fit in one 512-byte page → caller must split
        return None

    # Build the actual page
    hdr, p2 = make_leaf_header(n, key_len, max_recno, is_root)

    headers  = bytearray()
    keys_rev = bytearray()
    prev_key = b'\x00' * key_len

    for key_data, recno in entries:
        # Duplicate prefix count
        dupe = 0
        for i in range(min(len(key_data), len(prev_key))):
            if key_data[i] != prev_key[i]:
                break
            dupe = i + 1
        dupe = min(dupe, (1 << p2['duplen']) - 1)

        # Trailing space count
        trail = 0
        for i in range(key_len - 1, -1, -1):
            if key_data[i] < 32:
                break
            trail += 1
        trail = min(trail, (1 << p2['traillen']) - 1)

        stored = key_data[dupe: key_len - trail]
        headers.extend(pack_entry_header(
            recno, dupe, trail,
            p2['reclen'], p2['duplen'], p2['traillen'],
            p2['recduptrail'],
        ))
        keys_rev[0:0] = stored
        prev_key = key_data

    page = bytearray(512)
    page[0:24]                         = hdr
    page[24: 24 + len(headers)]        = headers
    page[512 - len(keys_rev): 512]     = keys_rev

    used = hdr_bytes + len(headers) + len(keys_rev)
    free = max(512 - used, 0)
    struct.pack_into('<H', page, 0, _clamp(free, 0, 65535))

    return bytes(page)


def build_interior(key_len: int,
                   children: list[tuple[bytes, int]],
                   is_root: bool = True,
                   left_peer: int = -1,
                   right_peer: int = -1) -> bytes | None:
    """Build an interior B-tree node. Returns None if entries dont fit in 512 bytes."""
    attrs = 0
    if is_root:
        attrs |= 1

    n = len(children)
    entry_sz = key_len + 4
    # Interior header is 12 bytes; return None if content exceeds page
    if 12 + entry_sz * n > 512:
        return None

    page = bytearray(512)
    # 12-byte interior header: attrs(2) + n_keys(2) + left_peer(4) + right_peer(4)
    page[0:12] = struct.pack('<HHii', attrs, n, left_peer, right_peer)

    off = 12
    for k, child_offset in children:
        entry = k[:key_len].ljust(key_len, b' ') + struct.pack('<I', child_offset)
        page[off: off + entry_sz] = entry
        off += entry_sz

    return bytes(page)


def build_btree(key_len: int,
                entries: list[tuple[bytes, int]]) -> list[bytes]:
    """Build a complete B-tree; returns list of 512-byte pages (leaves first, root last)."""
    if not entries:
        hdr, _ = make_leaf_header(0, key_len, 1, is_root=True)
        return [hdr + b'\x00' * (512 - len(hdr))]

    # Try single-leaf
    leaf = build_compact_leaf(key_len, entries, is_root=True)
    if leaf is not None:
        return [leaf]

    # Multi-leaf
    max_per_leaf = max(488 // (key_len + 4), 1)
    leaf_pages: list[bytes] = []

    for i in range(0, len(entries), max_per_leaf):
        chunk   = entries[i: i + max_per_leaf]
        is_root = max_per_leaf < len(entries)
        leaf    = build_compact_leaf(key_len, chunk, is_root=is_root)
        if leaf is None:
            return _empty_tag_tree(key_len)
        leaf_pages.append(leaf)

    children = []
    for i, lp in enumerate(leaf_pages):
        min_key = entries[i * max_per_leaf][0]
        # child offset = page index * 512
        children.append((min_key, i * 512))

    root = build_interior(key_len, children, is_root=True)
    if root is None:
        return _empty_tag_tree(key_len)

    return leaf_pages + [root]


def _empty_tag_tree(key_len: int) -> list[bytes]:
    """Minimal empty leaf page for a tag."""
    hdr, _ = make_leaf_header(0, key_len, 1, is_root=True)
    return [hdr + b'\x00' * (512 - len(hdr))]


# ---------------------------------------------------------------------------
# CdxBuilder — assembles pages into a .CDX file
# ---------------------------------------------------------------------------

class CdxBuilder:
    """Builds a .CDX file page by page."""

    PAGE = 512

    def __init__(self):
        self.pages: list[bytearray] = []
        self._n: int = 0

    def alloc(self, data: bytes | None = None) -> int:
        d = bytearray(data) if data is not None else bytearray(self.PAGE)
        assert len(d) == self.PAGE
        self.pages.append(d)
        pn = self._n
        self._n += 1
        return pn

    def write(self, path: str):
        with open(path, 'wb') as f:
            for p in self.pages:
                f.write(bytes(p))

    def build(self, tags: list[dict], tag_keys: list[list[tuple[bytes, int]]]):
        """
        Build the CDX from tag definitions and pre-computed key lists.

        tags      : [{'key_expr': str, 'key_len': int, 'for_expr': str, 'tag_name': str}, ...]
        tag_keys  : [[  (key_bytes, recno), ...  ], ...]  one list per tag
        """
        n_tags = len(tags)
        if n_tags == 0:
            return

        # ── 1. Build tag B-trees ──────────────────────────────────────
        tag_trees: list[list[bytes]] = []
        for ti in range(n_tags):
            kl      = tags[ti]['key_len']
            sorted_k = sorted(tag_keys[ti], key=lambda x: x[0])
            tree    = build_btree(kl, sorted_k)
            tag_trees.append(tree)

        tree_sizes = [len(t) for t in tag_trees]

        # ── 2. Layout calculation ────────────────────────────────────
        # Page layout:
        #   page 0           : master index (root of tag-name B-tree)
        #   pages 1..2*n_tags: tag info pages (2 per tag: def + data)
        #   page 2*n_tags+1  : master leaf
        #   then each tag's B-tree pages
        dict_pages  = 2 * n_tags
        master_size = 1
        dict_start  = 1
        master_pn   = dict_start + dict_pages
        leaf_start  = master_pn + master_size

        # ── 3. Assign page numbers for tag trees ─────────────────────
        cur = leaf_start
        tree_roots: list[int] = []
        for ti in range(n_tags):
            tree_roots.append(cur)
            cur += tree_sizes[ti]

        # ── 4. Build tag info pages (2 per tag) ───────────────────────
        info_pages: list[int] = []
        for ti in range(n_tags):
            t = tags[ti]
            info = bytearray(self.PAGE)

            # Bytes 0-3: page number of tag's root B-tree page
            struct.pack_into('<i', info, 0, tree_roots[ti] * self.PAGE)
            # Bytes 4-7: key length
            struct.pack_into('<H', info, 4, t['key_len'])
            # Byte 8: index options (0 = none)
            info[8] = 0

            # key_expr + NUL + for_expr + NUL (cp1252, at offset 22)
            def_text = (t.get('key_expr', '') + '\x00' +
                        t.get('for_expr', '') + '\x00'
                        ).encode('cp1252', errors='replace')
            info[22: 22 + min(len(def_text), self.PAGE - 22)] = \
                def_text[:self.PAGE - 22]

            info_pn = self.alloc(bytes(info))
            info_pages.append(info_pn)

            # Second page: definition data (zeros, placeholder)
            def_data = bytearray(self.PAGE)
            self.alloc(bytes(def_data))

        # ── 5. Build master index (tag-name → info page offset) ───────
        mkl = 10   # tag name key length in master index
        master_entries: list[tuple[bytes, int]] = []
        for ti in range(n_tags):
            tag_name = tags[ti].get('tag_name', '')
            if tag_name:
                k_str = tag_name.encode('cp1252', errors='replace') \
                                .ljust(mkl, b'\x00')[:mkl]
            else:
                k_str = f'{ti:>10}'.encode('cp1252', errors='replace')

            master_entries.append((k_str, info_pages[ti] * self.PAGE))

        master_entries.sort(key=lambda x: x[0])

        master_leaf = build_compact_leaf(mkl, master_entries, is_root=True)
        if master_leaf is None:
            master_leaf = _empty_tag_tree(mkl)[0]
        self.alloc(master_leaf)

        # ── 6. Append tag B-tree pages ────────────────────────────────
        for tree in tag_trees:
            for page_data in tree:
                self.alloc(page_data)

        # ── 7. Build CDX file header (page 0) ────────────────────────
        hdr = bytearray(self.PAGE)
        # Root page of master index (page number × 512)
        struct.pack_into('<i', hdr, 0, master_pn * self.PAGE)
        # Free page list pointer (-1 = none)
        struct.pack_into('<i', hdr, 4, -1)
        # Total pages
        struct.pack_into('<i', hdr, 8, self._n)
        # Key length of master index
        struct.pack_into('<H', hdr, 12, mkl)
        # Index options
        hdr[14] = 224   # 0xE0
        hdr[15] = 1
        # Page 0 is allocated at position 0
        self.alloc(hdr)

        # Re-order: page 0 must come first
        # Pages were appended in order: info pages, master leaf, tag trees, header
        # We need: header(0), info pages(1..2n), master_leaf(2n+1), trees(2n+2..)
        # Simpler: just write in reverse and patch — instead, rebuild correctly:
        # (The alloc order above already puts header last; we move it to front)
        self.pages.insert(0, self.pages.pop())


# ---------------------------------------------------------------------------
# VFP expression evaluator (for building index keys from records)
# ---------------------------------------------------------------------------

def _get_field(rec, fname: str):
    """Get a field value from a dbf record, handling case and type."""
    try:
        return getattr(rec, fname)
    except AttributeError:
        pass
    try:
        return rec[fname]
    except (IndexError, KeyError):
        pass
    try:
        return getattr(rec, fname.upper())
    except AttributeError:
        pass
    try:
        return rec[fname.upper()]
    except (IndexError, KeyError):
        pass
    return ''


def _split_plus(expr: str) -> list[str]:
    """Split a VFP expression on top-level '+' operators."""
    parts = []
    depth = 0
    cur   = ''
    for ch in expr:
        if ch == '(':
            depth += 1
            cur   += ch
        elif ch == ')':
            depth -= 1
            cur   += ch
        elif ch == '+' and depth == 0:
            parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur:
        parts.append(cur.strip())
    return parts


def _split_args(s: str) -> list[str]:
    """Split function arguments by comma at depth 0."""
    parts   = []
    depth   = 0
    cur     = ''
    in_str  = False
    for ch in s:
        if ch == '"':
            in_str = not in_str
            cur   += ch
        elif not in_str and ch == '(':
            depth += 1
            cur   += ch
        elif not in_str and ch == ')':
            depth -= 1
            cur   += ch
        elif not in_str and depth == 0 and ch == ',':
            parts.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur:
        parts.append(cur.strip())
    return parts


def _eval_vfp_expr(rec, expr: str, fi_getter=None) -> str:
    """Evaluate a simple VFP expression and return a string result."""
    expr = expr.strip()

    # Function call: NAME(args)
    m = re.match(r'(\w+)\((.+)\)$', expr, re.I)
    if m:
        fname = m.group(1).upper()
        inner = m.group(2)

        if fname == 'STR':
            args = _split_args(inner)
            if len(args) >= 2:
                length   = int(_eval_vfp_expr(rec, args[1], fi_getter))
                decimals = int(_eval_vfp_expr(rec, args[2], fi_getter)) \
                           if len(args) >= 3 else 0
                inner_val = _eval_vfp_expr(rec, args[0], fi_getter)
                try:
                    n = float(inner_val)
                    if decimals > 0:
                        s = f'{n:.{decimals}f}'
                    else:
                        s = str(int(n))
                except ValueError:
                    s = str(inner_val)
                return s.rjust(length)[:length]
            return '          '

        if fname == 'DTOS':
            val = _eval_vfp_expr(rec, inner, fi_getter)
            from datetime import date, datetime
            if isinstance(val, (date, datetime)):
                return val.strftime('%Y%m%d')
            if isinstance(val, str):
                val_clean = val.strip()
                if val_clean:
                    try:
                        d = datetime.strptime(val_clean[:10], '%Y-%m-%d')
                        return d.strftime('%Y%m%d')
                    except ValueError:
                        pass
            return '00000000'

        if fname == 'IIF':
            args = _split_args(inner)
            if len(args) >= 3:
                cond_val = _eval_vfp_expr(rec, args[0], fi_getter).strip().upper()
                is_true  = cond_val in ('1', '.T.', '.TRUE.', 'TRUE', 'Y', 'YES')
                branch   = args[1] if is_true else args[2]
                branch   = branch.strip()
                if branch.startswith('"') and branch.endswith('"'):
                    return branch[1:-1]
                if branch.startswith("'") and branch.endswith("'"):
                    return branch[1:-1]
                return _eval_vfp_expr(rec, branch, fi_getter)
            return ''

        if fname == 'UPPER':
            return _eval_vfp_expr(rec, inner, fi_getter).upper()

        if fname == 'VAL':
            inner_val = _eval_vfp_expr(rec, inner, fi_getter)
            try:
                return str(float(inner_val))
            except ValueError:
                try:
                    return str(int(float(inner_val)))
                except (ValueError, TypeError):
                    return '0'

        # Unknown function — try evaluating the inner arg
        return _eval_vfp_expr(rec, inner, fi_getter)

    # String literal "…"
    if expr.startswith('"') and expr.endswith('"'):
        return expr[1:-1]
    if expr.startswith("'") and expr.endswith("'"):
        return expr[1:-1]

    # Numeric literal
    try:
        float(expr)
        return expr
    except ValueError:
        pass

    # Arithmetic with top-level operator
    for i, ch in enumerate(expr):
        if ch == '(':
            pass   # depth tracking below
        if ch in '+-*/':
            depth = sum(1 if c == '(' else -1 if c == ')' else 0
                        for c in expr[:i])
            if depth == 0:
                left  = _eval_vfp_expr(rec, expr[:i],   fi_getter)
                right = _eval_vfp_expr(rec, expr[i+1:], fi_getter)
                try:
                    l, r = float(left), float(right)
                    if ch == '+': return str(l + r)
                    if ch == '-': return str(l - r)
                    if ch == '*': return str(l * r)
                    if ch == '/': return str(l / r) if r != 0 else '0'
                except (ValueError, ZeroDivisionError):
                    pass

    # Field name
    fname = expr.strip()
    flen  = None
    ft    = None
    if fi_getter:
        try:
            fi = fi_getter(fname)
            if fi:
                ft, flen, _ = fi
        except Exception:
            pass

    val = _get_field(rec, fname)

    # Date field → YYYYMMDD string
    if ft == 68:   # ord('D')
        from datetime import date, datetime
        if isinstance(val, (date, datetime)):
            return val.strftime('%Y%m%d')
        if isinstance(val, str):
            try:
                d = datetime.strptime(val.strip()[:10], '%Y-%m-%d')
                return d.strftime('%Y%m%d')
            except ValueError:
                pass
        return '00000000'

    if isinstance(val, bool):
        return '.T.' if val else '.F.'

    if isinstance(val, (int, float)):
        s = str(int(val)) if val == int(val) else str(val)
        return s.rjust(flen)[:flen] if flen else s

    s = str(val).strip() if val is not None else ''
    if flen and ft != 68:
        return s.ljust(flen)[:flen]
    return s


def eval_vfp_key(rec, expr: str, key_len: int, fi_getter=None) -> bytes:
    """Evaluate a VFP key expression and return a fixed-length bytes key."""
    result = ''
    for part in _split_plus(expr):
        part = part.strip()
        if part.upper() in ('.NOT.', 'DELETED()'):
            continue
        result += _eval_vfp_expr(rec, part, fi_getter)

    if len(result) > key_len:
        result = result[:key_len]
    elif len(result) < key_len:
        result = result.ljust(key_len)

    return result.encode('cp1252', errors='replace')


def _make_fi_getter(table):
    """Create a field info getter from a dbf Table object."""
    def fi_getter(fname):
        try:
            fi = table.field_info(fname.upper())
            return fi.field_type, fi.length, fi.decimal_count
        except Exception:
            return None
    return fi_getter


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def make_cdx(dbf_path, cdx_path, tags: list[dict],
             records: list = None, table=None):
    """
    Create CDX from dbf records.

    tags:    [{'key_expr': str, 'key_len': int, 'for_expr': str, 'tag_name': str}]
    records: list of dbf records (from table iteration)
    table:   optional dbf Table (for field metadata)
    """
    fi_getter = _make_fi_getter(table) if table else None
    n_tags    = len(tags)
    tag_keys: list[list[tuple[bytes, int]]] = [[] for _ in range(n_tags)]

    if records:
        for ri, rec in enumerate(records):
            rn = ri + 1
            for ti in range(n_tags):
                t        = tags[ti]
                kl       = t['key_len']
                key_data = eval_vfp_key(rec, t['key_expr'], kl, fi_getter)
                tag_keys[ti].append((key_data, rn))

    builder = CdxBuilder()
    builder.build(tags, tag_keys)
    builder.write(str(cdx_path))
