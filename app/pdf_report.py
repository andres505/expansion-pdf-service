from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Image,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
import json
from io import BytesIO


def generate_basic_pdf(
    *,
    payload: dict,
    site_image_path: str | None,
    map_image_buf: BytesIO,
    map_counts: dict,
    output_path: str,
):
    """
    Genera un PDF sencillo que incluye:
    - Payload (JSON pretty)
    - Imagen del sitio (si existe)
    - Mapa de entorno comercial (PNG en memoria)
    - Conteos por categoría
    """

    styles = getSampleStyleSheet()
    story = []

    # =====================================================
    # TÍTULO
    # =====================================================
    story.append(Paragraph("Evaluación de Sitio – PDF Test", styles["Title"]))
    story.append(Spacer(1, 12))

    # =====================================================
    # PAYLOAD (JSON)
    # =====================================================
    story.append(Paragraph("Payload recibido", styles["Heading2"]))
    story.append(Spacer(1, 6))

    pretty_payload = json.dumps(payload, indent=2, ensure_ascii=False)
    story.append(
        Paragraph(
            f"<pre>{pretty_payload}</pre>",
            styles["Code"],
        )
    )
    story.append(Spacer(1, 16))

    # =====================================================
    # IMAGEN DEL SITIO (OPCIONAL)
    # =====================================================
    if site_image_path:
        story.append(Paragraph("Imagen del sitio", styles["Heading2"]))
        story.append(Spacer(1, 6))

        img = Image(site_image_path, width=14 * cm, height=9 * cm)
        img.hAlign = "CENTER"
        story.append(img)
        story.append(Spacer(1, 16))

    # =====================================================
    # MAPA DE ENTORNO
    # =====================================================
    story.append(Paragraph("Mapa de entorno comercial", styles["Heading2"]))
    story.append(Spacer(1, 6))

    map_img = Image(map_image_buf, width=16 * cm, height=16 * cm)
    map_img.hAlign = "CENTER"
    story.append(map_img)
    story.append(Spacer(1, 16))

    # =====================================================
    # CONTEOS
    # =====================================================
    story.append(Paragraph("Conteo de puntos por categoría", styles["Heading2"]))
    story.append(Spacer(1, 6))

    if map_counts:
        table_data = [["Categoría", "Cantidad"]]
        for k, v in sorted(map_counts.items(), key=lambda x: x[0]):
            table_data.append([k, str(v)])

        table = Table(table_data, colWidths=[8 * cm, 4 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No se encontraron puntos en el entorno.", styles["Normal"]))

    # =====================================================
    # BUILD PDF
    # =====================================================
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    doc.build(story)
