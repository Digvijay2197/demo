import rag.generation.answer_service as answer_service
from rag.ingestion.index import ingest_fermentation_cards


def setup_module():
    ingest_fermentation_cards()


def test_grounded_question_receives_an_answer_with_resolvable_citation(monkeypatch):
    def fake_generate(question, context_chunks):
        chunk_id = context_chunks[0]["chunk_id"]
        return f"The recipe uses 7g of fine sea salt. [chunk:{chunk_id}]"

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)

    response = answer_service.answer_question("How much fine sea salt does the 2kg sourdough recipe use?")

    assert response["refused"] is False
    assert len(response["citations"]) == 1
    citation = response["citations"][0]
    assert citation["recipe_id"] == "sourdough-2kg"
    assert citation["source_file"] == "sourdough-2kg.md"


def test_out_of_corpus_question_is_refused_without_calling_llm(monkeypatch):
    def fail_if_called(question, context_chunks):
        raise AssertionError("LLM should not be called when there is no evidence above threshold")

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fail_if_called)

    # A dietary filter that matches nothing forces the no-evidence refusal path.
    response = answer_service.answer_question(
        "What is the vitamin B12 content of the miso paste?", dietary_tag="not-a-real-tag"
    )

    assert response["refused"] is True
    assert response["citations"] == []
    assert "couldn't find enough information" in response["answer"]


def test_vague_recipe_browse_request_lists_real_recipes_instead_of_refusing(monkeypatch):
    def fail_if_called(question, context_chunks):
        raise AssertionError("A generic browse request should not need an LLM call")

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fail_if_called)

    # Typo ("recipy") is intentional: this reproduces a real user query that scored
    # far below the similarity threshold and was previously refused outright.
    response = answer_service.answer_question("give me the any of the recipy")

    assert response["refused"] is False
    assert "sourdough" in response["answer"].lower()
    assert len(response["citations"]) == 6
    assert all(c["section"] == "metadata" for c in response["citations"])


def test_named_recipe_question_is_scoped_to_that_recipes_own_chunks(monkeypatch):
    seen_recipe_ids = []

    def fake_generate(question, context_chunks):
        seen_recipe_ids.extend(c["recipe_id"] for c in context_chunks)
        return f"Answer. [chunk:{context_chunks[0]['chunk_id']}]"

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)

    response = answer_service.answer_question("What ingredients are required for the kimchi recipe?")

    assert response["refused"] is False
    assert seen_recipe_ids  # retrieval found something
    assert all(rid == "kimchi-napa" for rid in seen_recipe_ids)


def test_uncited_answer_falls_back_to_citing_all_context_chunks(monkeypatch):
    monkeypatch.setattr(answer_service, "generate_grounded_answer", lambda q, c: "A plain answer with no markers.")

    response = answer_service.answer_question("What ingredients are required for the kimchi recipe?")

    assert response["refused"] is False
    assert len(response["citations"]) > 1
    assert all(c["recipe_id"] == "kimchi-napa" for c in response["citations"])


def test_dietary_tag_listing_question_lists_matching_recipes_without_llm_call(monkeypatch):
    def fail_if_called(question, context_chunks):
        raise AssertionError("Dietary-tag listing should be answered deterministically from metadata")

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fail_if_called)

    response = answer_service.answer_question("Which recipes are vegan?")

    assert response["refused"] is False
    assert "Homemade Dairy Yogurt" not in response["answer"]  # not vegan, must be excluded
    assert "Napa Cabbage Kimchi" in response["answer"]
    assert len(response["citations"]) == 5  # 5 of the 6 recipes are tagged vegan


def test_comparison_question_across_two_named_recipes_cites_both(monkeypatch):
    seen_recipe_ids = []

    def fake_generate(question, context_chunks):
        seen_recipe_ids.extend(c["recipe_id"] for c in context_chunks)
        one_per_recipe = {c["recipe_id"]: c["chunk_id"] for c in context_chunks}
        ids = "".join(f"[chunk:{cid}]" for cid in one_per_recipe.values())
        return f"Comparison answer. {ids}"

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)

    response = answer_service.answer_question("Which uses more salt, the sourdough or the sauerkraut?")

    recipe_ids = {c["recipe_id"] for c in response["citations"]}
    assert response["refused"] is False
    # the merged retrieval must have pulled chunks from both named recipes, not just one
    assert set(seen_recipe_ids) == {"sourdough-2kg", "sauerkraut-classic"}
    assert recipe_ids == {"sourdough-2kg", "sauerkraut-classic"}


def test_llm_refusal_wording_is_also_treated_as_refused(monkeypatch):
    def fake_generate(question, context_chunks):
        return "I couldn't find enough information in the provided recipes to answer that question."

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)

    response = answer_service.answer_question("What is the vitamin B12 content of the miso paste?")

    assert response["refused"] is True
    assert response["citations"] == []
