"""Application settings loaded from the environment."""
import os
from dotenv import load_dotenv

load_dotenv()


def _positive_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "")
    MAX_CONTENT_LENGTH = _positive_int("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001").strip()
    TOP_K = _positive_int("TOP_K", 3)
    CHUNK_SIZE = _positive_int("CHUNK_SIZE", 1200)
    CHUNK_OVERLAP = _positive_int("CHUNK_OVERLAP", 150)
    MAX_PAGES = _positive_int("MAX_PAGES", 500)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 4
