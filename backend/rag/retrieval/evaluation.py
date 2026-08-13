from dataclasses import dataclass
from typing import List
from rag.vectorstore.store import SearchResult


@dataclass
class KnownAnswerQuestion:
    id: str
    question: str
    expected_answer: str
    recipe_id: str
    section: str
    ingredient_dependent: bool
    expected_keyword: str


def build_search_dump(q: KnownAnswerQuestion, results: List[SearchResult]) -> dict:
    """Hit@5 requires BOTH: the retrieved chunk belongs to the expected recipe,
    AND the chunk's text actually contains the evidence needed to answer the
    question (expected_keyword, e.g. "7g" for a salt-weight question). Recipe
    match alone is too weak a signal with only 6 distinct recipes in the
    corpus - it would saturate at 8/8 for both strategies and hide the real
    difference chunking makes (see results.md retrieval-failure section)."""
    keyword = q.expected_keyword.lower()
    hit = any(r.chunk.recipe_id == q.recipe_id and keyword in r.chunk.text.lower() for r in results)

    return {
        "question": q.question,
        "expected_recipe_id": q.recipe_id,
        "expected_section": q.section,
        "results": [
            {
                "chunk_id": r.chunk.chunk_id,
                "recipe_id": r.chunk.recipe_id,
                "source_file": r.chunk.source_file,
                "section": r.chunk.section,
                "score": r.score,
                "text": r.chunk.text,
            }
            for r in results
        ],
        "hit_at_5": hit,
    }


def compute_hit_at_5(dumps: List[dict]) -> int:
    return sum(1 for d in dumps if d["hit_at_5"])
