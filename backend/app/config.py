"""
Environment-driven configuration.

Import `settings` from here rather than reading os.getenv() elsewhere,
so all configuration lives in one place.
"""
import os

from dotenv import load_dotenv

load_dotenv()

try:
    from pgvector.sqlalchemy import Vector  # noqa: F401
    PGVECTOR_AVAILABLE = True
except Exception:
    PGVECTOR_AVAILABLE = False

try:
    from elasticsearch import Elasticsearch  # noqa: F401
    ELASTICSEARCH_AVAILABLE = True
except Exception:
    ELASTICSEARCH_AVAILABLE = False


class Settings:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    UPLOAD_DIR: str = "uploads"

    SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "pgvector").lower()  # pgvector | elasticsearch
    ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    ELASTICSEARCH_INDEX: str = os.getenv("ELASTICSEARCH_INDEX", "pdf_chunks")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384"))

    # Comma-separated list, e.g. "http://localhost:5173,https://app.example.com"
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    def validate(self) -> None:
        if not self.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing in .env")

        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is missing in .env")

        if self.SEARCH_BACKEND not in {"pgvector", "elasticsearch"}:
            raise RuntimeError("SEARCH_BACKEND must be 'pgvector' or 'elasticsearch'")

        if self.SEARCH_BACKEND == "pgvector" and not PGVECTOR_AVAILABLE:
            raise RuntimeError("pgvector package not installed. Run: pip install pgvector")

        if self.SEARCH_BACKEND == "elasticsearch" and not ELASTICSEARCH_AVAILABLE:
            raise RuntimeError("elasticsearch package not installed. Run: pip install elasticsearch")


settings = Settings()
settings.validate()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
