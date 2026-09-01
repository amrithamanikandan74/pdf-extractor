"""
Schema-based extraction runs, run history, run comparison, and ad-hoc search.
"""
import json
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.db import Document, ExtractionRun, SessionLocal
from app.services.extraction import (
    backfill_payload_confidence,
    compare_extraction_payloads,
    hash_schema,
    normalize_stored_result_payload,
    run_whole_extraction,
    safe_json_loads,
)
from app.services.retrieval import retrieve_relevant_chunks

router = APIRouter(tags=["extraction"])


@router.post("/extract-run/{document_id}")
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


@router.get("/runs")
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


@router.get("/runs/{run_id}")
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


@router.get("/compare-runs/{run1_id}/{run2_id}")
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


@router.post("/search/{document_id}")
def search_document(document_id: str, query: str, backend: str = "pgvector"):
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        fake_schema = {
            "fields": {
                "answer": {
                    "type": "string",
                    "description": query
                }
            }
        }

        chunks = retrieve_relevant_chunks(
            document_id=document_id,
            schema=fake_schema,
            backend=backend,
            top_k_per_field=5
        )

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
