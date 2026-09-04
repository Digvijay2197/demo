"""Retrieval over the Chroma collection, optionally fused with BM25 keyword search."""
from typing import Dict, List, Tuple

from langchain_core.documents import Document

from rag.config import HYBRID_SEARCH, SIMILARITY_THRESHOLD, TOP_K
from rag.retrieval.keyword_search import keyword_search
from rag.vectorstore.store import get_vectorstore

# How many candidates each method contributes to the fusion pool - wide
# enough that a keyword-only rare-token hit (an exact code, an uncommon
# ingredient) is still available to be pulled up even if it ranked outside a
# plain top-k on meaning alone.
_POOL_SIZE = 20
_RRF_K = 60  # standard Reciprocal Rank Fusion damping constant


def _semantic_search(query: str, k: int) -> List[Tuple[Document, float]]:
    store = get_vectorstore()
    hits = store.similarity_search_with_score(query, k=k)
    return [(doc, 1.0 - float(distance)) for doc, distance in hits]


def _chunk_key(doc: Document) -> str:
    return doc.metadata.get("chunk_id") or f"{doc.metadata.get('source_file')}::{doc.metadata.get('page')}"


def _reciprocal_rank_fusion(
    ranked_lists: List[List[Tuple[Document, float]]], k: int
) -> List[Tuple[Document, float]]:
    """Combine ranked lists by rank position, not raw score - cosine
    similarity and BM25 score live on unrelated scales, so RRF sidesteps
    having to normalise one against the other.

    The score attached to each returned doc is still the *semantic*
    similarity (ranked_lists[0]), not the fusion score, so a doc pulled up
    purely by a keyword match still reports how (un)related it is by
    meaning - which is what has_sufficient_evidence's threshold is about.
    """
    fused_score: Dict[str, float] = {}
    doc_by_key: Dict[str, Document] = {}
    for results in ranked_lists:
        for rank, (doc, _score) in enumerate(results):
            key = _chunk_key(doc)
            fused_score[key] = fused_score.get(key, 0.0) + 1.0 / (_RRF_K + rank + 1)
            doc_by_key.setdefault(key, doc)

    semantic_score = {_chunk_key(d): s for d, s in ranked_lists[0]}
    ordered_keys = sorted(fused_score, key=lambda kk: fused_score[kk], reverse=True)[:k]
    return [(doc_by_key[kk], semantic_score.get(kk, 0.0)) for kk in ordered_keys]


def retrieve(query: str, top_k: int = None, hybrid: bool = None) -> List[Tuple[Document, float]]:
    """Return [(document, similarity)] sorted best-first.

    similarity = 1 - cosine_distance, so 1.0 is an exact match and values near
    0 (or below) mean unrelated. This is always the semantic score, even in
    hybrid mode (see _reciprocal_rank_fusion).

    hybrid=True additionally runs BM25 keyword search and fuses it with the
    semantic ranking (Reciprocal Rank Fusion), so an exact code / rare
    ingredient name / exact title that ranks low by meaning alone can still
    surface in the top-k. hybrid=None (default) uses the HYBRID_SEARCH config
    flag; pass hybrid=False explicitly to reproduce the semantic-only baseline.
    """
    k = top_k or TOP_K
    use_hybrid = HYBRID_SEARCH if hybrid is None else hybrid

    semantic_hits = _semantic_search(query, max(k, _POOL_SIZE))
    if not use_hybrid:
        return semantic_hits[:k]

    keyword_hits = keyword_search(query, max(k, _POOL_SIZE))
    return _reciprocal_rank_fusion([semantic_hits, keyword_hits], k)


def has_sufficient_evidence(results: List[Tuple[Document, float]]) -> bool:
    """Grounding gate: only answer when the best hit clears the threshold.

    Checks the max score, not just results[0]: in hybrid mode the top-ranked
    result is ranked by fused position, not necessarily by semantic score, so
    the strongest semantic match may not be first. (When hybrid is off this is
    equivalent to the old results[0]-only check, since results are already
    sorted by that same score.)
    """
    return any(score >= SIMILARITY_THRESHOLD for _doc, score in results)
