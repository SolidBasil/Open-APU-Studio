"""
backend/latex.py
================
Motor de generación de presupuestos en LaTeX / PDF para Open APU Studio.

Flujo principal (llamado desde handlers.py)
-------------------------------------------
    nodos = self._api.presupuesto_arbol()   # lista de nodos con hijos anidados
    ReportePresupuesto(nombre, nodos).generar(tex_path)

API alternativa desde DB
------------------------
    reporte  = ReportePresupuesto.desde_db(conn, proyecto_id=1)
    pdf_path = reporte.exportar()

API funcional
-------------
    pdf_bytes = generar_presupuesto(datos)
    guardar_presupuesto(datos, "salida/presupuesto.pdf")
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Resolución de la plantilla
# ─────────────────────────────────────────────────────────────────────────────

_TEMPLATE_NAME = "presupuesto.tex"

_TEMPLATE_CANDIDATES = [
    Path(__file__).parent / "latex" / "templates" / _TEMPLATE_NAME,
    Path(__file__).parent / _TEMPLATE_NAME,
]


def _cargar_plantilla(nombre: str = _TEMPLATE_NAME) -> str:
    """
    Carga la plantilla .tex.
    Orden: carpeta templates del usuario → bundled en backend/latex/templates/.
    """
    try:
        from backend.db import Rutas
        user = Rutas.templates() / nombre
        if user.exists():
            return user.read_text(encoding="utf-8")
    except Exception:
        pass

    for candidate in _TEMPLATE_CANDIDATES:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"No se encontró la plantilla '{nombre}'. "
        "Colócala en la carpeta de templates del usuario "
        "o en backend/latex/templates/."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Escapado LaTeX
# ─────────────────────────────────────────────────────────────────────────────

_TEX_SPECIAL = re.compile(r"([&%$#_{}~^\\])")


def escape_tex(text: str | None) -> str:
    """Escapa caracteres especiales de LaTeX en texto plano."""
    if not text:
        return ""
    s = str(text)
    s = s.replace("\\", "\\textbackslash ")
    s = s.replace("~",  "\\textasciitilde ")
    s = _TEX_SPECIAL.sub(r"\\\1", s)
    return s


def _fmt_wbs(wbs: str | None) -> str:
    """Convierte WBS numérico a formato con puntos: '111' → '1.1.1'"""
    if not wbs:
        return ""
    s = str(wbs).strip()
    # Si ya tiene puntos o letras, devolver tal cual
    if "." in s or not s.isdigit():
        return s
    # Insertar punto cada dígito: 11101 → 1.1.1.0.1
    return ".".join(s)


def _fmt_moneda(v) -> str:
    """Formatea un número como '\\$1,234.56'. Devuelve '' si v es None."""
    if v is None:
        return ""
    try:
        return f"\\${float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


# ─────────────────────────────────────────────────────────────────────────────
# Conversión de nodos (lista del árbol) → partidas para la plantilla
# ─────────────────────────────────────────────────────────────────────────────

def _nodos_a_partidas(nodos_raiz: list[dict]) -> tuple[list[dict], float]:
    """
    Convierte la lista de nodos del árbol del presupuesto en la estructura
    de partidas que espera _build_conceptos(), y calcula el gran total.

    Cada nodo raíz (capítulo) se convierte en una partida.
    Sus hijos tipo 'concepto' se convierten en filas de la longtable.
    Los hijos tipo 'capitulo' se expanden recursivamente.

    Los nodos pueden venir en dos formatos:
      A) Árbol anidado: cada nodo tiene clave 'hijos' con sus hijos.
      B) Lista plana:   cada nodo tiene 'padre_id'; se construye el árbol.
    """
    # ── Detectar formato y normalizar a árbol anidado ────────────────────
    if nodos_raiz and "hijos" not in nodos_raiz[0]:
        nodos_raiz = _aplanar_a_arbol(nodos_raiz)

    partidas: list[dict] = []
    gran_total = 0.0

    for raiz in nodos_raiz:
        conceptos: list[dict] = []
        _extraer_conceptos(raiz.get("hijos", []), conceptos)

        subtotal = raiz.get("subtotal") or 0.0
        gran_total += subtotal

        partidas.append({
            "nombre":    raiz.get("descripcion") or raiz.get("descripcion_corta") or "",
            "wbs":       _fmt_wbs(raiz.get("wbs", "")),
            "conceptos": conceptos,
            "subtotal":  _fmt_moneda(subtotal),
            "_depth":    0,
        })

    return partidas, gran_total


def _extraer_conceptos(hijos: list[dict], acum: list[dict], _depth: int = 1) -> None:
    """Recorre el árbol recursivamente y acumula filas.

    capitulo → _partida=True con _depth para padding progresivo.
    concepto → fila \\Concepto{}.
    """
    for hijo in hijos:
        if hijo.get("tipo") == "concepto":
            cant = hijo.get("cantidad")
            acum.append({
                "nivel":       _fmt_wbs(hijo.get("wbs") or str(hijo.get("nivel") or "")),
                "clave":       hijo.get("clave") or "",
                "descripcion": hijo.get("descripcion") or hijo.get("descripcion_corta") or "",
                "unidad":      hijo.get("unidad") or "",
                "cantidad":    (
                    f"{float(cant):,.4f}".rstrip("0").rstrip(".")
                    if cant not in (None, "") else ""
                ),
                "importe":     _fmt_moneda(hijo.get("importe")),
            })
        elif hijo.get("tipo") == "capitulo":
            sub_desc = hijo.get("descripcion") or hijo.get("descripcion_corta") or ""
            acum.append({"_partida": True, "nombre": sub_desc, "_depth": _depth, "wbs": _fmt_wbs(hijo.get("wbs", ""))})
            _extraer_conceptos(hijo.get("hijos", []), acum, _depth + 1)


def _aplanar_a_arbol(nodos: list[dict]) -> list[dict]:
    """Convierte lista plana con padre_id en árbol anidado con 'hijos'."""
    por_id = {n["id"]: {**n, "hijos": []} for n in nodos}
    raices = []
    for n in por_id.values():
        padre = n.get("padre_id")
        if padre and padre in por_id:
            por_id[padre]["hijos"].append(n)
        else:
            raices.append(n)
    return raices


# ─────────────────────────────────────────────────────────────────────────────
# Lectura de metadatos del proyecto desde SQLite
# ─────────────────────────────────────────────────────────────────────────────

def _leer_meta_db(conn, proyecto_id: int) -> dict:
    """Lee proyecto + configuracion_proyecto y devuelve los campos de encabezado."""
    cur = conn.cursor()

    row = cur.execute(
        "SELECT * FROM proyectos WHERE id = ? AND activo = 1", [proyecto_id]
    ).fetchone()
    if not row:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado.")
    proy = dict(row)

    cfg_row = cur.execute(
        "SELECT * FROM configuracion_proyecto WHERE proyecto_id = ?", [proyecto_id]
    ).fetchone()
    cfg = dict(cfg_row) if cfg_row else {}

    return {
        "nombre_prot":    cfg.get("nombre_prototipo") or proy.get("nombre", ""),
        "nombre":         proy.get("nombre", ""),
        "cliente":        proy.get("cliente", ""),
        "ubicacion":      proy.get("ubicacion", ""),
        "version":        cfg.get("version", "1.0") or "1.0",
        "moneda":         cfg.get("moneda", "MXN"),
        "iva_pct":        float(cfg.get("iva_pct") or 16.0),
        "responsable":    cfg.get("responsable") or "",
        "observaciones":  cfg.get("observaciones") or "",
        "total_obra":     proy.get("total_obra"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del bloque <<conceptos>>
# ─────────────────────────────────────────────────────────────────────────────

def _build_conceptos(partidas: list[dict]) -> str:
    """
    Genera el cuerpo LaTeX de la longtable usando los comandos de la plantilla:
        \\Partida{nombre}
        \\Concepto{nivel}{clave}{descripcion}{unidad}{cantidad}{importe}
        \\SubtotalPartida{importe}
    """
    lines: list[str] = []

    for partida in partidas:
        depth = partida.get("_depth", 0)
        padding = "\\quad " * depth
        wbs = escape_tex(partida.get("wbs", ""))
        lines.append(rf"\Partida{{{wbs}}}{{{padding}{escape_tex(partida['nombre'])}}}")

        for c in partida.get("conceptos", []):
            if c.get("_partida"):
                depth = c.get("_depth", 1)
                padding = "\\quad " * depth
                wbs = escape_tex(c.get("wbs", ""))
                lines.append(rf"\Partida{{{wbs}}}{{{padding}{escape_tex(c['nombre'])}}}")
                continue
            desc = escape_tex(c.get("descripcion", ""))
            lines.append(
                rf"\Concepto"
                rf"{{{escape_tex(c.get('nivel', ''))}}}"
                rf"{{{escape_tex(c.get('clave', ''))}}}"
                rf"{{{desc}}}"
                rf"{{{escape_tex(c.get('unidad', ''))}}}"
                rf"{{{escape_tex(c.get('cantidad', ''))}}}"
                rf"{{{c.get('importe', '')}}}"   # ya formateado con \$
            )

        if "subtotal" in partida and partida["subtotal"]:
            lines.append(rf"\SubtotalPartida{{{partida['subtotal']}}}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Sustitución de marcadores <<campo>>
# ─────────────────────────────────────────────────────────────────────────────

_MARKER_RE = re.compile(r"<<([a-zA-Z0-9_]+)>>")

_SIMPLE_FIELDS = frozenset({
    "nombre_prototipo", "nombre_presupuesto", "proyecto", "cliente",
    "ubicacion", "version", "fecha", "moneda", "responsable",
})

_RAW_FIELDS = frozenset({"observaciones", "subtotal", "iva", "total"})


def _render_template(template: str, datos: dict) -> str:
    """Reemplaza todos los marcadores <<campo>> con los valores de `datos`."""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key == "conceptos":
            return _build_conceptos(datos.get("partidas", []))
        if key in _RAW_FIELDS:
            return str(datos.get(key, ""))
        if key in _SIMPLE_FIELDS:
            return escape_tex(datos.get(key, ""))
        return escape_tex(datos.get(key, f"<<{key}>>"))

    return _MARKER_RE.sub(_replace, template)


# ─────────────────────────────────────────────────────────────────────────────
# Compilación con pdflatex
# ─────────────────────────────────────────────────────────────────────────────

def compilar_pdf(tex_path: str | Path) -> str | None:
    """
    Ejecuta pdflatex (2 pasadas) sobre un .tex existente.
    Retorna ruta al .pdf o None si falla. Limpia auxiliares.
    """
    tex_path = Path(tex_path)
    if not tex_path.exists():
        return None

    try:
        for _ in range(2):
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                cwd=tex_path.parent,
                capture_output=True,
                text=True,
                timeout=120,
            )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[latex] Error compilando: {e}")
        return None

    for ext in (".aux", ".log", ".out", ".toc"):
        (tex_path.parent / (tex_path.stem + ext)).unlink(missing_ok=True)

    pdf = tex_path.with_suffix(".pdf")
    return str(pdf) if pdf.exists() else None


def _compilar_fuente(tex_source: str) -> bytes:
    """Compila código LaTeX en memoria y devuelve bytes del PDF."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tex_file = tmp_path / "presupuesto.tex"
        tex_file.write_text(tex_source, encoding="utf-8")

        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
                 str(tex_file)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"pdflatex falló (código {result.returncode}):\n"
                    + result.stdout[-3000:]
                )

        pdf_file = tmp_path / "presupuesto.pdf"
        if not pdf_file.exists():
            raise FileNotFoundError("pdflatex no generó el PDF esperado.")
        return pdf_file.read_bytes()


# ─────────────────────────────────────────────────────────────────────────────
# Clase principal
# ─────────────────────────────────────────────────────────────────────────────

class ReportePresupuesto:
    """
    Genera el presupuesto en .tex y/o .pdf.

    Uso desde handlers.py (flujo original, sin cambios)
    ---------------------------------------------------
        nodos = self._api.presupuesto_arbol()
        ReportePresupuesto(nombre, nodos).generar(tex_path)

    Uso desde DB (metadatos completos)
    ----------------------------------
        reporte = ReportePresupuesto.desde_db(conn, proyecto_id=1)
        reporte.exportar()
    """

    def __init__(self, nombre_proyecto: str, nodos_o_datos):
        """
        Parámetros
        ----------
        nombre_proyecto : nombre del proyecto (stem del .db)
        nodos_o_datos   : lista de nodos del árbol  ← lo que pasa handlers.py
                          o dict de datos ya preparado (uso interno)
        """
        self.nombre = nombre_proyecto

        if isinstance(nodos_o_datos, list):
            # ── Caso principal: lista de nodos del árbol ──────────────────
            partidas, gran_total = _nodos_a_partidas(nodos_o_datos)
            iva_pct   = 16.0
            iva_monto = gran_total * (iva_pct / 100)
            total     = gran_total + iva_monto

            self.datos = {
                "nombre_prototipo":   nombre_proyecto,
                "nombre_presupuesto": nombre_proyecto,
                "proyecto":           nombre_proyecto,
                "cliente":            "",
                "ubicacion":          "",
                "version":            "1.0",
                "fecha":              date.today().strftime("%d/%m/%Y"),
                "moneda":             "MXN",
                "responsable":        "",
                "observaciones":      "",
                "subtotal":           _fmt_moneda(gran_total),
                "iva":                f"{iva_pct:.0f}\\% ({_fmt_moneda(iva_monto)})",
                "total":              _fmt_moneda(total),
                "partidas":           partidas,
            }
        else:
            # ── Caso interno: dict ya preparado (desde_db / API funcional) ─
            self.datos = {
                **nodos_o_datos,
                "nombre_presupuesto": nodos_o_datos.get("nombre_presupuesto", nombre_proyecto),
            }

    # ── Constructor desde DB (enriquece con metadatos del proyecto) ───────

    @classmethod
    def desde_db(cls, conn, proyecto_id: int) -> "ReportePresupuesto":
        """
        Construye el reporte leyendo datos completos desde la DB.
        Los nodos del árbol también se leen desde estructura_presupuesto.
        """
        meta = _leer_meta_db(conn, proyecto_id)

        # Leer nodos planos y convertir a árbol
        cur = conn.cursor()
        nodos_planos = [dict(r) for r in cur.execute("""
            SELECT id, padre_id, tipo, nivel, wbs, clave,
                   descripcion, descripcion_corta, unidad,
                   cantidad, precio_unitario, importe, subtotal
            FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id]).fetchall()]

        raices = _aplanar_a_arbol(nodos_planos)
        partidas, gran_total = _nodos_a_partidas(raices)

        total_obra = meta["total_obra"] or gran_total
        iva_pct    = meta["iva_pct"]
        iva_monto  = total_obra * (iva_pct / 100)

        datos = {
            "nombre_prototipo":   meta["nombre_prot"],
            "nombre_presupuesto": meta["nombre"],
            "proyecto":           meta["nombre"],
            "cliente":            meta["cliente"],
            "ubicacion":          meta["ubicacion"],
            "version":            meta["version"],
            "fecha":              date.today().strftime("%d/%m/%Y"),
            "moneda":             meta["moneda"],
            "responsable":        meta["responsable"],
            "observaciones":      escape_tex(meta["observaciones"]),
            "subtotal":           _fmt_moneda(total_obra),
            "iva":                f"{iva_pct:.0f}\\% ({_fmt_moneda(iva_monto)})",
            "total":              _fmt_moneda(total_obra + iva_monto),
            "partidas":           partidas,
        }
        return cls(meta["nombre"], datos)

    # ── generar: escribe el .tex (interfaz que llama handlers.py) ─────────

    def generar(self, filepath: str | Path) -> str:
        """Renderiza la plantilla y escribe el .tex en filepath."""
        plantilla = _cargar_plantilla()
        contenido = _render_template(plantilla, self.datos)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contenido, encoding="utf-8")
        return str(path)

    # ── exportar: genera .tex y compila a .pdf ────────────────────────────

    def exportar(
        self,
        destino: str | Path | None = None,
        solo_tex: bool = False,
    ) -> str:
        """Genera el .tex y (por defecto) compila a .pdf. Retorna ruta del archivo."""
        if destino is None:
            try:
                from backend.db import Rutas
                base = Rutas.reportes() / self.nombre.replace(" ", "_")
            except Exception:
                base = Path(self.nombre.replace(" ", "_"))
        else:
            base = Path(destino).with_suffix("")

        tex_path = base.with_suffix(".tex")
        self.generar(tex_path)

        if solo_tex:
            return str(tex_path)

        pdf = compilar_pdf(tex_path)
        return pdf if pdf else str(tex_path)

    def compilar(self, tex_path: str | Path) -> str | None:
        """Compila un .tex existente a PDF."""
        return compilar_pdf(tex_path)


# ─────────────────────────────────────────────────────────────────────────────
# API funcional
# ─────────────────────────────────────────────────────────────────────────────

def generar_presupuesto(
    datos: dict,
    plantilla_path: str | Path | None = None,
) -> bytes:
    """Genera PDF desde un dict de datos y devuelve sus bytes."""
    template = (
        Path(plantilla_path).read_text(encoding="utf-8")
        if plantilla_path else _cargar_plantilla()
    )
    return _compilar_fuente(_render_template(template, datos))


def guardar_presupuesto(
    datos: dict,
    destino: str | Path,
    plantilla_path: str | Path | None = None,
) -> Path:
    """Genera el PDF y lo guarda en `destino`. Retorna el Path escrito."""
    pdf_bytes = generar_presupuesto(datos, plantilla_path=plantilla_path)
    dest = Path(destino)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(pdf_bytes)
    return dest


def renderizar_tex(
    datos: dict,
    plantilla_path: str | Path | None = None,
) -> str:
    """Devuelve el .tex renderizado sin compilar. Útil para depuración."""
    template = (
        Path(plantilla_path).read_text(encoding="utf-8")
        if plantilla_path else _cargar_plantilla()
    )
    return _render_template(template, datos)