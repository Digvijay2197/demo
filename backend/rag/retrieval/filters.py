from rag.chunking.types import RecipeChunk


def by_dietary_tag(tag: str):
    return lambda chunk: tag in chunk.dietary_tags


def by_recipe_id(recipe_id: str):
    return lambda chunk: chunk.recipe_id == recipe_id
