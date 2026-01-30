import pandas as pd
import plotly.graph_objects as go
import math
import io

# =====================================================
# CONFIG
# =====================================================
RADIO_COLORS = {50: "green", 200: "gold", 500: "red"}
MARGIN_FACTOR = 1.30
DEFAULT_RADIOS = (50, 200, 500)

# =====================================================
# HELPERS
# =====================================================
def pick_col(df, candidates):
    cols = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


def circle_coords(lat, lon, radius_m, n=200):
    R = 6378137
    lat, lon = math.radians(lat), math.radians(lon)
    ang = radius_m / R
    lats, lons = [], []

    for i in range(n + 1):
        t = 2 * math.pi * i / n
        lat2 = math.asin(
            math.sin(lat) * math.cos(ang)
            + math.cos(lat) * math.sin(ang) * math.cos(t)
        )
        lon2 = lon + math.atan2(
            math.sin(t) * math.sin(ang) * math.cos(lat),
            math.cos(ang) - math.sin(lat) * math.sin(lat2)
        )
        lats.append(math.degrees(lat2))
        lons.append(math.degrees(lon2))

    return lats, lons


def bbox_from_radius(lat, lon, radius_m):
    d = (radius_m * MARGIN_FACTOR) / 111_320
    return dict(
        lat_min=lat - d,
        lat_max=lat + d,
        lon_min=lon - d,
        lon_max=lon + d
    )

# =====================================================
# MAIN
# =====================================================
def generate_places_map_in_memory(
    *,
    csv_path: str,
    image_size: int = 820,
    radios=DEFAULT_RADIOS,
):
    """
    Genera un mapa PNG en memoria (BytesIO) con:
    - puntos clasificados
    - radios reales
    - bounds exactos
    - conteos por grupo

    Retorna:
        buf (BytesIO), counts (dict)
    """

    # -------------------------------------------------
    # LOAD CSV
    # -------------------------------------------------
    df = pd.read_csv(csv_path)

    lat_col = pick_col(df, ["place_lat", "lat", "latitude"])
    lon_col = pick_col(df, ["place_lon", "lon", "lng", "longitude"])
    name_col = pick_col(df, ["name", "nombre"])

    if not lat_col or not lon_col:
        raise ValueError("No se encontraron columnas de latitud/longitud")

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    main_lat = df[pick_col(df, ["query_lat"])].iloc[0]
    main_lon = df[pick_col(df, ["query_lon"])].iloc[0]

    # -------------------------------------------------
    # CLASIFICACIÓN
    # -------------------------------------------------
    def classify(row):
        name = str(row.get(name_col, "")).lower()
        types = str(row.get("types", "")).lower()

        if "neto" in name:
            return "NETO"
        if "3b" in name:
            return "3B"
        if "aurrera" in name:
            return "AURRERA"
        if "oxxo" in name:
            return "OXXO"
        if "abarrot" in name:
            return "ABARROTES"

        if any(x in name for x in ["tortill", "carnicer", "verdura", "fruta"]) or "restaurant" in types:
            return "GENERADOR_COMERCIAL"

        if "school" in types:
            return "ESCUELA"
        if "church" in types:
            return "IGLESIA"

        return "OTROS"

    df["grupo"] = df.apply(classify, axis=1)
    counts = df["grupo"].value_counts().to_dict()

    # -------------------------------------------------
    # ESTILOS
    # -------------------------------------------------
    STYLE = {
        "NETO": dict(color="#FFD700", size=16),
        "3B": dict(color="#D32F2F", size=12),
        "AURRERA": dict(color="#2E7D32", size=12),
        "OXXO": dict(color="#F57C00", size=12),
        "ABARROTES": dict(color="#F57C00", size=12),
        "GENERADOR_COMERCIAL": dict(color="#1976D2", size=9),
        "ESCUELA": dict(color="#8E24AA", size=9),
        "IGLESIA": dict(color="#8E24AA", size=9),
        "OTROS": dict(color="#1976D2", size=8),
    }

    DRAW_ORDER = [
        "OTROS", "GENERADOR_COMERCIAL", "ESCUELA", "IGLESIA",
        "3B", "AURRERA", "OXXO", "ABARROTES", "NETO"
    ]

    # -------------------------------------------------
    # MAPA
    # -------------------------------------------------
    fig = go.Figure()

    for g in DRAW_ORDER:
        dfi = df[df["grupo"] == g]
        if dfi.empty:
            continue
        s = STYLE[g]
        fig.add_trace(go.Scattermapbox(
            lat=dfi[lat_col],
            lon=dfi[lon_col],
            mode="markers",
            marker=dict(size=s["size"], color=s["color"], opacity=0.9),
            name=g
        ))

    # Sitio evaluado
    fig.add_trace(go.Scattermapbox(
        lat=[main_lat],
        lon=[main_lon],
        mode="markers",
        marker=dict(size=12, color="black"),
        name="Sitio evaluado"
    ))

    # Radios
    for r in radios:
        clats, clons = circle_coords(main_lat, main_lon, r)
        fig.add_trace(go.Scattermapbox(
            lat=clats,
            lon=clons,
            mode="lines",
            line=dict(width=2, color=RADIO_COLORS[r]),
            name=f"{r} m"
        ))

    # Bounds exactos
    bbox = bbox_from_radius(main_lat, main_lon, max(radios))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            bounds=dict(
                west=bbox["lon_min"],
                east=bbox["lon_max"],
                south=bbox["lat_min"],
                north=bbox["lat_max"],
            )
        ),
        width=image_size,
        height=image_size,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h")
    )

    # -------------------------------------------------
    # EXPORT PNG EN MEMORIA
    # -------------------------------------------------
    buf = io.BytesIO()
    fig.write_image(
        buf,
        format="png",
        width=image_size,
        height=image_size,
        scale=2
    )
    buf.seek(0)

    return buf, counts
