# app/main.py
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
import json
import os
import tempfile
import shutil

from app.places_map import generate_places_map_in_memory
from app.pdf_report import generate_expansion_pdf


app = FastAPI()


@app.post("/generate-pdf")
async def generate_pdf(
    payload: str = Form(...),
    places_csv: UploadFile = File(...),
    site_image: UploadFile = File(...),
):
    """
    Recibe payload + CSV de Google Places + foto del sitio
    Devuelve PDF binario listo para n8n
    """

    # ======================================================
    # 1. Parse payload
    # ======================================================
    payload_dict = json.loads(payload)

    payload_flat = payload_dict.get("payload_flat", {})
    decision_modelo_1 = payload_dict.get("decision_modelo_1", {})
    decision_modelo_2 = payload_dict.get("decision_modelo_2", {})

    # ======================================================
    # 2. Directorio temporal de trabajo
    # ======================================================
    workdir = tempfile.mkdtemp()

    try:
        # --------------------------------------------------
        # Guardar CSV de places
        # --------------------------------------------------
        csv_path = os.path.join(workdir, "places.csv")
        with open(csv_path, "wb") as f:
            shutil.copyfileobj(places_csv.file, f)

        # --------------------------------------------------
        # Guardar imagen del sitio
        # --------------------------------------------------
        site_image_path = os.path.join(workdir, site_image.filename)
        with open(site_image_path, "wb") as f:
            shutil.copyfileobj(site_image.file, f)

        # ======================================================
        # 3. Generar mapa + conteos
        # ======================================================
        map_buf, poi_counts = generate_places_map_in_memory(
            csv_path=csv_path
        )

        map_image_path = os.path.join(workdir, "map.png")
        with open(map_image_path, "wb") as f:
            f.write(map_buf.getvalue())

        # ======================================================
        # 4. Generar PDF
        # ======================================================
        pdf_path = os.path.join(
            workdir,
            f"reporte_expansion_{payload_flat.get('id_ubicacion', 'site')}.pdf"
        )

        logo_path = "assets/logo_neto.png"  # ajusta path real

        generate_expansion_pdf(
            payload=payload_flat,
            decision_modelo_1=decision_modelo_1,
            decision_modelo_2=decision_modelo_2,
            output_path=pdf_path,
            logo_path=logo_path,
            map_image_path=map_image_path,
            poi_counts=poi_counts,
            site_image_path=site_image_path,
        )

        # ======================================================
        # 5. Responder PDF binario
        # ======================================================
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
        )

    finally:
        # Limpieza silenciosa
        try:
            shutil.rmtree(workdir)
        except Exception:
            pass
