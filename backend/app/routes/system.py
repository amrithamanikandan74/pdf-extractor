"""
Health check and search-backend selection endpoints.
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.services.retrieval import ensure_elasticsearch_index, es_client

router = APIRouter(tags=["system"])


@router.get("/")
def home():
    return {
        "message": "Backend is running",
        "default_search_backend": settings.SEARCH_BACKEND,
        "elasticsearch_available": bool(es_client is not None and es_client.ping()) if es_client is not None else False,
    }


@router.get("/status")
def status():
    es_available = False
    if es_client is not None:
        try:
            es_available = es_client.ping()
        except Exception:
            es_available = False

    from app.db import Vector  # local import avoids a hard dependency for callers that don't need it

    return {
        "message": "Backend is running",
        "default_search_backend": settings.SEARCH_BACKEND,
        "search_backend": settings.SEARCH_BACKEND,
        "elasticsearch_available": es_available,
        "pgvector_available": Vector is not None,
    }


@router.post("/set-backend")
async def set_backend(payload: Dict[str, Any]):
    backend = str(payload.get("backend", "pgvector")).lower().strip()
    if backend not in {"pgvector", "elasticsearch"}:
        raise HTTPException(status_code=400, detail="backend must be 'pgvector' or 'elasticsearch'")

    if backend == "elasticsearch":
        if es_client is None:
            raise HTTPException(status_code=500, detail="Elasticsearch package is not installed")
        try:
            if not es_client.ping():
                raise HTTPException(status_code=503, detail="Elasticsearch is not running or not reachable")
            ensure_elasticsearch_index()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Elasticsearch connection failed: {str(e)}")

    return {
        "message": "Backend selection accepted",
        "search_backend": backend,
    }
