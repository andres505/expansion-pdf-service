from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from io import BytesIO
import json
import os
import tempfile

from app.places_map import generate_places_map_in_memory
from app.pdf_report import generate_expansion_pdf

app = FastAPI(title="Expansion PDF Service")


@app.post("/generate-pdf")
async def generate_pdf(
    payload_flat: str = Form(...),
    places_csv: UploadFile = File(...),
    site_image: UploadFile | None = File(None),
):
    """
    Endpoint principal:
    - payload_flat: JSON string
    - places_csv: CSV Google Places
    - site_image: foto del sitio (opcional)
    - devuelve PDF binario
    """

    # -------------------------------
    # Parse payload
    # -------------------------------
    payload = json.loads(payload_flat)
    folio = payload.get("id_ubicacion", "TEST")

    # decisiones (por ahora dummy o pasadas desde n8n luego)
    decision_modelo_1 = payload.get("decision_modelo_1", {
        "decision": "-",
        "explicacion": "-"
    })
    decision_modelo_2 = payload.get("decision_modelo_2", {
        "decision": "-",
        "explicacion": "-"
    })

    with tempfile.TemporaryDirectory() as tmp:
        # -------------------------------
        # Guardar CSV temporal
        # -------------------------------
        csv_path = os.path.join(tmp, "places.csv")
        with open(csv_path, "wb") as f:
            f.write(await places_csv.read())

        # -------------------------------
        # Generar mapa + conteos
        # -------------------------------
        map_buf, counts = generate_places_map_in_memory(
            csv_path=csv_path
        )

        # -------------------------------
        # Guardar imagen del sitio (opcional)
        # -------------------------------
        site_image_path = None
        if site_image:
            site_image_path = os.path.join(tmp, site_image.filename)
            with open(site_image_path, "wb") as f:
                f.write(await site_image.read())

        # -------------------------------
        # Generar PDF
        # -------------------------------
        pdf_path = os.path.join(tmp, f"evaluacion_{folio}.pdf")

        generate_expansion_pdf(
            payload=payload,
            decision_modelo_1=decision_modelo_1,
            decision_modelo_2=decision_modelo_2,
            map_image_buf=map_buf,
            poi_counts=counts,
            site_image_path=site_image_path,
            logo_path="app/assets/logo_neto.png",
            output_path=pdf_path,
        )

        # -------------------------------
        # Leer PDF a memoria
        # -------------------------------
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    # -------------------------------
    # Respuesta binaria
    # -------------------------------
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="evaluacion_{folio}.pdf"'
        },
    )
