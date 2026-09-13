from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

TOP_K = 8
RERANK_K = 5
MIN_EVIDENCE_SCORE = 0.18