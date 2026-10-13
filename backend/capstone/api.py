"""Thin HTTP face over the single entry point - exists so citations are CLICKABLE links.
No UI. `python -m capstone serve` -> http://127.0.0.1:8100/docs"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from capstone import agent, domain, obs

app = FastAPI(title="Pantry-to-Plate (capstone)")


class Ask(BaseModel):
    question: str


@app.post("/ask")
def ask(body: Ask) -> dict:
    out = agent.ask(body.question)
    return {k: out[k] for k in ("trace_id", "answer", "citations", "refused", "guards_fired", "cost_usd", "latency_ms")}


@app.get("/recipes/{recipe_id}")
def recipe(recipe_id: str, version: str | None = None) -> dict:
    try:
        return domain.get_record(recipe_id, version)
    except domain.RecipeNotFound as exc:
        raise HTTPException(404, str(exc))


@app.get("/traces/{trace_id}")
def trace(trace_id: str) -> dict:
    t = obs.load_trace(trace_id)
    if not t:
        raise HTTPException(404, "no such trace")
    return t
