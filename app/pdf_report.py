from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Image as RLImage, Spacer, PageBreak
)
from reportlab.lib.units import cm
import numpy as np
import os
import tempfile
from io import BytesIO

# Pillow para orientar/cropear fotos de celular
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
    if isinstance(val, (int, float)) and not isinstance(val, bool):
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
    add(ParagraphStyle("NetoHeader", fontSize=13.5, leading=16, textColor=NETO_BLUE, spaceAfter=6))
    add(ParagraphStyle("NetoBody", fontSize=9, leading=12))
    add(ParagraphStyle("NetoSmall", fontSize=8.3, leading=11))

    return styles


def _safe_get(payload: dict, *keys, default="-"):
    for k in keys:
        if k in payload and payload.get(k) not in [None, ""]:
            return payload.get(k)
    return default


def _build_tienda_cercana_rows(payload: dict):
    return [
        ["ID tienda", _fmt(_safe_get(payload, "id_tienda_cercana"))],
        ["Distancia (km)", _fmt_km(_safe_get(payload, "distancia_tienda_cercana_km", default=np.nan))],
        ["Ventas sin impuestos", _fmt(_safe_get(payload, "tienda_cercanaVenta_Sin_Impuestos", default=np.nan))],
        ["Transacciones", _fmt(_safe_get(payload, "tienda_cercanaTransacciones", default=np.nan))],
        ["Ticket promedio", _fmt(_safe_get(payload, "tienda_cercanaTicket_Promedio", default=np.nan))],
        ["Prom. monto sin imp.", _fmt(_safe_get(payload, "tienda_cercanaProm_Monto_Sin_Imp", default=np.nan))],
    ]


def _logo_flowable(logo_path: str, max_w_cm=4.2, max_h_cm=1.2) -> RLImage:
    logo = RLImage(logo_path)
    max_w = max_w_cm * cm
    max_h = max_h_cm * cm
    iw, ih = logo.imageWidth, logo.imageHeight
    scale = min(max_w / iw, max_h / ih)
    logo.drawWidth = iw * scale
    logo.drawHeight = ih * scale
    logo.hAlign = "LEFT"
    return logo


def _prep_image_for_box(path: str, box_w: float, box_h: float) -> str:
    if (not path) or (not os.path.exists(path)) or (not _PIL_OK):
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

    out_w_px = int((box_w / cm) * 220)
    out_h_px = int((box_h / cm) * 220)
    im = im.resize((out_w_px, out_h_px), PILImage.LANCZOS)

    fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    im.save(tmp_path, "JPEG", quality=92, optimize=True)
    return tmp_path


def _img_or_placeholder(path: str | None, box_w: float, box_h: float, text: str):
    if path and os.path.exists(path):
        p = _prep_image_for_box(path, box_w, box_h)
        return RLImage(p, width=box_w, height=box_h)

    ph = Table([[Paragraph(text, getSampleStyleSheet()["BodyText"])]],
               colWidths=[box_w], rowHeights=[box_h])
    ph.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIGHT_GREY),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TEXTCOLOR", (0,0), (-1,-1), NETO_BLUE),
    ]))
    return ph


def _img_from_buf_or_placeholder(buf: BytesIO | None, box_w: float, box_h: float, text: str):
    if buf:
        return RLImage(buf, width=box_w, height=box_h)
    return _img_or_placeholder(None, box_w, box_h, text)


def _build_counts_table(counts: dict | None):
    counts = counts or {}
    comp = sum(int(counts.get(k, 0)) for k in ["3B", "AURRERA", "OXXO", "ABARROTES"])

    data = [
        ["Categoría", "Cantidad"],
        ["Competencias directas", str(comp)],
        ["Tiendas 3B", str(int(counts.get("3B", 0)))],
        ["Aurrera", str(int(counts.get("AURRERA", 0)))],
        ["OXXO", str(int(counts.get("OXXO", 0)))],
        ["Abarrotes", str(int(counts.get("ABARROTES", 0)))],
        ["Generadores comerciales", str(int(counts.get("GENERADOR_COMERCIAL", 0)))],
        ["Escuelas", str(int(counts.get("ESCUELA", 0)))],
        ["Iglesias", str(int(counts.get("IGLESIA", 0)))],
        ["Otros", str(int(counts.get("OTROS", 0)))],
    ]

    t = Table(data, colWidths=[6*cm, 2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("GRID", (0,0), (-1,-1), 0.25, HexColor("#666666")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))
    return t


def _decision_block(title: str, d: dict, styles):
    decision = (d or {}).get("decision", "-")
    explanation = (d or {}).get("explicacion", "-")
    bg, tx = _decision_colors(decision)

    badge = Table([[Paragraph(f"<b>{decision}</b>", styles["NetoBody"])]],
                  colWidths=[7.8*cm], rowHeights=[0.9*cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("TEXTCOLOR", (0,0), (-1,-1), tx),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))

    return Table(
        [
            [Paragraph(f"<b>{title}</b>", styles["NetoBody"])],
            [badge],
            [Paragraph(explanation, styles["NetoSmall"])]
        ],
        colWidths=[7.8*cm]
    )


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

    map_image_buf: BytesIO | None = None,
    poi_counts: dict | None = None,
    site_image_path: str | None = None,

    ubicacion_en_cuadra: str | None = None,
    tipo_adquisicion: str | None = None,
    tipo_inmueble: str | None = None,
):
    styles = _build_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm
    )

    story = []

    # ================= HEADER =================
    logo = _logo_flowable(logo_path)
    title = Paragraph("Evaluación de sitio – Expansión NETO", styles["NetoTitle"])

    header = Table([[logo, title]], colWidths=[4.8 * cm, 12.4 * cm])
    story.append(header)

    subtitle = Paragraph(
        f"""
        <b>Folio:</b> {payload.get("id_ubicacion","-")} &nbsp;&nbsp;
        <b>Región:</b> {payload.get("region","-")} &nbsp;&nbsp;
        <b>Estado:</b> {payload.get("estado","-")}<br/>
        <b>Ubicación en cuadra:</b> {ubicacion_en_cuadra or payload.get("ubicacion_en_manzana","-")} &nbsp;&nbsp;
        <b>Tipo adquisición:</b> {tipo_adquisicion or payload.get("tipo_adquisicion","-")} &nbsp;&nbsp;
        <b>Tipo:</b> {tipo_inmueble or payload.get("tipo_sitio","-")}
        """,
        styles["NetoSubtitle"]
    )
    story.append(subtitle)
    story.append(Spacer(1, 12))

    # ================= PAGE 1 =================
    MAP_W, MAP_H = 9.6 * cm, 9.6 * cm
    RIGHT_W, GAP_W = 8.0 * cm, 0.6 * cm

    map_flow = _img_from_buf_or_placeholder(map_image_buf, MAP_W, MAP_H, "MAPA")
    counts_table = _build_counts_table(poi_counts)

    story.append(Table([[map_flow, Spacer(1,1), counts_table]],
                       colWidths=[MAP_W, GAP_W, RIGHT_W]))

    story.append(Spacer(1, 12))

    PHOTO_W, PHOTO_H = MAP_W, 6.2 * cm
    photo_flow = _img_or_placeholder(site_image_path, PHOTO_W, PHOTO_H, "FOTO DEL SITIO")

    dec1 = _decision_block("Decisión modelo 1", decision_modelo_1, styles)
    dec2 = _decision_block("Decisión modelo 2", decision_modelo_2, styles)

    story.append(Table([[photo_flow, Spacer(1,1), Table([[dec1],[Spacer(1,8)],[dec2]], colWidths=[RIGHT_W])]],
                       colWidths=[PHOTO_W, GAP_W, RIGHT_W]))

    # ================= BUILD =================
    doc.build(story)
