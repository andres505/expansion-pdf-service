from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
import tempfile
import json
import os
from pathlib import Path

from app.places_map import generate_places_map
from app.pdf_report import generate_expansion_pdf

app = FastAPI(title="Expansion PDF Service")

print("=== DEBUG PAYLOAD ===")
print(payload_obj)
print("site_lat raw:", site_lat)
print("site_lon raw:", site_lon)
print("CSV filename:", places_csv.filename)

@app.post("/generate-pdf")
async def generate_pdf(
    # ---------- JSON principal ----------
    payload: str = Form(...),

    # ---------- binarios ----------
    places_csv: UploadFile = File(...),
    site_image: UploadFile | None = File(None),
):
    """
    Recibe:
    - payload (string JSON)
    - places_csv (CSV Google Places)
    - site_image (foto del sitio, opcional)

    Devuelve:
    - PDF binario
    """

    # =====================================================
    # PARSE PAYLOAD
    # =====================================================
    payload_obj = json.loads(payload)

    status = payload_obj.get("status")
    levantamiento_raw = payload_obj.get("levantamiento", "{}")
    payload_flat = payload_obj.get("payload_flat", {})
    decision_modelo_1 = payload_obj.get("decision_modelo_1", {})
    decision_modelo_2 = payload_obj.get("decision_modelo_2", {})

    levantamiento = json.loads(levantamiento_raw)

    # coordenadas del sitio
    site_lat = payload_flat.get("lat") or levantamiento.get("latitud")
    site_lon = payload_flat.get("longitud") or levantamiento.get("longitud")

    # =====================================================
    # FILESYSTEM TEMP
    # =====================================================
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # ---------- CSV ----------
        csv_path = tmpdir / places_csv.filename
        with open(csv_path, "wb") as f:
            f.write(await places_csv.read())

        # ---------- FOTO SITIO ----------
        site_image_path = None
        if site_image:
            site_image_path = tmpdir / site_image.filename
            with open(site_image_path, "wb") as f:
                f.write(await site_image.read())

        # =====================================================
        # GENERAR MAPA + CONTEOS
        # =====================================================
        map_result = generate_places_map(
            csv_path=str(csv_path),
            site_lat=float(site_lat),
            site_lon=float(site_lon),
        )

        map_png_buf = map_result["map_png"]
        poi_counts = map_result["counts"]

        map_image_path = tmpdir / "places_map.png"
        with open(map_image_path, "wb") as f:
            f.write(map_png_buf.read())

        # =====================================================
        # PDF
        # =====================================================
        pdf_path = tmpdir / "expansion_report.pdf"

        generate_expansion_pdf(
            payload={
                **payload_flat,
                **levantamiento,
            },
            df_benchmark=None,  # 🔴 por ahora no se usa
            decision_modelo_1=decision_modelo_1,
            decision_modelo_2=decision_modelo_2,
            output_path=str(pdf_path),
            logo_path="app/assets/neto logo.jpg",  # asegúrate que exista
            map_image_path=str(map_image_path),
            poi_counts=poi_counts,
            site_image_path=str(site_image_path) if site_image_path else None,
            ubicacion_en_cuadra=levantamiento.get("ubicacion_en_manzana"),
            tipo_adquisicion=levantamiento.get("tipo_adquisicion"),
            tipo_inmueble=levantamiento.get("tipo_sitio"),
        )

        # =====================================================
        # RESPONSE BINARIO
        # =====================================================
        pdf_file = open(pdf_path, "rb")

        return StreamingResponse(
            pdf_file,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=expansion_report.pdf"
            },
        )
