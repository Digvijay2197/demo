"""Week 10 — the multi-agent orchestrator.

Same task as agent/loop.py's single agent (find the recipe, scale it, remove
every banned allergen, return the adapted method) but split across three
independent LLM contexts instead of one continuous lap loop:

    orchestrator
      -> nutrition/allergen worker   (tools: SearchRecipes, GetNutrition)
      -> substitution worker         (tool:  SubstituteIngredient only)
      -> synthesis call              (no tools: renders the adapted method)

Each worker gets its OWN system prompt and its OWN narrow tool list — the
"narrow-prompt-fewer-tools" constraint the Week 10 brief calls out as the only
plausible source of a multi-agent win. The orchestrator itself makes no LLM
call of its own to "decide" anything: the request is already the structured
RecipeRequest both other systems consume, so decomposition is a fixed,
three-step routing, not a fourth model call invented just to look agentic.

The cost this buys: every hand-off is a **fresh** message history seeded by
serializing the previous worker's JSON result into text. Groq re-bills the
whole message list every lap (see agent/llm.py), so a hand-off does not reuse
a single continuous context the way agent/loop.py's one growing message list
does — it restates it. `run_orchestrator` records each hand-off's own token
total in ``Result.handoffs`` precisely so that overhead is visible instead of
folded into one grand total.

Failure injection (Week 10 requirement 4): pass ``inject_failure={"tool":
"GetNutrition", "status": 500}`` to make the nutrition/allergen worker's
get_nutrition call raise a simulated upstream 500 on every attempt for this
request. The orchestrator retries the whole worker call once, and if it still
fails, degrades to a partial answer built from whatever the worker already
had (the unscaled base recipe from search_recipes, if that lap completed) —
it does not call the substitution worker on unconfirmed data, and it does not
synthesize an allergen-free claim the failed worker never made.
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from typing import List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.budget import Budget, BudgetExceeded
from agent.contract import RecipeRequest, Result, passes
from agent.llm import Usage, _base_llm, usage_of
from agent.tools import GetNutrition, SearchRecipes, SubstituteIngredient, run_tool
from agent.workflow import _render_method

_SCHEMAS = {"SearchRecipes": SearchRecipes, "GetNutrition": GetNutrition,
            "SubstituteIngredient": SubstituteIngredient}


def _extract_worker_json(text: str) -> dict:
    """Pull the first *balanced* {...} object out of a worker's reply.

    agent/contract.py's ``extract_json`` is greedy-to-the-last-brace, which
    is fine for the single agent's one big schema but breaks on this small
    model's narrow-worker replies: gpt-oss-20b occasionally tails its JSON
    with one extra stray ``}`` (observed live on the substitution worker), and
    a greedy match then swallows it into an unparseable candidate. Scanning
    brace depth instead stops at the first properly closed object and ignores
    whatever garbage follows it."""
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:  # noqa: BLE001
                    return {}
    return {}


class WorkerHTTPError(RuntimeError):
    """Raised when a worker's tool call fails like an upstream service would
    (used only by the injected-failure demo — the real tools never raise
    this; they return a JSON ``error`` payload instead, see agent/tools.py).

    Carries whatever the worker had already spent (tokens/laps/tool calls) up
    to the point of failure, since that spend is real even though the worker
    never returned a result — losing it would understate the cost of a
    failed hand-off."""

    def __init__(self, tool: str, status: int, detail: str = "", *,
                 partial_usage: Optional[Usage] = None, partial_laps: int = 0,
                 partial_tool_calls: int = 0, partial_laps_log: Optional[List[dict]] = None):
        self.tool, self.status = tool, status
        self.partial_usage = partial_usage or Usage()
        self.partial_laps = partial_laps
        self.partial_tool_calls = partial_tool_calls
        self.partial_laps_log = partial_laps_log or []
        super().__init__(f"{tool} failed: simulated upstream HTTP {status} {detail}".strip())


class WorkerRuntimeError(RuntimeError):
    """Wraps any invoke-time failure that is NOT the malformed-tool-call
    retry pattern and NOT an injected ``WorkerHTTPError`` — a real rate limit,
    a network error, anything this module did not itself cause. Carries
    whatever the worker already spent so a genuine failure never silently
    zeroes out real cost, the same principle as ``WorkerHTTPError``."""

    def __init__(self, original: Exception, partial_usage: Usage, partial_laps: int,
                 partial_tool_calls: int, partial_laps_log: List[dict]):
        self.original = original
        self.partial_usage = partial_usage
        self.partial_laps = partial_laps
        self.partial_tool_calls = partial_tool_calls
        self.partial_laps_log = partial_laps_log
        super().__init__(str(original))


@lru_cache(maxsize=8)
def _worker_llm(tool_names: Tuple[str, ...]):
    return _base_llm().bind_tools([_SCHEMAS[n] for n in tool_names])


NUTRITION_SYSTEM_PROMPT = """You are the nutrition/allergen worker in a multi-agent \
recipe system. Your ONLY job:
1. search_recipes to fetch the recipe.
2. get_nutrition to scale it to the requested servings.
You do not substitute anything — a different worker does that. Then STOP calling
tools and reply with ONLY this JSON object, no prose:

{"recipe": <exact name>, "servings": <int>,
 "ingredients": [{"item": <str>, "qty": <number or str>, "unit": <str>, "allergens": [<str>, ...]}],
 "method": [<step>, ...], "allergens_present": [<banned allergen classes that appear in ingredients>]}"""

SUBSTITUTION_SYSTEM_PROMPT = """You are the substitution worker in a multi-agent \
recipe system. Your ONLY job: given a recipe's already-scaled ingredient list and a
list of banned allergen classes, remove every banned allergen.
For each ingredient whose allergens intersect the banned list, call
substitute_ingredient with {"recipe_name": ..., "ingredient": ..., "avoid_allergen":
<the banned class it carries>}. If the result says cascade=true, call
substitute_ingredient again on the substitute (checking ITS allergens against the
banned list) until clear. EVERY call needs all three arguments. You do not fetch or
scale — that already happened. Then STOP calling tools and reply with ONLY this JSON
object, no prose:

{"substitutions": [{"from": <str>, "to": <str>, "reason": <str>}],
 "final_ingredients": [{"item": <str>, "qty": <number or str>, "unit": <str>}]}

final_ingredients is the COMPLETE list — untouched ingredients included unchanged,
substituted ones replaced. Do not invent ingredients or substitutions."""


def _worker_user_msg_nutrition(req: RecipeRequest) -> str:
    return (f'Fetch and scale "{req.query}" to {req.servings} servings. '
            f'Banned allergen classes for this request: {", ".join(req.avoid)}. '
            f'Report which of those are present in allergens_present.')


def _worker_user_msg_substitution(req: RecipeRequest, nutrition_out: dict) -> str:
    return (f'Recipe "{nutrition_out.get("recipe")}", {nutrition_out.get("servings")} servings. '
            f'Scaled ingredients (JSON): {json.dumps(nutrition_out.get("ingredients") or [])}. '
            f'Banned allergen classes: {", ".join(req.avoid)}.')


def _run_worker(label: str, system_prompt: str, tool_names: Tuple[str, ...], user_msg: str,
                 budget: Budget, pace_s: float, verbose: bool,
                 inject_failure: Optional[dict] = None) -> Tuple[dict, Usage, int, int, List[dict], str]:
    """One bounded lap loop, scoped to exactly the tools named in
    ``tool_names`` and seeded with a brand-new message history — this is the
    hand-off: nothing from the orchestrator's or the other worker's context
    carries over except what ``user_msg`` restates in text.

    Returns ``(output, usage, laps, tool_calls, laps_log, terminated_by)``.
    ``terminated_by`` is non-empty when THIS worker's own budget tripped —
    caught here (not left to propagate) so the tokens it already spent are
    still returned instead of silently dropped, exactly as agent/loop.py
    already does for the single agent."""
    llm = _worker_llm(tool_names)
    messages: List = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]
    usage = Usage()
    started = time.monotonic()
    laps_log: List[dict] = []
    lap = 0
    tool_calls = 0

    while True:
        try:
            budget.check(iteration=lap, tokens=usage.total_tokens,
                        cost_usd=usage.cost_usd, started_at=started)
        except BudgetExceeded as be:
            laps_log.append({"lap": lap + 1, "terminated_by": be.which,
                             "value": be.value, "limit": be.limit})
            if verbose:
                print(f"    [{label}] BUDGET STOP: {be}")
            return {}, usage, lap, tool_calls, laps_log, be.which
        try:
            resp: AIMessage = llm.invoke(messages)
        except Exception as invoke_exc:  # noqa: BLE001
            text = str(invoke_exc)
            if "tool_use_failed" in text or "Tool call validation failed" in text:
                lap += 1
                messages.append(HumanMessage(content=(
                    "Your last tool call was rejected as malformed: "
                    f"{text[-300:]}\nRe-issue it with every required argument.")))
                laps_log.append({"lap": lap, "tool_calls": ["<rejected: malformed>"]})
                continue
            # anything else (rate limits, network errors, ...) is a real
            # failure this module did not inject -- wrap it so whatever this
            # worker already spent across prior laps is not silently
            # discarded, same accounting principle as WorkerHTTPError above.
            raise WorkerRuntimeError(invoke_exc, usage, lap, tool_calls, laps_log) from invoke_exc
        lap += 1
        usage = usage + usage_of(resp)
        messages.append(resp)
        called = [tc["name"] for tc in (resp.tool_calls or [])]
        laps_log.append({"lap": lap, "tool_calls": called, "cum_tokens": usage.total_tokens})
        if verbose:
            print(f"    [{label}] lap {lap}: {called or 'final answer'} "
                  f"cum_tokens={usage.total_tokens}")

        if resp.tool_calls:
            for tc in resp.tool_calls:
                name, args = tc["name"], tc.get("args") or {}
                if inject_failure and name == inject_failure.get("tool"):
                    raise WorkerHTTPError(
                        name, int(inject_failure.get("status", 500)),
                        inject_failure.get("detail", "(injected for Week 10 demo)"),
                        partial_usage=usage, partial_laps=lap, partial_tool_calls=tool_calls,
                        partial_laps_log=laps_log)
                result = run_tool(name, args)
                tool_calls += 1
                messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
            if pace_s:
                time.sleep(pace_s)
            continue

        output = _extract_worker_json(resp.content or "")
        return output, usage, lap, tool_calls, laps_log, ""


def _degrade_from_partial_recipe(req: RecipeRequest, worker_error: WorkerHTTPError) -> dict:
    """Best-effort partial answer when the nutrition/allergen worker fails
    after a retry: fall back to the *unscaled* base recipe (a plain lookup,
    no LLM, no invented allergen claim) rather than pretend the failed worker
    ever confirmed a scaled, allergen-checked ingredient list."""
    from agent.recipes import find

    r = find(req.query)
    if not r:
        return {}
    return {
        "recipe": r["name"],
        "servings": r["base_servings"],  # NOT req.servings — scaling never happened
        "ingredients": [{"item": i["item"], "qty": i["qty"], "unit": i["unit"]}
                        for i in r["ingredients"]],
        "substitutions": [],
        "method": list(r["method"]),
        "degraded": True,
        "degraded_reason": str(worker_error),
    }


def run_orchestrator(req: RecipeRequest, budget: Optional[Budget] = None,
                      pace_s: float = 0.0, verbose: bool = False,
                      inject_failure: Optional[dict] = None) -> Result:
    started = time.monotonic()
    handoffs: List[dict] = []
    all_laps: List[dict] = []
    total = Usage()
    llm_calls = tool_calls = 0
    terminated_by = ""
    err = ""
    output: dict = {}
    failure_note: dict = {}

    def _budget() -> Budget:
        # a fresh Budget instance per worker (same limits every time) so one
        # worker's lap count cannot starve another's
        b = budget or Budget()
        return Budget(max_iterations=b.max_iterations, max_tokens=b.max_tokens,
                      max_cost_usd=b.max_cost_usd, wall_clock_s=b.wall_clock_s)

    try:
        # --- hand-off 1: orchestrator -> nutrition/allergen worker ---------
        nutrition_out = None
        retried = False
        for attempt in (1, 2):
            try:
                nutrition_out, attempt_usage, laps, tcalls, laps_log, worker_tb = _run_worker(
                    "nutrition_worker", NUTRITION_SYSTEM_PROMPT, ("SearchRecipes", "GetNutrition"),
                    _worker_user_msg_nutrition(req), _budget(), pace_s, verbose,
                    inject_failure=inject_failure)
                if worker_tb:
                    total = total + attempt_usage
                    llm_calls += laps
                    tool_calls += tcalls
                    all_laps.append({"stage": "nutrition_worker", "laps": laps_log})
                    handoffs.append({"handoff": "orchestrator->nutrition_worker",
                                     "prompt_tokens": attempt_usage.prompt_tokens,
                                     "completion_tokens": attempt_usage.completion_tokens,
                                     "total_tokens": attempt_usage.total_tokens, "laps": laps,
                                     "tool_calls": tcalls, "outcome": f"budget_stop:{worker_tb}"})
                    terminated_by = worker_tb
                    raise _BudgetStopped()
                break
            except WorkerHTTPError as we:
                total = total + we.partial_usage
                llm_calls += we.partial_laps
                tool_calls += we.partial_tool_calls
                all_laps.append({"stage": f"nutrition_worker_attempt{attempt}",
                                 "laps": we.partial_laps_log})
                if attempt == 1:
                    retried = True
                    if verbose:
                        print(f"    [nutrition_worker] {we} — retrying once")
                    continue
                # retry also failed: degrade, do not call the substitution
                # worker on data we never confirmed
                output = _degrade_from_partial_recipe(req, we)
                failure_note = {"worker": "nutrition_allergen", "tool": we.tool,
                                 "status_code": we.status, "retried": retried,
                                 "behavior": "retried_then_degraded_partial_answer",
                                 "detail": str(we)}
                handoffs.append({"handoff": "orchestrator->nutrition_worker",
                                 "prompt_tokens": total.prompt_tokens,
                                 "completion_tokens": total.completion_tokens,
                                 "total_tokens": total.total_tokens, "laps": llm_calls,
                                 "tool_calls": tool_calls, "outcome": "failed_after_retry"})
                raise _Degraded()
            except WorkerRuntimeError as wre:
                total = total + wre.partial_usage
                llm_calls += wre.partial_laps
                tool_calls += wre.partial_tool_calls
                all_laps.append({"stage": "nutrition_worker", "laps": wre.partial_laps_log})
                handoffs.append({"handoff": "orchestrator->nutrition_worker",
                                 "prompt_tokens": wre.partial_usage.prompt_tokens,
                                 "completion_tokens": wre.partial_usage.completion_tokens,
                                 "total_tokens": wre.partial_usage.total_tokens,
                                 "laps": wre.partial_laps, "tool_calls": wre.partial_tool_calls,
                                 "outcome": f"error:{type(wre.original).__name__}"})
                raise wre.original
        total = total + attempt_usage
        llm_calls += laps
        tool_calls += tcalls
        all_laps.append({"stage": "nutrition_worker", "laps": laps_log})
        handoffs.append({"handoff": "orchestrator->nutrition_worker",
                         "prompt_tokens": attempt_usage.prompt_tokens,
                         "completion_tokens": attempt_usage.completion_tokens,
                         "total_tokens": attempt_usage.total_tokens, "laps": laps,
                         "tool_calls": tcalls, "outcome": "ok"})

        # --- hand-off 2: orchestrator -> substitution worker ---------------
        try:
            sub_out, sub_usage, sub_laps, sub_tcalls, sub_laps_log, sub_tb = _run_worker(
                "substitution_worker", SUBSTITUTION_SYSTEM_PROMPT, ("SubstituteIngredient",),
                _worker_user_msg_substitution(req, nutrition_out), _budget(), pace_s, verbose)
        except WorkerRuntimeError as wre:
            total = total + wre.partial_usage
            llm_calls += wre.partial_laps
            tool_calls += wre.partial_tool_calls
            all_laps.append({"stage": "substitution_worker", "laps": wre.partial_laps_log})
            handoffs.append({"handoff": "orchestrator->substitution_worker",
                             "prompt_tokens": wre.partial_usage.prompt_tokens,
                             "completion_tokens": wre.partial_usage.completion_tokens,
                             "total_tokens": wre.partial_usage.total_tokens,
                             "laps": wre.partial_laps, "tool_calls": wre.partial_tool_calls,
                             "outcome": f"error:{type(wre.original).__name__}"})
            raise wre.original
        total = total + sub_usage
        llm_calls += sub_laps
        tool_calls += sub_tcalls
        all_laps.append({"stage": "substitution_worker", "laps": sub_laps_log})
        handoffs.append({"handoff": "orchestrator->substitution_worker",
                         "prompt_tokens": sub_usage.prompt_tokens,
                         "completion_tokens": sub_usage.completion_tokens,
                         "total_tokens": sub_usage.total_tokens, "laps": sub_laps,
                         "tool_calls": sub_tcalls,
                         "outcome": f"budget_stop:{sub_tb}" if sub_tb else "ok"})
        if sub_tb:
            terminated_by = sub_tb
            raise _BudgetStopped()

        # --- hand-off 3: orchestrator -> synthesis (render the method) -----
        synth_usage = Usage()
        method = _render_method(nutrition_out.get("method") or [],
                                 sub_out.get("substitutions") or [], synth_usage)
        total = total + synth_usage
        llm_calls += 1 if synth_usage.total_tokens else 0
        handoffs.append({"handoff": "orchestrator->synthesis",
                         "prompt_tokens": synth_usage.prompt_tokens,
                         "completion_tokens": synth_usage.completion_tokens,
                         "total_tokens": synth_usage.total_tokens,
                         "laps": 1 if synth_usage.total_tokens else 0,
                         "tool_calls": 0, "outcome": "ok"})

        output = {
            "recipe": nutrition_out.get("recipe"),
            "servings": nutrition_out.get("servings"),
            "ingredients": sub_out.get("final_ingredients") or nutrition_out.get("ingredients") or [],
            "substitutions": sub_out.get("substitutions") or [],
            "method": method,
        }

    except _Degraded:
        pass  # output/failure_note already set above
    except _BudgetStopped:
        pass  # terminated_by already set above, with tokens already counted
    except Exception as exc:  # noqa: BLE001
        err = repr(exc)

    latency = time.monotonic() - started
    checks = passes(req, output) if output else {"is_object": False}
    ok = bool(output) and all(checks.values()) and not terminated_by and not err and not failure_note

    res = Result(
        request_id=req.id, system="orchestrator", output=output, ok=ok, checks=checks,
        latency_s=round(latency, 3), prompt_tokens=total.prompt_tokens,
        completion_tokens=total.completion_tokens, llm_calls=llm_calls,
        tool_calls=tool_calls, terminated_by=terminated_by, error=err,
    )
    res.handoffs = handoffs          # type: ignore[attr-defined]
    res.laps_log = all_laps          # type: ignore[attr-defined]
    res.failure = failure_note       # type: ignore[attr-defined]
    return res


class _Degraded(Exception):
    """Internal control-flow signal: the nutrition worker failed twice and
    the orchestrator already built its degraded partial output — skip the
    rest of the pipeline without treating this like an unhandled error."""


class _BudgetStopped(Exception):
    """Internal control-flow signal: a worker's own budget tripped (e.g. too
    many laps burned re-issuing a malformed tool call on a hard cascade).
    ``terminated_by`` and every token already spent are recorded before this
    is raised — it only short-circuits the remaining hand-offs."""
