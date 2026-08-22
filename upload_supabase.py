# ============================================================
# KALIMANTAN FIREWATCH
# UPLOAD FIRMS HOTSPOTS → SUPABASE
# ============================================================

import os
import hashlib

import pandas as pd

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# 1. LOAD ENVIRONMENT
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")


if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL tidak ditemukan di .env"
    )

if not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_KEY tidak ditemukan di .env"
    )


print("========================================")
print("KALIMANTAN FIREWATCH")
print("UPLOAD HOTSPOT → SUPABASE")
print("========================================")


# ============================================================
# 2. CONNECT SUPABASE
# ============================================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

print("\nKoneksi Supabase berhasil.")


# ============================================================
# 3. LOAD CSV
# ============================================================

CSV_PATH = (
    "output/"
    "kalimantan_hotspots.csv"
)


if not os.path.exists(CSV_PATH):

    raise FileNotFoundError(
        f"File tidak ditemukan: {CSV_PATH}"
    )


df = pd.read_csv(CSV_PATH)


print(
    "\nJumlah data dari CSV:",
    len(df)
)


# ============================================================
# 4. CEK KOLOM
# ============================================================

required_columns = [

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


missing_columns = [

    col
    for col in required_columns
    if col not in df.columns

]


if missing_columns:

    raise ValueError(
        "Kolom berikut tidak ditemukan: "
        + str(missing_columns)
    )


# ============================================================
# 5. BUAT FIRE ID
# ============================================================
#
# Kita membuat ID berdasarkan:
#
# latitude
# longitude
# tanggal
# waktu
# satellite
#
# Tujuannya agar data yang sama
# tidak dimasukkan berkali-kali.
#
# ============================================================


def create_fire_id(row):

    raw_id = (

        f"{row['latitude']:.5f}|"
        f"{row['longitude']:.5f}|"
        f"{row['acq_date']}|"
        f"{row['acq_time']}|"
        f"{row['satellite']}"

    )

    return hashlib.sha256(
        raw_id.encode("utf-8")
    ).hexdigest()


df["fire_id"] = df.apply(
    create_fire_id,
    axis=1
)


# ============================================================
# 6. CEK DUPLIKAT DI CSV
# ============================================================

duplicate_count = (
    df["fire_id"]
    .duplicated()
    .sum()
)


print(
    "\nDuplikat dalam CSV:",
    duplicate_count
)


df = df.drop_duplicates(
    subset=["fire_id"]
)


print(
    "Data setelah deduplikasi:",
    len(df)
)


# ============================================================
# 7. SIAPKAN DATA UNTUK SUPABASE
# ============================================================

records = []


for _, row in df.iterrows():

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

        # PostGIS geometry
        "geom":
            f"POINT({longitude} {latitude})"

    }


    records.append(record)


# ============================================================
# 8. CEK JUMLAH RECORD
# ============================================================

print(
    "\nJumlah record siap upload:",
    len(records)
)


# ============================================================
# 9. UPLOAD BERTAHAP / BATCH
# ============================================================
#
# Kita tidak mengirim 1.714 sekaligus.
#
# Batch = 500 record
#
# Jika data sudah ada berdasarkan
# fire_id → diabaikan.
#
# ============================================================

BATCH_SIZE = 500


total_uploaded = 0


for start in range(
    0,
    len(records),
    BATCH_SIZE
):

    batch = records[
        start:
        start + BATCH_SIZE
    ]


    print(
        f"\nUploading "
        f"{start + 1}"
        f"-"
        f"{start + len(batch)}"
        f" ..."
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


    uploaded = (
        len(response.data)
        if response.data
        else 0
    )


    total_uploaded += uploaded


    print(
        "Berhasil diproses:",
        uploaded
    )


# ============================================================
# 10. HASIL
# ============================================================

print(
    "\n========================================"
)

print(
    "UPLOAD SELESAI"
)

print(
    "========================================"
)

print(
    "Total record CSV:",
    len(df)
)

print(
    "Total record yang dikembalikan Supabase:",
    total_uploaded
)

print(
    "\nCek Supabase → Table Editor → hotspots"
)