from rag.ingestion.loader import load_recipe_cards
from rag.ingestion.metadata import assert_valid_chunks, validate_chunk_metadata
from rag.chunking.baseline_chunker import chunk_recipe_baseline
from rag.chunking.structure_aware_chunker import chunk_recipe_structure_aware


def test_six_recipe_cards_are_loaded():
    recipes = load_recipe_cards()
    assert len(recipes) == 6


def test_every_baseline_chunk_has_required_metadata():
    recipes = load_recipe_cards()
    chunks = [c for r in recipes for c in chunk_recipe_baseline(r)]
    assert len(chunks) > 0
    assert_valid_chunks(chunks)  # raises if any chunk is missing a required field


def test_every_structure_aware_chunk_has_required_metadata():
    recipes = load_recipe_cards()
    chunks = [c for r in recipes for c in chunk_recipe_structure_aware(r)]
    assert len(chunks) > 0
    assert_valid_chunks(chunks)


def test_chunk_missing_source_file_fails_validation():
    recipes = load_recipe_cards()
    chunk = chunk_recipe_structure_aware(recipes[0])[0]
    chunk.source_file = ""
    errors = validate_chunk_metadata(chunk)
    assert any("source_file" in e for e in errors)
