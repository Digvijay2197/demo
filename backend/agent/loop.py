"""The hand-built agent loop: model decides which tool to call, every lap,
until it emits the final JSON — or a budget stops it.

    run_agent(request, budget) -> Result

Token accounting sums ``usage_of`` over *every* lap, because Groq (like any
chat API) re-bills the whole message list each call and that list grows with
every tool result — counting only the last call understates the agent's cost by
multiples (Week 7 common mistake #3).
"""
from __future__ import annotations

import time
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.budget import Budget, BudgetExceeded
from agent.contract import RecipeRequest, Result, extract_json, passes
from agent.llm import Usage, tool_llm, usage_of
from agent.tools import run_tool

SYSTEM_PROMPT = """You adapt recipes for people with allergies. For each request:
1. search_recipes to fetch the recipe.
2. get_nutrition to scale it to the requested servings.
3. substitute_ingredient for EACH ingredient that carries a banned allergen. If a
   substitute itself carries a banned allergen (the result says cascade=true),
   call substitute_ingredient again on that substitute until it is clear.
   EVERY substitute_ingredient call needs all three arguments, e.g.
   {"recipe_name": "Classic Pancakes", "ingredient": "whole milk", "avoid_allergen": "dairy"}.
Then STOP calling tools and reply with ONLY this JSON object, no prose:

{"recipe": <name>, "servings": <int>, "ingredients": [{"item": <str>, "qty": <number or str>, "unit": <str>}],
 "substitutions": [{"from": <str>, "to": <str>, "reason": <str>}], "method": [<step>, ...]}

The ingredients array is the final scaled, substituted list. The method array is
the recipe's steps with the substitutions applied. Do not invent ingredients."""


def _user_msg(req: RecipeRequest) -> str:
    banned = ", ".join(req.avoid)
    return (f"Request {req.id}: adapt \"{req.query}\" to {req.servings} servings "
            f"and remove all sources of: {banned}.")


def run_agent(req: RecipeRequest, budget: Optional[Budget] = None,
              pace_s: float = 0.0, verbose: bool = False) -> Result:
    budget = budget or Budget()
    llm = tool_llm()
    messages: List = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=_user_msg(req))]

    usage = Usage()
    started = time.monotonic()
    paced = 0.0   # deliberate inter-call sleeps (a rate-limit workaround, not
                  # a property of the system) — excluded from latency and the
                  # wall-clock budget
    lap = 0
    llm_calls = tool_calls = 0
    laps_log: List[dict] = []
    terminated_by = ""
    output: dict = {}
    err = ""

    try:
        while True:
            budget.check(iteration=lap, tokens=usage.total_tokens,
                         cost_usd=usage.cost_usd, started_at=started + paced)

            try:
                resp: AIMessage = llm.invoke(messages)
            except Exception as invoke_exc:  # noqa: BLE001
                # Groq rejects a malformed tool call with `tool_use_failed`
                # instead of returning it. Feed the error back and let the
                # model retry — this still costs a lap, so budgets bound it.
                text = str(invoke_exc)
                if "tool_use_failed" in text or "Tool call validation failed" in text:
                    lap += 1
                    messages.append(HumanMessage(content=(
                        "Your last tool call was rejected as malformed: "
                        f"{text[-300:]}\nRe-issue it with every required argument.")))
                    laps_log.append({"lap": lap, "tool_calls": ["<rejected: malformed>"],
                                     "cum_tokens": usage.total_tokens,
                                     "elapsed_s": round(time.monotonic() - started, 2)})
                    if verbose:
                        print(f"  lap {lap}: malformed tool call rejected, retrying")
                    continue
                raise
            lap += 1
            llm_calls += 1
            step_usage = usage_of(resp)
            usage = usage + step_usage
            messages.append(resp)

            called = [tc["name"] for tc in (resp.tool_calls or [])]
            call_args = [tc.get("args") or {} for tc in (resp.tool_calls or [])]
            laps_log.append({
                "lap": lap, "tool_calls": called, "tool_args": call_args,
                "lap_tokens": step_usage.total_tokens,
                "cum_tokens": usage.total_tokens,
                "cum_cost_usd": round(usage.cost_usd, 6),
                "elapsed_s": round(time.monotonic() - started, 2),
            })
            if verbose:
                print(f"  lap {lap}: {called or 'final answer'}  "
                      f"cum_tokens={usage.total_tokens} cum_cost=${usage.cost_usd:.5f}")

            if resp.tool_calls:
                for tc in resp.tool_calls:
                    result = run_tool(tc["name"], tc.get("args") or {})
                    tool_calls += 1
                    messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
                if pace_s:
                    time.sleep(pace_s)
                    paced += pace_s
                continue

            output = extract_json(resp.content or "")
            break

    except BudgetExceeded as be:
        terminated_by = be.which
        laps_log.append({"lap": lap + 1, "terminated_by": be.which,
                         "value": be.value, "limit": be.limit,
                         "cum_tokens": usage.total_tokens,
                         "cum_cost_usd": round(usage.cost_usd, 6),
                         "elapsed_s": round(time.monotonic() - started, 2)})
        if verbose:
            print(f"  BUDGET STOP: {be}")
        # best effort: use the last JSON the model produced, if any
        for m in reversed(messages):
            if isinstance(m, AIMessage) and not m.tool_calls:
                output = extract_json(m.content or "")
                if output:
                    break
    except Exception as exc:  # noqa: BLE001
        err = repr(exc)

    latency = time.monotonic() - started - paced
    checks = passes(req, output) if output else {"is_object": False}
    ok = bool(output) and all(checks.values()) and not terminated_by and not err

    res = Result(
        request_id=req.id, system="agent", output=output, ok=ok, checks=checks,
        latency_s=round(latency, 3), prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens, llm_calls=llm_calls,
        tool_calls=tool_calls, terminated_by=terminated_by, error=err,
    )
    res.laps_log = laps_log  # type: ignore[attr-defined]
    return res
