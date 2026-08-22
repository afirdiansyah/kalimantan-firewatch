import os

from dotenv import load_dotenv
from supabase import create_client


# ============================================
# LOAD ENV
# ============================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


# ============================================
# VALIDASI ENV
# ============================================

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL tidak ditemukan di .env"
    )

if not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_KEY tidak ditemukan di .env"
    )


print("SUPABASE_URL berhasil dibaca.")
print(
    "SUPABASE_KEY berhasil dibaca."
)


# ============================================
# CONNECT
# ============================================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


print(
    "Koneksi Supabase berhasil dibuat."
)


# ============================================
# TEST QUERY
# ============================================

response = (
    supabase
    .table("hotspots")
    .select("id")
    .limit(1)
    .execute()
)


print(
    "Query berhasil."
)

print(
    "Data:",
    response.data
)