"""ChromaDB vector store (persisted on disk).

Chroma is the single source of truth for embedded chunks. The collection
survives restarts under CHROMA_DIR, so ingestion is a one-off step and the
API just opens the existing collection.
"""
from functools import lru_cache

from langchain_chroma import Chroma

from rag.config import CHROMA_COLLECTION, CHROMA_DIR
from rag.embeddings.embedding_service import get_embeddings


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_DIR,
        # embeddings are L2-normalised, so cosine is the right space; this also
        # makes similarity_search_with_relevance_scores return scores in [0, 1].
        collection_metadata={"hnsw:space": "cosine"},
    )


def collection_count() -> int:
    """Number of chunks currently indexed."""
    store = get_vectorstore()
    try:
        return store._collection.count()
    except Exception:  # noqa: BLE001 - fall back to a portable path
        return len(store.get().get("ids") or [])


def reset_collection() -> None:
    """Drop every vector in the collection (used for a clean re-ingest)."""
    store = get_vectorstore()
    ids = store.get().get("ids") or []
    if ids:
        store.delete(ids=ids)
