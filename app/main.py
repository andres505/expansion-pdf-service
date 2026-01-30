from fastapi import FastAPI, UploadFile, File, Form
from typing import Optional
import json

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate-pdf")
async def generate_pdf(
    payload: str = Form(...),
    places_csv: UploadFile = File(...),
    site_image: Optional[UploadFile] = File(None),
):
    # Parse payload
    payload_json = json.loads(payload)

    return {
        "message": "inputs received",
        "payload_keys": list(payload_json.keys()),
        "places_csv_filename": places_csv.filename,
        "site_image_filename": site_image.filename if site_image else None,
    }
