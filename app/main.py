from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from io import BytesIO
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
        # --------------------
        # Imagen
        # --------------------
        image_path = None
        if site_image:
            image_path = os.path.join(tmp, site_image.filename)
            with open(image_path, "wb") as f:
                f.write(await site_image.read())

        # --------------------
        # PDF
        # --------------------
        pdf_path = os.path.join(tmp, f"evaluacion_{folio}.pdf")

        generate_basic_pdf(
            payload=payload,
            site_image_path=image_path,
            output_path=pdf_path,
        )

        # --------------------
        # Leer PDF a memoria
        # --------------------
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    # 👈 Aquí el temp dir YA se borró, pero el PDF vive en memoria

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="evaluacion_{folio}.pdf"'
        },
    )
