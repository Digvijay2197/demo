"""Per-request tracing for the capstone: ONE trace id from question in to answer out,
surviving the agent hop (laps) and the MCP hop (a separate server process).

  client process  : trace record  {trace_id, spans:[llm / mcp_call / guard / ...], totals}
  server process  : span records  {trace_id, tool, latency_ms, pid}  -> capstone_mcp_spans.jsonl
                    (the client injects `trace_id` into every tool call; the server logs it)
  load_trace(id)  : joins both files, so one id shows every hop with cost + latency.

THE PII LINE (a stated allergy is health data - decided deliberately, not by default):

  WRITTEN : allergen CLASSES the deterministic parser extracted (tree_nut, dairy, ...) -
            needed to reproduce a safety failure; tool names/args/results (recipe ids,
            versions); token counts, cost, latency; guard decisions.
  REDACTED: names, relationships ("my daughter Priya"), ages, emails, phone numbers
            are stripped from the question AND the answer before they are written.
  NEVER   : a raw user id (a user id is only logged, salted+hashed, if CAPSTONE_LOG_USER=1),
            the unredacted question text, anything the user said about a diagnosis.
  Regex redaction is best-effort, not a guarantee - see docs/capstone/weaknesses.md.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from capstone import config

_LOCK = threading.Lock()
_current: contextvars.ContextVar = contextvars.ContextVar("capstone_trace", default=None)

_REL = (r"(?:daughter|son|child|kid|baby|toddler|wife|husband|partner|mother|mom|mum|father|dad|"
        r"brother|sister|nephew|niece|grandson|granddaughter|friend|girlfriend|boyfriend|cousin|"
        r"grandma|grandpa|grandmother|grandfather|student|pupil|customer)")
_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)"), "[PHONE]"),
    (re.compile(rf"\bmy\s+{_REL}(?:\s+[A-Z][a-z]+)?(?:'s)?", re.I), "my [FAMILY]"),
    (re.compile(rf"\b(?:the|a|our)\s+{_REL}\b", re.I), "the [PERSON]"),
    (re.compile(r"\b(?:named|called)\s+[A-Z][a-z]+"), "named [NAME]"),
    (re.compile(r"\b\d{1,2}[- ]?(?:year|yr)s?[- ]?old\b|\bage[d]?\s+\d{1,2}\b", re.I), "[AGE]"),
    (re.compile(r"\b(?:i am|i'm|im)\b", re.I), "user is"),
]


_NAME_IN_Q = re.compile(rf"\bmy\s+{_REL}\s+([A-Z][a-z]+)|\b(?:named|called)\s+([A-Z][a-z]+)", re.I)


def names_in(question: str) -> list:
    """Personal names the user introduced - scrubbed from the ANSWER too, which tends to echo them."""
    out = []
    for m in _NAME_IN_Q.finditer(question or ""):
        n = m.group(1) or m.group(2)
        if n and n[0].isupper():
            out.append(n)
    return out


def redact(text: Optional[str], names: tuple = ()) -> Optional[str]:
    if not text:
        return text
    for n in names:
        text = re.sub(rf"\b{re.escape(n)}(?:'s)?\b", "[NAME]", text)
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text


def _hash_user(user_id: str) -> str:
    salt = os.environ.get("CAPSTONE_LOG_SALT", "capstone-dev-salt")
    return "u_" + hashlib.sha256((salt + user_id).encode()).hexdigest()[:10]


class Trace:
    def __init__(self, question: str, avoid: list, unsupported: list, user_id: str = "", extra: dict | None = None):
        self.trace_id = "cap_" + uuid.uuid4().hex[:12]
        self.t0 = time.perf_counter()
        self.names = tuple(names_in(question))
        self.rec = {
            "trace_id": self.trace_id,
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "config": config.config_snapshot(),
            "question_redacted": redact(question),
            "avoid_classes": avoid,
            "unsupported_allergens": unsupported,
            "spans": [], "answer_redacted": None, "raw_answer_redacted": None,
            "refused": None, "guards_fired": [], "error": None, **(extra or {}),
        }
        if os.environ.get("CAPSTONE_LOG_USER") == "1" and user_id:
            self.rec["user"] = _hash_user(user_id)


def current() -> Optional[Trace]:
    return _current.get()


def start_trace(question: str, avoid: list, unsupported: list, user_id: str = "", extra: dict | None = None) -> Trace:
    tr = Trace(question, avoid, unsupported, user_id, extra)
    _current.set(tr)
    return tr


@contextmanager
def span(name: str, kind: str = "internal", **attrs):
    """Times a stage; the caller can add tokens/cost/attrs to the yielded dict."""
    tr = _current.get()
    s = {"name": name, "kind": kind, "latency_ms": None, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, **attrs}
    start = time.perf_counter()
    try:
        yield s
    finally:
        s["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        if tr is not None:
            s["start_ms"] = round((start - tr.t0) * 1000, 1)
            tr.rec["spans"].append(s)


def finish_trace(**fields) -> Optional[dict]:
    tr = _current.get()
    if tr is None:
        return None
    rec = tr.rec
    try:
        for k in ("answer", "raw_answer"):
            if k in fields:
                rec[k + "_redacted"] = redact(fields.pop(k), tr.names)
        rec.update(fields)
        rec["latency_ms"] = round((time.perf_counter() - tr.t0) * 1000, 1)
        rec["tokens_in"] = sum(s["tokens_in"] for s in rec["spans"])
        rec["tokens_out"] = sum(s["tokens_out"] for s in rec["spans"])
        rec["cost_usd"] = round(sum(s["cost_usd"] for s in rec["spans"]), 8)
        if os.environ.get("CAPSTONE_TRACE", "on") != "off":
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            with _LOCK, open(config.trace_path(), "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001 - observability must never break a request
        print("[trace] write failed:", repr(exc))
    finally:
        _current.set(None)
    return rec


# ---- server side (runs inside the MCP server process) ----------------------
def log_server_span(trace_id: str, tool: str, latency_ms: float, ok: bool = True) -> None:
    if not trace_id or os.environ.get("CAPSTONE_TRACE", "on") == "off":
        return
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        rec = {"trace_id": trace_id, "side": "mcp_server", "tool": tool,
               "latency_ms": round(latency_ms, 2), "ok": ok, "pid": os.getpid(), "cost_usd": 0.0,
               "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
        with _LOCK, open(config.mcp_span_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:  # noqa: BLE001
        pass


def _read_jsonl(path) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def load_trace(trace_id: str) -> Optional[dict]:
    """The whole request: client trace + the server-side spans that carried its id."""
    client = next((r for r in reversed(_read_jsonl(config.trace_path())) if r.get("trace_id") == trace_id), None)
    if client is None:
        return None
    server = [r for r in _read_jsonl(config.mcp_span_path()) if r.get("trace_id") == trace_id]
    return {**client, "mcp_server_spans": server,
            "trace_id_survived_mcp_hop": bool(server) or not any(s["kind"] == "mcp_call" for s in client["spans"])}
