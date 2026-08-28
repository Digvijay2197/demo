"""LLM wrapper (Groq via LangChain).

Isolated here so the provider can be swapped without touching retrieval or the
API layer. Two things guard the Groq free tier (8k tokens/minute):
  - the retrieved context is trimmed to MAX_CONTEXT_CHARS before it is sent;
  - reasoning effort is forced low (gpt-oss / qwen burn hidden reasoning tokens);
  - the client retries 429s with backoff, honouring Retry-After.
"""
from functools import lru_cache
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from rag.config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_REASONING_EFFORT,
    MAX_CONTEXT_CHARS,
)
from rag.generation.prompt import GROUNDING_SYSTEM_PROMPT, build_context_block


class RateLimitedError(RuntimeError):
    """Groq returned 429 and retries were exhausted."""


@lru_cache(maxsize=1)
def _get_llm():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set (copy .env.example to .env and fill it in)")
    from langchain_groq import ChatGroq

    kwargs = dict(model=GROQ_MODEL, temperature=0, api_key=GROQ_API_KEY, max_retries=4)
    try:
        return ChatGroq(reasoning_effort=GROQ_REASONING_EFFORT, **kwargs)
    except TypeError:
        # older langchain-groq without the dedicated field
        return ChatGroq(model_kwargs={"reasoning_effort": GROQ_REASONING_EFFORT}, **kwargs)


def _fit_context(results: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
    """Keep the best chunks whose combined text fits the context budget."""
    kept, used = [], 0
    for doc, score in results:
        cost = len(doc.page_content) + 40  # + room for the [source: ...] header
        if kept and used + cost > MAX_CONTEXT_CHARS:
            break
        kept.append((doc, score))
        used += cost
    return kept


def generate_grounded_answer(question: str, results: List[Tuple[Document, float]]) -> str:
    context_block = build_context_block(_fit_context(results))
    messages = [
        SystemMessage(content=GROUNDING_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Retrieved recipe context:\n\n{context_block}\n\nQuestion: {question}"
        ),
    ]
    try:
        return _get_llm().invoke(messages).content or ""
    except Exception as exc:  # noqa: BLE001
        if "rate_limit" in str(exc).lower() or "429" in str(exc):
            raise RateLimitedError(
                "The language model is rate-limited right now (Groq free tier is "
                "8,000 tokens/minute). Wait a few seconds and ask again."
            ) from exc
        raise
