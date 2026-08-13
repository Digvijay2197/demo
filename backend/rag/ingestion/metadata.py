from typing import List
from rag.chunking.types import RecipeChunk

REQUIRED_FIELDS = ["source_file", "recipe_id", "cuisine", "dietary_tags"]


def validate_chunk_metadata(chunk: RecipeChunk) -> List[str]:
    errors = []
    for field in REQUIRED_FIELDS:
        value = getattr(chunk, field)
        missing = value is None or value == "" or (isinstance(value, list) and len(value) == 0)
        if missing:
            errors.append(f"missing required field: {field}")
    return errors


def assert_valid_chunks(chunks: List[RecipeChunk]) -> None:
    for chunk in chunks:
        errors = validate_chunk_metadata(chunk)
        if errors:
            raise ValueError(f"Chunk {chunk.chunk_id} failed metadata validation: {', '.join(errors)}")
