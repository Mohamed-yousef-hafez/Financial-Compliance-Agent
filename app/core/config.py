import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

REPO_DATA_DIR = BASE_DIR / "data"
if os.getenv("VERCEL"):
    DATA_DIR = Path("/tmp/financial-compliance-data")
else:
    DATA_DIR = Path(os.getenv("DATA_DIR", str(REPO_DATA_DIR)))

SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL", "").strip()
TOP_K = int(os.getenv("TOP_K", "8"))
RERANK_K = int(os.getenv("RERANK_K", "5"))
MIN_EVIDENCE_SCORE = float(os.getenv("MIN_EVIDENCE_SCORE", "0.18"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
