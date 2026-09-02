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
    # ── Credentials & secrets ──────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # API key for protecting all backend endpoints.
    # Required — there is no fallback. In production set this to a long
    # random string via the API_KEY env var:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    API_KEY: str = os.getenv("API_KEY", "").strip()

    # ── File storage ───────────────────────────────────────────────────────────
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads").strip()
    # Maximum allowed upload size in bytes (default: 10 MiB).
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", str(10 * 1024 * 1024)).strip())

    # ── Search / retrieval ─────────────────────────────────────────────────────
    SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "pgvector").lower().strip()  # pgvector | elasticsearch
    ELASTICSEARCH_URL: str = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200").strip()
    ELASTICSEARCH_INDEX: str = os.getenv("ELASTICSEARCH_INDEX", "pdf_chunks").strip()
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "384").strip())
    # TODO: Integrate external secret manager (e.g., Azure Key Vault) for production.

    # Comma-separated list, e.g. "http://localhost:5173,https://app.example.com"
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    def validate(self) -> None:
        # Ensure required env vars are present and non‑empty.
        if not self.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is missing or empty in environment variables")
        if not self.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is missing or empty in environment variables")
        if not self.API_KEY:
            raise RuntimeError("API_KEY is missing or empty in environment variables")
        if not self.CORS_ORIGINS:
            raise RuntimeError("CORS_ORIGINS is empty; please set at least one allowed origin")
        # Combining allow_credentials=True with a wildcard origin is invalid per
        # the CORS spec and is a security risk.
        if "*" in self.CORS_ORIGINS:
            raise RuntimeError(
                "CORS_ORIGINS must not contain '*' when allow_credentials=True. "
                "Specify exact origins instead."
            )

        if self.SEARCH_BACKEND not in {"pgvector", "elasticsearch"}:
            raise RuntimeError("SEARCH_BACKEND must be 'pgvector' or 'elasticsearch'")

        if self.SEARCH_BACKEND == "pgvector" and not PGVECTOR_AVAILABLE:
            raise RuntimeError("pgvector package not installed. Run: pip install pgvector")

        if self.SEARCH_BACKEND == "elasticsearch" and not ELASTICSEARCH_AVAILABLE:
            raise RuntimeError("elasticsearch package not installed. Run: pip install elasticsearch")


settings = Settings()
settings.validate()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
