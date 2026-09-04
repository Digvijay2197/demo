"""Load text-based PDF files into LangChain Documents.

Any PDF dropped into PDF_DIR is accepted regardless of filename. Each page
becomes one Document with metadata: source_file, page (1-indexed), title.
Uses PyMuPDF directly (fast, no extra deps). Scanned / image-only PDFs are
out of scope (no OCR) - a page with no extractable text is skipped and the
file is reported as skipped if it has no text at all.
"""
import os
import re
import unicodedata
from typing import List, Tuple

import pymupdf  # PyMuPDF
from langchain_core.documents import Document

from rag.config import PDF_DIR

_WS_RUN = re.compile(r"[ \t]{2,}")
_BLANK_RUN = re.compile(r"\n{3,}")
_KV_PAIR = re.compile(r"([a-zA-Z_]+)=([^;]*)")


def _structured_metadata(doc: pymupdf.Document) -> dict:
    """Recipe metadata (recipe_id, cuisine, dietary_tags, ...) authored into
    the PDF's `keywords` field as "key=value;key=value" - a generator-side
    convention (see scripts/generate_fermentation_cards.py), not a PDF
    standard. Returns {} for PDFs that don't use it (nothing extra to attach).
    """
    keywords = (doc.metadata or {}).get("keywords") or ""
    pairs = {k: v.strip() for k, v in _KV_PAIR.findall(keywords)}
    if not pairs:
        return {}

    meta = dict(pairs)
    tags = {t.strip().lower() for t in meta.get("dietary_tags", "").split(",") if t.strip()}
    meta["dietary_tags"] = ", ".join(sorted(tags))
    # Individual booleans too: Chroma's `where` filter needs scalar equality,
    # it can't test membership in a comma-joined string.
    for tag in ("vegan", "vegetarian", "gluten-free", "contains-dairy"):
        meta[f"is_{tag.replace('-', '_')}"] = tag in tags
    return meta


def _clean(text: str) -> str:
    """Normalise PDF-extracted text so retrieval and citations stay clean.

    NFKC splits typographic ligatures (ﬁ -> fi, ﬂ -> fl) that would otherwise
    make words like "flour" unsearchable; bullet glyphs become "- "; runs of
    spaces / blank lines are collapsed.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("•", "- ").replace("\xa0", " ")
    text = _WS_RUN.sub(" ", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip()


def list_pdf_files(directory: str = None) -> List[str]:
    directory = directory or PDF_DIR
    if not os.path.isdir(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.lower().endswith(".pdf")
    )


def load_pdf(path: str) -> List[Document]:
    """Return one Document per page that has extractable text."""
    source_file = os.path.basename(path)
    pages: List[Document] = []
    with pymupdf.open(path) as doc:
        doc_title = (doc.metadata or {}).get("title") or source_file
        extra_meta = _structured_metadata(doc)
        for page_number, page in enumerate(doc, start=1):
            text = _clean(page.get_text("text"))
            if not text:
                continue  # image-only / empty page - nothing to embed
            pages.append(
                Document(
                    page_content=text,
                    metadata={
                        "source_file": source_file,
                        "page": page_number,
                        "title": doc_title.strip() or source_file,
                        **extra_meta,
                    },
                )
            )
    return pages


def load_all_pdfs(directory: str = None) -> Tuple[List[Document], List[str]]:
    """Load every PDF in the directory.

    Returns (pages, skipped_files) where skipped_files are PDFs that yielded
    no extractable text at all (likely scanned images).
    """
    docs: List[Document] = []
    skipped: List[str] = []
    for path in list_pdf_files(directory):
        pages = load_pdf(path)
        if pages:
            docs.extend(pages)
        else:
            skipped.append(os.path.basename(path))
    return docs, skipped
