"""The request and the output contract both systems share, plus the pass check.

Both the agent loop and the workflow must return a dict shaped like::

    {
      "recipe": str,
      "servings": int,
      "ingredients": [{"item": str, "qty": <number|str>, "unit": str}],
      "substitutions": [{"from": str, "to": str, "reason": str}],
      "method": [str, ...]
    }

``passes`` scores that dict against the request with cheap deterministic
assertions — no LLM judge — so agent and workflow are held to the identical bar.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List

from agent.recipes import SUBSTITUTIONS, find


@dataclass
class RecipeRequest:
    id: str
    query: str
    servings: int
    avoid: List[str]
    # cascade == at least one first-choice substitute is itself in `avoid`
    cascade: bool = False
    notes: str = ""


@dataclass
class Result:
    request_id: str
    system: str                 # "agent" | "workflow"
    output: dict
    ok: bool
    checks: dict
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    llm_calls: int
    tool_calls: int
    terminated_by: str = ""     # set when a budget fired
    error: str = ""

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict:
    """Pull the first {...} object out of a model message, tolerating ```json
    fences and leading prose. Returns {} if nothing parses."""
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else (_JSON_BLOCK.search(text) or [None])
    raw = candidate if isinstance(candidate, str) else (candidate.group(0) if candidate else "")
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


def _allergens_of(item: str) -> List[str]:
    """Allergen classes of a final-list ingredient: from the recipe book if it
    is an original ingredient, else from the substitution table."""
    it = item.strip().lower()
    for r in (find(it),):
        if r:
            for ing in r["ingredients"]:
                if ing["item"] == it:
                    return ing["allergens"]
    for src, sub in SUBSTITUTIONS.items():
        if sub["to"].lower() == it:
            return sub["allergens"]
    # original ingredient not matched above: scan every recipe
    from agent.recipes import RECIPES
    for r in RECIPES.values():
        for ing in r["ingredients"]:
            if ing["item"] == it:
                return ing["allergens"]
    return []


def passes(req: RecipeRequest, out: dict) -> dict:
    """Deterministic assertion checks. Returns {check_name: bool}; the case
    passes iff every value is True."""
    checks = {}
    checks["is_object"] = isinstance(out, dict) and bool(out)
    if not checks["is_object"]:
        return checks

    recipe = find(req.query)
    ing_list = out.get("ingredients") or []
    items = [str(i.get("item", "")).strip().lower() for i in ing_list if isinstance(i, dict)]
    method = out.get("method") or []

    checks["right_recipe"] = bool(recipe) and recipe["name"].lower() in str(out.get("recipe", "")).lower()
    checks["servings_set"] = str(out.get("servings")) == str(req.servings)
    checks["has_ingredients"] = len(items) >= 3
    checks["has_method"] = isinstance(method, list) and len(method) >= 3

    # every banned allergen is absent from the final ingredient list
    present = {a for it in items for a in _allergens_of(it)}
    checks["allergen_free"] = not (present & set(req.avoid))

    # the original banned ingredients are actually gone
    if recipe:
        banned_originals = [
            ing["item"] for ing in recipe["ingredients"]
            if set(ing["allergens"]) & set(req.avoid)
        ]
        checks["originals_removed"] = all(b not in items for b in banned_originals)
    else:
        checks["originals_removed"] = False

    # scaling actually happened: a sentinel scalable ingredient is at base*factor
    checks["scaled"] = _scaling_ok(req, recipe, ing_list)
    return checks


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group(0)) if m else None


def _scaling_ok(req, recipe, ing_list) -> bool:
    if not recipe:
        return False
    factor = req.servings / recipe["base_servings"]
    if abs(factor - 1.0) < 1e-6:
        return True  # nothing to prove
    by_item = {str(i.get("item", "")).strip().lower(): i.get("qty") for i in ing_list
               if isinstance(i, dict)}
    for ing in recipe["ingredients"]:
        if not isinstance(ing["qty"], (int, float)):
            continue
        if set(ing["allergens"]) & set(req.avoid):
            continue  # this one was substituted, ratio differs
        got = _num(by_item.get(ing["item"]))
        if got is None:
            continue
        return abs(got - ing["qty"] * factor) <= max(0.5, 0.05 * ing["qty"] * factor)
    return False
