import os
from typing import Callable, List, Optional
from rag.embeddings.embedding_service import embed_text
from rag.vectorstore.store import search, SearchResult
from rag.chunking.types import RecipeChunk

TOP_K = int(os.environ.get("TOP_K", "5"))
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.5"))


def retrieve(
    collection: str,
    query: str,
    top_k: Optional[int] = None,
    filter_fn: Optional[Callable[[RecipeChunk], bool]] = None,
) -> List[SearchResult]:
    query_embedding = embed_text(query)
    return search(collection, query_embedding, top_k=top_k or TOP_K, filter_fn=filter_fn)


def has_sufficient_evidence(results: List[SearchResult]) -> bool:
    """Backend grounding check: only proceed to generation when evidence clears the similarity threshold."""
    return len(results) > 0 and results[0].score >= SIMILARITY_THRESHOLD
