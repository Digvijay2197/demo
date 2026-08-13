import os
from typing import List
from rag.generation.prompt import GROUNDING_SYSTEM_PROMPT, build_context_block

# LLM provider isolated behind this service so Groq can be swapped later
# without touching retrieval, chunking, or the API layer.
_client = None


def _get_client():
    global _client
    if _client is None:
        from groq import Groq

        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=api_key)
    return _client


def generate_grounded_answer(question: str, context_chunks: List[dict]) -> str:
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    context_block = build_context_block(context_chunks)

    completion = _get_client().chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Retrieved recipe context:\n\n{context_block}\n\nQuestion: {question}",
            },
        ],
    )

    return completion.choices[0].message.content or ""
