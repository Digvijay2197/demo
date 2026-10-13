"""One-command eval of the INTEGRATED system.

    python -m capstone eval                    # AFTER config: all 30 cases, assertions, trajectory, taxonomy, judge
    python -m capstone eval --before           # BEFORE config (naive versions, no guards, plain substitution), safety subset
    python -m capstone eval --validate-judge   # judge vs hand labels on integrated outputs
    python -m capstone eval --report           # rebuild docs/capstone/*.md numbers from the saved runs
    flags: --only c01,c02   --repeat N   --patient (sleep through Groq 429s)   --pace S   --tag NAME

Everything is written to docs/capstone/results/. LLM calls are real Groq calls (budget ~5k tokens/case).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import Counter, defaultdict

from capstone import agent, config
from capstone.eval import assertions, judge
from capstone.eval.cases import CASES

RESULTS = config.DOCS_DIR / "results"
SAFETY_CATS = {"allergen_version", "pantry_swap", "refusal"}
SEVERITY = {
    "unsafe_allergen_endorsement": "critical", "superseded_version_cited": "critical",
    "substitution_introduced_allergen": "critical", "allergen_claim_without_check": "high",
    "safe_temp_dropped": "high", "guessed_instead_of_refusing": "high", "scaling_error": "medium",
    "cross_hop_version_drift": "high", "mcp_tool_error": "medium", "over_refusal": "low",
    "citation_missing_version": "medium", "other_failure": "low",
}
CONFIGS = {
    "after": {"CAPSTONE_VERSION_POLICY": "resolved", "CAPSTONE_GUARDS": "on", "CAPSTONE_SUBSTITUTION": "checked"},
    "before": {"CAPSTONE_VERSION_POLICY": "naive", "CAPSTONE_GUARDS": "off", "CAPSTONE_SUBSTITUTION": "plain"},
}


def _is_rate_limit(exc_text: str) -> bool:
    t = (exc_text or "").lower()
    return "rate" in t and "limit" in t or "429" in t


def run_suite(config_name: str, cases: list[dict], repeat: int | None, patient: bool, pace: float) -> dict:
    os.environ.update(CONFIGS[config_name])
    os.environ["CAPSTONE_TRACE_LOG"] = str(config.LOG_DIR / "capstone_eval_traces.jsonl")
    os.environ["CAPSTONE_MCP_SPAN_LOG"] = str(config.LOG_DIR / "capstone_eval_mcp_spans.jsonl")
    agent.reset_connection()
    conn = agent.connection()
    discovered = conn.tool_names
    print(f"[{config_name}] config={config.config_snapshot()}  tools discovered over MCP: {discovered}", flush=True)
    results = []
    for case in cases:
        n = repeat or case["expect"].get("repeat", 1)
        runs = []
        for _ in range(n):
            out = None
            for attempt in range(40 if patient else 1):
                out = agent.ask(case["question"], user_id="eval")
                if out["error"] and _is_rate_limit(out["error"]) and patient:
                    print("  [patient] rate-limited, sleeping 120s", flush=True)
                    time.sleep(120)
                    continue
                break
            sc = assertions.score_case(case, out, discovered)
            runs.append({"trace_id": out["trace_id"], "answer": out["answer"], "raw_answer": out["raw_answer"],
                         "guards_fired": out["guards_fired"], "tool_calls": out["tool_calls"], "error": out["error"],
                         "terminated_by": out["terminated_by"], "tokens": out["tokens"], "cost_usd": out["cost_usd"],
                         "latency_ms": out["latency_ms"], "laps": out["laps"], **sc})
            if pace:
                time.sleep(pace)
        # a case passes only if EVERY repeat passes; report the worst run
        worst = next((r for r in runs if not assertions.case_passes(r)), runs[0])
        res = {"id": case["id"], "category": case["category"], "question": case["question"],
               "expect": case["expect"], "n_runs": n, "passes": sum(assertions.case_passes(r) for r in runs),
               "pass": all(assertions.case_passes(r) for r in runs), "run": worst, "all_runs": [r["trace_id"] for r in runs]}
        results.append(res)
        bad = [k for k, v in worst["checks"].items() if not v]
        print(f"{case['id']} {case['category']:16s} {'PASS' if res['pass'] else 'FAIL'}  "
              f"{res['passes']}/{n}  guards={worst['guards_fired']} {('failing: ' + ','.join(bad)) if bad else ''}", flush=True)
    return {"config_name": config_name, "config": config.config_snapshot(), "discovered_tools": discovered,
            "n_cases": len(results), "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}


# ----------------------------------------------------------------------------- metrics
def summarize(run: dict) -> dict:
    rs = run["results"]
    n = len(rs)
    runs = [r["run"] for r in rs]
    cats = defaultdict(list)
    for r in rs:
        cats[r["category"]].append(r)
    mode_cases = defaultdict(list)
    for r in rs:
        for m in r["run"]["modes"]:
            mode_cases[m].append(r)
    safety = [r for r in rs if r["category"] in SAFETY_CATS]
    unsafe_final = [r for r in safety if r["run"]["final_unsafe"]]
    unsafe_raw = [r for r in safety if r["run"]["raw_unsafe"]]
    traj_pass = sum(r["run"]["trajectory"]["pass"] for r in rs)
    outcome_pass = sum(r["pass"] for r in rs)
    costs = [x["cost_usd"] for x in runs]
    lats = sorted(x["latency_ms"] or 0 for x in runs)
    return {
        "config": run["config_name"], "n": n,
        "pass_rate": round(outcome_pass / n, 3), "pass": outcome_pass,
        "per_category": {c: {"n": len(v), "pass": sum(x["pass"] for x in v)} for c, v in cats.items()},
        "taxonomy": {m: {"cases": len(v), "frequency_pct": round(100 * len(v) / n, 1), "severity": SEVERITY.get(m, "medium"),
                         "example_trace": v[0]["run"]["trace_id"], "example_case": v[0]["id"]}
                     for m, v in sorted(mode_cases.items(), key=lambda kv: -len(kv[1]))},
        "allergen_unsafe": {"n_safety_cases": len(safety), "final_unsafe": len(unsafe_final),
                            "final_rate": round(len(unsafe_final) / len(safety), 3) if safety else None,
                            "raw_unsafe_before_guards": len(unsafe_raw),
                            "raw_rate": round(len(unsafe_raw) / len(safety), 3) if safety else None,
                            "unsafe_case_ids": [r["id"] for r in unsafe_final]},
        "trajectory": {"n": n, "tool_choice_accuracy": round(statistics.mean(x["trajectory"]["tool_choice_accuracy"] for x in runs), 3),
                       "trajectory_pass_rate": round(traj_pass / n, 3), "outcome_pass_rate": round(outcome_pass / n, 3),
                       "outcome_minus_trajectory_gap": round((outcome_pass - traj_pass) / n, 3),
                       "all_required_called": round(sum(x["trajectory"]["all_required_called"] for x in runs) / n, 3)},
        "cost": {"mean_usd": round(statistics.mean(costs), 6), "p50_usd": round(statistics.median(costs), 6),
                 "mean_tokens": round(statistics.mean(x["tokens"] for x in runs)),
                 "p50_latency_ms": lats[n // 2], "p95_latency_ms": lats[min(n - 1, int(n * 0.95))],
                 "mean_laps": round(statistics.mean(x["laps"] for x in runs), 2)},
        "safe_temp_dropped_by_model_before_guard": sum(x["raw_temp_dropped"] for x in runs),
    }


def save(run: dict, tag: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"run-{tag}.json").write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    (RESULTS / f"summary-{tag}.json").write_text(json.dumps(summarize(run), indent=1), encoding="utf-8")


def judge_run(run: dict, patient: bool) -> dict:
    rows = []
    for r in run["results"]:
        if r["expect"]["verdict"] in ("refuse",):
            continue
        x = r["run"]
        j = judge.judge(r["question"], x["answer"], x["tool_calls"])
        rows.append({"id": r["id"], **j})
        time.sleep(1)
    passed = sum(1 for r in rows if r["verdict"] == "PASS")
    return {"n": len(rows), "judge_pass": passed, "rows": rows}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m capstone eval")
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--repeat", type=int)
    ap.add_argument("--patient", action="store_true")
    ap.add_argument("--pace", type=float, default=0.0)
    ap.add_argument("--tag")
    ap.add_argument("--validate-judge", action="store_true")
    ap.add_argument("--judge", action="store_true", help="also run the prose judge over the outputs")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)

    if a.validate_judge:
        path = os.path.join(os.path.dirname(__file__), "judge_labels.json")
        v = judge.validate(path)
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / "judge_validation.json").write_text(json.dumps(v, indent=1), encoding="utf-8")
        print(f"judge agreement with hand labels: {v['agree']}/{v['n']} = {v['agreement']}  "
              f"clears 85%: {v['clears_85']}  (passes-a-bad-answer={v['judge_passes_a_bad_answer']}, "
              f"fails-a-good-answer={v['judge_fails_a_good_answer']})")
        return 0
    if a.report:
        from capstone.eval.report import write_reports
        write_reports()
        return 0

    name = "before" if a.before else "after"
    cases = CASES
    if a.only:
        ids = set(a.only.split(","))
        cases = [c for c in CASES if c["id"] in ids]
    elif a.before:
        cases = [c for c in CASES if c["category"] in SAFETY_CATS or c["category"] == "safe_temp"]
    run = run_suite(name, cases, a.repeat, a.patient, a.pace)
    if a.judge:
        run["judge"] = judge_run(run, a.patient)
    tag = a.tag or name
    save(run, tag)
    s = summarize(run)
    print("\n=== SUMMARY ===")
    print(json.dumps({k: s[k] for k in ("config", "n", "pass_rate", "per_category", "allergen_unsafe", "trajectory", "cost")}, indent=1))
    print("taxonomy:", json.dumps(s["taxonomy"], indent=1))
    from capstone.eval.report import write_reports
    write_reports()
    return 0
