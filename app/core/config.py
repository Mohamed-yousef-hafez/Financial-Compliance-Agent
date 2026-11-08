
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

REPO_DATA_DIR = BASE_DIR / "data"

DEFAULT_DATA_DIR = (
    Path("/tmp/financial-compliance-data")
    if os.getenv("VERCEL")
    else REPO_DATA_DIR
)

DATA_DIR = Path(
    os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR))
).expanduser()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "").strip()

AUTH_MODE = os.getenv("AUTH_MODE", "demo").strip().lower()
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

MAX_UPLOAD_BYTES = int(
    os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
)

TOP_K = int(os.getenv("TOP_K", "8"))
RERANK_K = int(os.getenv("RERANK_K", "5"))

MIN_EVIDENCE_SCORE = float(
    os.getenv("MIN_EVIDENCE_SCORE", "0.18")
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL", ""
)
