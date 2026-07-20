"""
exportar_pdf.py
===============
Exportación ligera de PDF para el visor DWG.

Captura los píxeles actuales del canvas como PNG y los incrusta
en un documento A4 apaisado con reportlab, con cabecera que registra
nombre del dibujo, fecha y escala activa.
"""

from __future__ import annotations

import datetime
import io
import os

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdf_canvas


def _ymd_stamp(d: datetime.date | None = None) -> str:
    d = d or datetime.date.today()
    return d.strftime("%Y%m%d")


def _header_date(d: datetime.date | None = None) -> str:
    d = d or datetime.date.today()
    return d.strftime("%d %b %Y")


def _strip_ext(name: str) -> str:
    for ext in (".dxf", ".dwg", ".rvt", ".ifc", ".pdf"):
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name


def export_canvas_to_pdf(
    image_data: bytes,
    *,
    filename: str | None = None,
    scale: int = 1,
    download_name: str | None = None,
    output_path: str | None = None,
) -> str:
    """Exporta imagen PNG del canvas a PDF A4 apaisado.

    Args:
        image_data: bytes PNG del canvas.
        filename: nombre del dibujo fuente (para cabecera).
        scale: denominador de escala (e.g. 50 para 1:50).
        download_name: nombre de descarga (sin extensión).
        output_path: ruta de salida. Si None, genera nombre automático.

    Returns:
        Ruta del PDF generado.
    """
    page_w, page_h = landscape(A4)  # 297 × 210 mm en puntos
    margin = 10 * mm
    header_h = 12 * mm

    display_name = _strip_ext(filename or "drawing")
    out = output_path or f"{_strip_ext(download_name or filename or 'drawing')}-{_ymd_stamp()}.pdf"

    c = pdf_canvas.Canvas(out, pagesize=landscape(A4))

    # ── Cabecera ──────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, page_h - margin - 6 * mm, display_name)

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    meta = f"Scale 1:{scale}    {_header_date()}"
    c.drawRightString(page_w - margin, page_h - margin - 6 * mm, meta)

    # Línea separadora
    c.setStrokeColorRGB(0.78, 0.78, 0.78)
    c.setLineWidth(0.2)
    c.line(margin, page_h - margin - header_h, page_w - margin, page_h - margin - header_h)
    c.setFillColorRGB(0, 0, 0)

    # ── Imagen ────────────────────────────────────────────────
    from PIL import Image
    img = Image.open(io.BytesIO(image_data))
    img_w, img_h = img.size

    avail_w = page_w - margin * 2
    avail_h = page_h - margin * 2 - header_h - 2 * mm
    img_ratio = img_w / img_h
    av_ratio = avail_w / avail_h

    if img_ratio > av_ratio:
        draw_w = avail_w
        draw_h = avail_w / img_ratio
    else:
        draw_h = avail_h
        draw_w = avail_h * img_ratio

    draw_x = (page_w - draw_w) / 2
    draw_y = page_h - margin - header_h - 2 * mm - draw_h

    c.drawImage(
        io.BytesIO(image_data),
        draw_x, draw_y, draw_w, draw_h,
        preserveAspectRatio=True,
    )

    c.save()
    return os.path.abspath(out)
