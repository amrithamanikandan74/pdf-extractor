"""
Chunk retrieval — pgvector (Postgres) and Elasticsearch backends.
"""
from typing import Any, Dict, List

from fastapi import HTTPException

from app.config import settings
from app.db import DocumentChunk, SessionLocal
from app.services.embeddings import get_embeddings

try:
    from elasticsearch import Elasticsearch
except Exception:
    Elasticsearch = None

es_client = Elasticsearch(settings.ELASTICSEARCH_URL) if Elasticsearch is not None else None


def ensure_elasticsearch_index() -> None:
    if es_client is None:
        return

    if not es_client.indices.exists(index=settings.ELASTICSEARCH_INDEX):
        es_client.indices.create(
            index=settings.ELASTICSEARCH_INDEX,
            mappings={
                "properties": {
                    "document_id": {"type": "keyword"},
                    "filename": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "page_number": {"type": "integer"},
                    "heading": {"type": "text"},
                    "chunk_text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": settings.EMBEDDING_DIM,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )


def index_chunks_to_elasticsearch(document_id: str, filename: str, chunks: List[Dict[str, Any]]) -> None:
    if es_client is None:
        return

    operations = []
    for chunk in chunks:
        operations.append({
            "index": {
                "_index": settings.ELASTICSEARCH_INDEX,
                "_id": f"{document_id}_{chunk['chunk_index']}",
            }
        })
        operations.append({
            "document_id": document_id,
            "filename": filename,
            "chunk_index": chunk["chunk_index"],
            "page_number": chunk["page_number"],
            "heading": chunk["heading"],
            "chunk_text": chunk["chunk_text"],
            "embedding": chunk["embedding"],
        })

    if operations:
        es_client.bulk(operations=operations, refresh=True)


def _build_retrieval_query(field_name: str, description: str) -> str:
    return f"""
    Find the most relevant content in the PDF for this field.

    Field name: {field_name}
    Field description: {description}

    Rules:
    - Retrieve complete and relevant content
    - Prefer chunks that directly explain this field
    - Include lists, bullet points, and detailed explanations if relevant
    - Avoid unrelated nearby content
    - Combine information if the answer appears in multiple chunks
    """.strip()


def retrieve_relevant_chunks_pgvector(document_id: str, schema: Dict[str, Any], top_k_per_field: int = 12) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        selected_map: Dict[int, Dict[str, Any]] = {}
        fields = schema.get("fields", {})

        for field_name, field_def in fields.items():
            description = field_def.get("description", "")
            query = _build_retrieval_query(field_name, description)
            query_embedding = get_embeddings([query])[0]

            rows = (
                db.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .filter(DocumentChunk.embedding.is_not(None))
                .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
                .limit(top_k_per_field)
                .all()
            )

            for rank, row in enumerate(rows):
                key = row.chunk_index
                score = round(1.0 / (rank + 1), 4)

                if key not in selected_map:
                    selected_map[key] = {
                        "chunk_index": row.chunk_index,
                        "page_number": row.page_number,
                        "heading": row.heading,
                        "chunk_text": row.chunk_text,
                        "retrieval_confidence": score,
                        "field_scores": {field_name: score},
                    }
                else:
                    selected_map[key]["retrieval_confidence"] = max(
                        float(selected_map[key].get("retrieval_confidence", 0.0)),
                        score,
                    )
                    selected_map[key].setdefault("field_scores", {})[field_name] = score

        return sorted(selected_map.values(), key=lambda item: item["chunk_index"])
    finally:
        db.close()


def retrieve_relevant_chunks_elasticsearch(document_id: str, schema: Dict[str, Any], top_k_per_field: int = 12) -> List[Dict[str, Any]]:
    if es_client is None:
        raise RuntimeError("Elasticsearch client is not initialized")

    selected_map: Dict[int, Dict[str, Any]] = {}
    fields = schema.get("fields", {})

    for field_name, field_def in fields.items():
        description = field_def.get("description", "")
        query = _build_retrieval_query(field_name, description)
        query_embedding = get_embeddings([query])[0]

        response = es_client.search(
            index=settings.ELASTICSEARCH_INDEX,
            knn={
                "field": "embedding",
                "query_vector": query_embedding,
                "k": top_k_per_field,
                "num_candidates": max(top_k_per_field * 3, 20),
                "filter": {
                    "term": {
                        "document_id": document_id
                    }
                }
            },
            size=top_k_per_field
        )

        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            chunk_index = int(source["chunk_index"])
            score = round(float(hit["_score"]), 4)

            if chunk_index not in selected_map:
                selected_map[chunk_index] = {
                    "chunk_index": chunk_index,
                    "page_number": source.get("page_number"),
                    "heading": source.get("heading"),
                    "chunk_text": source.get("chunk_text", ""),
                    "retrieval_confidence": score,
                    "field_scores": {field_name: score},
                }
            else:
                selected_map[chunk_index]["retrieval_confidence"] = max(
                    float(selected_map[chunk_index].get("retrieval_confidence", 0.0)),
                    score,
                )
                selected_map[chunk_index].setdefault("field_scores", {})[field_name] = score

    return sorted(selected_map.values(), key=lambda item: item["chunk_index"])


def retrieve_relevant_chunks(
    document_id: str,
    schema: Dict[str, Any],
    backend: str = "pgvector",
    top_k_per_field: int = 12,
) -> List[Dict[str, Any]]:
    """
    Select retrieval backend per extraction request.
    The frontend sends backend=pgvector or backend=elasticsearch.
    """
    selected_backend = (backend or "pgvector").lower().strip()

    if selected_backend not in {"pgvector", "elasticsearch"}:
        raise HTTPException(status_code=400, detail="backend must be 'pgvector' or 'elasticsearch'")

    if selected_backend == "elasticsearch":
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
        return retrieve_relevant_chunks_elasticsearch(document_id, schema, top_k_per_field)

    return retrieve_relevant_chunks_pgvector(document_id, schema, top_k_per_field)
