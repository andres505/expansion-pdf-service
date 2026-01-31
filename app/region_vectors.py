import json
import os

# Cache en memoria
_REGION_VECTORS = None


def load_region_vectors():
    global _REGION_VECTORS

    if _REGION_VECTORS is not None:
        return _REGION_VECTORS

    base_dir = os.path.dirname(__file__)
    json_path = os.path.join(base_dir, "assets", "vectores_promedio_region.json")

    with open(json_path, "r", encoding="utf-8") as f:
        _REGION_VECTORS = json.load(f)

    return _REGION_VECTORS


def get_region_vector(region_name: str | None):
    """
    Devuelve el vector regional correspondiente al nombre de región.
    """
    if not region_name:
        return {}

    vectors = load_region_vectors()

    # Normalización defensiva
    region_key = region_name.strip().upper()

    return vectors.get(region_key, {})
