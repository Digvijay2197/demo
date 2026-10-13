"""Capstone configuration, read from the environment at call time (not import
time) so the eval can flip the BEFORE/AFTER switches between runs and the MCP
server subprocess inherits them."""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
RECIPES_JSON = DATA_DIR / "recipes.json"
LOG_DIR = BACKEND_DIR / "logs"
CHROMA_DIR = str(BACKEND_DIR / "data" / "chroma_capstone")
COLLECTION = "capstone_recipes"
DOCS_DIR = BACKEND_DIR.parent / "docs" / "capstone"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip().lower()


def version_policy() -> str:
    """'resolved' = the fix (current version by default, superseded flagged);
    'naive'    = what the client's site did: a recipe id returns whichever row was
                 indexed first, with no notion of superseded."""
    return _env("CAPSTONE_VERSION_POLICY", "resolved")


def guards_on() -> bool:
    return _env("CAPSTONE_GUARDS", "on") in ("on", "1", "true")


def substitution_mode() -> str:
    """'checked' = substitutions are filtered against the avoid list AND the recipe
    is re-checked AS SUBSTITUTED (bonus fix); 'plain' = table lookup, allergen check
    on the published recipe only (the pre-bonus system)."""
    return _env("CAPSTONE_SUBSTITUTION", "checked")


def trace_path() -> Path:
    return Path(os.environ.get("CAPSTONE_TRACE_LOG") or (LOG_DIR / "capstone_traces.jsonl"))


def mcp_span_path() -> Path:
    return Path(os.environ.get("CAPSTONE_MCP_SPAN_LOG") or (LOG_DIR / "capstone_mcp_spans.jsonl"))


def config_snapshot() -> dict:
    return {"version_policy": version_policy(), "guards": guards_on(),
            "substitution": substitution_mode(),
            "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")}
