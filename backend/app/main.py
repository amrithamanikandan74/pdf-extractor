
import json
import os
import uuid
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

import fitz
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from groq import Groq
from sentence_transformers import SentenceTransformer
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Optional imports
try:
    from pgvector.sqlalchemy import Vector
except Exception:
    Vector = None

try:
    from elasticsearch import Elasticsearch
except Exception:
    Elasticsearch = None

load_dotenv()

# ========================
# Setup
# ========================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
UPLOAD_DIR = "uploads"

SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "pgvector").lower()  # pgvector | elasticsearch
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX", "pdf_chunks")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing in .env")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in .env")

if SEARCH_BACKEND not in {"pgvector", "elasticsearch"}:
    raise RuntimeError("SEARCH_BACKEND must be 'pgvector' or 'elasticsearch'")

if SEARCH_BACKEND == "pgvector" and Vector is None:
    raise RuntimeError("pgvector package not installed. Run: pip install pgvector")

if SEARCH_BACKEND == "elasticsearch" and Elasticsearch is None:
    raise RuntimeError("elasticsearch package not installed. Run: pip install elasticsearch")

os.makedirs(UPLOAD_DIR, exist_ok=True)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

app = FastAPI(title="Whole Run PDF Extraction")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_client = Groq(api_key=GROQ_API_KEY)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

es_client = Elasticsearch(ELASTICSEARCH_URL) if Elasticsearch is not None else None


# ========================
# DB Models
# ========================
class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    extracted_text = Column(Text, nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String, nullable=True)
    chunk_text = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True)

    # keep pgvector column only if package exists
    if Vector is not None:
        embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    document = relationship("Document", back_populates="chunks")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    document_filename = Column(String, nullable=False)
    schema_name = Column(String, nullable=False)
    schema_hash = Column(String, nullable=False)
    schema_json = Column(Text, nullable=False)
    extracted_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ========================
# Startup helpers
# ========================
def ensure_pgvector_and_columns() -> None:
    """
    Ensure pgvector extension exists and add vector column if missing.
    This avoids 'column document_chunks.embedding does not exist'.
    """
    if Vector is None:
        return

    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass

        try:
            conn.execute(text(f"ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})"))
        except Exception:
            # table may not exist yet on first run; Base.metadata.create_all will create it
            pass

        try:
            conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_json TEXT"))
        except Exception:
            pass


def ensure_elasticsearch_index() -> None:
    if es_client is None:
        return

    if not es_client.indices.exists(index=ELASTICSEARCH_INDEX):
        es_client.indices.create(
            index=ELASTICSEARCH_INDEX,
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
                        "dims": EMBEDDING_DIM,
                        "index": True,
                        "similarity": "cosine",
                    },
                }
            },
        )


ensure_pgvector_and_columns()
Base.metadata.create_all(bind=engine)
if es_client is not None:
    try:
        if es_client.ping():
            ensure_elasticsearch_index()
    except Exception:
        pass


# ========================
# Helpers
# ========================
def hash_schema(schema: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()


def chunk_text(text: str, chunk_size: int = 1500) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue

        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence.strip()

    if current:
        chunks.append(current)

    return chunks


def extract_heading(page_text: str) -> str:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    return lines[0][:200] if lines else ""


def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        pages.append({
            "page": i,
            "text": page.get_text("text", sort=True).strip()
        })
    return pages


def get_embeddings(texts: List[str]) -> List[List[float]]:
    arr = embedding_model.encode(texts)
    return [list(map(float, row)) for row in arr]


def normalize_json_response(text_response: str) -> str:
    text_response = text_response.strip()
    if text_response.startswith("```"):
        text_response = text_response.replace("```json", "").replace("```", "").strip()

    start = text_response.find("{")
    end = text_response.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text_response[start:end + 1]
    return text_response


def build_empty_output(fields: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for field_name, field_def in fields.items():
        field_type = field_def.get("type", "string")
        if field_type == "string":
            result[field_name] = ""
        elif field_type == "number":
            result[field_name] = 0
        elif field_type == "boolean":
            result[field_name] = False
        elif field_type == "array":
            result[field_name] = []
        elif field_type == "object":
            result[field_name] = {}
        else:
            result[field_name] = ""
    return result


def normalize_for_confidence(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text_value = value
    elif isinstance(value, (int, float, bool)):
        text_value = str(value)
    else:
        text_value = json.dumps(value, ensure_ascii=False)

    text_value = text_value.lower()
    text_value = re.sub(r"[^a-z0-9\s]", " ", text_value)
    text_value = re.sub(r"\s+", " ", text_value).strip()
    return text_value


def calculate_match_confidence(extracted_value: Any, chunk_text_value: str) -> float:
    extracted = normalize_for_confidence(extracted_value)
    chunk_text_value = normalize_for_confidence(chunk_text_value)

    if not extracted:
        return 0.0

    if extracted in chunk_text_value:
        return 1.0

    extracted_tokens = extracted.split()
    if not extracted_tokens:
        return 0.0

    chunk_token_set = set(chunk_text_value.split())
    matched_count = sum(1 for token in extracted_tokens if token in chunk_token_set)
    confidence = matched_count / len(extracted_tokens)
    return round(confidence, 4)


def backfill_payload_confidence(document_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    db = SessionLocal()
    try:
        chunks = (
            db.query(DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.chunk_index, DocumentChunk.page_number, DocumentChunk.heading, DocumentChunk.chunk_text)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        chunk_lookup: Dict[int, Dict[str, Any]] = {}
        for chunk in chunks:
            chunk_lookup[int(chunk.chunk_index)] = {
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "heading": chunk.heading,
                "chunk_text": chunk.chunk_text,
            }

        result_data = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
        sources = payload.get("sources", {}) if isinstance(payload.get("sources", {}), dict) else {}

        enriched_sources: Dict[str, List[Dict[str, Any]]] = {}
        for field_name, refs in sources.items():
            field_value = result_data.get(field_name)
            enriched_refs: List[Dict[str, Any]] = []
            if not isinstance(refs, list):
                refs = []

            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                chunk_index = ref.get("chunk_index")
                if chunk_index is None:
                    continue
                try:
                    chunk_index_int = int(chunk_index)
                except (TypeError, ValueError):
                    continue

                chunk = chunk_lookup.get(chunk_index_int)
                if not chunk:
                    continue

                confidence = ref.get("confidence")
                if confidence is None:
                    confidence = calculate_match_confidence(field_value, chunk.get("chunk_text", ""))

                enriched_refs.append({
                    "chunk_index": chunk_index_int,
                    "page_number": ref.get("page_number", chunk.get("page_number")),
                    "heading": ref.get("heading", chunk.get("heading")),
                    "chunk_text": chunk.get("chunk_text", ""),
                    "confidence": round(float(confidence), 4),
                })

            enriched_sources[field_name] = enriched_refs

        payload["sources"] = enriched_sources

        if isinstance(payload.get("used_chunks"), list):
            enriched_used_chunks = []
            for item in payload["used_chunks"]:
                if not isinstance(item, dict):
                    continue
                chunk_index = item.get("chunk_index")
                if chunk_index is None:
                    continue
                try:
                    chunk_index_int = int(chunk_index)
                except (TypeError, ValueError):
                    continue
                chunk = chunk_lookup.get(chunk_index_int)
                if not chunk:
                    continue
                enriched_used_chunks.append({
                    "chunk_index": chunk_index_int,
                    "page_number": item.get("page_number", chunk.get("page_number")),
                    "heading": item.get("heading", chunk.get("heading")),
                    "chunk_text": item.get("chunk_text", chunk.get("chunk_text", "")),
                })
            payload["used_chunks"] = enriched_used_chunks

        return payload
    finally:
        db.close()


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


# ========================
# Retrieval backends
# ========================
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
            index=ELASTICSEARCH_INDEX,
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


# ========================
# Extraction
# ========================
def run_whole_extraction(schema: Dict[str, Any], context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    formatted_context = "\n\n".join(
        [
            f"[Chunk {c['chunk_index']} | Page {c['page_number']} | Heading: {c['heading']}]\n{c['chunk_text']}"
            for c in context_chunks
        ]
    )

    empty_output = build_empty_output(schema.get("fields", {}))

    prompt = f"""
Extract data from the PDF context and return ONLY valid JSON.

Schema:
{json.dumps(schema, indent=2, ensure_ascii=False)}

Return output in this exact format:
{{
  "result": {{
    ...
  }},
  "sources": {{
    "field_name": [
      {{
        "chunk_index": 0,
        "page_number": 1,
        "heading": "..."
      }}
    ]
  }}
}}

Rules:
- Follow the schema exactly
- Use each field's description carefully
- Do not add extra fields
- Extract complete information for each field
- Do NOT shorten content
- Do NOT give partial sentences
- Extract FULL paragraphs completely (especially introduction and summary)
- If the content is long, return the FULL content, do not cut it
- For arrays, include ALL points (do not skip any)
- For array fields, return complete items, not cut or truncated phrases
- Do not include duplicate or repeated items
- If two items convey the same meaning, keep only one
- Ensure no important items are missed if present in the document
- Extract content only from the chunks most relevant to each field
- Do not mix unrelated nearby content
- If information is spread across multiple chunks, combine it into one complete answer
- Ensure summary is COMPLETE paragraph (not starting fragment)
- If a value is not clearly found, use this empty default structure:
{json.dumps(empty_output, ensure_ascii=False)}
- Return ONLY valid JSON
- Do not include markdown
- Do not include explanation

Relevant PDF Chunks:
{formatted_context}
"""

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You extract structured data from PDF chunks and return only valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=2500
    )

    text_response = response.choices[0].message.content.strip()
    text_response = normalize_json_response(text_response)
    parsed = json.loads(text_response)

    if "result" not in parsed:
        parsed["result"] = empty_output
    if "sources" not in parsed or not isinstance(parsed["sources"], dict):
        parsed["sources"] = {}

    chunk_lookup = {int(chunk["chunk_index"]): chunk for chunk in context_chunks}
    extracted_result = parsed.get("result", {}) if isinstance(parsed.get("result", {}), dict) else {}

    enriched_sources: Dict[str, List[Dict[str, Any]]] = {}
    for field_name, refs in parsed["sources"].items():
        enriched_refs: List[Dict[str, Any]] = []
        field_value = extracted_result.get(field_name)

        if not isinstance(refs, list):
            refs = []

        for ref in refs:
            if not isinstance(ref, dict):
                continue

            chunk_index = ref.get("chunk_index")
            if chunk_index is None:
                continue

            try:
                chunk = chunk_lookup.get(int(chunk_index))
            except (TypeError, ValueError):
                chunk = None
            if not chunk:
                continue

            confidence = calculate_match_confidence(field_value, chunk.get("chunk_text", ""))

            enriched_refs.append({
                "chunk_index": chunk["chunk_index"],
                "page_number": ref.get("page_number", chunk.get("page_number")),
                "heading": ref.get("heading", chunk.get("heading")),
                "chunk_text": chunk.get("chunk_text", ""),
                "confidence": round(float(confidence), 4),
            })

        enriched_sources[field_name] = enriched_refs

    parsed["sources"] = enriched_sources
    return parsed


def flatten_dict(data: Any, parent_key: str = "") -> Dict[str, Any]:
    items: Dict[str, Any] = {}

    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}.{key}" if parent_key else key
            if isinstance(value, dict):
                items.update(flatten_dict(value, new_key))
            else:
                items[new_key] = value
    else:
        items[parent_key] = data

    return items


def safe_json_loads(text_value: str, fallback: Any) -> Any:
    try:
        return json.loads(text_value)
    except Exception:
        return fallback


def normalize_stored_result_payload(parsed_payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(parsed_payload, dict):
        return {
            "document_id": None,
            "document_filename": None,
            "schema_name": None,
            "result": {},
            "sources": {},
            "used_chunks": [],
        }

    return {
        "document_id": parsed_payload.get("document_id"),
        "document_filename": parsed_payload.get("document_filename"),
        "schema_name": parsed_payload.get("schema_name"),
        "result": parsed_payload.get("result", {}),
        "sources": parsed_payload.get("sources", {}),
        "used_chunks": parsed_payload.get("used_chunks", []),
    }


def compare_extraction_payloads(run1_payload: Dict[str, Any], run2_payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    run1_result = flatten_dict(run1_payload.get("result", {}))
    run2_result = flatten_dict(run2_payload.get("result", {}))

    all_fields = sorted(set(run1_result.keys()) | set(run2_result.keys()))
    comparison = []
    matched = 0
    mismatched = 0

    run1_sources = run1_payload.get("sources", {})
    run2_sources = run2_payload.get("sources", {})

    for field in all_fields:
        run1_value = run1_result.get(field)
        run2_value = run2_result.get(field)

        status = "match" if run1_value == run2_value else "mismatch"
        if status == "match":
            matched += 1
        else:
            mismatched += 1

        comparison.append(
            {
                "field": field,
                "run1_value": run1_value,
                "run2_value": run2_value,
                "status": status,
                "run1_source": run1_sources.get(field, []),
                "run2_source": run2_sources.get(field, []),
            }
        )

    total_fields = len(all_fields)
    accuracy_percentage = round((matched / total_fields) * 100, 2) if total_fields else 100.0

    summary = {
        "total_fields": total_fields,
        "matched": matched,
        "mismatched": mismatched,
        "accuracy_percentage": accuracy_percentage,
    }

    return comparison, summary


# ========================
# Elasticsearch indexing helper
# ========================
def index_chunks_to_elasticsearch(document_id: str, filename: str, chunks: List[Dict[str, Any]]) -> None:
    if es_client is None:
        return

    operations = []
    for chunk in chunks:
        operations.append({
            "index": {
                "_index": ELASTICSEARCH_INDEX,
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


# ========================
# Core Routes
# ========================
@app.get("/")
def home():
    return {
        "message": "Backend is running",
        "default_search_backend": SEARCH_BACKEND,
        "elasticsearch_available": bool(es_client is not None and es_client.ping()) if es_client is not None else False,
    }


@app.get("/status")
def status():
    es_available = False
    if es_client is not None:
        try:
            es_available = es_client.ping()
        except Exception:
            es_available = False

    return {
        "message": "Backend is running",
        "default_search_backend": SEARCH_BACKEND,
        "search_backend": SEARCH_BACKEND,
        "elasticsearch_available": es_available,
        "pgvector_available": Vector is not None,
    }


@app.get("/documents")
def list_documents():
    db = SessionLocal()
    try:
        docs = db.query(Document).order_by(Document.filename.asc()).all()
        return [{"id": d.id, "filename": d.filename} for d in docs]
    finally:
        db.close()


@app.get("/documents/{document_id}")
def get_document(document_id: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_path": doc.file_path,
            "extracted_text": doc.extracted_text
        }
    finally:
        db.close()


@app.get("/documents/{document_id}/file")
def get_document_file(document_id: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        if not os.path.exists(doc.file_path):
            raise HTTPException(status_code=404, detail="PDF file not found on server")

        safe_filename = doc.filename.replace('"', '')

        return FileResponse(
            path=doc.file_path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{safe_filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        db.close()


@app.get("/documents/{document_id}/chunks")
def get_document_chunks(document_id: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = (
            db.query(DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.chunk_index, DocumentChunk.page_number, DocumentChunk.heading, DocumentChunk.chunk_text)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )

        return {
            "document_id": document_id,
            "filename": doc.filename,
            "chunks": [
                {
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                    "heading": c.heading,
                    "chunk_text": c.chunk_text,
                    "retrieval_confidence": None
                }
                for c in chunks
            ]
        }
    finally:
        db.close()


@app.get("/documents/{document_id}/runs")
def get_document_runs(document_id: str):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        runs = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.document_id == document_id)
            .order_by(ExtractionRun.created_at.desc())
            .all()
        )

        output = []
        for run in runs:
            parsed = normalize_stored_result_payload(safe_json_loads(run.extracted_json, {}))
            parsed = backfill_payload_confidence(run.document_id, parsed)
            output.append(
                {
                    "run_id": run.id,
                    "document_id": run.document_id,
                    "document_filename": run.document_filename,
                    "schema_name": run.schema_name,
                    "backend": parsed.get("backend"),
                    "created_at": run.created_at.isoformat(),
                    "result": parsed.get("result", {}),
                    "sources": parsed.get("sources", {}),
                    "used_chunks": parsed.get("used_chunks", []),
                }
            )

        return {
            "document_id": document_id,
            "filename": doc.filename,
            "total_runs": len(output),
            "runs": output,
        }
    finally:
        db.close()


@app.get("/documents/{document_id}/runs/by-schema/{schema_name}")
def get_document_run_by_schema(document_id: str, schema_name: str):
    db = SessionLocal()
    try:
        run = (
            db.query(ExtractionRun)
            .filter(
                ExtractionRun.document_id == document_id,
                ExtractionRun.schema_name == schema_name,
            )
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )

        if not run:
            raise HTTPException(status_code=404, detail="No extraction found for this schema")

        parsed = normalize_stored_result_payload(safe_json_loads(run.extracted_json, {}))

        return {
            "already_exists": True,
            "run_id": run.id,
            "document_id": run.document_id,
            "document_filename": run.document_filename,
            "schema_name": run.schema_name,
            "created_at": run.created_at.isoformat(),
            "result": parsed,
        }
    finally:
        db.close()


@app.post("/set-backend")
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


@app.post("/upload-pdf")
async def upload_pdf(pdf_file: UploadFile = File(...)):
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{pdf_file.filename}")

    with open(file_path, "wb") as f:
        f.write(await pdf_file.read())

    pages = extract_text_from_pdf(file_path)
    combined_text = "\n\n".join([f"Page {p['page']}:\n{p['text']}" for p in pages if p["text"].strip()])

    if not combined_text.strip():
        raise HTTPException(status_code=400, detail="No text extracted from PDF")

    all_chunks = []
    all_chunk_meta = []

    for page in pages:
        page_text = page["text"]
        page_chunks = chunk_text(page_text)
        heading = extract_heading(page_text)

        for ch in page_chunks:
            all_chunks.append(ch)
            all_chunk_meta.append({
                "page_number": page["page"],
                "heading": heading,
            })

    embeddings = get_embeddings(all_chunks)

    db = SessionLocal()
    try:
        doc = Document(
            id=file_id,
            filename=pdf_file.filename,
            file_path=file_path,
            extracted_text=combined_text
        )
        db.add(doc)

        es_chunks = []

        for idx, (chunk, emb, meta) in enumerate(zip(all_chunks, embeddings, all_chunk_meta)):
            db.add(
                DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=file_id,
                    chunk_index=idx,
                    page_number=meta["page_number"],
                    heading=meta["heading"],
                    chunk_text=chunk,
                    embedding_json=json.dumps(emb),
                    embedding=emb,
                )
            )

            es_chunks.append({
                "chunk_index": idx,
                "page_number": meta["page_number"],
                "heading": meta["heading"],
                "chunk_text": chunk,
                "embedding": emb,
            })

        db.commit()

        # Index into Elasticsearch when Elasticsearch is available.
        # This lets the UI choose Elasticsearch later for the same uploaded PDF.
        if es_client is not None:
            try:
                if es_client.ping():
                    ensure_elasticsearch_index()
                    index_chunks_to_elasticsearch(file_id, pdf_file.filename, es_chunks)
            except Exception:
                # Do not fail PDF upload just because Elasticsearch is not running.
                # pgvector extraction can still work.
                pass

        return {
            "document_id": file_id,
            "filename": pdf_file.filename,
            "total_pages": len(pages),
            "total_chunks": len(all_chunks),
            "message": "PDF uploaded successfully"
        }
    finally:
        db.close()


@app.post("/extract-run/{document_id}")
async def extract_run(
    document_id: str,
    schema_file: UploadFile = File(...),
    backend: str = Form("pgvector"),
):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        selected_backend = (backend or "pgvector").lower().strip()
        if selected_backend not in {"pgvector", "elasticsearch"}:
            raise HTTPException(status_code=400, detail="backend must be 'pgvector' or 'elasticsearch'")

        raw_schema = await schema_file.read()
        try:
            schema = json.loads(raw_schema)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid schema JSON file")

        schema_name = schema.get("schema_name", "default_schema")
        schema_hash = hash_schema({"schema": schema, "backend": selected_backend})

        existing = db.query(ExtractionRun).filter(
            ExtractionRun.document_id == document_id,
            ExtractionRun.schema_hash == schema_hash
        ).order_by(ExtractionRun.created_at.desc()).first()

        if existing:
            existing_payload = normalize_stored_result_payload(safe_json_loads(existing.extracted_json, {}))
            existing_payload = backfill_payload_confidence(document_id, existing_payload)
            return {
                "message": "Extraction already exists",
                "already_exists": True,
                "reused": True,
                "run_id": existing.id,
                "document_id": existing.document_id,
                "document_filename": existing.document_filename,
                "schema_name": existing.schema_name,
                "backend": selected_backend,
                "created_at": existing.created_at.isoformat(),
                "result": existing_payload,
            }

        context_chunks = retrieve_relevant_chunks(document_id, schema, backend=selected_backend, top_k_per_field=12)
        extraction = run_whole_extraction(schema, context_chunks)

        payload = {
            "document_id": document_id,
            "document_filename": doc.filename,
            "schema_name": schema_name,
            "backend": selected_backend,
            "result": extraction.get("result", {}),
            "sources": extraction.get("sources", {}),
            "used_chunks": context_chunks
        }

        run = ExtractionRun(
            id=str(uuid.uuid4()),
            document_id=document_id,
            document_filename=doc.filename,
            schema_name=schema_name,
            schema_hash=schema_hash,
            schema_json=json.dumps(schema, ensure_ascii=False),
            extracted_json=json.dumps(payload, ensure_ascii=False),
        )

        db.add(run)
        db.commit()

        return {
            "message": "Extraction created",
            "already_exists": False,
            "reused": False,
            "run_id": run.id,
            "document_id": run.document_id,
            "document_filename": run.document_filename,
            "schema_name": run.schema_name,
            "backend": selected_backend,
            "created_at": run.created_at.isoformat(),
            "result": payload
        }
    finally:
        db.close()


@app.get("/runs")
def list_all_runs() -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        runs = (
            db.query(ExtractionRun)
            .order_by(ExtractionRun.created_at.desc())
            .all()
        )

        output = []
        for r in runs:
            parsed = normalize_stored_result_payload(safe_json_loads(r.extracted_json, {}))
            parsed = backfill_payload_confidence(r.document_id, parsed)
            output.append(
                {
                    "run_id": r.id,
                    "document_id": r.document_id,
                    "document_filename": r.document_filename,
                    "schema_name": r.schema_name,
                    "backend": parsed.get("backend"),
                    "created_at": r.created_at.isoformat(),
                    "result": parsed,
                }
            )
        return output
    finally:
        db.close()


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        return {
            "run_id": run.id,
            "document_id": run.document_id,
            "document_filename": run.document_filename,
            "schema_name": run.schema_name,
            "backend": normalize_stored_result_payload(safe_json_loads(run.extracted_json, {})).get("backend"),
            "created_at": run.created_at.isoformat(),
            "schema_json": safe_json_loads(run.schema_json, {}),
            "result": backfill_payload_confidence(
                run.document_id,
                normalize_stored_result_payload(safe_json_loads(run.extracted_json, {}))
            ),
        }
    finally:
        db.close()


@app.get("/compare-runs/{run1_id}/{run2_id}")
def compare_runs(run1_id: str, run2_id: str):
    db = SessionLocal()
    try:
        run1 = db.query(ExtractionRun).filter(ExtractionRun.id == run1_id).first()
        run2 = db.query(ExtractionRun).filter(ExtractionRun.id == run2_id).first()

        if not run1:
            raise HTTPException(status_code=404, detail="Run 1 not found")
        if not run2:
            raise HTTPException(status_code=404, detail="Run 2 not found")

        run1_payload = normalize_stored_result_payload(safe_json_loads(run1.extracted_json, {}))
        run2_payload = normalize_stored_result_payload(safe_json_loads(run2.extracted_json, {}))

        comparison, summary = compare_extraction_payloads(run1_payload, run2_payload)

        return {
            "run1": {
                "run_id": run1.id,
                "document_id": run1.document_id,
                "document_filename": run1.document_filename,
                "schema_name": run1.schema_name,
                "created_at": run1.created_at.isoformat(),
            },
            "run2": {
                "run_id": run2.id,
                "document_id": run2.document_id,
                "document_filename": run2.document_filename,
                "schema_name": run2.schema_name,
                "created_at": run2.created_at.isoformat(),
            },
            "comparison": comparison,
            "summary": summary,
        }
    finally:
        db.close()

@app.post("/search/{document_id}")
def search_document(document_id: str, query: str, backend: str = "pgvector"):
    db = SessionLocal()
    try:
        # Check document
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Create temporary schema using user question
        fake_schema = {
            "fields": {
                "answer": {
                    "type": "string",
                    "description": query
                }
            }
        }

        # Retrieve relevant chunks
        chunks = retrieve_relevant_chunks(
            document_id=document_id,
            schema=fake_schema,
            backend=backend,
            top_k_per_field=5
        )

        # Return best chunk as answer
        answer = ""
        if chunks:
            answer = chunks[0].get("chunk_text", "")

        return {
            "document_id": document_id,
            "filename": doc.filename,
            "query": query,
            "backend": backend,
            "answer": answer,
            "results": chunks
        }

    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
