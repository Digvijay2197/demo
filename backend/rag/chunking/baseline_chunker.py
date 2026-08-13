from typing import List
from rag.chunking.types import ParsedRecipe, RecipeChunk

# Baseline chunker: the "existing" chunking strategy carried over unchanged.
# It treats the whole recipe card as plain text and splits it with a
# fixed-size sliding window, with no awareness of ingredient tables,
# method steps, or section boundaries.
CHUNK_SIZE = 200
CHUNK_OVERLAP = 40


def chunk_recipe_baseline(recipe: ParsedRecipe) -> List[RecipeChunk]:
    text = recipe.raw_text.strip()
    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        slice_ = text[start:end].strip()
        if slice_:
            chunks.append(
                RecipeChunk(
                    chunk_id=f"baseline-{recipe.recipe_id}-{index}",
                    source_file=recipe.source_file,
                    recipe_id=recipe.recipe_id,
                    recipe_title=recipe.title,
                    cuisine=recipe.cuisine,
                    dietary_tags=recipe.dietary_tags,
                    section="unstructured",
                    chunk_index=index,
                    chunk_strategy="baseline",
                    text=slice_,
                )
            )
            index += 1
        if end == len(text):
            break
        start = end - CHUNK_OVERLAP

    return chunks
