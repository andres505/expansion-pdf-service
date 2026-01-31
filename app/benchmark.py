from __future__ import annotations

import math
from typing import Dict, List, Any

from app.region_vectors import get_region_vector


# ======================================================
# HELPERS
# ======================================================
def _safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, str):
            return None
        if math.isnan(x):
            return None
        return float(x)
    except Exception:
        return None


def _safe_div(site, benchmark):
    """
    (site - benchmark) / benchmark
    """
    site = _safe_float(site)
    benchmark = _safe_float(benchmark)

    if site is None or benchmark is None or benchmark == 0:
        return None

    return (site - benchmark) / benchmark


def _fmt_val(x):
    if x is None:
        return "-"
    try:
        x = float(x)
        return f"{x:,.0f}"
    except Exception:
        return str(x)


def _fmt_delta(x):
    if x is None:
        return "-"
    try:
        pct = int(round(x * 100))
        sign = "+" if pct > 0 else ""
        return f"{sign}{pct}%"
    except Exception:
        return "-"


# ======================================================
# MAIN BUILDER
# ======================================================
def build_benchmark_table(
    *,
    payload: Dict[str, Any],
    variables_map: Dict[str, Dict[str, str]] | None = None,
) -> List[List[str]]:
    """
    Devuelve una tabla lista para PDF:

    [
      ["Variable", "Benchmark regional", "Sitio", "Δ vs benchmark"],
      ["Población total", "9,264", "242,307", "+2515%"],
      ...
    ]
    """

    # ----------------------------------------------
    # Resolver región y vector
    # ----------------------------------------------
    region_name = payload.get("region")
    region_vector = get_region_vector(region_name)

    profile_eq = (
        region_vector
        .get("profile_equilibrio", {})
        if region_vector else {}
    )

    # ----------------------------------------------
    # Variables por defecto (alineadas a tu diseño)
    # ----------------------------------------------
    if variables_map is None:
        variables_map = {

            # -----------------------
            # DEMOGRAFÍA
            # -----------------------
            "Población total": {
                "payload": "INEGI_POB_TOTAL_CENSO_2020",
                "vector": "Poblacion Total"
            },
            "Hogares": {
                "payload": "INEGI_hogares",
                "vector": "INEGI_hogares"
            },

            # -----------------------
            # GENERADORES COMERCIALES
            # -----------------------
            "Generadores comerciales totales": {
                "payload": "total_lugares",
                "vector": "total_lugares"
            },
            "Escuelas": {
                "payload": "primary_school",
                "vector": "primary_school"
            },
            "Hospitales": {
                "payload": "hospital",
                "vector": "hospital"
            },
            "Restaurantes": {
                "payload": "restaurant",
                "vector": "restaurant"
            },

            # -----------------------
            # COMPETENCIA
            # -----------------------
            "Tiendas 3B": {
                "payload": "TIENDAS_3B",
                "vector": "TIENDAS_3B"
            },

            # -----------------------
            # INTEGRACIÓN
            # -----------------------
            "Integración comercial": {
                "payload": "integracion_score",
                "vector": "__HARDCODE_80__"
            }
        }

    # ----------------------------------------------
    # Construcción de tabla
    # ----------------------------------------------
    table: List[List[str]] = [
        ["Variable", "Benchmark regional", "Sitio", "Δ vs benchmark"]
    ]

    for label, cfg in variables_map.items():
        payload_key = cfg.get("payload")
        vector_key = cfg.get("vector")

        site_val = payload.get(payload_key)

        if vector_key == "__HARDCODE_80__":
            bench_val = 80
        elif vector_key is None:
            bench_val = None
        else:
            bench_val = profile_eq.get(vector_key)

        delta = _safe_div(site_val, bench_val)

        table.append([
            label,
            _fmt_val(bench_val),
            _fmt_val(site_val),
            _fmt_delta(delta),
        ])

    return table
