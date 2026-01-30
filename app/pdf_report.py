# app/pdf_report.py
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
import json
import os


def generate_basic_pdf(
    *,
    payload: dict,
    site_image_path: str | None,
    output_path: str,
):
    styles = getSampleStyleSheet()
    story = []

    # Título
    story.append(Paragraph("PDF TEST – Payload recibido", styles["Title"]))
    story.append(Spacer(1, 12))

    # Payload como texto
    pretty_payload = json.dumps(payload, indent=2, ensure_ascii=False)
    story.append(Paragraph("<pre>%s</pre>" % pretty_payload, styles["Code"]))
    story.append(Spacer(1, 20))

    # Imagen (si viene)
    if site_image_path and os.path.exists(site_image_path):
        story.append(Paragraph("Imagen del sitio:", styles["Heading2"]))
        story.append(Spacer(1, 8))
        img = Image(site_image_path, width=14 * cm, height=9 * cm)
        img.hAlign = "CENTER"
        story.append(img)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    doc.build(story)
