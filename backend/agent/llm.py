"""One Groq client for both systems, with per-call token + cost metering.

The race's token and cost numbers come straight out of ``usage_of`` on every
LLM response — the agent loop sums it over every lap (so the growing re-sent
message list is counted, not just the last call), and the workflow sums it over
its one generation call.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from langchain_core.messages import AIMessage

# Groq list price in USD per 1M tokens (input, output), from groq.com/pricing,
# checked 2026-02. Override for a model not listed here via GROQ_PRICE_IN/OUT.
GROQ_PRICING = {
    "openai/gpt-oss-20b": (0.10, 0.50),
    "openai/gpt-oss-120b": (0.15, 0.75),
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
}

GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
_PRICE_IN = float(os.environ.get("GROQ_PRICE_IN", GROQ_PRICING.get(GROQ_MODEL, (0.10, 0.50))[0]))
_PRICE_OUT = float(os.environ.get("GROQ_PRICE_OUT", GROQ_PRICING.get(GROQ_MODEL, (0.10, 0.50))[1]))


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        return (self.prompt_tokens / 1e6) * _PRICE_IN + (self.completion_tokens / 1e6) * _PRICE_OUT

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(self.prompt_tokens + other.prompt_tokens,
                     self.completion_tokens + other.completion_tokens)


def usage_of(msg: AIMessage) -> Usage:
    """Pull token counts off a LangChain AIMessage (Groq puts them in both
    ``usage_metadata`` and ``response_metadata['token_usage']``)."""
    um = getattr(msg, "usage_metadata", None)
    if um:
        return Usage(int(um.get("input_tokens", 0)), int(um.get("output_tokens", 0)))
    tu = (msg.response_metadata or {}).get("token_usage", {})
    return Usage(int(tu.get("prompt_tokens", 0)), int(tu.get("completion_tokens", 0)))


@lru_cache(maxsize=1)
def _base_llm():
    from langchain_groq import ChatGroq

    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set (copy backend/.env.example to .env)")
    kwargs = dict(model=GROQ_MODEL, temperature=0, api_key=key, max_retries=4)
    try:
        return ChatGroq(reasoning_effort="low", **kwargs)
    except TypeError:
        return ChatGroq(model_kwargs={"reasoning_effort": "low"}, **kwargs)


@lru_cache(maxsize=1)
def tool_llm():
    """The model with the three tools bound — used by the agent loop."""
    from agent.tools import TOOL_SCHEMAS

    return _base_llm().bind_tools(TOOL_SCHEMAS)


def plain_llm():
    """The model with no tools — used by the workflow's single render call."""
    return _base_llm()
