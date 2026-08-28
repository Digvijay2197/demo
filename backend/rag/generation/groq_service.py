"""LLM wrapper (Groq via LangChain).

Isolated here so the provider can be swapped (OpenAI, Anthropic, a local
model) without touching retrieval or the API layer.
"""
from functools import lru_cache
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from rag.config import GROQ_API_KEY, GROQ_MODEL
from rag.generation.prompt import GROUNDING_SYSTEM_PROMPT, build_context_block


@lru_cache(maxsize=1)
def _get_llm():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set (copy .env.example to .env and fill it in)")
    from langchain_groq import ChatGroq

    return ChatGroq(model=GROQ_MODEL, temperature=0, api_key=GROQ_API_KEY)


def generate_grounded_answer(question: str, results: List[Tuple[Document, float]]) -> str:
    context_block = build_context_block(results)
    messages = [
        SystemMessage(content=GROUNDING_SYSTEM_PROMPT),
        HumanMessage(
            content=f"Retrieved recipe context:\n\n{context_block}\n\nQuestion: {question}"
        ),
    ]
    return _get_llm().invoke(messages).content or ""
