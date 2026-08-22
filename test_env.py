import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("FIRMS_API_KEY")

if api_key:
    print("FIRMS API KEY berhasil dibaca.")
    print("Panjang API key:", len(api_key))
else:
    print("FIRMS API KEY tidak ditemukan.")