# app/main.py
from fastapi import FastAPI, UploadFile, File, Form
import json
import os
import tempfile

from app.pdf_report import generate_basic_pdf

app = FastAPI(title="Expansion PDF Service – MVP")


@app.post("/generate-pdf")
async def generate_pdf(
    payload_flat: str = Form(...),
    site_image: UploadFile | None = File(None),
):
    payload = json.loads(payload_flat)

    folio = payload.get("id_ubicacion", "TEST")

    with tempfile.TemporaryDirectory() as tmp:
        # Guardar imagen
        image_path = None
        if site_image:
            image_path = os.path.join(tmp, site_image.filename)
            with open(image_path, "wb") as f:
                f.write(await site_image.read())

        # PDF
        pdf_path = os.path.join(tmp, f"test_{folio}.pdf")

        generate_basic_pdf(
            payload=payload,
            site_image_path=image_path,
            output_path=pdf_path,
        )

        return {
            "status": "ok",
            "folio": folio,
            "pdf_generated": True
        }
