"""End-to-end RAG: question -> retrieve -> grounding gate -> generate -> cite."""
import re
from typing import List, Tuple

from langchain_core.documents import Document

from rag.config import SIMILARITY_THRESHOLD
from rag.generation.groq_service import generate_grounded_answer
from rag.generation.prompt import REFUSAL_MESSAGE
from rag.retrieval.retriever import has_sufficient_evidence, retrieve

# Models sometimes render the citation with full-width brackets or smart
# hyphens, and typographic spaces (narrow/no-break) around units and "%".
# Normalise all of that before parsing / display.
_NORMALISE = {
    "【": "[", "】": "]",
    "［": "[", "］": "]",
    "‑": "-", "­": "-",              # non-breaking / soft hyphen
    "–": "-", "—": "-",                    # en / em dash inside filenames
    " ": " ", " ": " ", " ": " ",  # narrow / no-break / thin space
    "​": "",                          # zero-width space
}
# Matches [source: file.pdf p.1] and the shorter [file.pdf p.1] the model
# sometimes emits. The filename must carry a .ext so ordinary bracketed prose
# is never mistaken for a citation.
_CITATION_RE = re.compile(
    r"\[\s*(?:source:\s*)?([^\]]*?\.[A-Za-z0-9]+)\s+p(?:age|\.)?\s*(\d+)\s*\]",
    re.IGNORECASE,
)


def _normalise_answer(text: str) -> str:
    for bad, good in _NORMALISE.items():
        text = text.replace(bad, good)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def _stem(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _citations_from_results(results: List[Tuple[Document, float]]) -> List[dict]:
    seen = set()
    citations = []
    for doc, score in results:
        src = doc.metadata.get("source_file", "unknown.pdf")
        page = int(doc.metadata.get("page", 0) or 0)
        key = (src, page)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "chunk_id": doc.metadata.get("chunk_id", ""),
                "source_file": src,
                "page": page,
                "snippet": doc.metadata.get("snippet") or doc.page_content[:280].strip(),
                "score": round(float(score), 4),
            }
        )
    return citations


def answer_question(question: str, hybrid: bool = None) -> dict:
    results = retrieve(question, hybrid=hybrid)

    if not has_sufficient_evidence(results):
        return {"answer": REFUSAL_MESSAGE, "citations": [], "refused": True}

    answer = _normalise_answer(generate_grounded_answer(question, results))

    if answer.startswith("I couldn't find enough information"):
        return {"answer": REFUSAL_MESSAGE, "citations": [], "refused": True}

    all_citations = _citations_from_results(results)

    # Which sources did the model actually cite? Match tolerantly on filename
    # stem + page, since the model may re-spell the filename.
    cited_keys = {(_stem(m.group(1)), int(m.group(2))) for m in _CITATION_RE.finditer(answer)}
    referenced = [
        c for c in all_citations
        if any(k[1] == c["page"] and (k[0] in _stem(c["source_file"]) or _stem(c["source_file"]) in k[0])
               for k in cited_keys)
    ]

    if referenced:
        citations = referenced
    else:
        # Model emitted no parseable markers - the answer is still grounded in
        # the retrieved context, so attribute it to the chunks that actually
        # cleared the relevance gate (top 2 at most), not every retrieved chunk.
        citations = [c for c in all_citations if c["score"] >= SIMILARITY_THRESHOLD][:2] or all_citations[:1]

    return {"answer": answer, "citations": citations, "refused": False}
