"""Retrieval over the Chroma collection."""
from typing import List, Tuple

from langchain_core.documents import Document

from rag.config import SIMILARITY_THRESHOLD, TOP_K
from rag.vectorstore.store import get_vectorstore


def retrieve(query: str, top_k: int = None) -> List[Tuple[Document, float]]:
    """Return [(document, similarity)] sorted best-first.

    similarity = 1 - cosine_distance, so 1.0 is an exact match and values near
    0 (or below) mean unrelated. The collection is created with cosine space
    (see vectorstore.store).
    """
    store = get_vectorstore()
    hits = store.similarity_search_with_score(query, k=top_k or TOP_K)
    return [(doc, 1.0 - float(distance)) for doc, distance in hits]


def has_sufficient_evidence(results: List[Tuple[Document, float]]) -> bool:
    """Grounding gate: only answer when the best hit clears the threshold."""
    return len(results) > 0 and results[0][1] >= SIMILARITY_THRESHOLD
