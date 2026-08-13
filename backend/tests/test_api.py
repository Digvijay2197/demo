import io
from fastapi.testclient import TestClient
import rag.generation.answer_service as answer_service
from rag.ingestion.index import ingest_fermentation_cards
from app.main import app

client = TestClient(app)


def setup_module():
    ingest_fermentation_cards()


def test_get_documents_lists_six_recipes_with_metadata():
    res = client.get("/documents")
    assert res.status_code == 200
    documents = res.json()["documents"]
    assert len(documents) == 6
    for doc in documents:
        assert doc["source_file"]
        assert doc["recipe_id"]
        assert doc["cuisine"]
        assert isinstance(doc["dietary_tags"], list) and len(doc["dietary_tags"]) > 0
        assert doc["indexed"] is True


def test_post_chat_returns_grounded_answer(monkeypatch):
    def fake_generate(question, context_chunks):
        chunk_id = context_chunks[0]["chunk_id"]
        return f"The recipe uses 7g of fine sea salt. [chunk:{chunk_id}]"

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)

    res = client.post("/chat", json={"question": "How much fine sea salt does the 2kg sourdough recipe use?"})
    assert res.status_code == 200
    body = res.json()
    assert body["refused"] is False
    assert len(body["citations"]) == 1


def test_post_chat_rejects_empty_question():
    res = client.post("/chat", json={"question": ""})
    assert res.status_code == 422


def test_get_evaluation_returns_hit_at_5_summary():
    res = client.get("/evaluation")
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["total_questions"] == 8
    assert "baseline_hit_at_5" in body["summary"]
    assert "structure_aware_hit_at_5" in body["summary"]


def test_upload_rejects_unsupported_file_type():
    res = client.post(
        "/documents/upload",
        files={"file": ("recipe.pdf", io.BytesIO(b"not a real recipe"), "application/pdf")},
    )
    assert res.status_code == 400


def test_upload_rejects_oversized_file():
    big_content = b"x" * (250 * 1024)
    res = client.post(
        "/documents/upload",
        files={"file": ("big.md", io.BytesIO(big_content), "text/markdown")},
    )
    assert res.status_code == 400


def test_upload_indexes_a_valid_recipe_card():
    from rag.vectorstore.store import load_collection, save_collection
    from rag.ingestion.index import BASELINE_COLLECTION, STRUCTURE_AWARE_COLLECTION


    content = (
        "recipe_id: test-pickles\n"
        "title: Quick Test Pickles\n"
        "cuisine: Test Cuisine\n"
        "dietary_tags: vegan, gluten-free\n\n"
        "## Ingredients\n\n"
        "| Ingredient | Weight | Baker's Percentage |\n"
        "|---|---|---|\n"
        "| Cucumber | 500g | 100% |\n"
        "| Salt | 15g | 3% |\n\n"
        "## Method\n\nBrine the cucumbers for 3 days.\n\n"
        "## Allergen Note\n\nNo common allergens.\n"
    ).encode("utf-8")

    res = client.post(
        "/documents/upload",
        files={"file": ("test-pickles.md", io.BytesIO(content), "text/markdown")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recipe_id"] == "test-pickles"
    assert body["baseline_chunks_indexed"] > 0
    assert body["structure_aware_chunks_indexed"] > 0

    # Clean up: this deliverable's vector store must only contain the 6 official
    # fermentation cards, so remove the throwaway test recipe added above.
    for collection in (BASELINE_COLLECTION, STRUCTURE_AWARE_COLLECTION):
        entries = load_collection(collection)
        save_collection(collection, [e for e in entries if e.chunk.recipe_id != "test-pickles"])
