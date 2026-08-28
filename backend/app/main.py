import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.config import CORS_ORIGIN, PDF_DIR
from rag.citations.citations import resolve_citation
from rag.generation.answer_service import answer_question
from rag.ingestion.pdf_loader import list_pdf_files, load_pdf
from rag.ingestion.pipeline import ingest, split_pages
from rag.vectorstore.store import collection_count, get_vectorstore

app = FastAPI(title="Recipe RAG Backend", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


@app.get("/health")
def health():
    return {"status": "ok", "chunks_indexed": collection_count()}


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return answer_question(req.question)
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        print("chat error:", repr(exc))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/documents")
def get_documents():
    """List every PDF in PDF_DIR and how many chunks of it are in Chroma."""
    indexed = get_vectorstore().get(include=["metadatas"])
    counts: dict[str, int] = {}
    pages: dict[str, set] = {}
    for meta in indexed.get("metadatas") or []:
        src = meta.get("source_file")
        if not src:
            continue
        counts[src] = counts.get(src, 0) + 1
        pages.setdefault(src, set()).add(meta.get("page"))

    on_disk = {os.path.basename(p): p for p in list_pdf_files()}
    # Show everything that is either sitting in the folder or already indexed,
    # so a PDF that was ingested and later moved out of the folder still appears.
    names = sorted(set(on_disk) | set(counts))

    documents = []
    for name in names:
        path = on_disk.get(name)
        documents.append(
            {
                "source_file": name,
                "size_kb": round(os.path.getsize(path) / 1024, 1) if path else None,
                "on_disk": path is not None,
                "chunks_indexed": counts.get(name, 0),
                "pages_indexed": len(pages.get(name, set())),
                "indexed": counts.get(name, 0) > 0,
            }
        )
    return {"documents": documents, "total_chunks": collection_count()}


@app.post("/ingest")
def run_ingest(rebuild: bool = Query(False)):
    """(Re)index every PDF currently in PDF_DIR."""
    try:
        return ingest(rebuild=rebuild)
    except Exception as exc:  # noqa: BLE001
        print("ingest error:", repr(exc))
        raise HTTPException(status_code=500, detail="Ingestion failed")


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension != ".pdf":
        raise HTTPException(status_code=400, detail="Only .pdf files are supported")

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400, detail=f"File too large. Max size is {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB"
        )

    os.makedirs(PDF_DIR, exist_ok=True)
    dest = os.path.join(PDF_DIR, os.path.basename(file.filename or "upload.pdf"))
    with open(dest, "wb") as fh:
        fh.write(raw_bytes)

    try:
        pages = load_pdf(dest)
        if not pages:
            os.remove(dest)
            raise HTTPException(
                status_code=400,
                detail="No extractable text found. Scanned / image-only PDFs are not supported.",
            )
        chunks = split_pages(pages)
        store = get_vectorstore()
        ids = [c.metadata["chunk_id"] for c in chunks]
        existing = set(store.get(ids=ids).get("ids") or [])
        new = [(c, i) for c, i in zip(chunks, ids) if i not in existing]
        if new:
            store.add_documents(documents=[c for c, _ in new], ids=[i for _, i in new])
        return {
            "source_file": os.path.basename(dest),
            "pages": len(pages),
            "chunks_new": len(new),
            "total_chunks": collection_count(),
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        print("upload indexing error:", repr(exc))
        raise HTTPException(status_code=500, detail="Internal server error while indexing document")


@app.get("/citations")
def get_citation(chunkId: str = Query(...)):
    resolved = resolve_citation(chunkId)
    if not resolved:
        raise HTTPException(status_code=404, detail="chunk not found")
    return resolved
