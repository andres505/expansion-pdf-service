from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Image as RLImage, Spacer, PageBreak
)
from reportlab.lib.units import cm
from io import BytesIO
from pathlib import Path
import numpy as np
import os

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
    return str(candidate) if candidate.exists() else None


# ======================================================
# BRAND
# ======================================================
NETO_BLUE = HexColor("#0B2C4D")
NETO_ORANGE = HexColor("#F37021")
LIGHT_GREY = HexColor("#F4F4F4")

GREEN_BG = HexColor("#DFF2E1")
GREEN_TX = HexColor("#1E7F43")
YELLOW_BG = HexColor("#FFF4CC")
YELLOW_TX = HexColor("#9A7B00")
RED_BG = HexColor("#FDE2E2")
RED_TX = HexColor("#9B1C1C")


# ======================================================
# HELPERS
# ======================================================
def _build_styles():
    styles = getSampleStyleSheet()

    def add(ps):
        if ps.name not in styles.byName:
            styles.add(ps)

    add(ParagraphStyle(
        "NetoTitle",
        fontSize=22,
        leading=26,
        textColor=NETO_BLUE
    ))
    add(ParagraphStyle(
        "NetoSubtitle",
        fontSize=9.5,
        leading=12,
        textColor=NETO_ORANGE
    ))
    add(ParagraphStyle(
        "NetoHeader",
        fontSize=13.5,
        leading=16,
        textColor=NETO_BLUE,
        spaceAfter=8
    ))
    add(ParagraphStyle("NetoBody", fontSize=9, leading=12))
    add(ParagraphStyle("NetoSmall", fontSize=8.3, leading=11))

    return styles


def _fmt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    if isinstance(v, (int, float)):
        return f"{v:,.0f}".replace(",", ".")
    return str(v)


def _fmt_km(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "-"


def _img_from_buf(buf: BytesIO | None, w, h, label):
    if buf:
        buf.seek(0)
        return RLImage(buf, width=w, height=h)
    return Table([[label]], colWidths=[w], rowHeights=[h],
                 style=[("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])


def _img_from_path(path: str | None, w, h, label):
    if path and os.path.exists(path):
        return RLImage(path, width=w, height=h)
    return Table([[label]], colWidths=[w], rowHeights=[h],
                 style=[("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])


def _decision_colors(decision: str):
    d = (decision or "").upper()
    if d == "AVANZAR":
        return GREEN_BG, GREEN_TX
    if d == "EVALUAR":
        return YELLOW_BG, YELLOW_TX
    return RED_BG, RED_TX


def _decision_block(title: str, d: dict, styles):
    decision = d.get("decision", "-")
    explanation = d.get("explicacion", "-")
    bg, tx = _decision_colors(decision)

    badge = Table([[decision]], colWidths=[7.8 * cm], rowHeights=[0.9 * cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("TEXTCOLOR", (0, 0), (-1, -1), tx),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))

    return Table([
        [Paragraph(f"<b>{title}</b>", styles["NetoBody"])],
        [badge],
        [Paragraph(explanation, styles["NetoSmall"])]
    ], colWidths=[7.8 * cm])


def _counts_table(counts: dict | None):
    counts = counts or {}
    comp = sum(int(counts.get(k, 0)) for k in ["3B", "AURRERA", "OXXO", "ABARROTES"])

    data = [
        ["Categoría", "Cantidad"],
        ["Competencia directa", comp],
        ["Tiendas 3B", counts.get("3B", 0)],
        ["Aurrera", counts.get("AURRERA", 0)],
        ["OXXO", counts.get("OXXO", 0)],
        ["Abarrotes", counts.get("ABARROTES", 0)],
        ["Generadores comerciales", counts.get("GENERADOR_COMERCIAL", 0)],
        ["Escuelas", counts.get("ESCUELA", 0)],
        ["Iglesias", counts.get("IGLESIA", 0)],
        ["Otros", counts.get("OTROS", 0)],
    ]

    t = Table(data, colWidths=[6 * cm, 2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NETO_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("GRID", (0, 0), (-1, -1), 0.25, black),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    return t


def _tienda_cercana_table(payload: dict):
    rows = [
        ["ID tienda", _fmt(payload.get("id_tienda_cercana"))],
        ["Distancia (km)", _fmt_km(payload.get("distancia_tienda_cercana_km"))],
        ["Ventas sin impuestos", _fmt(payload.get("tienda_cercanaVenta_Sin_Impuestos"))],
        ["Transacciones", _fmt(payload.get("tienda_cercanaTransacciones"))],
        ["Ticket promedio", _fmt(payload.get("tienda_cercanaTicket_Promedio"))],
        ["Prom. monto sin imp.", _fmt(payload.get("tienda_cercanaProm_Monto_Sin_Imp"))],
    ]

    t = Table([["Variable", "Valor"]] + rows, colWidths=[8 * cm, 9.2 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NETO_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("GRID", (0, 0), (-1, -1), 0.25, black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 6),
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
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    story = []

    # ================= HEADER =================
    logo = _img_from_path(_resolve_path(logo_path), 4.2 * cm, 1.2 * cm, "LOGO")
    title = Paragraph("Evaluación de sitio – Expansión NETO", styles["NetoTitle"])

    subtitle = Paragraph(
        f"""
        <b>Folio:</b> {payload.get("id_ubicacion","-")} &nbsp;&nbsp;
        <b>Región:</b> {payload.get("region","-")} &nbsp;&nbsp;
        <b>Estado:</b> {payload.get("estado","-")}<br/>
        <b>Dirección:</b> {payload.get("direccion","-")}
        """,
        styles["NetoSubtitle"]
    )

    header = Table([[logo, title]], colWidths=[4.8 * cm, 12.4 * cm])
    bar = Table([[""]], colWidths=[17.2 * cm], rowHeights=[0.22 * cm],
                style=[("BACKGROUND", (0, 0), (-1, -1), NETO_ORANGE)])

    story += [header, Spacer(1, 4), subtitle, Spacer(1, 8), bar, Spacer(1, 16)]

    # ================= MAP =================
    story.append(Paragraph("Mapa y entorno comercial", styles["NetoHeader"]))

    MAP_W, MAP_H = 9.6 * cm, 9.6 * cm
    RIGHT_W = 8.0 * cm

    row_map = Table(
        [[_img_from_buf(map_image_buf, MAP_W, MAP_H, "MAPA"),
          _counts_table(poi_counts)]],
        colWidths=[MAP_W, RIGHT_W]
    )
    story += [row_map, Spacer(1, 18)]

    # ================= SITE IMAGE + DECISIONS =================
    story.append(Paragraph("Evaluación del sitio", styles["NetoHeader"]))

    photo = _img_from_path(site_image_path, MAP_W, 6.2 * cm, "FOTO DEL SITIO")

    decisions = Table([
        [_decision_block("Decisión modelo 1", decision_modelo_1, styles)],
        [Spacer(1, 10)],
        [_decision_block("Decisión modelo 2", decision_modelo_2, styles)],
    ], colWidths=[RIGHT_W])

    story.append(Table([[photo, decisions]], colWidths=[MAP_W, RIGHT_W]))

    # ================= PAGE 2 =================
    story.append(PageBreak())
    story += [header, Spacer(1, 8), bar, Spacer(1, 16)]

    story.append(Paragraph("Tienda NETO más cercana", styles["NetoHeader"]))
    story.append(_tienda_cercana_table(payload))

    doc.build(story)
