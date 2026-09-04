"""BM25 keyword search over the indexed corpus.

Dense embeddings compress a whole chunk into one vector, so a single rare
token (a batch code, an exact recipe title, an uncommon ingredient name) can
get diluted by the surrounding prose and rank lower than it should. BM25
scores exact term overlap directly and gives rare tokens a large IDF boost,
which is exactly what's missing from pure semantic search - see
rag/retrieval/retriever.py for how the two are fused.
"""
import re
from functools import lru_cache
from typing import List, Tuple

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from rag.vectorstore.store import get_vectorstore

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class _Bm25Index:
    def __init__(self, texts: List[str], metadatas: List[dict]):
        self._texts = texts
        self._metadatas = metadatas
        self._bm25 = BM25Okapi([_tokenize(t) for t in texts]) if texts else None

    def search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [
            (Document(page_content=self._texts[i], metadata=dict(self._metadatas[i])), float(scores[i]))
            for i in ranked
            if scores[i] > 0
        ]


@lru_cache(maxsize=1)
def _get_index() -> _Bm25Index:
    got = get_vectorstore().get(include=["documents", "metadatas"])
    return _Bm25Index(got.get("documents") or [], got.get("metadatas") or [])


def invalidate_keyword_index() -> None:
    """Call after ingestion changes the collection so BM25 rebuilds from the
    new corpus on next use (mirrors how the Chroma store itself just stays
    open and picks up new adds, but BM25 has to be rebuilt from scratch)."""
    _get_index.cache_clear()


def keyword_search(query: str, k: int) -> List[Tuple[Document, float]]:
    """Return [(document, bm25_score)] sorted best-first. BM25 scores are
    unbounded and not on the same scale as cosine similarity - don't compare
    them directly, fuse by rank instead (see _reciprocal_rank_fusion)."""
    return _get_index().search(query, k)
