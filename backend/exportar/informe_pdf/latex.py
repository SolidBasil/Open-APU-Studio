"""
backend/latex.py
================
Motor de generación de presupuestos en LaTeX / PDF para Open APU Studio.

Flujo principal (llamado desde handlers.py)
-------------------------------------------
    nodos = self._api.presupuesto_arbol()   # lista de nodos con hijos anidados
    columnas = tabla_arbol.columnas_para_reporte()  # opcional — ver arbol.py
    ReportePresupuesto(nombre, nodos, columnas=columnas).generar(tex_path)

API alternativa desde DB
------------------------
    reporte  = ReportePresupuesto.desde_db(conn, proyecto_id=1)
    pdf_path = reporte.exportar()
"""

from __future__ import annotations

import re
import subprocess
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
        from backend.database.db import Rutas
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
# Campos disponibles para la tabla de conceptos
# ─────────────────────────────────────────────────────────────────────────────
# Cada campo: (extractor(nodo) -> str, alineación 'l'|'c'|'r', escapar_tex)
# alineación decide el tipo de columna en el longtable; escapar_tex=False
# para campos que ya traen su propio escapado (moneda con "\$" literal).

def _campo_estructura(n: dict) -> str:
    return ""


def _campo_nivel(n: dict) -> str:
    return _fmt_wbs(n.get("wbs") or str(n.get("nivel") or ""))


def _campo_tipo(n: dict) -> str:
    return {"capitulo": "Capítulo", "concepto": "Concepto"}.get(n.get("tipo"), n.get("tipo") or "")


def _campo_clave(n: dict) -> str:
    return n.get("clave_opus") or ""


def _campo_descripcion(n: dict) -> str:
    return n.get("descripcion") or n.get("descripcion_corta") or ""


def _campo_unidad(n: dict) -> str:
    return n.get("unidad") or ""


def _campo_cantidad(n: dict) -> str:
    cant = n.get("cantidad")
    if cant in (None, ""):
        return ""
    return f"{float(cant):,.4f}".rstrip("0").rstrip(".")


def _campo_precio_unitario(n: dict) -> str:
    pu = n.get("precio_unitario")
    return _fmt_moneda(pu) if pu not in (None, "") else ""


def _campo_total(n: dict) -> str:
    return _fmt_moneda(n.get("total"))


def _campo_estado(n: dict) -> str:
    from backend.database.repos.presupuesto import ESTADO_NOMBRE
    return ESTADO_NOMBRE.get(n.get("estado"), "")


def _campo_notas(n: dict) -> str:
    return n.get("notas_rapidas") or ""


def _campo_creado(n: dict) -> str:
    return str(n.get("creado_en") or "")


def _campo_modificado(n: dict) -> str:
    return str(n.get("modificado_en") or "")


def _campo_orden(n: dict) -> str:
    return str(n.get("orden") or "")


def _campo_formula(n: dict) -> str:
    return n.get("formula") or ""


# campo -> (extractor, alineación, escapar_tex)
_CAMPOS: dict[str, tuple] = {
    "estructura":      (_campo_estructura,      "c", True),
    "nivel":           (_campo_nivel,           "c", True),
    "tipo":            (_campo_tipo,             "c", True),
    "clave":           (_campo_clave,            "c", True),
    "descripcion":     (_campo_descripcion,      "l", True),
    "unidad":          (_campo_unidad,           "c", True),
    "cantidad":        (_campo_cantidad,         "r", True),
    "precio_unitario": (_campo_precio_unitario,  "r", False),  # ya trae \$ escapado
    "total":           (_campo_total,            "r", False),  # ídem
    "estado":          (_campo_estado,           "c", True),
    "notas":           (_campo_notas,            "l", True),
    "creado":          (_campo_creado,           "l", True),
    "modificado":      (_campo_modificado,       "l", True),
    "orden":           (_campo_orden,             "r", True),
    "formula":         (_campo_formula,          "l", True),
}

# Columnas por defecto cuando no se pasa una lista explícita (ej. exportar()
# / desde_db() invocados sin una TablaArbol de por medio). Reproduce
# aproximadamente el layout fijo que tenía el reporte antes de que las
# columnas fueran personalizables; los anchos son proporcionales entre sí
# (ver _anchos_a_cm), no absolutos.
DEFAULT_COLUMNAS: list[dict] = [
    {"campo": "nivel",           "label": "Nivel",       "ancho_px": 40},
    {"campo": "descripcion",     "label": "Descripción", "ancho_px": 240},
    {"campo": "unidad",          "label": "Unidad",      "ancho_px": 48},
    {"campo": "cantidad",        "label": "Cantidad",    "ancho_px": 80},
    {"campo": "precio_unitario", "label": "P.U.",        "ancho_px": 56},
    {"campo": "total",           "label": "Importe",     "ancho_px": 88},
]

# Ancho de hoja A4 en cm, según orientación — para calcular cuánto espacio
# horizontal queda disponible para la tabla una vez descontados los
# márgenes (ver DialogoConfigImpresion / ReportePresupuesto).
_ANCHO_PAPEL_CM = {"vertical": 21.0, "horizontal": 29.7}

_MARGENES_DEFAULT = {"sup": 2.0, "inf": 2.0, "izq": 2.0, "der": 2.0}


def _ancho_tabla_cm(orientacion: str, margenes: dict) -> float:
    """Ancho horizontal disponible para la tabla: ancho de hoja menos
    márgenes izquierdo y derecho, según orientación."""
    ancho_papel = _ANCHO_PAPEL_CM.get(orientacion, _ANCHO_PAPEL_CM["vertical"])
    return max(5.0, ancho_papel - margenes.get("izq", 2.0) - margenes.get("der", 2.0))


TABCOLSEP_CM = 0.211  # 6pt → cm (LaTeX default \tabcolsep)


def _anchos_a_cm(columnas: list[dict], ancho_total_cm: float, overrides: dict | None = None) -> list[float]:
    """Reparte ancho_total_cm entre las columnas.

    Una columna con override explícito (ver DialogoConfigImpresion) usa
    ese ancho fijo; el resto se reparte proporcionalmente al ancho en
    píxeles que tiene cada una en pantalla, con un mínimo de 1cm para que
    ninguna quede ilegible.

    NOTA: LaTeX añade 2\tabcolsep (~0.422cm) entre columnas adyacentes,
    incluso con @{} en los extremos del longtable. Restamos ese espacio
    del total disponible para que la tabla no se salga de los márgenes.
    """
    n = len(columnas)
    if n > 1:
        ancho_total_cm -= (n - 1) * 2 * TABCOLSEP_CM

    overrides = overrides or {}
    anchos: list[float | None] = [None] * len(columnas)
    resto_idx: list[int] = []
    resto_px_total = 0
    ancho_restante = ancho_total_cm

    for i, c in enumerate(columnas):
        ov = overrides.get(c["campo"])
        if ov:
            anchos[i] = ov
            ancho_restante -= ov
        else:
            resto_idx.append(i)
            resto_px_total += c["ancho_px"]

    ancho_restante = max(ancho_restante, 1.0 * len(resto_idx))
    resto_px_total = resto_px_total or 1
    for i in resto_idx:
        anchos[i] = max(1.0, columnas[i]["ancho_px"] / resto_px_total * ancho_restante)

    return anchos


def _tabla_colspec(columnas: list[dict], ancho_total_cm: float, overrides: dict | None = None) -> str:
    """Construye el argumento de columnas del longtable, ej.:
    '@{}>{\\centering\\arraybackslash}p{1.0cm} p{6.0cm} ... @{}'"""
    anchos = _anchos_a_cm(columnas, ancho_total_cm, overrides)
    partes = []
    for c, ancho in zip(columnas, anchos):
        alineacion = _CAMPOS.get(c["campo"], (None, "l", True))[1]
        if alineacion == "c":
            partes.append(rf">{{\centering\arraybackslash}}p{{{ancho:.2f}cm}}")
        elif alineacion == "r":
            partes.append(rf">{{\raggedleft\arraybackslash}}p{{{ancho:.2f}cm}}")
        else:
            partes.append(rf"p{{{ancho:.2f}cm}}")
    return "@{} " + " ".join(partes) + " @{}"


def _geometry_opts(orientacion: str, margenes: dict) -> str:
    """Opciones para \\usepackage[...]{geometry}: papel, márgenes por lado
    y, si aplica, orientación horizontal (landscape)."""
    opts = (
        f"a4paper,"
        f"top={margenes.get('sup', 2.0)}cm,"
        f"bottom={margenes.get('inf', 2.0)}cm,"
        f"left={margenes.get('izq', 2.0)}cm,"
        f"right={margenes.get('der', 2.0)}cm"
    )
    if orientacion == "horizontal":
        opts += ",landscape"
    return opts


def _tabla_header(columnas: list[dict]) -> str:
    """Fila de encabezado del longtable a partir de los labels de columna."""
    celdas = [rf"\textbf{{{escape_tex(c['label'])}}}" for c in columnas]
    return " & ".join(celdas) + r"\\"


# ─────────────────────────────────────────────────────────────────────────────
# Conversión de nodos (lista del árbol) → partidas para la plantilla
# ─────────────────────────────────────────────────────────────────────────────

def _subtotal_nodo(nodo: dict) -> float:
    """Suma recursiva de los totales de los conceptos bajo `nodo`.

    Se usa en vez de leer directamente nodo.get('total') porque, al
    imprimir solo una selección (ver filtrar_por_seleccion), el subtotal
    impreso debe cuadrar con las filas realmente incluidas y no con el
    total guardado del capítulo completo.
    """
    total = 0.0
    for hijo in nodo.get("hijos", []):
        if hijo.get("tipo") == "concepto":
            total += hijo.get("total") or 0.0
        else:
            total += _subtotal_nodo(hijo)
    return total


def filtrar_por_seleccion(nodos_raiz: list[dict], ids_seleccionados: set[int]) -> list[dict]:
    """Poda el árbol anidado para dejar solo el contenido seleccionado.

    Un nodo cuyo id está en `ids_seleccionados` se incluye completo (con
    todo su subárbol, sin más filtrado). Un nodo no seleccionado pero con
    algún descendiente seleccionado se conserva como contenedor —para no
    perder el contexto de jerarquía en el reporte— pero solo con esos
    descendientes, no con sus hermanos no seleccionados.

    Si `ids_seleccionados` viene vacío, devuelve `nodos_raiz` tal cual
    (reporte completo, comportamiento sin cambios).
    """
    if not ids_seleccionados:
        return nodos_raiz

    def _incluir(nodo: dict) -> dict | None:
        if nodo.get("id") in ids_seleccionados:
            return nodo
        hijos_incluidos = [
            resultado for hijo in nodo.get("hijos", [])
            if (resultado := _incluir(hijo)) is not None
        ]
        if hijos_incluidos:
            return {**nodo, "hijos": hijos_incluidos}
        return None

    return [n for raiz in nodos_raiz if (n := _incluir(raiz)) is not None]


def _nodos_a_partidas(
    nodos_raiz: list[dict],
    columnas: list[dict],
    ids_seleccionados: set[int] | None = None,
) -> tuple[list[dict], float]:
    """
    Convierte la lista de nodos del árbol del presupuesto en la estructura
    de partidas que espera _build_conceptos(), y calcula el gran total.

    Cada nodo raíz (capítulo) se convierte en una partida.
    Sus hijos tipo 'concepto' se convierten en filas de la longtable.
    Los hijos tipo 'capitulo' se expanden recursivamente.

    `columnas` es la lista {"campo","label","ancho_px"} de columnas
    imprimibles (ver TablaArbol.columnas_para_reporte) — determina qué
    valores se extraen de cada concepto.

    `ids_seleccionados`, si viene con contenido, restringe el árbol a esos
    nodos (ver filtrar_por_seleccion) antes de construir las partidas.

    Los nodos pueden venir en dos formatos:
      A) Árbol anidado: cada nodo tiene clave 'hijos' con sus hijos.
      B) Lista plana:   cada nodo tiene 'padre_id'; se construye el árbol.
    """
    # ── Detectar formato y normalizar a árbol anidado ────────────────────
    if nodos_raiz and "hijos" not in nodos_raiz[0]:
        nodos_raiz = _aplanar_a_arbol(nodos_raiz)

    if ids_seleccionados:
        nodos_raiz = filtrar_por_seleccion(nodos_raiz, ids_seleccionados)

    partidas: list[dict] = []
    gran_total = 0.0

    for raiz in nodos_raiz:
        conceptos: list[dict] = []
        _extraer_conceptos(raiz.get("hijos", []), conceptos, columnas)

        subtotal = _subtotal_nodo(raiz)
        gran_total += subtotal

        partidas.append({
            "nombre":    raiz.get("descripcion") or raiz.get("descripcion_corta") or "",
            "wbs":       _fmt_wbs(raiz.get("wbs", "")),
            "conceptos": conceptos,
            "subtotal":  _fmt_moneda(subtotal),
            "_depth":    0,
        })

    return partidas, gran_total


def _extraer_conceptos(hijos: list[dict], acum: list[dict], columnas: list[dict], _depth: int = 1) -> None:
    """Recorre el árbol recursivamente y acumula filas.

    capitulo → _partida=True con _depth para padding progresivo.
    concepto → fila con un valor por columna imprimible, en "valores".
    """
    for hijo in hijos:
        if hijo.get("tipo") == "concepto":
            valores = []
            for c in columnas:
                extractor, _alineacion, escapar = _CAMPOS.get(c["campo"], (lambda n: "", "l", True))
                valor = extractor(hijo)
                valores.append(escape_tex(valor) if escapar else valor)
            acum.append({"valores": valores})
        elif hijo.get("tipo") == "capitulo":
            sub_desc = hijo.get("descripcion") or hijo.get("descripcion_corta") or ""
            acum.append({"_partida": True, "nombre": sub_desc, "_depth": _depth, "wbs": _fmt_wbs(hijo.get("wbs", ""))})
            _extraer_conceptos(hijo.get("hijos", []), acum, columnas, _depth + 1)


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
    """Lee proyecto y devuelve los campos de encabezado para el reporte."""
    cur = conn.cursor()

    row = cur.execute(
        "SELECT * FROM proyectos WHERE id = ? AND activo = 1", [proyecto_id]
    ).fetchone()
    if not row:
        raise ValueError(f"Proyecto {proyecto_id} no encontrado.")
    proy = dict(row)

    return {
        "nombre_prot":    proy.get("nombre", ""),
        "nombre":         proy.get("nombre", ""),
        "cliente":        proy.get("cliente_nombre", ""),
        "ubicacion":      proy.get("obra_domicilio", ""),
        "version":        proy.get("reporte_version", "1.0") or "1.0",
        "moneda":         proy.get("moneda_abrev", "MXN"),
        "iva_pct":        float(proy.get("iva_porcentaje") or 16.0),
        "responsable":    proy.get("reporte_responsable", ""),
        "observaciones":  proy.get("reporte_observaciones", ""),
        "total_obra":     proy.get("total_obra"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Construcción del bloque <<conceptos>>
# ─────────────────────────────────────────────────────────────────────────────

def _build_conceptos(partidas: list[dict], num_columnas: int) -> str:
    """
    Genera el cuerpo LaTeX de la longtable. Cada fila se arma directamente
    (sin macro \\Concepto de aridad fija) porque el número de columnas es
    variable según cuáles estén marcadas como imprimibles.
    """
    lines: list[str] = []

    for partida in partidas:
        depth = partida.get("_depth", 0)
        padding = "\\quad " * depth
        wbs = escape_tex(partida.get("wbs", ""))
        titulo = f"{wbs}\\ \\ {padding}{escape_tex(partida['nombre'])}" if wbs else f"{padding}{escape_tex(partida['nombre'])}"
        lines.append(rf"\rowcolor{{Gris2}}\multicolumn{{{num_columnas}}}{{l}}{{\textbf{{{titulo}}}}}\\")

        for c in partida.get("conceptos", []):
            if c.get("_partida"):
                depth = c.get("_depth", 1)
                padding = "\\quad " * depth
                wbs = escape_tex(c.get("wbs", ""))
                titulo = f"{wbs}\\ \\ {padding}{escape_tex(c['nombre'])}" if wbs else f"{padding}{escape_tex(c['nombre'])}"
                lines.append(rf"\rowcolor{{Gris2}}\multicolumn{{{num_columnas}}}{{l}}{{\textbf{{{titulo}}}}}\\")
                continue
            lines.append(" & ".join(c.get("valores", [])) + r"\\")

        if "subtotal" in partida and partida["subtotal"]:
            if num_columnas > 1:
                lines.append(
                    rf"\rowcolor{{Gris}}\multicolumn{{{num_columnas - 1}}}{{r}}{{\textbf{{Total partida:}}}} & "
                    rf"\textbf{{{partida['subtotal']}}}\\"
                )
            else:
                lines.append(
                    rf"\rowcolor{{Gris}}\multicolumn{{1}}{{r}}{{\textbf{{Total partida: {partida['subtotal']}}}}}\\"
                )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Sustitución de marcadores <<campo>>
# ─────────────────────────────────────────────────────────────────────────────

_MARKER_RE = re.compile(r"<<([a-zA-Z0-9_]+)>>")

_SIMPLE_FIELDS = frozenset({
    "nombre_prototipo", "nombre_presupuesto", "proyecto", "cliente",
    "ubicacion", "version", "fecha", "moneda", "responsable",
})

_RAW_FIELDS = frozenset({
    "observaciones", "subtotal", "iva", "total",
    "tabla_colspec", "tabla_header", "num_columnas", "geometry_opts",
})


def _render_template(template: str, datos: dict) -> str:
    """Reemplaza todos los marcadores <<campo>> con los valores de `datos`."""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        if key == "conceptos":
            return _build_conceptos(datos.get("partidas", []), len(datos.get("columnas", DEFAULT_COLUMNAS)))
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

    def __init__(
        self,
        nombre_proyecto: str,
        nodos_o_datos,
        columnas: list[dict] | None = None,
        ids_seleccionados: set[int] | None = None,
        margenes: dict | None = None,
        orientacion: str = "vertical",
        anchos_cm: dict | None = None,
    ):
        """
        Parámetros
        ----------
        nombre_proyecto : nombre del proyecto (stem del .db)
        nodos_o_datos   : lista de nodos del árbol  ← lo que pasa handlers.py
                          o dict de datos ya preparado (uso interno)
        columnas        : columnas imprimibles en orden, con ancho actual
                          en píxeles — ver TablaArbol.columnas_para_reporte().
                          Si no se pasa (o viene vacía), se usa DEFAULT_COLUMNAS.
        ids_seleccionados : si se pasa (no vacío), solo se incluye en el
                          reporte el contenido seleccionado — ver
                          TablaArbol.ids_seleccionados_arbol() y
                          filtrar_por_seleccion(). Si es None o vacío, se
                          imprime el presupuesto completo (comportamiento
                          por defecto, sin cambios).
        margenes        : dict {"sup","inf","izq","der"} en cm. Si no se
                          pasa, usa 2cm en los cuatro lados — ver
                          frontend/ventana/widgets/config_impresion.py.
        orientacion     : "vertical" (default) u "horizontal".
        anchos_cm       : overrides de ancho por campo (ver
                          DialogoConfigImpresion) — el resto de las
                          columnas se reparte proporcionalmente entre el
                          espacio restante.
        """
        self.nombre = nombre_proyecto
        columnas = columnas or DEFAULT_COLUMNAS
        margenes = {**_MARGENES_DEFAULT, **(margenes or {})}
        ancho_tabla_cm = _ancho_tabla_cm(orientacion, margenes)

        if isinstance(nodos_o_datos, list):
            # ── Caso principal: lista de nodos del árbol ──────────────────
            partidas, gran_total = _nodos_a_partidas(nodos_o_datos, columnas, ids_seleccionados)
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
                "columnas":           columnas,
                "tabla_colspec":      _tabla_colspec(columnas, ancho_tabla_cm, anchos_cm),
                "tabla_header":       _tabla_header(columnas),
                "num_columnas":       str(len(columnas)),
                "geometry_opts":      _geometry_opts(orientacion, margenes),
            }
        else:
            # ── Caso interno: dict ya preparado (desde_db / API funcional) ─
            self.datos = {
                **nodos_o_datos,
                "nombre_presupuesto": nodos_o_datos.get("nombre_presupuesto", nombre_proyecto),
            }
            self.datos.setdefault("columnas", columnas)
            self.datos.setdefault("tabla_colspec", _tabla_colspec(self.datos["columnas"], ancho_tabla_cm, anchos_cm))
            self.datos.setdefault("tabla_header", _tabla_header(self.datos["columnas"]))
            self.datos.setdefault("num_columnas", str(len(self.datos["columnas"])))
            self.datos.setdefault("geometry_opts", _geometry_opts(orientacion, margenes))

    # ── Constructor desde DB (enriquece con metadatos del proyecto) ───────

    @classmethod
    def desde_db(
        cls, conn, proyecto_id: int,
        columnas: list[dict] | None = None,
        margenes: dict | None = None,
        orientacion: str = "vertical",
        anchos_cm: dict | None = None,
    ) -> "ReportePresupuesto":
        """
        Construye el reporte leyendo datos completos desde la DB.
        Los nodos del árbol también se leen desde estructura_presupuesto.

        columnas, margenes, orientacion, anchos_cm: ver __init__.
        """
        meta = _leer_meta_db(conn, proyecto_id)
        columnas = columnas or DEFAULT_COLUMNAS

        # Leer nodos planos y convertir a árbol
        cur = conn.cursor()
        nodos_planos = [dict(r) for r in cur.execute("""
            SELECT id, padre_id, tipo, nivel, wbs,
                   descripcion, cantidad, total
            FROM estructura_presupuesto
            WHERE proyecto_id = ? AND activo = 1
            ORDER BY wbs
        """, [proyecto_id]).fetchall()]

        raices = _aplanar_a_arbol(nodos_planos)
        partidas, gran_total = _nodos_a_partidas(raices, columnas)

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
            "columnas":           columnas,
        }
        return cls(meta["nombre"], datos, margenes=margenes, orientacion=orientacion, anchos_cm=anchos_cm)

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
                from backend.database.db import Rutas
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
