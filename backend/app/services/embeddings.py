"""
Text embeddings via sentence-transformers.
"""
from typing import List

from sentence_transformers import SentenceTransformer

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embeddings(texts: List[str]) -> List[List[float]]:
    arr = embedding_model.encode(texts)
    return [list(map(float, row)) for row in arr]
