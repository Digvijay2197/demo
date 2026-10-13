"""Week 3-4 RAG pipeline, re-pointed at the capstone corpus.

Reuses the Week 4 pieces unchanged - the MiniLM embedding service, Chroma, the BM25
index class and Reciprocal Rank Fusion from rag/retrieval - but over a SEPARATE
collection (capstone_recipes), so the existing PDF chatbot's index is untouched.
One chunk per recipe VERSION: both the original and the reformulated-2025 record
stay in the index (dropping the old one would hide the bug, not fix it).
"""
from __future__ import annotations

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from capstone import config, domain
from rag.embeddings.embedding_service import get_embeddings
from rag.retrieval.keyword_search import _Bm25Index
from rag.retrieval.retriever import _reciprocal_rank_fusion

_POOL = 20


def record_text(r: dict) -> str:
    ing = ", ".join(i["item"] for i in r["ingredients"])
    return (f"{r['title']} ({r['version']}). {r['cuisine']} {' '.join(r['tags'])}. "
            f"Ingredients: {ing}. Method: {' '.join(r['method'])}")


@lru_cache(maxsize=1)
def _store() -> Chroma:
    return Chroma(collection_name=config.COLLECTION, embedding_function=get_embeddings(),
                  persist_directory=config.CHROMA_DIR, collection_metadata={"hnsw:space": "cosine"})


@lru_cache(maxsize=1)
def _bm25() -> _Bm25Index:
    got = _store().get(include=["documents", "metadatas"])
    return _Bm25Index(got.get("documents") or [], got.get("metadatas") or [])


def build_index(rebuild: bool = False) -> int:
    """Idempotent: ids are '<recipe_id>@<version>', so re-running only adds what is missing."""
    store = _store()
    recs = domain.records()
    ids = [f"{r['recipe_id']}@{r['version']}" for r in recs]
    have = set(store.get(ids=ids).get("ids") or [])
    if rebuild and have:
        store.delete(ids=list(have))
        have = set()
    new = [(r, i) for r, i in zip(recs, ids) if i not in have]
    if new:
        store.add_documents(
            documents=[Document(page_content=record_text(r), metadata={
                "recipe_id": r["recipe_id"], "version": r["version"], "status": r["status"],
                "title": r["title"], "chunk_id": i}) for r, i in new],
            ids=[i for _, i in new])
        _bm25.cache_clear()
    return len(recs)


@lru_cache(maxsize=1)
def _ensure_index() -> int:
    return build_index()


def retrieve(query: str, k: int = 6) -> list[tuple[Document, float]]:
    """Hybrid (semantic + BM25 -> RRF) over record chunks; score = semantic similarity."""
    _ensure_index()
    sem = [(d, 1.0 - float(dist)) for d, dist in _store().similarity_search_with_score(query, k=_POOL)]
    kw = _bm25().search(query, _POOL)
    return _reciprocal_rank_fusion([sem, kw], k=k)


def search_recipes(query: str, k: int = 4, include_superseded: bool = False) -> dict:
    """Retrieval + version policy.

    naive    : whatever ranked first; both versions of a recipe can appear; no status.
    resolved : one hit per recipe_id showing the CURRENT version (the old one stays
               indexed and reachable by explicit version) - the superseded-citation fix."""
    hits = retrieve(query, k=8)
    policy = config.version_policy()
    out, seen = [], set()
    for doc, score in hits:
        rid, ver = doc.metadata["recipe_id"], doc.metadata["version"]
        if policy == "naive":
            rec = domain.get_record(rid, ver)
            out.append({"recipe_id": rid, "version": ver, "title": rec["title"],
                        "score": round(score, 3), "citation": domain.cite(rec)})
        else:
            if rid in seen:
                continue
            rec = domain.get_record(rid, ver if include_superseded else None)
            seen.add(rid)
            vs = domain.versions_of(rid)
            item = {"recipe_id": rid, "version": rec["version"], "status": rec["status"],
                    "title": rec["title"], "score": round(score, 3), "citation": domain.cite(rec)}
            if len(vs) > 1:
                item["other_versions"] = [v["version"] for v in vs if v["version"] != rec["version"]]
                item["note"] = "reformulated recipe: allergen profile differs between versions"
            out.append(item)
        if len(out) >= k:
            break
    return {"query": query, "hits": out, "policy": policy,
            "best_score": out[0]["score"] if out else 0.0}
