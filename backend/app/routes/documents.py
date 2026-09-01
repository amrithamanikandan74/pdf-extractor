"""
Document upload, listing, metadata, and per-document run history.
"""
import io
import json
import os
import re
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from app.config import settings
from app.db import Document, DocumentChunk, ExtractionRun, SessionLocal
from app.services.embeddings import get_embeddings
from app.services.extraction import backfill_payload_confidence, normalize_stored_result_payload, safe_json_loads
from app.services.pdf import chunk_text, extract_heading, extract_text_from_pdf
from app.services.retrieval import ensure_elasticsearch_index, es_client, index_chunks_to_elasticsearch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_UNSAFE_CHARS = re.compile(r'[^\w\s\.\-]')


def _safe_filename(name: str) -> str:
    """Strip directory separators and dangerous characters from a filename.

    Guards against path-traversal attacks such as filenames like
    ``../../app/main.py`` or ``../secret.pdf``.
    """
    # Take only the base filename — no directory components
    name = os.path.basename(name)
    # Replace any remaining unsafe characters with underscores
    name = _UNSAFE_CHARS.sub('_', name)
    # Collapse multiple dots to prevent extension tricks (e.g. file..pdf)
    name = re.sub(r'\.{2,}', '.', name)
    return name or 'upload.pdf'

router = APIRouter(tags=["documents"])


@router.get("/documents")
def list_documents():
    db = SessionLocal()
    try:
        docs = db.query(Document).order_by(Document.filename.asc()).all()
        return [{"id": d.id, "filename": d.filename} for d in docs]
    finally:
        db.close()


@router.get("/documents/{document_id}")
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


@router.get("/documents/{document_id}/file")
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


@router.get("/documents/{document_id}/chunks")
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


@router.get("/documents/{document_id}/runs")
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


@router.get("/documents/{document_id}/runs/by-schema/{schema_name}")
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


@router.post("/upload-pdf")
async def upload_pdf(pdf_file: UploadFile = File(...)):
    # ── Basic extension check (fast, cheap) ───────────────────────────────────
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await pdf_file.read()

    # ── Upload size limit ──────────────────────────────────────────────────────
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MiB.",
        )

    # ── MIME type validation (magic bytes, not just extension) ─────────────────
    try:
        import magic  # python-magic; see requirements.txt
        mime = magic.from_buffer(content, mime=True)
        if mime != "application/pdf":
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{mime}'. Only PDF files are accepted.",
            )
    except ImportError:
        # python-magic unavailable — fall back to PyMuPDF validation below
        logger.warning("python-magic not installed; skipping MIME validation")

    # ── Safe filename (path traversal prevention) ──────────────────────────────
    safe_name = _safe_filename(pdf_file.filename)
    pdf_file.file = io.BytesIO(content)

    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

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
                    index_chunks_to_elasticsearch(file_id, safe_name, es_chunks)
            except Exception as exc:
                # Do not fail PDF upload just because Elasticsearch is not running.
                # pgvector extraction can still work.
                logger.error("Elasticsearch indexing failed for document {}: {}", file_id, exc)

        return {
            "document_id": file_id,
            "filename": safe_name,
            "total_pages": len(pages),
            "total_chunks": len(all_chunks),
            "message": "PDF uploaded successfully"
        }
    finally:
        db.close()
