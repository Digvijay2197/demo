from typing import Optional
from rag.vectorstore.store import load_collection


def resolve_citation(collection: str, chunk_id: str) -> Optional[dict]:
    """Resolves chunk_id -> recipe -> source_file -> relevant text."""
    entries = load_collection(collection)
    for entry in entries:
        if entry.chunk.chunk_id == chunk_id:
            chunk = entry.chunk
            return {
                "chunk_id": chunk.chunk_id,
                "recipe_id": chunk.recipe_id,
                "source_file": chunk.source_file,
                "section": chunk.section,
                "recipe_title": chunk.recipe_title,
                "cuisine": chunk.cuisine,
                "text": chunk.text,
            }
    return None


def to_citation(chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "recipe_id": chunk.recipe_id,
        "source_file": chunk.source_file,
        "section": chunk.section,
    }
