# ============================================================
# KALIMANTAN FIREWATCH
# FIRMS ACTIVE FIRE → GAUL SPATIAL FILTER
#
# Tahap:
# FIRMS API
#      ↓
# Raw hotspot points
#      ↓
# GAUL province boundaries
#      ↓
# Spatial Join
#      ↓
# Kalimantan Barat
# Kalimantan Selatan
# Kalimantan Tengah
# Kalimantan Timur
#
# BELUM ADA SUPABASE
# ============================================================


# ============================================================
# 1. IMPORT LIBRARY
# ============================================================

import os

import requests

import pandas as pd

import geopandas as gpd

from io import StringIO

from dotenv import load_dotenv


# ============================================================
# 2. LOAD ENVIRONMENT
# ============================================================

load_dotenv()


API_KEY = os.getenv(
    "FIRMS_API_KEY"
)


if not API_KEY:

    raise ValueError(
        "FIRMS_API_KEY tidak ditemukan "
        "di file .env"
    )


# ============================================================
# 3. PATH GAUL
# ============================================================

GAUL_PATH = (
    "data/"
    "kalimantan_provinces.geojson"
)


# ============================================================
# 4. CEK FILE GAUL
# ============================================================

if not os.path.exists(
    GAUL_PATH
):

    raise FileNotFoundError(
        f"File GAUL tidak ditemukan: "
        f"{GAUL_PATH}"
    )


print(
    "========================================"
)

print(
    "KALIMANTAN FIREWATCH"
)

print(
    "FIRMS → GAUL SPATIAL FILTER"
)

print(
    "========================================"
)


# ============================================================
# 5. LOAD GAUL
# ============================================================

print(
    "\nMembaca batas GAUL..."
)


gaul = gpd.read_file(
    GAUL_PATH
)


print(
    "Jumlah polygon GAUL:",
    len(gaul)
)


print(
    "\nKolom GAUL:"
)

print(
    gaul.columns.tolist()
)


# ============================================================
# 6. FILTER PROVINSI KALIMANTAN
# ============================================================

target_provinces = [

    "Kalimantan Barat",

    "Kalimantan Selatan",

    "Kalimantan Tengah",

    "Kalimantan Timur"

]


# Pastikan nama kolom ADM1_NAME tersedia

if "ADM1_NAME" not in gaul.columns:

    raise ValueError(
        "Kolom ADM1_NAME tidak ditemukan "
        "pada file GAUL."
    )


gaul_kalimantan = gaul[
    gaul["ADM1_NAME"].isin(
        target_provinces
    )
].copy()


print(
    "\nProvinsi yang digunakan:"
)

print(
    gaul_kalimantan[
        "ADM1_NAME"
    ].tolist()
)


print(
    "\nJumlah provinsi:",
    len(gaul_kalimantan)
)


# ============================================================
# 7. VALIDASI JUMLAH PROVINSI
# ============================================================

if len(
    gaul_kalimantan
) != 4:

    raise ValueError(
        "Jumlah provinsi Kalimantan "
        "tidak sesuai. Pastikan nama "
        "ADM1_NAME pada GeoJSON benar."
    )


# ============================================================
# 8. FIRMS API
# ============================================================

url = (
    "https://firms.modaps.eosdis.nasa.gov/"
    "api/area/csv/"
    f"{API_KEY}/"
    "VIIRS_NOAA20_NRT/"
    "108,-4,119,4/1"
)


print(
    "\nMengambil data FIRMS..."
)


response = requests.get(
    url,
    timeout=60
)


print(
    "HTTP Status:",
    response.status_code
)


response.raise_for_status()


# ============================================================
# 9. BACA DATA FIRMS
# ============================================================

df = pd.read_csv(
    StringIO(
        response.text
    )
)


print(
    "\nJumlah raw FIRMS points:",
    len(df)
)


# ============================================================
# 10. BUAT GEODATAFRAME
# ============================================================

hotspots = gpd.GeoDataFrame(

    df,

    geometry=gpd.points_from_xy(

        df["longitude"],

        df["latitude"]

    ),

    crs="EPSG:4326"

)


# ============================================================
# 11. CEK CRS
# ============================================================

print(
    "\nCRS FIRMS:",
    hotspots.crs
)

print(
    "CRS GAUL:",
    gaul_kalimantan.crs
)


# ============================================================
# 12. SAMAKAN CRS
# ============================================================

gaul_kalimantan = (
    gaul_kalimantan
    .to_crs(
        hotspots.crs
    )
)


# ============================================================
# 13. SPATIAL JOIN
# ============================================================
#
# Setiap titik FIRMS dicocokkan
# dengan polygon provinsi GAUL.
#
# predicate = within
#
# artinya:
#
# POINT berada DI DALAM polygon
#
# ============================================================

print(
    "\nMelakukan spatial join..."
)


hotspots_joined = gpd.sjoin(

    hotspots,

    gaul_kalimantan[
        [
            "ADM1_NAME",
            "geometry"
        ]
    ],

    how="inner",

    predicate="within"

)


# ============================================================
# 14. RENAME PROVINCE
# ============================================================

hotspots_joined = (
    hotspots_joined
    .rename(
        columns={
            "ADM1_NAME":
            "province"
        }
    )
)


# ============================================================
# 15. HAPUS KOLOM JOIN INDEX
# ============================================================

if "index_right" in (
    hotspots_joined.columns
):

    hotspots_joined = (
        hotspots_joined
        .drop(
            columns=[
                "index_right"
            ]
        )
    )


# ============================================================
# 16. HASIL SPATIAL FILTER
# ============================================================

print(
    "\n========================================"
)

print(
    "HASIL SPATIAL FILTER"
)

print(
    "========================================"
)


print(
    "Jumlah hotspot Kalimantan:",
    len(hotspots_joined)
)


# ============================================================
# 17. STATISTIK PER PROVINSI
# ============================================================

print(
    "\n========================================"
)

print(
    "HOTSPOT PER PROVINSI"
)

print(
    "========================================"
)


province_stats = (
    hotspots_joined
    .groupby(
        "province"
    )
    .size()
    .sort_values(
        ascending=False
    )
)


print(
    province_stats
)


# ============================================================
# 18. STATISTIK CONFIDENCE
# ============================================================

print(
    "\n========================================"
)

print(
    "CONFIDENCE"
)

print(
    "========================================"
)


print(
    hotspots_joined[
        "confidence"
    ].value_counts()
)


# ============================================================
# 19. STATISTIK DAY / NIGHT
# ============================================================

print(
    "\n========================================"
)

print(
    "DAY / NIGHT"
)

print(
    "========================================"
)


print(
    hotspots_joined[
        "daynight"
    ].value_counts()
)


# ============================================================
# 20. SAMPLE DATA
# ============================================================

print(
    "\n========================================"
)

print(
    "10 HOTSPOT PERTAMA"
)

print(
    "========================================"
)


columns_to_show = [
    "latitude",
    "longitude",
    "bright_ti4",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_ti5",
    "frp",
    "daynight",
    "province"
]


print(
    hotspots_joined[
        columns_to_show
    ]
    .head(10)
    .to_string(
        index=False
    )
)


# ============================================================
# 21. EXPORT CSV
# ============================================================
#
# Geometry tidak diperlukan
# untuk file pengecekan CSV.
#
# ============================================================

os.makedirs(
    "output",
    exist_ok=True
)


output_csv = (
    "output/"
    "kalimantan_hotspots.csv"
)


hotspots_joined[
    columns_to_show
].to_csv(

    output_csv,

    index=False

)


print(
    "\nCSV berhasil dibuat:"
)

print(
    output_csv
)


# ============================================================
# 22. EXPORT GEOJSON
# ============================================================
#
# Ini berguna kalau nanti mau
# langsung dicek di QGIS / WebGIS.
#
# ============================================================

output_geojson = (
    "output/"
    "kalimantan_hotspots.geojson"
)


hotspots_joined.to_file(

    output_geojson,

    driver="GeoJSON"

)


print(
    "\nGeoJSON berhasil dibuat:"
)

print(
    output_geojson
)


# ============================================================
# 23. SELESAI
# ============================================================

print(
    "\n========================================"
)

print(
    "SPATIAL FILTER SELESAI"
)

print(
    "========================================"
)