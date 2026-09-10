"""The fixed workflow: the identical task as three hard-coded tool steps plus
one generation call. Same tools, same model, same output contract, no agent
loop.

The control flow is the same for every request regardless of its content:

    search_recipes  ->  get_nutrition  ->  substitute_ingredient (per banned
    ingredient, with a fixed-depth cascade resolve)  ->  one LLM call to render
    the adapted method.

The only bounded repetition is CASCADE_DEPTH: a substitute can itself carry a
banned allergen, and the substitution table has chains at most three deep
(flour -> almond flour -> oat flour -> rice flour). That is a fixed constant,
not iterate-until-the-model-says-stop.
"""
from __future__ import annotations

import json
import time
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agent.contract import RecipeRequest, Result, extract_json, passes
from agent.llm import Usage, plain_llm, usage_of
from agent.tools import run_tool

CASCADE_DEPTH = 3

_RENDER_SYSTEM = """You rewrite recipe method steps after ingredient swaps.
Given the original steps and a list of substitutions (from -> to), return the
steps with each 'from' replaced by its 'to', wording adjusted minimally so each
step still reads naturally. Reply with ONLY a JSON array of strings."""


def _call(name: str, args: dict, counter: List[int]) -> dict:
    counter[0] += 1
    return json.loads(run_tool(name, args))


def run_workflow(req: RecipeRequest, pace_s: float = 0.0, verbose: bool = False) -> Result:
    # pace_s is accepted for call-site symmetry with run_agent; the workflow
    # makes a single LLM call, which the race loop already spaces.
    _ = pace_s
    started = time.monotonic()
    usage = Usage()
    tool_calls = [0]
    err = ""
    output: dict = {}

    try:
        # --- step 1: fetch -------------------------------------------------
        s = _call("SearchRecipes", {"query": req.query}, tool_calls)
        recipe = (s.get("matches") or [None])[0]
        if not recipe:
            raise RuntimeError(f"search_recipes found nothing for {req.query!r}")
        name = recipe["name"]

        # --- step 2: scale ----------------------------------------------------
        n = _call("GetNutrition", {"recipe_name": name, "servings": req.servings}, tool_calls)
        ingredients = [dict(i) for i in n["scaled_ingredients"]]

        # --- step 3: substitute every banned ingredient ---------------------
        avoid = set(req.avoid)
        subs_applied: List[dict] = []
        for idx, ing in enumerate(ingredients):
            banned_here = set(ing["allergens"]) & avoid
            if not banned_here:
                continue
            cur_item, cur_qty, cur_allergens = ing["item"], ing["qty"], set(ing["allergens"])
            for _ in range(CASCADE_DEPTH):
                target = next(iter(cur_allergens & avoid))
                r = _call("SubstituteIngredient",
                          {"recipe_name": name, "ingredient": cur_item, "avoid_allergen": target},
                          tool_calls)
                if "error" in r:
                    break
                subs_applied.append({"from": cur_item, "to": r["substitute"],
                                     "reason": f"removes {target}"})
                if isinstance(cur_qty, (int, float)):
                    cur_qty = round(cur_qty * r["amount_ratio"], 2)
                cur_item = r["substitute"]
                cur_allergens = set(r["substitute_allergens"])
                if not (cur_allergens & avoid):   # cascade resolved
                    break
            ingredients[idx] = {"item": cur_item, "qty": cur_qty, "unit": ing["unit"],
                                "allergens": sorted(cur_allergens)}

        # --- step 4: one generation call to render the method --------------
        method = _render_method(recipe["method"], subs_applied, usage)

        # collapse a from->...->to chain to one row per original ingredient
        substitutions = _dedup_chain(subs_applied)

        output = {
            "recipe": name,
            "servings": req.servings,
            "ingredients": [{"item": i["item"], "qty": i["qty"], "unit": i["unit"]}
                            for i in ingredients],
            "substitutions": substitutions,
            "method": method,
        }
    except Exception as exc:  # noqa: BLE001
        err = repr(exc)

    latency = time.monotonic() - started
    checks = passes(req, output) if output else {"is_object": False}
    ok = bool(output) and all(checks.values()) and not err
    if verbose:
        print(f"  workflow: tools={tool_calls[0]} llm_calls={1 if usage.total_tokens else 0} "
              f"tokens={usage.total_tokens} ok={ok}")

    res = Result(
        request_id=req.id, system="workflow", output=output, ok=ok, checks=checks,
        latency_s=round(latency, 3), prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        llm_calls=1 if usage.total_tokens else 0, tool_calls=tool_calls[0], error=err,
    )
    res.laps_log = []  # type: ignore[attr-defined]
    return res


def _origin(subs: List[dict], frm: str) -> str:
    """Walk a chain backwards: if 'frm' is itself the 'to' of an earlier sub,
    return that earlier 'from'."""
    for s in subs:
        if s["to"] == frm:
            return _origin(subs, s["from"])
    return frm


def _dedup_chain(subs: List[dict]) -> List[dict]:
    seen, out = set(), []
    for s in subs:
        origin = _origin(subs, s["from"])
        if origin in seen:
            # update the existing row's final 'to'
            for row in out:
                if row["from"] == origin:
                    row["to"] = s["to"]
            continue
        seen.add(origin)
        out.append({"from": origin, "to": s["to"], "reason": s["reason"]})
    return out


def _render_method(base_steps: List[str], subs: List[dict], usage: Usage) -> List[str]:
    if not subs:
        return list(base_steps)
    pairs = _dedup_chain(subs)
    payload = {"steps": base_steps,
               "substitutions": [{"from": p["from"], "to": p["to"]} for p in pairs]}
    msg = [SystemMessage(content=_RENDER_SYSTEM),
           HumanMessage(content=json.dumps(payload))]
    try:
        resp = plain_llm().invoke(msg)
        usage_add = usage_of(resp)
        # mutate caller's Usage in place
        usage.prompt_tokens += usage_add.prompt_tokens
        usage.completion_tokens += usage_add.completion_tokens
        parsed = extract_json("{\"m\":" + (resp.content or "") + "}").get("m") \
            or _parse_array(resp.content or "")
        if isinstance(parsed, list) and parsed:
            return [str(x) for x in parsed]
    except Exception:  # noqa: BLE001
        pass
    # deterministic fallback: literal string replacement
    out = list(base_steps)
    for p in pairs:
        out = [step.replace(p["from"], p["to"]) for step in out]
    return out


def _parse_array(text: str):
    import re
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
