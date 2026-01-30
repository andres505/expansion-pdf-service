# expansion/pdf_report.py
from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Image as RLImage,
    Spacer, PageBreak
)
from reportlab.lib.units import cm
import numpy as np
import os
import tempfile

# Pillow (orientación / crop fotos)
try:
    from PIL import Image as PILImage, ImageOps
    _PIL_OK = True
except Exception:
    _PIL_OK = False


# ======================================================
# COLORES / BRAND
# ======================================================
NETO_BLUE   = HexColor("#0B2C4D")
NETO_ORANGE = HexColor("#F37021")
LIGHT_GREY  = HexColor("#F4F4F4")

GREEN_BG = HexColor("#DFF2E1")
GREEN_TX = HexColor("#1E7F43")
YELLOW_BG = HexColor("#FFF4CC")
YELLOW_TX = HexColor("#9A7B00")
RED_BG = HexColor("#FDE2E2")
RED_TX = HexColor("#9B1C1C")


# ======================================================
# UTILIDADES
# ======================================================
def _decision_colors(decision: str):
    d = (decision or "").upper().strip()
    if d == "AVANZAR":
        return GREEN_BG, GREEN_TX
    if d == "EVALUAR":
        return YELLOW_BG, YELLOW_TX
    return RED_BG, RED_TX


def _fmt(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "-"
    if isinstance(val, (int, float)):
        return f"{val:,.0f}".replace(",", ".")
    return str(val)


def _fmt_km(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "-"
    try:
        return f"{float(val):.2f}"
    except Exception:
        return str(val)


def _build_styles():
    styles = getSampleStyleSheet()

    def add(ps):
        if ps.name not in styles.byName:
            styles.add(ps)

    add(ParagraphStyle("NetoTitle", fontSize=22, leading=26, textColor=NETO_BLUE))
    add(ParagraphStyle("NetoSubtitle", fontSize=9.5, leading=12, textColor=NETO_ORANGE))
    add(ParagraphStyle("NetoHeader", fontSize=13.5, leading=16, textColor=NETO_BLUE))
    add(ParagraphStyle("NetoBody", fontSize=9, leading=12))
    add(ParagraphStyle("NetoSmall", fontSize=8.3, leading=11))

    return styles


def _safe_get(d: dict, key: str, default="-"):
    v = d.get(key)
    return v if v not in [None, ""] else default


def _build_tienda_cercana_rows(payload: dict):
    return [
        ["ID tienda", _fmt(payload.get("id_tienda_cercana"))],
        ["Distancia (km)", _fmt_km(payload.get("distancia_tienda_cercana_km"))],
        ["Ventas sin impuestos", _fmt(payload.get("tienda_cercanaVenta_Sin_Impuestos"))],
        ["Transacciones", _fmt(payload.get("tienda_cercanaTransacciones"))],
        ["Ticket promedio", _fmt(payload.get("tienda_cercanaTicket_Promedio"))],
        ["Prom. monto sin imp.", _fmt(payload.get("tienda_cercanaProm_Monto_Sin_Imp"))],
    ]


def _logo_flowable(logo_path: str) -> RLImage:
    logo = RLImage(logo_path)
    logo.drawHeight = 1.2 * cm
    logo.drawWidth = 4.2 * cm
    logo.hAlign = "LEFT"
    return logo


def _prep_image_for_box(path: str, box_w: float, box_h: float):
    if not (_PIL_OK and path and os.path.exists(path)):
        return path

    im = PILImage.open(path)
    im = ImageOps.exif_transpose(im)
    im = im.convert("RGB")

    target_ratio = box_w / box_h
    w, h = im.size
    img_ratio = w / h

    if img_ratio > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        im = im.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        im = im.crop((0, top, w, top + new_h))

    out_w = int((box_w / cm) * 220)
    out_h = int((box_h / cm) * 220)
    im = im.resize((out_w, out_h), PILImage.LANCZOS)

    fd, tmp = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    im.save(tmp, "JPEG", quality=92)
    return tmp


def _img_or_placeholder(path, w, h, text):
    if path and os.path.exists(path):
        p = _prep_image_for_box(path, w, h)
        return RLImage(p, w, h)

    t = Table([[Paragraph(text, getSampleStyleSheet()["BodyText"])]],
              colWidths=[w], rowHeights=[h])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIGHT_GREY),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def _build_counts_table(counts: dict):
    c = counts or {}
    comp = c.get("3B", 0) + c.get("AURRERA", 0) + c.get("OXXO", 0) + c.get("ABARROTES", 0)

    data = [
        ["Categoría", "Cantidad"],
        ["Competencias directas", str(comp)],
        ["Tiendas 3B", str(c.get("3B", 0))],
        ["Aurrera", str(c.get("AURRERA", 0))],
        ["OXXO", str(c.get("OXXO", 0))],
        ["Abarrotes", str(c.get("ABARROTES", 0))],
        ["Generadores comerciales", str(c.get("GENERADOR_COMERCIAL", 0))],
        ["Escuelas", str(c.get("ESCUELA", 0))],
        ["Iglesias", str(c.get("IGLESIA", 0))],
        ["Otros", str(c.get("OTROS", 0))],
    ]

    t = Table(data, colWidths=[6*cm, 2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("GRID", (0,0), (-1,-1), 0.25, black),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (1,-1), "CENTER"),
    ]))
    return t


def _decision_block(title, d, styles):
    decision = d.get("decision", "-")
    explanation = d.get("explicacion", "-")
    bg, tx = _decision_colors(decision)

    badge = Table([[Paragraph(f"<b>{decision}</b>", styles["NetoBody"])]],
                  colWidths=[7.8*cm], rowHeights=[0.9*cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("TEXTCOLOR", (0,0), (-1,-1), tx),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
    ]))

    return Table([
        [Paragraph(f"<b>{title}</b>", styles["NetoBody"])],
        [badge],
        [Paragraph(explanation, styles["NetoSmall"])]
    ], colWidths=[7.8*cm])


# ======================================================
# FUNCIÓN PRINCIPAL
# ======================================================
def generate_expansion_pdf(
    *,
    payload: dict,
    decision_modelo_1: dict,
    decision_modelo_2: dict,
    output_path: str,
    logo_path: str,
    map_image_path: str,
    poi_counts: dict,
    site_image_path: str,
):
    styles = _build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.6*cm,
        rightMargin=1.6*cm,
        topMargin=1.2*cm,
        bottomMargin=1.2*cm,
    )

    story = []

    # HEADER
    story.append(Table([
        [_logo_flowable(logo_path),
         Paragraph("Evaluación de sitio – Expansión NETO", styles["NetoTitle"])]
    ], colWidths=[5*cm, 12*cm]))

    story.append(Paragraph(
        f"<b>Folio:</b> {payload.get('id_ubicacion','-')} &nbsp;&nbsp; "
        f"<b>Región:</b> {payload.get('region','-')} &nbsp;&nbsp; "
        f"<b>Estado:</b> {payload.get('estado','-')}",
        styles["NetoSubtitle"]
    ))

    story.append(Spacer(1, 12))

    # MAPA + CONTEOS
    story.append(Paragraph("Mapa y entorno comercial", styles["NetoHeader"]))

    MAP_W, MAP_H = 9.6*cm, 9.6*cm
    RIGHT_W = 8.0*cm

    story.append(Table([
        [_img_or_placeholder(map_image_path, MAP_W, MAP_H, "MAPA"),
         Spacer(1,1),
         _build_counts_table(poi_counts)]
    ], colWidths=[MAP_W, 0.6*cm, RIGHT_W]))

    story.append(Spacer(1, 14))

    # FOTO + DECISIONES
    story.append(Paragraph("Evaluación del sitio", styles["NetoHeader"]))

    story.append(Table([
        [_img_or_placeholder(site_image_path, MAP_W, 6.2*cm, "FOTO DEL SITIO"),
         Spacer(1,1),
         Table([
             [_decision_block("Decisión modelo 1", decision_modelo_1, styles)],
             [Spacer(1,8)],
             [_decision_block("Decisión modelo 2", decision_modelo_2, styles)],
         ])]
    ], colWidths=[MAP_W, 0.6*cm, RIGHT_W]))

    doc.build(story)
