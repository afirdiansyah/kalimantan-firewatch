# ============================================================
# KALIMANTAN FIREWATCH
# VIIRS NRT:
# NOAA-20 + NOAA-21 + SUOMI-NPP
#
# FIRMS → GAUL → DEDUPLICATION → SUPABASE
# ============================================================

import os
import hashlib
from io import StringIO

import requests
import pandas as pd
import geopandas as gpd

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# 1. ENVIRONMENT
# ============================================================

load_dotenv()

FIRMS_API_KEY = os.getenv("FIRMS_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not FIRMS_API_KEY:
    raise ValueError("FIRMS_API_KEY tidak ditemukan.")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL tidak ditemukan.")

if not SUPABASE_SECRET_KEY:
    raise ValueError("SUPABASE_SECRET_KEY tidak ditemukan.")


# ============================================================
# 2. CONFIGURATION
# ============================================================

GAUL_PATH = "data/kalimantan_provinces.geojson"

BATCH_SIZE = 500

# Bounding box Kalimantan
# Akan dihitung otomatis dari GAUL.
#
# Format:
# west, south, east, north


SATELLITES = [
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
    "VIIRS_SNPP_NRT"
]


# ============================================================
# 3. HEADER
# ============================================================

print("=" * 60)
print("KALIMANTAN FIREWATCH")
print("VIIRS NOAA-20 + NOAA-21 + SUOMI-NPP")
print("FIRMS → GAUL → DEDUPLICATION → SUPABASE")
print("=" * 60)


# ============================================================
# 4. SUPABASE
# ============================================================

print("\n[1/7] Connecting to Supabase...")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)

print("Supabase connection OK.")


# ============================================================
# 5. LOAD GAUL
# ============================================================

print("\n[2/7] Loading GAUL...")

if not os.path.exists(GAUL_PATH):
    raise FileNotFoundError(
        f"GAUL tidak ditemukan: {GAUL_PATH}"
    )


kalimantan = gpd.read_file(
    GAUL_PATH
)


print(
    "Jumlah provinsi:",
    len(kalimantan)
)

print(
    "Provinsi:",
    kalimantan["ADM1_NAME"].tolist()
)


if kalimantan.crs is None:

    kalimantan = kalimantan.set_crs(
        "EPSG:4326"
    )

else:

    kalimantan = kalimantan.to_crs(
        "EPSG:4326"
    )


# ============================================================
# 6. CREATE FIRMS BOUNDING BOX
# ============================================================

bounds = kalimantan.total_bounds

west = bounds[0]
south = bounds[1]
east = bounds[2]
north = bounds[3]


area = (
    f"{west},{south},{east},{north}"
)


print("\nBounding box:")
print(area)


# ============================================================
# 7. DOWNLOAD FIRMS
# ============================================================

all_fires = []


print(
    "\n[3/7] Downloading FIRMS data..."
)


for satellite in SATELLITES:

    print(
        f"\nSatellite: {satellite}"
    )

    firms_url = (
        "https://firms.modaps.eosdis.nasa.gov/"
        "api/area/csv/"
        f"{FIRMS_API_KEY}/"
        f"{satellite}/"
        f"{area}/"
        "2"
    )


    response = requests.get(
        firms_url,
        timeout=120
    )


    print(
        "HTTP Status:",
        response.status_code
    )


    if response.status_code != 200:

        print(
            "WARNING: FIRMS gagal:",
            response.text[:500]
        )

        continue


    df = pd.read_csv(
        StringIO(response.text)
    )


    print(
        "Raw points:",
        len(df)
    )


    if df.empty:
        continue


    # Tambahkan sumber sensor

    df["firms_source"] = satellite


    all_fires.append(
        df
    )


if not all_fires:

    print(
        "\nTidak ada data FIRMS."
    )

    raise SystemExit(0)


fires = pd.concat(
    all_fires,
    ignore_index=True
)


print(
    "\nTotal raw dari semua sensor:",
    len(fires)
)


# ============================================================
# 8. GEODATAFRAME
# ============================================================

print(
    "\n[4/7] Spatial filtering..."
)


geometry = gpd.points_from_xy(
    fires["longitude"],
    fires["latitude"]
)


fires = gpd.GeoDataFrame(
    fires,
    geometry=geometry,
    crs="EPSG:4326"
)


# Spatial join dengan GAUL

fires = gpd.sjoin(
    fires,
    kalimantan[
        [
            "ADM1_NAME",
            "geometry"
        ]
    ],
    how="inner",
    predicate="within"
)


fires = fires.rename(
    columns={
        "ADM1_NAME": "province"
    }
)


if "index_right" in fires.columns:

    fires = fires.drop(
        columns=["index_right"]
    )


print(
    "Hotspot dalam Kalimantan:",
    len(fires)
)


# ============================================================
# 9. CREATE OBSERVATION ID
# ============================================================

def create_observation_id(row):

    raw = (

        f"{row['latitude']:.5f}|"
        f"{row['longitude']:.5f}|"
        f"{row['acq_date']}|"
        f"{row['acq_time']}|"
        f"{row['satellite']}"

    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


fires["observation_id"] = (
    fires.apply(
        create_observation_id,
        axis=1
    )
)


# ============================================================
# 10. REMOVE EXACT DUPLICATES
# ============================================================

before_exact = len(fires)


fires = fires.drop_duplicates(
    subset=["observation_id"]
)


after_exact = len(fires)


print(
    "\nExact duplicate removed:",
    before_exact - after_exact
)


# ============================================================
# 11. SPATIAL-TEMPORAL DEDUPLICATION
# ============================================================

print(
    "\n[5/7] Spatial-temporal deduplication..."
)


# ------------------------------------------------------------
# TIME
# ------------------------------------------------------------

fires["acq_datetime"] = pd.to_datetime(
    fires["acq_date"].astype(str)
    + " "
    + fires["acq_time"]
        .astype(str)
        .str.zfill(4)
        .str[:2]
    + ":"
    + fires["acq_time"]
        .astype(str)
        .str.zfill(4)
        .str[2:]
    ,
    errors="coerce"
)


# ------------------------------------------------------------
# SPATIAL GRID
#
# 0.01 degree ≈ 1 km
# ------------------------------------------------------------

GRID_SIZE = 0.01


fires["grid_lat"] = (
    fires["latitude"]
    / GRID_SIZE
).round().astype(int)


fires["grid_lon"] = (
    fires["longitude"]
    / GRID_SIZE
).round().astype(int)


# ------------------------------------------------------------
# TIME WINDOW
#
# 1 hour
# ------------------------------------------------------------

fires["time_hour"] = (
    fires["acq_datetime"]
    .dt.floor("1h")
)


# ------------------------------------------------------------
# DEDUP KEY
# ------------------------------------------------------------

fires["dedup_key"] = (

    fires["acq_date"].astype(str)
    + "|"
    + fires["grid_lat"].astype(str)
    + "|"
    + fires["grid_lon"].astype(str)
    + "|"
    + fires["time_hour"].astype(str)

)


before_dedup = len(fires)


# ------------------------------------------------------------
# PRIORITY
#
# confidence:
# h = high
# n = nominal
# l = low
#
# Keep highest confidence.
# If same confidence, keep highest FRP.
# ------------------------------------------------------------

confidence_priority = {

    "h": 3,
    "n": 2,
    "l": 1

}


fires["confidence_rank"] = (
    fires["confidence"]
    .astype(str)
    .str.lower()
    .map(confidence_priority)
    .fillna(0)
)


fires = fires.sort_values(
    by=[
        "dedup_key",
        "confidence_rank",
        "frp"
    ],
    ascending=[
        True,
        False,
        False
    ]
)


fires = fires.drop_duplicates(
    subset=["dedup_key"],
    keep="first"
)


after_dedup = len(fires)


print(
    "Sebelum dedup:",
    before_dedup
)

print(
    "Setelah dedup:",
    after_dedup
)

print(
    "Redundansi dihapus:",
    before_dedup - after_dedup
)


# ============================================================
# 12. CREATE FIRE ID
# ============================================================

def create_fire_id(row):

    raw = (

        f"{row['dedup_key']}|"
        f"{row['province']}"

    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


fires["fire_id"] = (
    fires.apply(
        create_fire_id,
        axis=1
    )
)


# ============================================================
# 13. PREPARE RECORDS
# ============================================================

print(
    "\n[6/7] Preparing Supabase records..."
)


records = []


for _, row in fires.iterrows():

    latitude = float(
        row["latitude"]
    )

    longitude = float(
        row["longitude"]
    )


    record = {

        "fire_id":
            row["fire_id"],

        "latitude":
            latitude,

        "longitude":
            longitude,

        "bright_ti4":
            float(row["bright_ti4"])
            if pd.notna(row["bright_ti4"])
            else None,

        "scan":
            float(row["scan"])
            if pd.notna(row["scan"])
            else None,

        "track":
            float(row["track"])
            if pd.notna(row["track"])
            else None,

        "acq_date":
            str(row["acq_date"]),

        "acq_time":
            int(row["acq_time"])
            if pd.notna(row["acq_time"])
            else None,

        "satellite":
            str(row["satellite"]),

        "instrument":
            str(row["instrument"]),

        "confidence":
            str(row["confidence"]),

        "version":
            str(row["version"]),

        "bright_ti5":
            float(row["bright_ti5"])
            if pd.notna(row["bright_ti5"])
            else None,

        "frp":
            float(row["frp"])
            if pd.notna(row["frp"])
            else None,

        "daynight":
            str(row["daynight"]),

        "province":
            str(row["province"]),

        "geom":
            f"POINT({longitude} {latitude})"
    }


    records.append(
        record
    )


print(
    "Record siap upload:",
    len(records)
)


# ============================================================
# 14. UPLOAD
# ============================================================

print(
    "\n[7/7] Uploading to Supabase..."
)


total_processed = 0


for start in range(
    0,
    len(records),
    BATCH_SIZE
):

    batch = records[
        start:
        start + BATCH_SIZE
    ]


    end = (
        start +
        len(batch)
    )


    print(
        f"Uploading {start + 1}-{end}..."
    )


    response = (

        supabase
        .table("hotspots")
        .upsert(
            batch,
            on_conflict="fire_id",
            ignore_duplicates=True
        )
        .execute()

    )


    processed = (
        len(response.data)
        if response.data
        else 0
    )


    total_processed += processed


    print(
        "Processed:",
        processed
    )


# ============================================================
# 15. SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("KALIMANTAN FIREWATCH UPDATE SELESAI")
print("=" * 60)

print(
    "Raw semua sensor:",
    len(pd.concat(all_fires, ignore_index=True))
)

print(
    "Setelah GAUL:",
    before_exact
)

print(
    "Setelah dedup:",
    len(fires)
)

print(
    "Redundansi dihapus:",
    before_dedup - after_dedup
)

print(
    "Supabase processed:",
    total_processed
)

print("=" * 60)