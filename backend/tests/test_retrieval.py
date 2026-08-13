from rag.ingestion.index import ingest_fermentation_cards, STRUCTURE_AWARE_COLLECTION
from rag.retrieval.retriever import retrieve, TOP_K
from rag.retrieval.filters import by_dietary_tag
from rag.retrieval.evaluation import KnownAnswerQuestion, build_search_dump, compute_hit_at_5


def setup_module():
    # Idempotent: append_to_collection dedupes by chunk_id, so re-running is safe.
    ingest_fermentation_cards()


def test_top_k_retrieval_returns_at_most_top_k_results():
    results = retrieve(STRUCTURE_AWARE_COLLECTION, "How much salt is in the sourdough recipe?", top_k=5)
    assert 0 < len(results) <= 5
    assert TOP_K > 0


def test_metadata_filter_restricts_results_to_matching_tag():
    results = retrieve(
        STRUCTURE_AWARE_COLLECTION,
        "Tell me about a fermented food",
        top_k=5,
        filter_fn=by_dietary_tag("contains-dairy"),
    )
    assert len(results) > 0
    assert all("contains-dairy" in r.chunk.dietary_tags for r in results)


def test_hit_at_5_calculation():
    q = KnownAnswerQuestion(
        id="test",
        question="How much fine sea salt does the 2kg sourdough recipe use?",
        expected_answer="7g",
        recipe_id="sourdough-2kg",
        section="ingredients",
        ingredient_dependent=True,
        expected_keyword="7g",
    )
    results = retrieve(STRUCTURE_AWARE_COLLECTION, q.question, top_k=5)
    dump = build_search_dump(q, results)
    assert dump["hit_at_5"] is True
    assert compute_hit_at_5([dump]) == 1
    assert compute_hit_at_5([{**dump, "hit_at_5": False}]) == 0
