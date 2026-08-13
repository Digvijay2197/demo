from rag.ingestion.loader import load_recipe_cards
from rag.chunking.baseline_chunker import chunk_recipe_baseline
from rag.chunking.structure_aware_chunker import chunk_recipe_structure_aware


def _sourdough():
    return next(r for r in load_recipe_cards() if r.recipe_id == "sourdough-2kg")


def test_ingredient_row_stays_connected_to_table_context():
    recipe = _sourdough()
    chunks = chunk_recipe_structure_aware(recipe)
    salt_chunks = [c for c in chunks if "Fine sea salt" in c.text]
    assert len(salt_chunks) == 1
    text = salt_chunks[0].text
    # weight and percentage must be present alongside the ingredient name, not isolated
    assert "Weight: 7g" in text
    assert "Baker's percentage: 0.35%" in text


def test_structure_aware_chunk_retains_recipe_title_and_recipe_id():
    recipe = _sourdough()
    chunks = chunk_recipe_structure_aware(recipe)
    ingredient_chunk = next(c for c in chunks if c.section == "ingredients")
    assert ingredient_chunk.recipe_id == "sourdough-2kg"
    assert "2kg Country Sourdough Loaf" in ingredient_chunk.text


def test_structure_aware_section_metadata_is_preserved():
    recipe = _sourdough()
    chunks = chunk_recipe_structure_aware(recipe)
    sections = {c.section for c in chunks}
    assert sections == {"metadata", "ingredients", "method", "allergen"}


def test_baseline_chunker_has_no_section_awareness():
    recipe = _sourdough()
    chunks = chunk_recipe_baseline(recipe)
    assert all(c.section == "unstructured" for c in chunks)
    assert all(c.chunk_strategy == "baseline" for c in chunks)
