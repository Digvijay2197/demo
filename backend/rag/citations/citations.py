"""Resolve a chunk_id back to its full stored text + metadata."""
from typing import Optional

from rag.vectorstore.store import get_vectorstore


def resolve_citation(chunk_id: str) -> Optional[dict]:
    store = get_vectorstore()
    got = store.get(ids=[chunk_id])
    docs = got.get("documents") or []
    metas = got.get("metadatas") or []
    if not docs:
        return None
    meta = metas[0] if metas else {}
    return {
        "chunk_id": chunk_id,
        "source_file": meta.get("source_file", "unknown.pdf"),
        "page": meta.get("page"),
        "title": meta.get("title"),
        "recipe_id": meta.get("recipe_id"),
        "text": docs[0],
    }
