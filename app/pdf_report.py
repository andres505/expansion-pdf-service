from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Image as RLImage,
    Spacer, PageBreak
)
from reportlab.lib.units import cm
from io import BytesIO
from pathlib import Path
import numpy as np
import os
import tempfile

# Pillow (opcional, solo para foto del sitio)
try:
    from PIL import Image as PILImage, ImageOps
    _PIL_OK = True
except Exception:
    _PIL_OK = False


# ======================================================
# PATHS
# ======================================================
BASE_DIR = Path(__file__).resolve().parent


def _resolve_path(path: str | None) -> str | None:
    if not path:
        return None

    p = Path(path)
    if p.is_absolute() and p.exists():
        return str(p)

    candidate = BASE_DIR / path
    if candidate.exists():
        return str(candidate)

    return None


# ======================================================
# BRAND
# ======================================================
NETO_BLUE = HexColor("#0B2C4D")
NETO_ORANGE = HexColor("#F37021")
LIGHT_GREY = HexColor("#F4F4F4")


# ======================================================
# HELPERS
# ======================================================
def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", ".")
    return str(v)


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "Title",
        fontSize=20,
        leading=24,
        textColor=NETO_BLUE
    ))

    styles.add(ParagraphStyle(
        "Header",
        fontSize=13,
        leading=16,
        textColor=NETO_BLUE,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        "Body",
        fontSize=9,
        leading=12
    ))

    styles.add(ParagraphStyle(
        "Small",
        fontSize=8,
        leading=10
    ))

    return styles


def _img_or_placeholder_from_buf(buf: BytesIO | None, w, h, label):
    if buf:
        buf.seek(0)
        return RLImage(buf, width=w, height=h)

    t = Table([[label]], colWidths=[w], rowHeights=[h])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIGHT_GREY),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def _img_or_placeholder_from_path(path: str | None, w, h, label):
    if path and os.path.exists(path):
        return RLImage(path, width=w, height=h)

    t = Table([[label]], colWidths=[w], rowHeights=[h])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIGHT_GREY),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    return t


def _counts_table(counts: dict | None):
    counts = counts or {}

    data = [
        ["Categoría", "Cantidad"],
        ["Competencias directas",
         sum(int(counts.get(k, 0)) for k in ["3B", "AURRERA", "OXXO", "ABARROTES"])],
        ["Tiendas 3B", counts.get("3B", 0)],
        ["Aurrera", counts.get("AURRERA", 0)],
        ["OXXO", counts.get("OXXO", 0)],
        ["Abarrotes", counts.get("ABARROTES", 0)],
        ["Generadores comerciales", counts.get("GENERADOR_COMERCIAL", 0)],
        ["Escuelas", counts.get("ESCUELA", 0)],
        ["Iglesias", counts.get("IGLESIA", 0)],
        ["Otros", counts.get("OTROS", 0)],
    ]

    t = Table(data, colWidths=[6*cm, 2*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("GRID", (0,0), (-1,-1), 0.25, black),
        ("ALIGN", (1,1), (1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    return t


# ======================================================
# MAIN
# ======================================================
def generate_expansion_pdf(
    *,
    payload: dict,
    decision_modelo_1: dict,
    decision_modelo_2: dict,
    map_image_buf: BytesIO | None,
    poi_counts: dict | None,
    site_image_path: str | None,
    logo_path: str | None,
    output_path: str,
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

    # ================= HEADER =================
    resolved_logo = _resolve_path(logo_path)
    logo = _img_or_placeholder_from_path(
        resolved_logo, 4.2*cm, 1.2*cm, "LOGO"
    )

    title = Paragraph("Evaluación de sitio – Expansión NETO", styles["Title"])

    header = Table([[logo, title]], colWidths=[5*cm, 12*cm])
    header.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
    ]))

    subtitle = Paragraph(
        f"""
        <b>Folio:</b> {payload.get("id_ubicacion","-")} &nbsp;&nbsp;
        <b>Región:</b> {payload.get("region","-")} &nbsp;&nbsp;
        <b>Estado:</b> {payload.get("estado","-")}<br/>
        <b>Lat:</b> {payload.get("lat","-")} &nbsp;&nbsp;
        <b>Lon:</b> {payload.get("longitud","-")}
        """,
        styles["Small"]
    )

    bar = Table([[""]], colWidths=[17*cm], rowHeights=[0.25*cm])
    bar.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), NETO_ORANGE)]))

    story += [header, subtitle, Spacer(1, 6), bar, Spacer(1, 14)]

    # ================= MAP + COUNTS =================
    story.append(Paragraph("Mapa y entorno comercial", styles["Header"]))

    MAP_W = 9.5*cm
    MAP_H = 9.5*cm
    RIGHT_W = 7.5*cm

    map_img = _img_or_placeholder_from_buf(
        map_image_buf, MAP_W, MAP_H, "MAPA"
    )

    counts_tbl = _counts_table(poi_counts)

    row1 = Table([[map_img, counts_tbl]], colWidths=[MAP_W, RIGHT_W])
    row1.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
    ]))

    story += [row1, Spacer(1, 16)]

    # ================= SITE IMAGE =================
    story.append(Paragraph("Imagen del sitio", styles["Header"]))

    site_img = _img_or_placeholder_from_path(
        site_image_path, MAP_W, 6*cm, "FOTO DEL SITIO"
    )

    story += [site_img, Spacer(1, 20)]

    # ================= DECISIONS =================
    story.append(Paragraph("Decisiones de evaluación", styles["Header"]))

    def decision_block(title, d):
        return Table([
            [Paragraph(f"<b>{title}</b>", styles["Body"])],
            [Paragraph(f"<b>{d.get('decision','-')}</b>", styles["Body"])],
            [Paragraph(d.get("explicacion","-"), styles["Small"])],
        ], colWidths=[17*cm])

    story.append(decision_block("Modelo 1", decision_modelo_1))
    story.append(Spacer(1, 10))
    story.append(decision_block("Modelo 2", decision_modelo_2))

    # ================= BUILD =================
    doc.build(story)
