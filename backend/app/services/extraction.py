"""
Schema-driven extraction via Groq, plus the confidence-scoring and
run-comparison helpers built on top of it.
"""
import hashlib
import json
import re
from typing import Any, Dict, List, Tuple

from groq import Groq

from app.config import settings
from app.db import DocumentChunk, SessionLocal

groq_client = Groq(api_key=settings.GROQ_API_KEY)


def hash_schema(schema: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()


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
