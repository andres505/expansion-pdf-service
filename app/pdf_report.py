# expansion/pdf_report.py
from __future__ import annotations

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Image as RLImage,
    Spacer, PageBreak, KeepTogether
)
from reportlab.lib.units import cm
import numpy as np
import os
import tempfile

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
        # si es "km" o algo similar, lo pasas ya formateado desde afuera
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
        spaceAfter=6
    ))
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
        ["ID tienda", _fmt(_safe_get(payload, "id_tienda_cercana", default="-"))],
        ["Distancia (km)", _fmt_km(_safe_get(payload, "distancia_tienda_cercana_km", default=np.nan))],
        ["Ventas sin impuestos", _fmt(_safe_get(payload, "tienda_cercanaVenta_Sin_Impuestos", default=np.nan))],
        ["Transacciones", _fmt(_safe_get(payload, "tienda_cercanaTransacciones", default=np.nan))],
        ["Ticket promedio", _fmt(_safe_get(payload, "tienda_cercanaTicket_Promedio", default=np.nan))],
        ["Prom. monto sin imp.", _fmt(_safe_get(payload, "tienda_cercanaProm_Monto_Sin_Imp", default=np.nan))],
    ]


def _logo_flowable(logo_path: str, max_w_cm=4.2, max_h_cm=1.2) -> RLImage:
    """
    Usa el PNG tal cual, solo lo escala a un max_w/max_h.
    """
    logo = RLImage(logo_path)
    max_w = max_w_cm * cm
    max_h = max_h_cm * cm

    iw, ih = logo.imageWidth, logo.imageHeight
    if iw <= 0 or ih <= 0:
        # fallback
        logo.drawWidth = max_w
        logo.drawHeight = max_h
        return logo

    scale = min(max_w / iw, max_h / ih)
    logo.drawWidth = iw * scale
    logo.drawHeight = ih * scale
    logo.hAlign = "LEFT"
    return logo


def _prep_image_for_box(path: str, box_w: float, box_h: float, mode: str = "cover") -> str:
    """
    Devuelve un archivo temporal (JPEG) ya orientado y recortado para llenar/encajar el box.
    Si Pillow no está, regresa el path original.
    """
    if (not path) or (not os.path.exists(path)) or (not _PIL_OK):
        return path

    im = PILImage.open(path)
    im = ImageOps.exif_transpose(im)

    # target ratio
    target_ratio = box_w / box_h if box_h else 1.0
    w, h = im.size
    img_ratio = w / h if h else target_ratio

    # Convertir a RGB (fotos de sitio son normales; si traen alpha, lo ponemos blanco)
    if im.mode in ("RGBA", "LA"):
        bg = PILImage.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")

    if mode == "cover":
        # crop centrado
        if img_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = max((w - new_w) // 2, 0)
            im = im.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = max((h - new_h) // 2, 0)
            im = im.crop((0, top, w, top + new_h))

    # export tamaño decente para PDF
    out_w_px = max(int((box_w / cm) * 220), 1200)
    out_h_px = max(int((box_h / cm) * 220), 900)
    im = im.resize((out_w_px, out_h_px), PILImage.LANCZOS)

    fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    im.save(tmp_path, "JPEG", quality=92, optimize=True)
    return tmp_path


def _img_or_placeholder(path: str | None, box_w: float, box_h: float, placeholder_text: str):
    """
    Regresa un flowable Image si existe el path, o un bloque gris con texto si no.
    """
    if path and os.path.exists(path):
        p = _prep_image_for_box(path, box_w, box_h, mode="cover")
        img = RLImage(p, width=box_w, height=box_h)
        img.hAlign = "LEFT"
        return img

    # placeholder
    ph = Table([[Paragraph(placeholder_text, getSampleStyleSheet()["BodyText"])]],
               colWidths=[box_w], rowHeights=[box_h])
    ph.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GREY),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 0), (-1, -1), NETO_BLUE),
    ]))
    return ph


def _build_counts_table(counts: dict | None):
    """
    counts viene de places_map.py (grupos):
      NETO, 3B, AURRERA, OXXO, ABARROTES, GENERADOR_COMERCIAL, ESCUELA, IGLESIA, OTROS, ...
    """
    counts = counts or {}
    c_3b = int(counts.get("3B", 0))
    c_au = int(counts.get("AURRERA", 0))
    c_ox = int(counts.get("OXXO", 0))
    c_ab = int(counts.get("ABARROTES", 0))
    comp_directas = c_3b + c_au + c_ox + c_ab

    data = [
        ["Categoría", "Cantidad"],
        ["Competencias directas", str(comp_directas)],
        ["Tiendas 3B", str(c_3b)],
        ["Aurrera", str(c_au)],
        ["OXXO", str(c_ox)],
        ["Abarrotes", str(c_ab)],
        ["Generadores comerciales", str(int(counts.get("GENERADOR_COMERCIAL", 0)))],
        ["Escuelas", str(int(counts.get("ESCUELA", 0)))],
        ["Iglesias", str(int(counts.get("IGLESIA", 0)))],
        ["Otros", str(int(counts.get("OTROS", 0)))],
    ]

    t = Table(data, colWidths=[6.0*cm, 2.0*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("ALIGN", (1,1), (1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.25, HexColor("#666666")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    return t


def _decision_block(title: str, d: dict, styles):
    decision = (d or {}).get("decision", "-")
    explanation = (d or {}).get("explicacion", "-")

    bg, tx = _decision_colors(decision)

    head = Paragraph(f"<b>{title}</b>", styles["NetoBody"])

    badge = Table([[Paragraph(f"<b>{decision}</b>", styles["NetoBody"])]], colWidths=[7.8*cm], rowHeights=[0.9*cm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), bg),
        ("TEXTCOLOR", (0,0), (-1,-1), tx),
        ("ALIGN", (0,0), (-1,-1), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
    ]))

    body = Paragraph(explanation, styles["NetoSmall"])

    box = Table([[head], [badge], [body]], colWidths=[7.8*cm])
    box.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    return box


# ======================================================
# FUNCIÓN PRINCIPAL (2 páginas verticales)
# ======================================================
def generate_expansion_pdf(
    *,
    payload: dict,
    df_benchmark,
    decision_modelo_1: dict,
    decision_modelo_2: dict,
    output_path: str,
    logo_path: str,

    # nuevos inputs
    map_image_path: str | None = None,     # PNG generado en Colab (places_map.py)
    poi_counts: dict | None = None,        # conteos de places_map.py
    site_image_path: str | None = None,    # foto celular del sitio

    ubicacion_en_cuadra: str | None = None,  # "Esquina" / "Media cuadra"
    tipo_adquisicion: str | None = None,     # "Renta" / "Venta"
    tipo_inmueble: str | None = None,        # "Local" / "Terreno"

    # hoja 2 opcional: imagen genérica neto
    neto_generic_image_path: str | None = None
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

    # ================= HEADER (reusable) =================
    def build_header():
        # Logo escalado (ajusta aquí si quieres más grande)
        logo = _logo_flowable(logo_path, max_w_cm=4.2, max_h_cm=1.2)

        title = Paragraph("Evaluación de sitio – Expansión NETO", styles["NetoTitle"])

        # nuevos campos (si no vienen por args, los intenta del payload)
        uc = ubicacion_en_cuadra or _safe_get(payload, "ubicacion_en_cuadra", "ubicacion_cuadra")
        ta = tipo_adquisicion or _safe_get(payload, "tipo_adquisicion", "tipo_adq")
        ti = tipo_inmueble or _safe_get(payload, "tipo_inmueble", "tipo")

        subtitle = Paragraph(
            f"""
            <b><u>Folio:</u></b> {payload.get("id_ubicacion","-")} &nbsp;&nbsp;
            <b><u>Región:</u></b> {payload.get("region","-")} &nbsp;&nbsp;
            <b><u>Estado:</u></b> {payload.get("estado","-")}<br/>
            <b><u>Dirección:</u></b> {payload.get("direccion","-")}<br/>
            <b><u>Ubicación en cuadra:</u></b> {uc} &nbsp;&nbsp;|&nbsp;&nbsp;
            <b><u>Tipo de adquisición:</u></b> {ta} &nbsp;&nbsp;|&nbsp;&nbsp;
            <b><u>Tipo:</u></b> {ti}
            """,
            styles["NetoSubtitle"]
        )

        # Header: logo + título (alineado izquierda)
        header = Table([[logo, title]], colWidths=[4.8 * cm, 12.4 * cm])
        header.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ]))

        bar = Table([[""]], colWidths=[17.2 * cm], rowHeights=[0.22 * cm])
        bar.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), NETO_ORANGE)]))

        return [header, subtitle, Spacer(1, 6), bar, Spacer(1, 14)]

    # ================= PAGE 1 =================
    story += build_header()

    story.append(Paragraph("Mapa y entorno comercial", styles["NetoHeader"]))

    # Layout widths (contenidos) dentro del área util
    MAP_W = 9.6 * cm
    MAP_H = 9.6 * cm
    RIGHT_W = 8.0 * cm
    GAP_W = 0.6 * cm

    map_flow = _img_or_placeholder(map_image_path, MAP_W, MAP_H, "MAPA")
    counts_table = _build_counts_table(poi_counts)

    row1 = Table([[map_flow, Spacer(1,1), counts_table]], colWidths=[MAP_W, GAP_W, RIGHT_W])
    row1.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(row1)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Evaluación del sitio", styles["NetoHeader"]))

    PHOTO_W = MAP_W
    PHOTO_H = 6.2 * cm

    photo_flow = _img_or_placeholder(site_image_path, PHOTO_W, PHOTO_H, "FOTO DEL SITIO")

    dec1 = _decision_block("Decisión modelo 1", decision_modelo_1, styles)
    dec2 = _decision_block("Decisión modelo 2", decision_modelo_2, styles)

    dec_stack = Table([[dec1], [Spacer(1, 10)], [dec2]], colWidths=[RIGHT_W])
    dec_stack.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    row2 = Table([[photo_flow, Spacer(1,1), dec_stack]], colWidths=[PHOTO_W, GAP_W, RIGHT_W])
    row2.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))
    story.append(row2)

    # ================= PAGE 2 =================
    story.append(PageBreak())
    story += build_header()

    story.append(Paragraph("Tienda NETO más cercana", styles["NetoHeader"]))

    tienda_rows = [["Variable", "Valor"]] + _build_tienda_cercana_rows(payload)
    tienda_table = Table(tienda_rows, colWidths=[8.0 * cm, 9.2 * cm])
    tienda_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("GRID", (0,0), (-1,-1), 0.25, HexColor("#666666")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))

    # bloque superior hoja 2: imagen neto opcional + tabla tienda cercana
    if neto_generic_image_path:
        IMG2_W = 7.8 * cm
        IMG2_H = 5.0 * cm
        img2 = _img_or_placeholder(neto_generic_image_path, IMG2_W, IMG2_H, "IMAGEN NETO")
        top2 = Table([[img2, Spacer(1,1), tienda_table]], colWidths=[IMG2_W, GAP_W, 17.2*cm - IMG2_W - GAP_W])
        top2.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 0),
            ("TOPPADDING", (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        story.append(top2)
    else:
        story.append(tienda_table)

    story.append(Spacer(1, 14))

    story.append(Paragraph("Comparativo sitio vs benchmark regional", styles["NetoHeader"]))

    # tabla benchmark (full width)
    data = [["Variable", "Benchmark", "Sitio", "Δ vs benchmark"]]
    for _, r in df_benchmark.iterrows():
        delta = r.get("Δ vs benchmark (%)", np.nan)
        if delta == delta:
            try:
                delta_str = f"{int(delta)}%"
            except Exception:
                delta_str = f"{delta}%"
        else:
            delta_str = "-"
        data.append([
            str(r.get("Variable", "")),
            _fmt(r.get("Benchmark regional", np.nan)),
            _fmt(r.get("Sitio", np.nan)),  # ✅ ESTA ES LA CORRECTA
            delta_str
        ])


    bench = Table(data, colWidths=[7.2*cm, 3.6*cm, 3.6*cm, 2.8*cm])
    bench.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), NETO_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("GRID", (0,0), (-1,-1), 0.25, HexColor("#666666")),
        ("PADDING", (0,0), (-1,-1), 6),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
    ]))
    story.append(bench)

    doc.build(story)
