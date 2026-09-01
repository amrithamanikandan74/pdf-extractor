"""
PDF text extraction and chunking.
"""
import re
from typing import Any, Dict, List

import fitz


def extract_text_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        pages.append({
            "page": i,
            "text": page.get_text("text", sort=True).strip()
        })
    return pages


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
