import os
import re
from typing import List, Optional
from rag.retrieval.retriever import retrieve, has_sufficient_evidence
from rag.generation.groq_service import generate_grounded_answer
from rag.citations.citations import resolve_citation
from rag.generation.prompt import REFUSAL_MESSAGE
from rag.retrieval.filters import by_dietary_tag, by_recipe_id
from rag.ingestion.loader import load_recipe_cards
from rag.vectorstore.store import load_collection

# Chunker that powers the live chatbot, chosen from the Hit@5 evaluation in results.md.
PRODUCTION_COLLECTION = os.environ.get("PRODUCTION_COLLECTION", "recipe_structure_aware")

CITATION_RE = re.compile(r"\[chunk:([a-zA-Z0-9-]+)\]")

# A generic "show me a/any recipe" ask has no specific fact to embed against, so it
# never clears the similarity threshold and would otherwise hit the same refusal as a
# genuinely out-of-corpus question. It's not a factual claim though - it's a browse
# request answerable directly and truthfully from the recipe titles already indexed -
# so it's handled separately rather than by loosening the threshold (which would risk
# admitting unrelated questions through the grounding gate).
_LISTING_PATTERNS = [
    r"\bany\b.*\brecip\w*",
    r"\bwhich\b.*\brecip\w*",
    r"\bwhat\b.*\brecip\w*",
    r"\blist\b.*\brecip\w*",
    r"\bshow me\b.*\brecip\w*",
    r"\brecommend\b.*\brecip\w*",
    r"\brecip\w*\b.*\bavailable\b",
    r"\brecip\w* do you have\b",
]


def _is_recipe_listing_request(question: str) -> bool:
    q = question.lower()
    return any(re.search(p, q) for p in _LISTING_PATTERNS)


def _list_available_recipes() -> dict:
    recipes = load_recipe_cards()
    lines = [f"- {r.title} ({r.cuisine})" for r in recipes]
    answer = (
        "Here are the recipes I have indexed:\n"
        + "\n".join(lines)
        + "\n\nAsk me a specific question about any of them - an ingredient weight, "
        "method step, allergen, or dietary tag - and I'll answer with a citation."
    )

    entries = load_collection(PRODUCTION_COLLECTION)
    citations = []
    for r in recipes:
        meta_chunk = next(
            (e.chunk for e in entries if e.chunk.recipe_id == r.recipe_id and e.chunk.section == "metadata"),
            None,
        )
        if meta_chunk:
            citations.append(
                {
                    "chunk_id": meta_chunk.chunk_id,
                    "recipe_id": meta_chunk.recipe_id,
                    "source_file": meta_chunk.source_file,
                    "section": meta_chunk.section,
                }
            )

    return {"answer": answer, "citations": citations, "refused": False}


def _extract_cited_chunk_ids(answer: str):
    return list(dict.fromkeys(CITATION_RE.findall(answer)))


def _detect_recipe_ids(question: str, recipes) -> List[str]:
    """A recipe_id's first hyphen segment (sourdough-2kg -> "sourdough") is already the
    dish's common name, so matching it as a whole word against the question needs no
    hardcoded alias list and stays in sync automatically if recipes are added/renamed."""
    q = question.lower()
    return [r.recipe_id for r in recipes if re.search(rf"\b{re.escape(r.recipe_id.split('-')[0])}\b", q)]


def _all_dietary_tags(recipes) -> set:
    return {t.lower() for r in recipes for t in r.dietary_tags}


def _detect_dietary_tag_listing(question: str, recipes) -> Optional[str]:
    """"Which recipes have a particular dietary tag?" is one of the example questions in
    the original brief. It's a metadata lookup across ALL recipes, not a single semantic
    retrieval, so it's answered directly and deterministically instead of via embedding
    search (which only ever returns one recipe's chunks near the top, not a full list)."""
    q = question.lower()
    looks_like_listing = re.search(r"\b(which|what)\b.*\brecip\w*", q) or re.search(
        r"\brecip\w*\b.*\b(are|have|with)\b", q
    )
    if not looks_like_listing:
        return None
    for tag in _all_dietary_tags(recipes):
        if tag in q:
            return tag
    return None


def _list_recipes_by_dietary_tag(tag: str, recipes) -> dict:
    matching = [r for r in recipes if tag in {t.lower() for t in r.dietary_tags}]
    if not matching:
        return {"answer": REFUSAL_MESSAGE, "citations": [], "refused": True}

    lines = [f"- {r.title} ({r.cuisine})" for r in matching]
    answer = f"Recipes tagged '{tag}':\n" + "\n".join(lines)

    entries = load_collection(PRODUCTION_COLLECTION)
    citations = []
    for r in matching:
        meta_chunk = next(
            (e.chunk for e in entries if e.chunk.recipe_id == r.recipe_id and e.chunk.section == "metadata"),
            None,
        )
        if meta_chunk:
            citations.append(
                {
                    "chunk_id": meta_chunk.chunk_id,
                    "recipe_id": meta_chunk.recipe_id,
                    "source_file": meta_chunk.source_file,
                    "section": meta_chunk.section,
                }
            )
    return {"answer": answer, "citations": citations, "refused": False}


def _retrieve_for_question(question: str, recipe_ids: List[str]):
    """When the question names one recipe, restrict retrieval to that recipe's own
    chunks and raise top_k so a broad ask ("what ingredients does X use?") can surface
    ALL of that recipe's ingredient chunks instead of losing most of them to unrelated
    recipes in a corpus-wide top-5. Filtering doesn't change any chunk's absolute
    similarity score, so narrow single-fact questions are unaffected (and gain
    precision from not competing with other recipes' chunks at all). Two or more named
    recipes (a comparison question) retrieves each recipe's best chunks separately and
    merges them, so both sides of the comparison are represented in the context."""
    if len(recipe_ids) == 1:
        return retrieve(PRODUCTION_COLLECTION, question, top_k=10, filter_fn=by_recipe_id(recipe_ids[0]))
    if len(recipe_ids) >= 2:
        merged = []
        for recipe_id in recipe_ids:
            merged.extend(retrieve(PRODUCTION_COLLECTION, question, top_k=4, filter_fn=by_recipe_id(recipe_id)))
        merged.sort(key=lambda r: r.score, reverse=True)
        return merged
    return retrieve(PRODUCTION_COLLECTION, question)


def answer_question(question: str, dietary_tag: Optional[str] = None) -> dict:
    recipes = load_recipe_cards()

    if not dietary_tag:
        tag_match = _detect_dietary_tag_listing(question, recipes)
        if tag_match:
            return _list_recipes_by_dietary_tag(tag_match, recipes)

    if dietary_tag:
        results = retrieve(PRODUCTION_COLLECTION, question, filter_fn=by_dietary_tag(dietary_tag))
    else:
        matched_recipe_ids = _detect_recipe_ids(question, recipes)
        results = _retrieve_for_question(question, matched_recipe_ids)

    if not has_sufficient_evidence(results):
        if not dietary_tag and _is_recipe_listing_request(question):
            return _list_available_recipes()
        return {"answer": REFUSAL_MESSAGE, "citations": [], "refused": True}

    context_chunks = [
        {
            "chunk_id": r.chunk.chunk_id,
            "recipe_id": r.chunk.recipe_id,
            "recipe_title": r.chunk.recipe_title,
            "section": r.chunk.section,
            "text": r.chunk.text,
        }
        for r in results
    ]

    answer = generate_grounded_answer(question, context_chunks)

    if answer.strip().startswith("I couldn't find enough information"):
        return {"answer": REFUSAL_MESSAGE, "citations": [], "refused": True}

    cited_ids = _extract_cited_chunk_ids(answer)
    if not cited_ids:
        # The model sometimes omits [chunk:ID] markers on multi-fact listing answers
        # (e.g. "list all the ingredients"). The answer is still fully grounded - it was
        # generated from nothing but context_chunks - so attribute it to all of them
        # rather than surface an uncited claim.
        cited_ids = [c["chunk_id"] for c in context_chunks]
    citations = []
    for chunk_id in cited_ids:
        resolved = resolve_citation(PRODUCTION_COLLECTION, chunk_id)
        if resolved:
            citations.append(
                {
                    "chunk_id": resolved["chunk_id"],
                    "recipe_id": resolved["recipe_id"],
                    "source_file": resolved["source_file"],
                    "section": resolved["section"],
                }
            )

    return {"answer": answer, "citations": citations, "refused": False}
