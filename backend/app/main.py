import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import json

from rag.ingestion.loader import load_recipe_cards
from rag.ingestion.index import BASELINE_COLLECTION, STRUCTURE_AWARE_COLLECTION
from rag.ingestion.parser import parse_recipe_card
from rag.ingestion.metadata import assert_valid_chunks
from rag.chunking.baseline_chunker import chunk_recipe_baseline
from rag.chunking.structure_aware_chunker import chunk_recipe_structure_aware
from rag.embeddings.embedding_service import embed_texts
from rag.vectorstore.store import load_collection, append_to_collection, StoredEntry
from rag.generation.answer_service import answer_question, PRODUCTION_COLLECTION
from rag.citations.citations import resolve_citation

app = FastAPI(title="Recipe RAG Backend")

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE_BYTES = 200 * 1024
ALLOWED_EXTENSIONS = {".md", ".txt"}


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    dietaryTag: Optional[str] = None


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return answer_question(req.question, req.dietaryTag)
    except Exception as exc:  # noqa: BLE001
        print("chat error", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/documents")
def get_documents():
    recipes = load_recipe_cards()
    indexed = {e.chunk.recipe_id for e in load_collection(STRUCTURE_AWARE_COLLECTION)}

    documents = [
        {
            "recipe_id": r.recipe_id,
            "title": r.title,
            "cuisine": r.cuisine,
            "dietary_tags": r.dietary_tags,
            "source_file": r.source_file,
            "indexed": r.recipe_id in indexed,
        }
        for r in recipes
    ]
    return {"documents": documents}


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Max size is {MAX_FILE_SIZE_BYTES // 1024}KB")

    raw_text = raw_bytes.decode("utf-8", errors="replace")

    try:
        recipe = parse_recipe_card(raw_text, file.filename or "upload.md")
        if not recipe.recipe_id or not recipe.title or not recipe.cuisine:
            raise ValueError("recipe card missing required front-matter fields (recipe_id, title, cuisine)")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid recipe card format: {exc}")

    try:
        baseline_chunks = chunk_recipe_baseline(recipe)
        structure_aware_chunks = chunk_recipe_structure_aware(recipe)
        assert_valid_chunks(baseline_chunks)
        assert_valid_chunks(structure_aware_chunks)

        baseline_embeddings = embed_texts([c.text for c in baseline_chunks])
        structure_embeddings = embed_texts([c.text for c in structure_aware_chunks])

        append_to_collection(
            BASELINE_COLLECTION,
            [StoredEntry(chunk=c, embedding=e) for c, e in zip(baseline_chunks, baseline_embeddings)],
        )
        append_to_collection(
            STRUCTURE_AWARE_COLLECTION,
            [StoredEntry(chunk=c, embedding=e) for c, e in zip(structure_aware_chunks, structure_embeddings)],
        )

        return {
            "recipe_id": recipe.recipe_id,
            "baseline_chunks_indexed": len(baseline_chunks),
            "structure_aware_chunks_indexed": len(structure_aware_chunks),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        print("upload indexing error", exc)
        raise HTTPException(status_code=500, detail="Internal server error while indexing document")


@app.get("/evaluation")
def get_evaluation():
    summary_path = os.path.join(os.getcwd(), "evaluation", "summary.json")
    if not os.path.exists(summary_path):
        raise HTTPException(status_code=404, detail="Evaluation has not been run yet")
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    metadata_filter_path = os.path.join(os.getcwd(), "evaluation", "metadata_filter.json")
    metadata_filter = None
    if os.path.exists(metadata_filter_path):
        with open(metadata_filter_path, "r", encoding="utf-8") as f:
            metadata_filter = json.load(f)

    return {"summary": summary, "metadataFilter": metadata_filter}


@app.get("/citations")
def get_citation(chunkId: str = Query(...)):
    resolved = resolve_citation(PRODUCTION_COLLECTION, chunkId)
    if not resolved:
        raise HTTPException(status_code=404, detail="chunk not found")
    return resolved
