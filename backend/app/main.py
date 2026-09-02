import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.db import Base, engine, ensure_extraction_run_columns, ensure_pgvector_and_columns
from app.routes import documents, extraction, system
from app.services.retrieval import ensure_elasticsearch_index, es_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    # DB/ES calls live here (not at import time) so importing this module —
    # e.g. from a test runner or linter — doesn't require a live database.
    ensure_pgvector_and_columns()
    ensure_extraction_run_columns()
    Base.metadata.create_all(bind=engine)
    if es_client is not None:
        try:
            if es_client.ping():
                ensure_elasticsearch_index()
        except Exception as exc:
            # Elasticsearch is optional; log the error but don't abort startup.
            logger.warning("Elasticsearch unavailable at startup: {}", exc)
    yield


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
# NOTE: auth is applied per-router (see app/routes/*.py), not globally here.
# /documents/{id}/file is deliberately left unauthenticated — the frontend
# loads it via <iframe src=...>, which cannot send a custom X-API-Key
# header, and the id itself is an unguessable UUID.
app = FastAPI(
    title="Whole Run PDF Extraction",
    lifespan=lifespan,
)

# Optional HTTPS redirect — enable in production by setting FORCE_HTTPS=true
if os.getenv("FORCE_HTTPS", "false").lower() == "true":
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please slow down."})


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(system.router)
app.include_router(documents.router)
app.include_router(documents.public_router)
app.include_router(extraction.router)


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
