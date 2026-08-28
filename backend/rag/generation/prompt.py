"""Grounded prompt for the recipe chatbot."""
from typing import List, Tuple

from langchain_core.documents import Document

GROUNDING_SYSTEM_PROMPT = """You are a recipe assistant. Answer using ONLY the \
retrieved context below. Never invent quantities, times, temperatures, or steps.

- Treat typos and synonyms as the same ("solt"=salt, "temp"=temperature).
- If the exact detail isn't stated but the context is about that recipe, say what \
the recipe does state that is relevant instead of refusing.
- For "list all ingredients / every step", give the full list from the context.
- Quote quantities exactly as written.
- After each factual sentence add its source in this exact form, copied from the \
header above that chunk: [source: FILENAME.pdf p.N]

If no retrieved context covers the question, reply with exactly:
"I couldn't find enough information in the provided recipes to answer that question."
"""

REFUSAL_MESSAGE = (
    "I couldn't find enough information in the provided recipes to answer that question."
)


def build_context_block(results: List[Tuple[Document, float]]) -> str:
    blocks = []
    for doc, score in results:
        src = doc.metadata.get("source_file", "unknown.pdf")
        page = doc.metadata.get("page", "?")
        blocks.append(f"[source: {src} p.{page}]\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)
