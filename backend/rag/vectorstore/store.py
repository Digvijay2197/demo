import json
import os
from typing import Callable, List, Optional
import numpy as np
from rag.chunking.types import RecipeChunk

VECTOR_STORE_PATH = os.environ.get("VECTOR_STORE_PATH", os.path.join(os.getcwd(), "data", "vectorstore"))


class StoredEntry:
    def __init__(self, chunk: RecipeChunk, embedding: List[float]):
        self.chunk = chunk
        self.embedding = embedding

    def to_dict(self) -> dict:
        return {"chunk": self.chunk.to_dict(), "embedding": self.embedding}

    @staticmethod
    def from_dict(d: dict) -> "StoredEntry":
        return StoredEntry(chunk=RecipeChunk.from_dict(d["chunk"]), embedding=d["embedding"])


class SearchResult:
    def __init__(self, chunk: RecipeChunk, score: float):
        self.chunk = chunk
        self.score = score


def _collection_file(collection: str) -> str:
    return os.path.join(VECTOR_STORE_PATH, f"{collection}.json")


def _ensure_dir() -> None:
    os.makedirs(VECTOR_STORE_PATH, exist_ok=True)


def load_collection(collection: str) -> List[StoredEntry]:
    path = _collection_file(collection)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [StoredEntry.from_dict(d) for d in data]


def save_collection(collection: str, entries: List[StoredEntry]) -> None:
    _ensure_dir()
    with open(_collection_file(collection), "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in entries], f, indent=2)


def append_to_collection(collection: str, new_entries: List[StoredEntry]) -> None:
    """Appends entries, avoiding duplicate chunk_ids. Used to index new documents without a full re-index."""
    existing = load_collection(collection)
    existing_ids = {e.chunk.chunk_id for e in existing}
    to_add = [e for e in new_entries if e.chunk.chunk_id not in existing_ids]
    save_collection(collection, existing + to_add)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def search(
    collection: str,
    query_embedding: List[float],
    top_k: int = 5,
    filter_fn: Optional[Callable[[RecipeChunk], bool]] = None,
) -> List[SearchResult]:
    entries = load_collection(collection)
    if filter_fn:
        entries = [e for e in entries if filter_fn(e.chunk)]

    q = np.array(query_embedding)
    scored = [SearchResult(chunk=e.chunk, score=_cosine_similarity(q, np.array(e.embedding))) for e in entries]
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]
