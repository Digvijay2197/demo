"""Week 8 -- trajectory eval for the recipe agent loop.

Outcome evals (agent/contract.py::passes, already exercised in Week 7) only
score the final JSON. They cannot see *how* the agent got there, so a request
that is answered correctly from the model's own memory -- without ever
calling substitute_ingredient -- passes clean. This script scores the path.

    python scripts/trajectory_eval_week8.py --tag before   # baseline run
    ... apply exactly one mitigation to agent/tools.py or agent/loop.py ...
    python scripts/trajectory_eval_week8.py --tag after    # post-mitigation run
    python scripts/trajectory_eval_week8.py --compare      # before/after + regression table

Ground truth for "steps needed" and the required (ingredient, allergen) pairs
is derived the same way agent/workflow.py resolves cascades -- pure Python,
no LLM call, so it costs nothing and cannot itself hallucinate.

Four trajectory numbers (Requirement 2):
  - tool-choice accuracy   -- of the tool calls the agent actually made, what
                              fraction were calls the minimal trajectory needed
                              (capped so redundant repeats don't count twice)?
  - argument validity rate -- of calls with an identity argument
                              (recipe_name / ingredient), what fraction named
                              something that actually exists in the recipe
                              book / substitution table, rather than fluent
                              fiction?
  - step efficiency        -- steps taken / steps needed, mean across cases.
  - cost per request       -- p50 AND max, not the mean (a single looping
                              request is the one that shows up on the bill).

Outcome-vs-trajectory gap (Requirement 3): outcome pass rate minus trajectory
pass rate. Trajectory pass requires every required tool to have been called
at least its minimal count, with valid arguments, search called first, and no
budget stop -- i.e. the agent actually walked the path, not just landed on a
plausible-looking output.

Failure-mode taxonomy (used for Requirement 4's "top mode" and Requirement
5's regression table):
  - tool_skipped       a required tool was called fewer times than needed
                        (includes the "it just knew" case named in the brief)
  - hallucinated_args  a call named a recipe/ingredient that doesn't exist
  - redundant_calls    a tool was called more times than needed
  - wrong_tool_choice  substitute_ingredient targeted an allergen the request
                        never asked to avoid
  - budget_exceeded    a Budget fired before the model finished
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter

sys.path.insert(0, os.getcwd())

try:  # Windows consoles default to cp1252; recipe text has non-ASCII dashes
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from dotenv import load_dotenv

load_dotenv()

from agent.budget import Budget
from agent.contract import RecipeRequest
from agent.llm import GROQ_MODEL, _PRICE_IN, _PRICE_OUT
from agent.loop import run_agent
from agent.recipes import ALLERGENS, SUBSTITUTIONS, find
from agent.workflow import CASCADE_DEPTH

sys.path.insert(0, os.path.dirname(__file__))
from race_week7 import REQUESTS  # the same 10 requests Week 7 raced

DOCS = os.path.abspath(os.path.join(os.getcwd(), "..", "docs"))
TOOLS = ["SearchRecipes", "GetNutrition", "SubstituteIngredient"]
FAILURE_MODES = ["tool_skipped", "hallucinated_args", "redundant_calls",
                  "wrong_tool_choice", "budget_exceeded"]


# --------------------------------------------------------- expected trajectory


def expected_trajectory(req: RecipeRequest) -> dict:
    """Minimal tool multiset + step count needed to satisfy `req`, walked the
    same way agent/workflow.py resolves cascades. Order between *different*
    original ingredients (and between get_nutrition and any substitution) is
    a legitimate alternate path -- asserted here as a set of counts, not a
    sequence. Order *within* one ingredient's own cascade chain is not
    negotiable: you cannot name the substitute before the tool has returned
    it, so each chain is kept as an ordered list for the trace printout."""
    recipe = find(req.query)
    avoid = set(req.avoid)
    chains: list[list[tuple[str, str]]] = []
    for ing in recipe["ingredients"]:
        banned_here = set(ing["allergens"]) & avoid
        if not banned_here:
            continue
        chain: list[tuple[str, str]] = []
        cur_item, cur_allergens = ing["item"], set(ing["allergens"])
        for _ in range(CASCADE_DEPTH):
            target = next(iter(cur_allergens & avoid))
            chain.append((cur_item, target))
            sub = SUBSTITUTIONS.get(cur_item)
            if not sub:
                break
            cur_item, cur_allergens = sub["to"], set(sub["allergens"])
            if not (cur_allergens & avoid):
                break
        chains.append(chain)
    n_subs = sum(len(c) for c in chains)
    counts = Counter({"SearchRecipes": 1, "GetNutrition": 1, "SubstituteIngredient": n_subs})
    return {"counts": counts, "chains": chains, "steps_needed": sum(counts.values()),
            "alternate_path": n_subs > 0}  # GetNutrition/SubstituteIngredient order is free


def _arg_valid(name: str, args: dict) -> bool:
    """Real ingredient/recipe identity, or fluent fiction?"""
    if name == "SearchRecipes":
        return isinstance(args.get("query"), str) and bool(args["query"].strip())
    if name == "GetNutrition":
        return find(str(args.get("recipe_name", ""))) is not None
    if name == "SubstituteIngredient":
        r = find(str(args.get("recipe_name", "")))
        if not r:
            return False
        ing = str(args.get("ingredient", "")).strip().lower()
        real_items = {i["item"] for i in r["ingredients"]} | {s["to"] for s in SUBSTITUTIONS.values()}
        return ing in real_items and args.get("avoid_allergen") in ALLERGENS
    return False


def _calls_of(res) -> list[tuple[str, dict]]:
    calls = []
    for lap in res.laps_log:
        names = lap.get("tool_calls") or []
        argss = lap.get("tool_args") or [{}] * len(names)
        for n, a in zip(names, argss):
            calls.append((n, a))
    return calls


def classify(req: RecipeRequest, res, expected: dict, calls: list[tuple[str, dict]]) -> set[str]:
    modes: set[str] = set()
    if res.terminated_by:
        modes.add("budget_exceeded")

    actual_counts = Counter(n for n, _ in calls)
    exp_counts = expected["counts"]
    for t in TOOLS:
        if actual_counts.get(t, 0) < exp_counts.get(t, 0):
            modes.add("tool_skipped")
        if actual_counts.get(t, 0) > exp_counts.get(t, 0):
            modes.add("redundant_calls")

    for n, a in calls:
        if not _arg_valid(n, a):
            modes.add("hallucinated_args")

    avoid = set(req.avoid)
    for n, a in calls:
        if n == "SubstituteIngredient" and a.get("avoid_allergen") not in avoid:
            modes.add("wrong_tool_choice")
    return modes


def trajectory_pass(calls: list[tuple[str, dict]], modes: set[str]) -> bool:
    if not calls or calls[0][0] != "SearchRecipes":
        return False
    blocking = {"tool_skipped", "hallucinated_args", "budget_exceeded", "wrong_tool_choice"}
    return not (modes & blocking)


# --------------------------------------------------------------------- run


def run_eval(pace_s: float) -> list[dict]:
    budget = Budget()
    rows = []
    for req in REQUESTS:
        expected = expected_trajectory(req)
        res = run_agent(req, budget=budget, pace_s=pace_s, verbose=True)
        calls = _calls_of(res)
        exp_counts = expected["counts"]

        running: Counter = Counter()
        correct = 0
        for n, _ in calls:
            if running[n] < exp_counts.get(n, 0):
                correct += 1
            running[n] += 1
        tool_choice_accuracy = correct / len(calls) if calls else 0.0

        valid_flags = [_arg_valid(n, a) for n, a in calls]
        argument_validity = sum(valid_flags) / len(valid_flags) if valid_flags else 0.0

        step_efficiency = (len(calls) / expected["steps_needed"]) if expected["steps_needed"] else None
        cost_usd = res.prompt_tokens / 1e6 * _PRICE_IN + res.completion_tokens / 1e6 * _PRICE_OUT

        modes = classify(req, res, expected, calls)
        traj_ok = trajectory_pass(calls, modes)

        print(f"    {req.id:14s} outcome={res.ok!s:5s} trajectory={traj_ok!s:5s} "
              f"steps={len(calls)}/{expected['steps_needed']} "
              f"tca={tool_choice_accuracy:.2f} argv={argument_validity:.2f} "
              f"modes={sorted(modes) or '-'}")

        rows.append({
            "id": req.id, "query": req.query, "servings": req.servings,
            "avoid": req.avoid, "cascade": req.cascade,
            "alternate_path": expected["alternate_path"],
            "outcome_ok": res.ok, "trajectory_ok": traj_ok, "modes": sorted(modes),
            "tool_choice_accuracy": round(tool_choice_accuracy, 3),
            "argument_validity": round(argument_validity, 3),
            "step_efficiency": round(step_efficiency, 3) if step_efficiency is not None else None,
            "steps_taken": len(calls), "steps_needed": expected["steps_needed"],
            "expected_counts": dict(exp_counts),
            "cost_usd": round(cost_usd, 6),
            "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
            "actual_call_sequence": [n for n, _ in calls],
            "failed_outcome_checks": [k for k, v in res.checks.items() if not v],
            "terminated_by": res.terminated_by,
        })
        if pace_s:
            time.sleep(pace_s)
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    outcome_pass_rate = sum(r["outcome_ok"] for r in rows) / n
    trajectory_pass_rate = sum(r["trajectory_ok"] for r in rows) / n

    total_calls = sum(r["steps_taken"] for r in rows) or 1
    tool_choice_accuracy = sum(r["tool_choice_accuracy"] * r["steps_taken"] for r in rows) / total_calls
    argument_validity = sum(r["argument_validity"] * r["steps_taken"] for r in rows) / total_calls

    step_effs = [r["step_efficiency"] for r in rows if r["step_efficiency"] is not None]
    costs = sorted(r["cost_usd"] for r in rows)

    mode_counts = Counter()
    for r in rows:
        for m in r["modes"]:
            mode_counts[m] += 1
    for m in FAILURE_MODES:
        mode_counts.setdefault(m, 0)

    # The headline right-answer-wrong-path case: among outcome-pass /
    # trajectory-fail rows, the one that skipped the most steps -- the
    # clearest "it just knew" example, not just the first one in list order.
    wrong_path_candidates = [r for r in rows if r["outcome_ok"] and not r["trajectory_ok"]]
    culprit = max(wrong_path_candidates, key=lambda r: r["steps_needed"] - r["steps_taken"],
                  default=None)

    return {
        "n": n,
        "outcome_pass_rate": round(outcome_pass_rate, 3),
        "trajectory_pass_rate": round(trajectory_pass_rate, 3),
        "gap": round(outcome_pass_rate - trajectory_pass_rate, 3),
        "tool_choice_accuracy": round(tool_choice_accuracy, 3),
        "argument_validity": round(argument_validity, 3),
        "step_efficiency_mean": round(statistics.mean(step_effs), 3) if step_effs else None,
        "cost_p50_usd": round(statistics.median(costs), 6) if costs else None,
        "cost_max_usd": round(max(costs), 6) if costs else None,
        "mode_counts": dict(sorted(mode_counts.items(), key=lambda kv: -kv[1])),
        "culprit_case_id": culprit["id"] if culprit else None,
    }


def _write(tag: str, rows: list[dict], summary: dict) -> str:
    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, f"week8-trajectory-{tag}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"model": GROQ_MODEL, "price_per_mtok": [_PRICE_IN, _PRICE_OUT],
                   "tag": tag, "summary": summary, "rows": rows}, f, indent=2)
    return path


def _print_summary(tag: str, summary: dict) -> None:
    print("\n" + "=" * 78)
    print(f"trajectory eval [{tag}]  model={GROQ_MODEL}")
    print("=" * 78)
    print(f"outcome pass rate       : {summary['outcome_pass_rate']*100:.0f}%")
    print(f"trajectory pass rate    : {summary['trajectory_pass_rate']*100:.0f}%")
    print(f"outcome-trajectory gap  : {summary['gap']*100:+.0f} pts")
    print(f"tool-choice accuracy    : {summary['tool_choice_accuracy']*100:.1f}%")
    print(f"argument validity rate  : {summary['argument_validity']*100:.1f}%")
    print(f"step efficiency (mean)  : {summary['step_efficiency_mean']}")
    print(f"cost / request  p50     : ${summary['cost_p50_usd']}")
    print(f"cost / request  max     : ${summary['cost_max_usd']}")
    print(f"failure-mode counts     : {summary['mode_counts']}")
    print(f"right-answer-wrong-path : {summary['culprit_case_id']}")
    print("=" * 78)


def cmd_run(tag: str, pace_s: float) -> None:
    budget = Budget()
    print(f"model: {GROQ_MODEL}   price $/Mtok: in={_PRICE_IN} out={_PRICE_OUT}   "
          f"budget: {budget}   tag={tag}\n")
    rows = run_eval(pace_s)
    summary = summarize(rows)
    path = _write(tag, rows, summary)
    _print_summary(tag, summary)
    print(f"\nwrote {path}")

    culprit = next((r for r in rows if r["id"] == summary["culprit_case_id"]), None)
    if culprit:
        print("\n--- right-answer-wrong-path case ---")
        print(f"{culprit['id']}: \"{culprit['query']}\" -> {culprit['servings']} servings, "
              f"avoid {culprit['avoid']}")
        print(f"  expected (minimal): {culprit['expected_counts']}  "
              f"({culprit['steps_needed']} steps)")
        print(f"  actual call sequence: {culprit['actual_call_sequence']}  "
              f"({culprit['steps_taken']} steps)")
        print(f"  modes: {culprit['modes']}")
        print(f"  outcome checks: all passed -> {culprit['outcome_ok']}")


def cmd_compare() -> None:
    before_path = os.path.join(DOCS, "week8-trajectory-before.json")
    after_path = os.path.join(DOCS, "week8-trajectory-after.json")
    with open(before_path, encoding="utf-8") as f:
        before = json.load(f)
    with open(after_path, encoding="utf-8") as f:
        after = json.load(f)

    bs, as_ = before["summary"], after["summary"]
    top_mode = max(bs["mode_counts"], key=lambda m: bs["mode_counts"][m])

    print("=" * 78)
    print(f"{'metric':28s} {'before':>12s} {'after':>12s}")
    print("-" * 78)
    for label, key in [
        ("outcome pass rate", "outcome_pass_rate"),
        ("trajectory pass rate", "trajectory_pass_rate"),
        ("outcome-trajectory gap", "gap"),
        ("tool-choice accuracy", "tool_choice_accuracy"),
        ("argument validity", "argument_validity"),
        ("step efficiency (mean)", "step_efficiency_mean"),
        ("cost / req p50 (USD)", "cost_p50_usd"),
        ("cost / req max (USD)", "cost_max_usd"),
    ]:
        print(f"{label:28s} {str(bs[key]):>12s} {str(as_[key]):>12s}")
    print("-" * 78)
    print(f"top failure mode targeted: {top_mode}")
    print(f"  before: {bs['mode_counts'].get(top_mode, 0)} / {before['summary']['n']} cases")
    print(f"  after : {as_['mode_counts'].get(top_mode, 0)} / {after['summary']['n']} cases")

    price_cost = round(as_["cost_p50_usd"] - bs["cost_p50_usd"], 6)
    price_tokens = None
    b_tok = sum(r["prompt_tokens"] + r["completion_tokens"] for r in before["rows"])
    a_tok = sum(r["prompt_tokens"] + r["completion_tokens"] for r in after["rows"])
    price_tokens = a_tok - b_tok
    print(f"  price paid: cost p50 {price_cost:+.6f} USD/request, "
          f"{price_tokens:+d} total tokens across {len(after['rows'])} requests")

    print("\n" + "=" * 78)
    print(f"{'mode (regression table)':28s} {'before':>8s} {'after':>8s} {'delta':>8s}")
    print("-" * 78)
    regressions = []
    new_modes = []
    for m in FAILURE_MODES:
        b = bs["mode_counts"].get(m, 0)
        a = as_["mode_counts"].get(m, 0)
        delta = a - b
        flag = ""
        if delta > 0 and b == 0:
            flag = "  <- NEW"
            new_modes.append(m)
        elif delta > 0:
            flag = "  <- WORSE"
            regressions.append(m)
        print(f"{m:28s} {b:8d} {a:8d} {delta:+8d}{flag}")
    print("-" * 78)
    if not regressions and not new_modes:
        print(f"no mode worsened; checked: {', '.join(FAILURE_MODES)}")
    else:
        print(f"regressions: {regressions or 'none'}   new modes: {new_modes or 'none'}")
    print("=" * 78)

    report = {
        "top_mode": top_mode,
        "before_count": bs["mode_counts"].get(top_mode, 0),
        "after_count": as_["mode_counts"].get(top_mode, 0),
        "price_cost_p50_delta_usd": price_cost,
        "price_tokens_delta": price_tokens,
        "regressions": regressions,
        "new_modes": new_modes,
        "before_summary": bs,
        "after_summary": as_,
    }
    path = os.path.join(DOCS, "week8-mitigation-report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", choices=["before", "after"], help="run and save under this tag")
    ap.add_argument("--pace", type=float, default=0.0, help="seconds between LLM calls")
    ap.add_argument("--compare", action="store_true", help="compare an existing before/after pair")
    args = ap.parse_args()

    if args.compare:
        cmd_compare()
        return
    if not args.tag:
        ap.error("pass --tag before|after, or --compare")
    cmd_run(args.tag, args.pace)


if __name__ == "__main__":
    main()
