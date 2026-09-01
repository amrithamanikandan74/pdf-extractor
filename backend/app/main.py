"""
FastAPI application entrypoint.

All actual logic lives in app/db.py, app/services/*, and app/routes/* —
this module just wires them together.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, engine, ensure_pgvector_and_columns
from app.routes import documents, extraction, system
from app.services.retrieval import ensure_elasticsearch_index, es_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    # DB/ES calls live here (not at import time) so importing this module —
    # e.g. from a test runner or linter — doesn't require a live database.
    ensure_pgvector_and_columns()
    Base.metadata.create_all(bind=engine)
    if es_client is not None:
        try:
            if es_client.ping():
                ensure_elasticsearch_index()
        except Exception:
            pass
    yield


app = FastAPI(title="Whole Run PDF Extraction", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(documents.router)
app.include_router(extraction.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
