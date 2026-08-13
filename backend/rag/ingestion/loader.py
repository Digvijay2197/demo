import os
from typing import List
from rag.ingestion.parser import parse_recipe_card
from rag.chunking.types import ParsedRecipe

FERMENTATION_RECIPES_DIR = os.path.join(os.getcwd(), "data", "recipes", "fermentation")


def load_recipe_cards(directory: str = FERMENTATION_RECIPES_DIR) -> List[ParsedRecipe]:
    files = sorted(f for f in os.listdir(directory) if f.endswith(".md"))
    recipes = []
    for file in files:
        with open(os.path.join(directory, file), "r", encoding="utf-8") as fh:
            raw_text = fh.read()
        recipes.append(parse_recipe_card(raw_text, file))
    return recipes
