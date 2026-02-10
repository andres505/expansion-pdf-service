import pandas as pd
import plotly.graph_objects as go
import math
import io
import ast

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


def parse_types_to_list(x):
    """
    `types` puede venir como:
      - lista real
      - string tipo "['school', 'point_of_interest']"
      - string "school,point_of_interest"
      - NaN / None
    """
    if x is None:
        return []
    if isinstance(x, (list, tuple, set)):
        return [str(t).strip().lower() for t in x if str(t).strip()]

    s = str(x).strip()
    if not s or s.lower() == "nan":
        return []

    # intento 1: literal_eval para strings estilo lista
    try:
        v = ast.literal_eval(s)
        if isinstance(v, (list, tuple, set)):
            return [str(t).strip().lower() for t in v if str(t).strip()]
    except Exception:
        pass

    # intento 2: CSV simple separado por coma
    if "," in s:
        return [t.strip().lower() for t in s.split(",") if t.strip()]

    # intento 3: single token
    return [s.lower()]


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
    Retorna:
      - map_image_buf
      - counts dict compatible con pdf_report:
        {
          "Competencias directas": int,
          "Tiendas 3B": int,
          "Aurrera": int,
          "OXXO": int,
          "Abarrotes": int,
          "Escuelas": int,
          "Iglesias": int,
          "Generadores de flujo": int,
          "Generadores de abasto": int,
          "Otros": int,
        }
    """

    # ---------------- LOAD ----------------
    df = pd.read_csv(csv_path)

    lat_col = pick_col(df, ["place_lat", "lat", "latitude"])
    lon_col = pick_col(df, ["place_lon", "lon", "lng", "longitude"])
    name_col = pick_col(df, ["name", "nombre"])
    types_col = pick_col(df, ["types", "place_types", "tipo", "type", "Types"])

    qlat_col = pick_col(df, ["query_lat", "q_lat", "lat_query"])
    qlon_col = pick_col(df, ["query_lon", "q_lon", "lng_query", "lon_query"])

    if not lat_col or not lon_col:
        raise ValueError("No se encontraron columnas de latitud/longitud")
    if not name_col:
        raise ValueError("No se encontró columna de nombre (name/nombre)")
    if not types_col:
        # No tronamos: solo evitamos flujo/abasto por types
        types_col = None

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")
    df = df.dropna(subset=[lat_col, lon_col])

    if not qlat_col or not qlon_col:
        # fallback: si no vienen query_lat/query_lon, usa el centroide de los puntos
        main_lat = float(df[lat_col].mean())
        main_lon = float(df[lon_col].mean())
    else:
        main_lat = float(df[qlat_col].iloc[0])
        main_lon = float(df[qlon_col].iloc[0])

    # ---------------- NORMALIZACIONES ÚNICAS ----------------
    df["name_norm"] = df[name_col].astype(str).str.lower().fillna("")

    if types_col:
        df["types_list"] = df[types_col].apply(parse_types_to_list)
    else:
        df["types_list"] = [[] for _ in range(len(df))]

    # para chequeos rápidos
    df["types_set"] = df["types_list"].apply(lambda xs: set(xs) if isinstance(xs, list) else set())

    # ---------------- CLASIFICACIÓN CONCEPTUAL ----------------
    ABASTO_KEYWORDS = [
        "neto", "3b", "aurrera", "bodega", "chedraui", "soriana",
        "walmart", "dunosusa", "abarrotes", "mini super",
        "miscelanea", "miscelánea",
        "carnicer", "polleri", "pescader",
        "verduler", "fruter", "tortiller", "panader"
    ]

    ABASTO_TYPES = {
        "supermarket", "grocery_or_supermarket",
        "convenience_store", "food_store"
    }

    FLUJO_TYPES = {
        "school", "university", "church",
        "hospital", "clinic",
        "bank", "atm",
        "gym", "park", "stadium",
        "shopping_mall",
        "restaurant", "cafe",
        "meal_takeaway", "meal_delivery"
    }

    def classify_conceptual(row):
        name = row["name_norm"]
        types = row["types_set"]

        if any(k in name for k in ABASTO_KEYWORDS) or (types & ABASTO_TYPES):
            return "ABASTO"
        if types & FLUJO_TYPES:
            return "FLUJO"
        return "OTROS"

    df["generador_tipo"] = df.apply(classify_conceptual, axis=1)

    # ---------------- CLASIFICACIÓN VISUAL (MAPA + COUNTS DE COMPETENCIA) ----------------
    # Importante: usa types_set (no string) para escuela/iglesia, y name_norm para marcas.
    def classify_visual(row):
        name = row["name_norm"]
        types = row["types_set"]

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

        if "school" in types or "university" in types:
            return "ESCUELA"
        if "church" in types:
            return "IGLESIA"

        return "OTROS"

    df["grupo"] = df.apply(classify_visual, axis=1)

    # ---------------- COUNTS (CONTRATO PDF) ----------------
    counts = {
        "Tiendas 3B": int((df["grupo"] == "3B").sum()),
        "Aurrera": int((df["grupo"] == "AURRERA").sum()),
        "OXXO": int((df["grupo"] == "OXXO").sum()),
        "Abarrotes": int((df["grupo"] == "ABARROTES").sum()),
        "Escuelas": int((df["grupo"] == "ESCUELA").sum()),
        "Iglesias": int((df["grupo"] == "IGLESIA").sum()),
        "Generadores de flujo": int((df["generador_tipo"] == "FLUJO").sum()),
        "Generadores de abasto": int((df["generador_tipo"] == "ABASTO").sum()),
        "Otros": int((df["generador_tipo"] == "OTROS").sum()),
    }

    counts["Competencias directas"] = (
        counts["Tiendas 3B"]
        + counts["Aurrera"]
        + counts["OXXO"]
        + counts["Abarrotes"]
    )

    # ---------------- MAPA ----------------
    STYLE = {
        "NETO": dict(color="#FFD700", size=16),
        "3B": dict(color="#D32F2F", size=12),
        "AURRERA": dict(color="#2E7D32", size=12),
        "OXXO": dict(color="#F57C00", size=12),
        "ABARROTES": dict(color="#F57C00", size=12),
        "ESCUELA": dict(color="#8E24AA", size=9),
        "IGLESIA": dict(color="#8E24AA", size=9),
        "OTROS": dict(color="#1976D2", size=8),
    }

    DRAW_ORDER = [
        "OTROS", "ESCUELA", "IGLESIA",
        "3B", "AURRERA", "OXXO", "ABARROTES", "NETO"
    ]

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

    fig.add_trace(go.Scattermapbox(
        lat=[main_lat],
        lon=[main_lon],
        mode="markers",
        marker=dict(size=12, color="black"),
        name="Sitio evaluado"
    ))

    for r in radios:
        clats, clons = circle_coords(main_lat, main_lon, r)
        fig.add_trace(go.Scattermapbox(
            lat=clats,
            lon=clons,
            mode="lines",
            line=dict(width=2, color=RADIO_COLORS[r]),
            name=f"{r} m"
        ))

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

    buf = io.BytesIO()
    fig.write_image(buf, format="png", width=image_size, height=image_size, scale=2)
    buf.seek(0)

    return buf, counts
