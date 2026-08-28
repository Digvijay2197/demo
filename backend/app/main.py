import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.config import (
    AUTO_INGEST_ON_STARTUP,
    CORS_ORIGIN,
    PDF_DIR,
    WATCH_PDF_DIR,
)
from rag.citations.citations import resolve_citation
from rag.generation.answer_service import answer_question
from rag.ingestion.pdf_loader import list_pdf_files
from rag.ingestion.pipeline import ingest, ingest_paths
from rag.vectorstore.store import collection_count, get_vectorstore

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB


async def _watch_pdf_dir() -> None:
    """Re-index PDFs as they are added / changed / removed in PDF_DIR, so you
    can just drop a file in the folder and ask about it - no manual ingest."""
    try:
        from watchfiles import awatch
    except ImportError:
        print("[watch] watchfiles not installed - `pip install watchfiles` for live indexing")
        return

    os.makedirs(PDF_DIR, exist_ok=True)
    print(f"[watch] watching {PDF_DIR} for PDF changes")
    try:
        async for changes in awatch(PDF_DIR):
            paths = sorted({p for _, p in changes if p.lower().endswith(".pdf")})
            if not paths:
                continue
            await asyncio.sleep(1.0)  # let the file finish being written
            try:
                result = await run_in_threadpool(ingest_paths, paths)
                print(f"[watch] indexed {result.get('files')}: "
                      f"+{result.get('chunks_new')} chunks "
                      f"(removed {result.get('removed_stale_chunks')} stale)")
            except Exception as exc:  # noqa: BLE001
                print("[watch] ingest failed:", repr(exc))
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    if AUTO_INGEST_ON_STARTUP:
        try:
            result = await run_in_threadpool(ingest)
            print(f"[startup] ingest: +{result.get('chunks_new', 0)} new chunks, "
                  f"{result.get('total_in_collection')} total")
        except Exception as exc:  # noqa: BLE001 - never block serving on this
            print("[startup] ingest failed:", repr(exc))

    watcher = asyncio.create_task(_watch_pdf_dir()) if WATCH_PDF_DIR else None
    try:
        yield
    finally:
        if watcher:
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Recipe RAG Backend", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "chunks_indexed": collection_count(),
        "auto_ingest": AUTO_INGEST_ON_STARTUP,
        "watching": WATCH_PDF_DIR,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        return answer_question(req.question)
    except RuntimeError as exc:  # missing GROQ_API_KEY, or Groq rate-limited
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        print("chat error:", repr(exc))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/documents")
def get_documents():
    """List every PDF (on disk or indexed) with its chunk counts."""
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
        result = await run_in_threadpool(ingest_paths, [dest])
        if result.get("chunks_new", 0) == 0 and not result.get("removed_stale_chunks"):
            os.remove(dest)
            raise HTTPException(
                status_code=400,
                detail="No extractable text found. Scanned / image-only PDFs are not supported.",
            )
        return {"source_file": os.path.basename(dest), **result}
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
