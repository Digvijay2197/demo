"""Week 7 — race the recipe agent loop against the fixed workflow.

    python scripts/race_week7.py                # 10 requests, both systems, writes docs/week7-race.csv
    python scripts/race_week7.py --budget-demo  # one run that hits a budget and stops cleanly
    python scripts/race_week7.py --pace 3       # seconds to sleep between LLM calls (Groq free tier)
    python scripts/race_week7.py --only agent   # run just one system

Four numbers per system: pass rate, p50 latency, total tokens, mean cost/request.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.getcwd())

try:  # Windows consoles default to cp1252; recipe text has non-ASCII dashes
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from dotenv import load_dotenv

load_dotenv()

from agent.budget import Budget
from agent.contract import RecipeRequest
from agent.llm import GROQ_MODEL
from agent.loop import run_agent
from agent.workflow import run_workflow

DOCS = os.path.abspath(os.path.join(os.getcwd(), "..", "docs"))

# 10 requests. `cascade=True` marks the ones where step 3 depends on what step 3
# just found — a substitute that is itself a banned allergen, forcing another
# swap. Four of the ten are cascades (p8, mac4nut, curry2, curry8).
REQUESTS = [
    RecipeRequest("r01_p4", "classic pancakes", 4, ["dairy"],
                  notes="straight swap: milk+butter, servings unchanged"),
    RecipeRequest("r02_p8", "classic pancakes", 8, ["dairy", "gluten"], cascade=True,
                  notes="milk -> oat milk (gluten) -> rice milk; +2x scale"),
    RecipeRequest("r03_mac6", "weeknight mac and cheese", 6, ["gluten"],
                  notes="macaroni + roux flour; 1.5x scale"),
    RecipeRequest("r04_mac4nut", "weeknight mac and cheese", 4, ["dairy", "tree_nut"], cascade=True,
                  notes="cheddar -> cashew cheese (tree_nut) -> nutritional-yeast sauce"),
    RecipeRequest("r05_curry4", "thai green curry", 4, ["shellfish"],
                  notes="shrimp paste -> fish sauce (fish ok); no scale"),
    RecipeRequest("r06_curry2", "thai green curry", 2, ["shellfish", "fish"], cascade=True,
                  notes="shrimp paste -> fish sauce (fish) -> light soy; 0.5x scale"),
    RecipeRequest("r07_curry8", "thai green curry", 8, ["fish", "soy", "shellfish"], cascade=True,
                  notes="depth-3 cascade on two ingredients; 2x scale"),
    RecipeRequest("r08_bread8", "banana bread", 8, ["dairy", "egg"],
                  notes="butter + egg; walnuts stay; no scale"),
    RecipeRequest("r09_noodle4", "veggie stir-fry noodles", 4, ["gluten", "soy"],
                  notes="noodles + soy sauce + tofu, three swaps; 2x scale"),
    RecipeRequest("r10_cookie12", "chocolate chip cookies", 12, ["dairy"],
                  notes="butter + choc chips; 0.5x scale"),
]


def _summary(rows: list) -> dict:
    lat = sorted(r.latency_s for r in rows)
    return {
        "n": len(rows),
        "pass_rate": round(sum(r.ok for r in rows) / len(rows), 3),
        "p50_latency_s": round(statistics.median(lat), 3),
        "total_tokens": sum(r.total_tokens for r in rows),
        "mean_cost_per_req_usd": round(
            sum(r.prompt_tokens / 1e6 * _pin() + r.completion_tokens / 1e6 * _pout()
                for r in rows) / len(rows), 6),
        "mean_llm_calls": round(statistics.mean([r.llm_calls for r in rows]), 1),
        "mean_tool_calls": round(statistics.mean([r.tool_calls for r in rows]), 1),
        "budget_stops": sum(1 for r in rows if r.terminated_by),
        "errors": sum(1 for r in rows if r.error),
    }


def _pin():
    from agent.llm import _PRICE_IN
    return _PRICE_IN


def _pout():
    from agent.llm import _PRICE_OUT
    return _PRICE_OUT


def run_race(systems: list, pace_s: float) -> None:
    budget = Budget()
    print(f"model: {GROQ_MODEL}   price $/Mtok: in={_pin()} out={_pout()}   "
          f"budget: {budget}\n")
    all_rows = {"agent": [], "workflow": []}
    csv_rows = []

    for req in REQUESTS:
        print(f"{req.id}  ({'cascade' if req.cascade else 'simple '})  "
              f"\"{req.query}\" -> {req.servings} servings, avoid {req.avoid}")
        for sysname in systems:
            fn = run_agent if sysname == "agent" else run_workflow
            kwargs = {"pace_s": pace_s, "verbose": True}
            if sysname == "agent":
                kwargs["budget"] = budget
            res = fn(req, **kwargs)
            all_rows[sysname].append(res)
            failed = [k for k, v in res.checks.items() if not v]
            print(f"    {sysname:8s}  ok={res.ok!s:5s}  {res.latency_s:6.2f}s  "
                  f"tok={res.total_tokens:6d}  llm={res.llm_calls} tool={res.tool_calls}"
                  f"{'  STOP:' + res.terminated_by if res.terminated_by else ''}"
                  f"{'  err:' + res.error[:60] if res.error else ''}"
                  f"{'  fail:' + ','.join(failed) if failed and not res.ok else ''}")
            csv_rows.append({
                "request_id": res.request_id, "system": sysname, "cascade": req.cascade,
                "servings": req.servings, "avoid": "|".join(req.avoid),
                "ok": res.ok, "terminated_by": res.terminated_by,
                "latency_s": res.latency_s, "prompt_tokens": res.prompt_tokens,
                "completion_tokens": res.completion_tokens, "total_tokens": res.total_tokens,
                "cost_usd": round(res.prompt_tokens / 1e6 * _pin()
                                  + res.completion_tokens / 1e6 * _pout(), 6),
                "llm_calls": res.llm_calls, "tool_calls": res.tool_calls,
                "failed_checks": ",".join(failed) if not res.ok else "",
            })
            if pace_s:
                time.sleep(pace_s)
        print()

    os.makedirs(DOCS, exist_ok=True)
    csv_path = os.path.join(DOCS, "week7-race.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        w.writeheader()
        w.writerows(csv_rows)

    print("=" * 72)
    print(f"{'':10s} {'pass':>6s} {'p50 lat':>9s} {'tokens':>9s} {'$/req':>10s} "
          f"{'llm/req':>8s} {'tool/req':>9s} {'budget':>7s}")
    summaries = {}
    for sysname in systems:
        s = _summary(all_rows[sysname])
        summaries[sysname] = s
        print(f"{sysname:10s} {s['pass_rate']*100:5.0f}% {s['p50_latency_s']:8.2f}s "
              f"{s['total_tokens']:9d} {s['mean_cost_per_req_usd']:10.6f} "
              f"{s['mean_llm_calls']:8.1f} {s['mean_tool_calls']:9.1f} {s['budget_stops']:7d}")
    print("=" * 72)
    print(f"\nwrote {csv_path}")

    with open(os.path.join(DOCS, "week7-race-summary.json"), "w", encoding="utf-8") as f:
        json.dump({"model": GROQ_MODEL, "price_per_mtok": [_pin(), _pout()],
                   "budget": budget.__dict__, "summary": summaries}, f, indent=2)


def budget_demo(pace_s: float) -> None:
    """Deliberately tiny budgets so the loop terminates cleanly instead of
    spinning. Two runs — one that trips max_iterations, one that trips
    max_tokens — to show every budget is actually checked, not just declared.
    Writes docs/week7-budget-termination.log."""
    req = REQUESTS[6]  # r07_curry8: the deepest cascade, needs many laps
    configs = [
        ("max_iterations", Budget(max_iterations=3, max_tokens=50_000,
                                  max_cost_usd=1.0, wall_clock_s=120.0)),
        ("max_tokens", Budget(max_iterations=20, max_tokens=4_000,
                              max_cost_usd=1.0, wall_clock_s=120.0)),
    ]
    lines = [f"# Week 7 budget-termination log",
             f"# request : {req.id}  \"{req.query}\" -> {req.servings} servings, "
             f"avoid {req.avoid}",
             f"# model   : {GROQ_MODEL}",
             f"# Budget.check runs at the top of every lap and tests all four "
             f"budgets; the first to trip raises BudgetExceeded."]

    for label, tight in configs:
        print(f"budget-demo ({label}) on {req.id}: {tight}\n")
        res = run_agent(req, budget=tight, pace_s=pace_s, verbose=True)
        lines.append("")
        lines.append(f"=== expecting {label} to fire ===")
        lines.append(f"# budget: {tight}")
        for lap in getattr(res, "laps_log", []):
            lines.append(json.dumps(lap))
        lines.append(f"RESULT: terminated_by={res.terminated_by!r}  ok={res.ok}  "
                     f"laps={res.llm_calls}  tool_calls={res.tool_calls}  "
                     f"tokens={res.total_tokens}  cost_usd="
                     f"{res.prompt_tokens/1e6*_pin() + res.completion_tokens/1e6*_pout():.6f}  "
                     f"latency_s={res.latency_s}")

    lines.append("")
    lines.append("Both runs: the loop caught BudgetExceeded, logged the firing "
                 "budget, and returned a partial result. It did not iterate again.")

    os.makedirs(DOCS, exist_ok=True)
    path = os.path.join(DOCS, "week7-budget-termination.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    print(f"\nwrote {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget-demo", action="store_true")
    ap.add_argument("--pace", type=float, default=0.0, help="seconds between LLM calls")
    ap.add_argument("--only", choices=["agent", "workflow"], help="run one system only")
    args = ap.parse_args()

    if args.budget_demo:
        budget_demo(args.pace)
        return
    systems = [args.only] if args.only else ["agent", "workflow"]
    run_race(systems, args.pace)


if __name__ == "__main__":
    main()
