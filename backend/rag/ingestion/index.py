from typing import List
from rag.ingestion.loader import load_recipe_cards
from rag.ingestion.metadata import assert_valid_chunks
from rag.chunking.baseline_chunker import chunk_recipe_baseline
from rag.chunking.structure_aware_chunker import chunk_recipe_structure_aware
from rag.embeddings.embedding_service import embed_texts
from rag.vectorstore.store import append_to_collection, StoredEntry
from rag.chunking.types import RecipeChunk

BASELINE_COLLECTION = "recipe_baseline"
STRUCTURE_AWARE_COLLECTION = "recipe_structure_aware"


def _embed_chunks(chunks: List[RecipeChunk]) -> List[StoredEntry]:
    embeddings = embed_texts([c.text for c in chunks])
    return [StoredEntry(chunk=c, embedding=e) for c, e in zip(chunks, embeddings)]


def ingest_fermentation_cards() -> dict:
    """Ingests ONLY the 6 new fermentation recipe cards into both experiment
    collections. This does not touch or re-index any pre-existing corpus."""
    recipes = load_recipe_cards()

    baseline_chunks = [c for r in recipes for c in chunk_recipe_baseline(r)]
    structure_aware_chunks = [c for r in recipes for c in chunk_recipe_structure_aware(r)]

    assert_valid_chunks(baseline_chunks)
    assert_valid_chunks(structure_aware_chunks)

    baseline_entries = _embed_chunks(baseline_chunks)
    structure_aware_entries = _embed_chunks(structure_aware_chunks)

    append_to_collection(BASELINE_COLLECTION, baseline_entries)
    append_to_collection(STRUCTURE_AWARE_COLLECTION, structure_aware_entries)

    return {
        "recipe_count": len(recipes),
        "baseline_chunk_count": len(baseline_chunks),
        "structure_aware_chunk_count": len(structure_aware_chunks),
    }
