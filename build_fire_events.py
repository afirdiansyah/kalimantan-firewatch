# ============================================================
# KALIMANTAN FIREWATCH
# BUILD FIRE EVENTS V2
#
# HOTSPOTS
#     ↓
# SPATIAL + TEMPORAL GRAPH
#     ↓
# FIRE EVENTS
#
# RULE:
#   Distance <= 1 km
#   AND
#   Time difference <= 3 hours
# ============================================================

import os
import hashlib

import numpy as np
import pandas as pd

from dotenv import load_dotenv
from supabase import create_client

from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


# ============================================================
# CONFIGURATION
# ============================================================

DISTANCE_KM = 1.0
TIME_WINDOW_HOURS = 3.0

EARTH_RADIUS_KM = 6371.0088

PAGE_SIZE = 1000
UPLOAD_BATCH_SIZE = 500


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL tidak ditemukan di .env"
    )

if not SUPABASE_SECRET_KEY:
    raise ValueError(
        "SUPABASE_SECRET_KEY tidak ditemukan di .env"
    )


# ============================================================
# HEADER
# ============================================================

print("=" * 60)
print("KALIMANTAN FIREWATCH")
print("BUILD FIRE EVENTS V2")
print("TRUE SPATIAL-TEMPORAL CONSTRAINT")
print("=" * 60)

print(
    f"\nSpatial threshold : {DISTANCE_KM} km"
)

print(
    f"Temporal threshold: {TIME_WINDOW_HOURS} hours"
)


# ============================================================
# CONNECT SUPABASE
# ============================================================

print("\n[1/7] Connecting to Supabase...")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)

print("Supabase connection OK.")


# ============================================================
# LOAD HOTSPOTS
# ============================================================

print("\n[2/7] Loading hotspot detections...")


columns = (
    "fire_id,"
    "latitude,"
    "longitude,"
    "acq_date,"
    "acq_time,"
    "satellite,"
    "confidence,"
    "frp,"
    "province"
)


all_rows = []

offset = 0


while True:

    start = offset + 1
    end = offset + PAGE_SIZE

    print(
        f"Loading records {start}-{end}..."
    )

    response = (
        supabase
        .table("hotspots")
        .select(columns)
        .range(
            offset,
            end - 1
        )
        .execute()
    )

    rows = response.data

    if not rows:
        break

    all_rows.extend(rows)

    if len(rows) < PAGE_SIZE:
        break

    offset += PAGE_SIZE


print(
    "\nTotal hotspot detections:",
    len(all_rows)
)


if not all_rows:

    print(
        "Tidak ada data hotspot."
    )

    raise SystemExit(0)


df = pd.DataFrame(
    all_rows
)


# ============================================================
# PREPARE DATETIME
# ============================================================

print("\n[3/7] Preparing datetime...")


def parse_datetime(row):

    date_value = str(
        row["acq_date"]
    )

    time_value = (
        str(row["acq_time"])
        .zfill(4)
    )

    hh = time_value[:2]
    mm = time_value[2:4]

    return pd.to_datetime(
        f"{date_value} {hh}:{mm}",
        errors="coerce"
    )


df["acq_datetime"] = df.apply(
    parse_datetime,
    axis=1
)


# Remove invalid rows

df = df.dropna(
    subset=[
        "latitude",
        "longitude",
        "acq_datetime"
    ]
).reset_index(
    drop=True
)


# Make sure numeric

df["latitude"] = pd.to_numeric(
    df["latitude"],
    errors="coerce"
)

df["longitude"] = pd.to_numeric(
    df["longitude"],
    errors="coerce"
)

df["frp"] = pd.to_numeric(
    df["frp"],
    errors="coerce"
)


df = df.dropna(
    subset=[
        "latitude",
        "longitude"
    ]
).reset_index(
    drop=True
)


print(
    "Valid detections:",
    len(df)
)


# ============================================================
# SORT BY TIME
# ============================================================

df = df.sort_values(
    "acq_datetime"
).reset_index(
    drop=True
)


# ============================================================
# CONVERT COORDINATES TO LOCAL KM
# ============================================================

print(
    "\n[4/7] Creating spatial index..."
)


lat_rad = np.radians(
    df["latitude"].values
)

lon_rad = np.radians(
    df["longitude"].values
)


lat_mean = np.mean(
    lat_rad
)


# Equirectangular approximation.
#
# Untuk area Kalimantan dan radius 1 km,
# pendekatan ini cukup untuk candidate search.

x_km = (
    lon_rad
    * EARTH_RADIUS_KM
    * np.cos(lat_mean)
)

y_km = (
    lat_rad
    * EARTH_RADIUS_KM
)


coordinates = np.column_stack(
    [
        x_km,
        y_km
    ]
)


tree = cKDTree(
    coordinates
)


# ============================================================
# SPATIAL + TEMPORAL GRAPH
# ============================================================

print(
    "\n[5/7] Building spatial-temporal graph..."
)


times = (
    df["acq_datetime"]
    .astype("int64")
    .values
)


TIME_WINDOW_NS = int(
    TIME_WINDOW_HOURS
    * 60
    * 60
    * 1_000_000_000
)


# ------------------------------------------------------------
# IMPORTANT
#
# Kita tidak membuat satu distance metric gabungan.
#
# Setiap candidate harus memenuhi:
#
# distance <= 1 km
# AND
# time difference <= 3 hours
# ------------------------------------------------------------


edges_i = []
edges_j = []


total_candidates = 0
valid_edges = 0


for i in range(
    len(df)
):

    # --------------------------------------------------------
    # Candidate spatial neighbors
    # --------------------------------------------------------

    neighbors = tree.query_ball_point(
        coordinates[i],
        DISTANCE_KM
    )


    total_candidates += len(
        neighbors
    )


    for j in neighbors:

        # Jangan self-loop

        if j <= i:
            continue


        # ----------------------------------------------------
        # TEMPORAL CONSTRAINT
        # ----------------------------------------------------

        time_difference = abs(
            times[j] - times[i]
        )


        if time_difference > TIME_WINDOW_NS:

            continue


        # ----------------------------------------------------
        # SPATIAL CONSTRAINT
        # ----------------------------------------------------

        dx = (
            coordinates[j, 0]
            - coordinates[i, 0]
        )

        dy = (
            coordinates[j, 1]
            - coordinates[i, 1]
        )


        distance = np.sqrt(
            dx * dx +
            dy * dy
        )


        if distance > DISTANCE_KM:

            continue


        # ----------------------------------------------------
        # VALID CONNECTION
        # ----------------------------------------------------

        edges_i.append(i)
        edges_j.append(j)

        valid_edges += 1


    # Progress

    if (
        (i + 1) % 1000 == 0
        or
        i == len(df) - 1
    ):

        print(
            f"Processed {i + 1}/"
            f"{len(df)} points..."
        )


print(
    "\nSpatial candidates:",
    total_candidates
)

print(
    "Valid spatial-temporal edges:",
    valid_edges
)


# ============================================================
# CONNECTED COMPONENTS
# ============================================================

print(
    "\nFinding connected components..."
)


n = len(df)


# Self connections

rows = (
    edges_i
    + edges_j
    + list(range(n))
)

cols = (
    edges_j
    + edges_i
    + list(range(n))
)


data = np.ones(
    len(rows),
    dtype=np.uint8
)


graph = coo_matrix(
    (
        data,
        (
            rows,
            cols
        )
    ),
    shape=(
        n,
        n
    )
).tocsr()


number_of_events, labels = (
    connected_components(
        graph,
        directed=False
    )
)


df["cluster_id"] = labels


print(
    "Jumlah fire events:",
    number_of_events
)


# ============================================================
# BUILD EVENT RECORDS
# ============================================================

print(
    "\n[6/7] Building fire event records..."
)


events = []


for cluster_id, group in df.groupby(
    "cluster_id"
):

    # --------------------------------------------------------
    # CENTER
    # --------------------------------------------------------

    center_lat = (
        group["latitude"]
        .mean()
    )

    center_lon = (
        group["longitude"]
        .mean()
    )


    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    start_time = (
        group["acq_datetime"]
        .min()
    )

    last_time = (
        group["acq_datetime"]
        .max()
    )


    # --------------------------------------------------------
    # SATELLITES
    # --------------------------------------------------------

    satellites = sorted(
        group["satellite"]
        .astype(str)
        .unique()
        .tolist()
    )


    # --------------------------------------------------------
    # FRP
    # --------------------------------------------------------

    frp_values = (
        pd.to_numeric(
            group["frp"],
            errors="coerce"
        )
    )


    total_frp = (
        frp_values
        .fillna(0)
        .sum()
    )


    max_frp = (
        frp_values
        .max()
    )


    # --------------------------------------------------------
    # PROVINCE
    # --------------------------------------------------------

    provinces = (
        group["province"]
        .dropna()
        .astype(str)
    )


    if len(provinces) > 0:

        province = (
            provinces
            .mode()
            .iloc[0]
        )

    else:

        province = None


    # --------------------------------------------------------
    # EVENT ID
    # --------------------------------------------------------

    raw_event_id = (

        f"{center_lat:.5f}|"
        f"{center_lon:.5f}|"
        f"{start_time.isoformat()}"

    )


    event_id = hashlib.sha256(
        raw_event_id.encode(
            "utf-8"
        )
    ).hexdigest()


    events.append({

        "event_id":
            event_id,

        "latitude":
            float(center_lat),

        "longitude":
            float(center_lon),

        "province":
            province,

        "start_time":
            start_time.isoformat(),

        "last_time":
            last_time.isoformat(),

        "detection_count":
            int(len(group)),

        "satellite_count":
            int(len(satellites)),

        "satellites":
            satellites,

        "total_frp":
            float(total_frp),

        "max_frp":
            float(max_frp)

    })


events_df = pd.DataFrame(
    events
)


# ============================================================
# CLEAR OLD EVENTS
# ============================================================

print(
    "\nClearing previous fire events..."
)


(
    supabase
    .table("fire_events")
    .delete()
    .neq(
        "event_id",
        ""
    )
    .execute()
)


print(
    "Previous fire events cleared."
)


# ============================================================
# UPLOAD
# ============================================================

print(
    "\nUploading fire events..."
)


records = (
    events_df
    .replace({
        np.nan: None
    })
    .to_dict(
        orient="records"
    )
)


processed = 0


for start in range(
    0,
    len(records),
    UPLOAD_BATCH_SIZE
):

    batch = records[
        start:
        start + UPLOAD_BATCH_SIZE
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
        .table("fire_events")
        .upsert(
            batch,
            on_conflict="event_id"
        )
        .execute()
    )


    count = len(
        response.data
        if response.data
        else []
    )


    processed += count


    print(
        "Processed:",
        count
    )


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("FIRE EVENT BUILD V2 SELESAI")
print("=" * 60)

print(
    "Hotspot detections:",
    len(df)
)

print(
    "Fire events:",
    number_of_events
)

print(
    "Average detections/event:",
    round(
        len(df) / number_of_events,
        2
    )
    if number_of_events > 0
    else 0
)

print(
    "Valid spatial-temporal edges:",
    valid_edges
)

print(
    "Supabase processed:",
    processed
)

print("=" * 60)