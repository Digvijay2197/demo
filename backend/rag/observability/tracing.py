"""Week 11: per-request tracing. One JSON line per /chat request.

A trace answers "what did the app do for this request, and what did it cost?"
without needing a trace id from the user. Every record carries:

  identity   trace_id, ts (UTC), user_id, session_id
  versions   prompt_version, model
  input      question, input_type (classified at log time)
  output     answer, refused, answer_flags (derived at log time)
  context    retrieved = [{chunk_id, source_file, page, score}]
  spans      [{name, latency_ms, tokens_in, tokens_out, cost_usd, ...}]
  totals     latency_ms, tokens_in, tokens_out, cost_usd

Both the question AND the answer are stored in full: a complaint usually
describes the output ("recommended ghee as dairy-free"), so both sides must be
searchable. Logging never raises into the request path.
"""
import contextvars
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from rag.config import GROQ_MODEL, PRICE_IN_PER_M, PRICE_OUT_PER_M

_LOG_LOCK = threading.Lock()
_current: contextvars.ContextVar = contextvars.ContextVar("w11_trace", default=None)


def log_path() -> str:
    return os.environ.get("TRACE_LOG_PATH") or os.path.join(os.getcwd(), "logs", "traces.jsonl")


def _enabled() -> bool:
    return os.environ.get("TRACE_LOG", "true").strip().lower() in ("1", "true", "yes", "on")


# ---- input classification (rule-based, cheap, done at log time) -------------
_DIETARY = re.compile(
    r"dairy[- ]?free|lactose|vegan|vegetarian|gluten|nut[- ]?free|allerg|"
    r"can't (have|eat)|cannot (have|eat)|halal|kosher", re.I)
_SUBST = re.compile(r"substitut|instead of|swap|replace|alternative|what else|what can i use", re.I)
_FULL = re.compile(r"\brecipe\b|give me|ingredients|steps", re.I)
_NUMERIC = re.compile(r"how (much|many|long)|total|temperature|calorie|minutes|hours", re.I)


def classify_input(question: str) -> str:
    if _DIETARY.search(question):
        return "dietary_restriction"
    if _SUBST.search(question):
        return "substitution"
    if _NUMERIC.search(question):
        return "lookup"
    if _FULL.search(question):
        return "full_recipe"
    return "other"


# ---- trace + spans -----------------------------------------------------------
class Trace:
    def __init__(self, question: str, user_id: str, session_id: str, prompt_version: str):
        self.trace_id = "tr_" + uuid.uuid4().hex[:12]
        self.t0 = time.perf_counter()
        self.rec = {
            "trace_id": self.trace_id,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "user_id": user_id or "anon",
            "session_id": session_id or "none",
            "prompt_version": prompt_version,
            "model": GROQ_MODEL,
            "input_type": classify_input(question),
            "question": question,
            "answer": None,
            "refused": None,
            "retrieved": [],
            "spans": [],
            "error": None,
        }


@contextmanager
def span(name: str, **attrs):
    """Time a stage; yields a dict the caller can add tokens/cost/attrs to."""
    tr = _current.get()
    s = {"name": name, "latency_ms": None, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, **attrs}
    start = time.perf_counter()
    try:
        yield s
    finally:
        s["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        if tr is not None:
            s["start_ms"] = round((start - tr.t0) * 1000, 1)
            tr.rec["spans"].append(s)


def current_trace() -> Optional[Trace]:
    return _current.get()


def start_trace(question: str, user_id: str = "anon", session_id: str = "none",
                prompt_version: str = "?") -> Trace:
    tr = Trace(question, user_id, session_id, prompt_version)
    _current.set(tr)
    return tr


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * PRICE_IN_PER_M + tokens_out * PRICE_OUT_PER_M) / 1_000_000


def record_llm_usage(response) -> None:
    """Attach token usage + cost from a LangChain AIMessage to the open generation span."""
    tr = _current.get()
    if tr is None:
        return
    um = getattr(response, "usage_metadata", None) or {}
    tin, tout = int(um.get("input_tokens", 0)), int(um.get("output_tokens", 0))
    reasoning = int((um.get("output_token_details") or {}).get("reasoning", 0))
    # the generation span may still be open (it closes after we return), so
    # stash on the trace and let finish_trace fold it into the span.
    tr.rec["_llm"] = {"tokens_in": tin, "tokens_out": tout, "reasoning_tokens": reasoning}


def finish_trace(result: Optional[dict] = None, error: Optional[str] = None,
                 answer_flags: Optional[dict] = None, retrieved: Optional[list] = None) -> Optional[str]:
    tr = _current.get()
    if tr is None:
        return None
    rec = tr.rec
    try:
        llm = rec.pop("_llm", None)
        for s in rec["spans"]:
            if s["name"] == "generation" and llm:
                s.update(llm)
                s["cost_usd"] = cost_usd(llm["tokens_in"], llm["tokens_out"])
        if result is not None:
            rec["answer"] = result.get("answer")
            rec["refused"] = result.get("refused")
        if retrieved is not None:
            rec["retrieved"] = retrieved
        if answer_flags is not None:
            rec["answer_flags"] = answer_flags
        rec["error"] = error
        rec["latency_ms"] = round((time.perf_counter() - tr.t0) * 1000, 1)
        rec["tokens_in"] = sum(s["tokens_in"] for s in rec["spans"])
        rec["tokens_out"] = sum(s["tokens_out"] for s in rec["spans"])
        rec["cost_usd"] = round(sum(s["cost_usd"] for s in rec["spans"]), 8)
        if _enabled():
            os.makedirs(os.path.dirname(log_path()), exist_ok=True)
            with _LOG_LOCK, open(log_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 - observability must never break a request
        print("[trace] write failed:", repr(exc))
    finally:
        _current.set(None)
    return rec["trace_id"]
