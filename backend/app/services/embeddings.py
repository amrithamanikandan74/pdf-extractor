"""
Text embeddings via fastembed (ONNX Runtime).

Deliberately NOT using sentence-transformers/torch here: importing torch and
loading a model that way commonly uses 400-600MB+ RAM, which exceeds
platforms like Render's free tier (512MB cap) and causes an OOM deploy
failure before the app can even start serving requests. fastembed runs the
same MiniLM-family model on ONNX Runtime with a much smaller footprint, and
the model is lazy-loaded on first use so app startup itself stays cheap.
"""
from typing import List

from fastembed import TextEmbedding

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        # BAAI/bge-small-en-v1.5 is a similarly-sized, ONNX-native model.
        # If you need embeddings from an existing pgvector column that was
        # populated with all-MiniLM-L6-v2 (384-dim), use
        # "sentence-transformers/all-MiniLM-L6-v2" instead so dimensions match.
        _model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return _model


def get_embeddings(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    return [list(map(float, row)) for row in model.embed(texts)]