from dataclasses import dataclass, field
from typing import List, Literal

ChunkStrategy = Literal["baseline", "structure_aware"]
ChunkSection = Literal["unstructured", "metadata", "ingredients", "method", "allergen"]


@dataclass
class ParsedIngredient:
    name: str
    weight: str
    percentage: str


@dataclass
class ParsedRecipe:
    recipe_id: str
    title: str
    cuisine: str
    dietary_tags: List[str]
    source_file: str
    ingredients: List[ParsedIngredient]
    method: str
    allergen_note: str
    raw_text: str


@dataclass
class RecipeChunk:
    chunk_id: str
    source_file: str
    recipe_id: str
    recipe_title: str
    cuisine: str
    dietary_tags: List[str]
    section: ChunkSection
    chunk_index: int
    chunk_strategy: ChunkStrategy
    text: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "recipe_id": self.recipe_id,
            "recipe_title": self.recipe_title,
            "cuisine": self.cuisine,
            "dietary_tags": self.dietary_tags,
            "section": self.section,
            "chunk_index": self.chunk_index,
            "chunk_strategy": self.chunk_strategy,
            "text": self.text,
        }

    @staticmethod
    def from_dict(d: dict) -> "RecipeChunk":
        return RecipeChunk(**d)
