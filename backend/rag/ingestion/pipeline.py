"""Ingestion pipeline: PDF files -> pages -> chunks -> embeddings -> Chroma.

Idempotent: each chunk's id is a hash of (source_file, page, chunk text), so
re-running after adding a new PDF only inserts the genuinely new chunks and
never duplicates existing ones.
"""
import hashlib
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE
from rag.ingestion.pdf_loader import load_all_pdfs
from rag.vectorstore.store import collection_count, get_vectorstore, reset_collection


def _splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )


def _chunk_id(doc: Document) -> str:
    key = f"{doc.metadata.get('source_file')}::{doc.metadata.get('page')}::{doc.page_content}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def split_pages(pages: List[Document]) -> List[Document]:
    chunks = _splitter().split_documents(pages)
    for c in chunks:
        c.metadata["chunk_id"] = _chunk_id(c)
        # a short preview kept in metadata so the API can show a snippet
        # without re-reading the source PDF
        c.metadata["snippet"] = c.page_content[:280].replace("\n", " ").strip()
    return chunks


def ingest(rebuild: bool = False) -> dict:
    """Load every PDF in PDF_DIR and index it into Chroma.

    rebuild=True wipes the collection first (use after removing/replacing PDFs).
    """
    pages, skipped = load_all_pdfs()
    if not pages:
        return {
            "pdf_pages": 0,
            "chunks_indexed": 0,
            "skipped_files": skipped,
            "total_in_collection": collection_count(),
        }

    chunks = split_pages(pages)

    if rebuild:
        reset_collection()

    store = get_vectorstore()
    ids = [c.metadata["chunk_id"] for c in chunks]

    existing = set(store.get(ids=ids).get("ids") or []) if not rebuild else set()
    new_chunks = [c for c, cid in zip(chunks, ids) if cid not in existing]
    new_ids = [cid for cid in ids if cid not in existing]

    if new_chunks:
        store.add_documents(documents=new_chunks, ids=new_ids)

    source_files = sorted({p.metadata["source_file"] for p in pages})
    return {
        "pdf_files": source_files,
        "pdf_pages": len(pages),
        "chunks_new": len(new_chunks),
        "chunks_skipped_duplicate": len(chunks) - len(new_chunks),
        "skipped_files": skipped,
        "total_in_collection": collection_count(),
    }
