from typing import List
from rag.chunking.types import ParsedRecipe, RecipeChunk

# Structure-aware chunker: understands Recipe Title -> Ingredient Table ->
# Method -> Allergen Note. Every ingredient row keeps its table context
# (name + weight + baker's percentage) and its parent recipe identity
# inline in the chunk text, so a row is never isolated from its meaning.


def chunk_recipe_structure_aware(recipe: ParsedRecipe) -> List[RecipeChunk]:
    chunks: List[RecipeChunk] = []
    index = 0

    def make_chunk(section: str, text: str) -> RecipeChunk:
        nonlocal index
        chunk = RecipeChunk(
            chunk_id=f"structure-{recipe.recipe_id}-{section}-{index}",
            source_file=recipe.source_file,
            recipe_id=recipe.recipe_id,
            recipe_title=recipe.title,
            cuisine=recipe.cuisine,
            dietary_tags=recipe.dietary_tags,
            section=section,
            chunk_index=index,
            chunk_strategy="structure_aware",
            text=text,
        )
        index += 1
        return chunk

    chunks.append(
        make_chunk(
            "metadata",
            f"Recipe: {recipe.title}\nCuisine: {recipe.cuisine}\nDietary tags: {', '.join(recipe.dietary_tags)}",
        )
    )

    for ingredient in recipe.ingredients:
        chunks.append(
            make_chunk(
                "ingredients",
                f"Recipe: {recipe.title}\nSection: Ingredients\n\n"
                f"Ingredient: {ingredient.name}\nWeight: {ingredient.weight}\n"
                f"Baker's percentage: {ingredient.percentage}",
            )
        )

    if recipe.method:
        chunks.append(make_chunk("method", f"Recipe: {recipe.title}\nSection: Method\n\n{recipe.method}"))

    if recipe.allergen_note:
        chunks.append(
            make_chunk("allergen", f"Recipe: {recipe.title}\nSection: Allergen Note\n\n{recipe.allergen_note}")
        )

    return chunks
