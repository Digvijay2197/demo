import io
import os

import pymupdf  # PyMuPDF
from fastapi.testclient import TestClient

import rag.generation.answer_service as answer_service
from rag.config import PDF_DIR
from rag.ingestion.pipeline import ingest
from app.main import app

client = TestClient(app)

RECIPE_TEXT = (
    "Classic Sauerkraut\n\n"
    "Ingredients:\n"
    "- 1000 g white cabbage\n"
    "- 20 g fine sea salt (2% of cabbage weight)\n\n"
    "Method:\n"
    "1. Shred the cabbage finely.\n"
    "2. Massage in the salt until liquid is released.\n"
    "3. Pack into a jar and ferment at 18-20 C for 2 to 4 weeks.\n"
)


def _write_pdf(name: str, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    os.makedirs(PDF_DIR, exist_ok=True)
    doc.save(os.path.join(PDF_DIR, name))
    doc.close()


def setup_module():
    _write_pdf("sauerkraut.pdf", RECIPE_TEXT)
    ingest(rebuild=True)


def test_health_reports_indexed_chunks():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["chunks_indexed"] > 0


def test_documents_lists_the_ingested_pdf():
    res = client.get("/documents")
    assert res.status_code == 200
    docs = res.json()["documents"]
    doc = next(d for d in docs if d["source_file"] == "sauerkraut.pdf")
    assert doc["indexed"] is True
    assert doc["on_disk"] is True
    assert doc["chunks_indexed"] >= 1


def test_documents_still_lists_a_pdf_removed_from_the_folder():
    """A PDF that was indexed and then deleted from the folder must still show,
    marked on_disk=False - otherwise the panel misleadingly reads 'no PDFs'."""
    _write_pdf("temp-removed.pdf", "Iced Tea\n\nSteep 2 tea bags in 500 ml boiling water for 5 minutes.")
    ingest()
    os.remove(os.path.join(PDF_DIR, "temp-removed.pdf"))

    docs = client.get("/documents").json()["documents"]
    doc = next(d for d in docs if d["source_file"] == "temp-removed.pdf")
    assert doc["indexed"] is True
    assert doc["on_disk"] is False
    assert doc["size_kb"] is None


def test_chat_returns_grounded_answer_with_citations(monkeypatch):
    def fake_generate(question, results):
        src = results[0][0].metadata["source_file"]
        page = results[0][0].metadata["page"]
        return f"Use 20 g of fine sea salt. [source: {src} p.{page}]"

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)

    res = client.post("/chat", json={"question": "How much salt for the sauerkraut?"})
    assert res.status_code == 200
    body = res.json()
    assert body["refused"] is False
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["source_file"] == "sauerkraut.pdf"


def test_chat_refuses_when_no_evidence(monkeypatch):
    def fail(*_a, **_k):
        raise AssertionError("LLM should not be called when evidence is insufficient")

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fail)

    res = client.post("/chat", json={"question": "What is the capital of France?"})
    assert res.status_code == 200
    assert res.json()["refused"] is True


def test_chat_rejects_empty_question():
    assert client.post("/chat", json={"question": ""}).status_code == 422


def test_upload_rejects_non_pdf():
    res = client.post(
        "/documents/upload",
        files={"file": ("recipe.md", io.BytesIO(b"# not a pdf"), "text/markdown")},
    )
    assert res.status_code == 400


def test_citations_resolve_round_trip(monkeypatch):
    def fake_generate(question, results):
        src = results[0][0].metadata["source_file"]
        page = results[0][0].metadata["page"]
        return f"Ferment for 2 to 4 weeks. [source: {src} p.{page}]"

    monkeypatch.setattr(answer_service, "generate_grounded_answer", fake_generate)
    body = client.post("/chat", json={"question": "How long to ferment sauerkraut?"}).json()
    chunk_id = body["citations"][0]["chunk_id"]

    res = client.get(f"/citations?chunkId={chunk_id}")
    assert res.status_code == 200
    assert "cabbage" in res.json()["text"].lower()
