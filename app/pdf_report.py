from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Image as RLImage, Spacer, PageBreak
)
from reportlab.lib.units import cm
import numpy as np
import os
import tempfile

# ======================================================
# BRAND
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
# HELPERS
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
    try:
        return f"{float(val):.2f}"
    except Exception:
        return "-"


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


def _logo_flowable(path, max_w=4.2*cm, max_h=1.2*cm):
    if not path or not os.path.exists(path):
        return Table([["LOGO"]], colWidths=[max_w], rowHeights=[max_h])

    img = RLImage(path)
    scale = min(max_w / img.imageWidth, max_h / img.imageHeight)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale
    return img


def _decision_block(title, d, styles):
    decision = d.get("decision", "-")
    explanation = d.get("explicacion", "-")

    bg, tx = _decision_colors(decision)

    badge = Table(
        [[Paragraph(f"<b>{decision}</b>", styles["NetoBody"])]],
        colWidths=[8.0 * cm],
        rowHeights=[0.9 * cm]
    )
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
        colWidths=[8.0 * cm]
    )


def _img_or_placeholder(path, w, h, text):
    if path and os.path.exists(path):
        img = RLImage(path, width=w, height=h)
        img.hAlign = "LEFT"
        return img

    return Table(
        [[Paragraph(text, getSampleStyleSheet()["BodyText"])]],
        colWidths=[w],
        rowHeights=[h],
        style=[
            ("BACKGROUND", (0,0), (-1,-1), LIGHT_GREY),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]
    )


def _build_counts_table(counts):
    counts = counts or {}
    c3b = int(counts.get("3B", 0))
    cau = int(counts.get("AURRERA", 0))
    cox = int(counts.get("OXXO", 0))
    cab = int(counts.get("ABARROTES", 0))

    data = [
        ["Categoría", "Cantidad"],
        ["Competencias directas", str(c3b + cau + cox + cab)],
        ["Tiendas 3B", c3b],
        ["Aurrera", cau],
        ["OXXO", cox],
        ["Abarrotes", cab],
        ["Generadores comerciales", counts.get("GENERADOR_COMERCIAL", 0)],
        ["Escuelas", counts.get("ESCUELA", 0)],
        ["Iglesias", counts.get("IGLESIA", 0)],
        ["Otros", counts.get("OTROS", 0)],
    ]

    t = Table(data, colWidths=[6*cm, 2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("GRID", (0,0), (-1,-1), 0.25, HexColor("#666")),
        ("ALIGN", (1,1), (1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    return t


# ======================================================
# MAIN PDF
# ======================================================
def generate_expansion_pdf(
    *,
    payload: dict,
    decision_modelo_1: dict,
    decision_modelo_2: dict,
    map_image_buf,
    poi_counts: dict,
    site_image_path: str | None,
    logo_path: str,
    output_path: str,
):
    styles = _build_styles()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(map_image_buf.getvalue())
        map_img_path = f.name

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.6*cm,
        rightMargin=1.6*cm,
        topMargin=1.2*cm,
        bottomMargin=1.2*cm
    )

    story = []

    # ================= HEADER =================
    logo = _logo_flowable(logo_path)
    title = Paragraph("Evaluación de sitio – Expansión NETO", styles["NetoTitle"])

    header = Table([[logo, title]], colWidths=[4.5*cm, 12.7*cm])
    header.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story += [header]

    subtitle = Paragraph(
        f"""
        <b>Folio:</b> {payload.get("id_ubicacion","-")} &nbsp;&nbsp;
        <b>Región:</b> {payload.get("region","-")} &nbsp;&nbsp;
        <b>Estado:</b> {payload.get("estado","-")}<br/>
        <b>Ubicación en cuadra:</b> {payload.get("ubicacion_en_manzana","-")}
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <b>Tipo de adquisición:</b> {payload.get("tipo_adquisicion","-")}
        &nbsp;&nbsp;|&nbsp;&nbsp;
        <b>Tipo:</b> {payload.get("tipo_sitio","-")}
        """,
        styles["NetoSubtitle"]
    )

    story += [subtitle, Spacer(1, 6)]
    story += [Table([[""]], colWidths=[17.2*cm], rowHeights=[0.22*cm],
                    style=[("BACKGROUND", (0,0), (-1,-1), NETO_ORANGE)])]
    story += [Spacer(1, 14)]

    # ================= MAPA =================
    story.append(Paragraph("Mapa y entorno comercial", styles["NetoHeader"]))

    MAP_W = 9.6 * cm
    MAP_H = 9.6 * cm

    map_img = RLImage(map_img_path, width=MAP_W, height=MAP_H)
    counts_tbl = _build_counts_table(poi_counts)

    story.append(Table(
        [[map_img, Spacer(1,1), counts_tbl]],
        colWidths=[MAP_W, 0.6*cm, 8.0*cm],
        style=[("VALIGN", (0,0), (-1,-1), "TOP")]
    ))

    story.append(Spacer(1, 14))

    # ================= EVALUACIÓN DEL SITIO =================
    story.append(Paragraph("Evaluación del sitio", styles["NetoHeader"]))

    PHOTO_W = MAP_W
    PHOTO_H = 6.5 * cm

    photo = _img_or_placeholder(site_image_path, PHOTO_W, PHOTO_H, "FOTO DEL SITIO")

    decisions_stack = Table(
        [
            [_decision_block("Decisión modelo 1", decision_modelo_1, styles)],
            [Spacer(1, 10)],
            [_decision_block("Decisión modelo 2", decision_modelo_2, styles)],
        ],
        colWidths=[8.0*cm]
    )

    story.append(Table(
        [[photo, Spacer(1,1), decisions_stack]],
        colWidths=[PHOTO_W, 0.6*cm, 8.0*cm],
        style=[("VALIGN", (0,0), (-1,-1), "TOP")]
    ))

    doc.build(story)
