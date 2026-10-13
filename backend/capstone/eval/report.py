"""Regenerates the number-bearing docs from the saved runs in docs/capstone/results/.
Nothing in the generated files is typed by hand - they are overwritten on every eval."""
from __future__ import annotations

import json

from capstone import config
from capstone.eval.run import RESULTS, SEVERITY, summarize

NOT_COVERED = """\
## What this suite does NOT cover (stated, not implied)

- **Corpus scale.** 26 recipes / 34 versioned records, not the client's 600 (the CMS export is not in the repo).
  Retrieval hit-rate at 600 recipes is unmeasured; near-duplicate titles are far likelier there.
- **Real users.** 30 hand-written questions. No typos, no multi-turn, no non-English, no voice, no images.
- **Cross-contamination / kitchen practice.** The suite checks the *declaration fields*; it cannot know whether the
  declaration is itself right. A "no_declared_conflict" verdict is not a clinical guarantee.
- **Allergens outside the 9 declared classes** (mustard, celery, sulphites...): only the refusal behaviour is tested (c28).
- **Prose quality at scale.** One judge, validated on a small hand-labelled set; its agreement interval is wide.
- **Statistical power.** Most cases run once. gpt-oss-20b is non-deterministic even at temperature 0, so a single
  pass is weak evidence; the before/after delta is directional, not significant.
- **Adversarial input** (prompt injection in pantry text, jailbreaks) - Week 8's injection suite was not re-run here.
- **Load, concurrency, MCP server crashes** - see tenx.md for the one micro-benchmark that exists.
"""


def _row(c, v):
    return f"| {c} | {v['pass']}/{v['n']} | {round(100 * v['pass'] / v['n'])}% |"


def write_reports() -> None:
    runs = {}
    for tag in ("before", "after"):
        p = RESULTS / f"run-{tag}.json"
        if p.exists():
            runs[tag] = json.loads(p.read_text(encoding="utf-8"))
    if not runs:
        return
    sums = {t: summarize(r) for t, r in runs.items()}
    jv = RESULTS / "judge_validation.json"
    jval = json.loads(jv.read_text(encoding="utf-8")) if jv.exists() else None
    L = ["# Eval report - integrated system (auto-generated)", ""]
    for tag, s in sums.items():
        r = runs[tag]
        L += [f"## Run `{tag}` - {r['ts']}", "",
              f"config: `{r['config']}`  |  tools discovered over MCP: `{', '.join(r['discovered_tools'])}`  |  n = {s['n']} cases", "",
              f"**Pass rate: {s['pass']}/{s['n']} = {round(100 * s['pass_rate'])}%** (a case passes only if every assertion passes)", "",
              "| category | pass | rate |", "|---|---|---|"]
        L += [_row(c, v) for c, v in s["per_category"].items()]
        a = s["allergen_unsafe"]
        L += ["", f"**Allergen-unsafe answer rate** (allergen_version + pantry_swap + refusal cases, n = {a['n_safety_cases']}): "
                  f"**{a['final_unsafe']}/{a['n_safety_cases']} = {round(100 * a['final_rate'])}%** as shown to the user; "
                  f"{a['raw_unsafe_before_guards']}/{a['n_safety_cases']} = {round(100 * a['raw_rate'])}% in the model's raw answer before guards. "
                  f"Cases: {a['unsafe_case_ids'] or 'none'}", ""]
        t = s["trajectory"]
        L += [f"**Trajectory (n = {t['n']}):** tool-choice accuracy {t['tool_choice_accuracy']}, trajectory pass {round(100 * t['trajectory_pass_rate'])}%, "
              f"outcome pass {round(100 * t['outcome_pass_rate'])}%, **outcome-minus-trajectory gap {round(100 * t['outcome_minus_trajectory_gap'])} points**", "",
              f"**Cost/latency:** mean ${s['cost']['mean_usd']} per query ({s['cost']['mean_tokens']} tokens, {s['cost']['mean_laps']} laps), "
              f"p50 {s['cost']['p50_latency_ms']} ms, p95 {s['cost']['p95_latency_ms']} ms", "",
              "### Failure taxonomy (this run)", "", "| mode | cases | frequency | severity | example trace |", "|---|---|---|---|---|"]
        L += [f"| {m} | {v['cases']} | {v['frequency_pct']}% | {v['severity']} | `{v['example_trace']}` ({v['example_case']}) |"
              for m, v in s["taxonomy"].items()] or ["| (none) | | | | |"]
        failing = [x for x in r["results"] if not x["pass"]]
        L += ["", "### Failing cases", ""]
        for x in failing:
            bad = [k for k, v in x["run"]["checks"].items() if not v]
            L += [f"- **{x['id']}** ({x['category']}) failing: `{', '.join(bad)}` - trace `{x['run']['trace_id']}`"]
        if not failing:
            L += ["- none"]
        L.append("")
    if "before" in sums and "after" in sums:
        b, a = sums["before"], sums["after"]
        ids = {x["id"] for x in runs["before"]["results"]}
        a_sub = [x for x in runs["after"]["results"] if x["id"] in ids]
        a_unsafe = sum(x["run"]["final_unsafe"] for x in a_sub if x["category"] in ("allergen_version", "pantry_swap", "refusal"))
        n_safe = sum(1 for x in a_sub if x["category"] in ("allergen_version", "pantry_swap", "refusal"))
        L += ["## Before -> after (same cases)", "",
              f"Allergen-unsafe answer rate on the same {n_safe} safety cases: **{b['allergen_unsafe']['final_unsafe']}/{b['allergen_unsafe']['n_safety_cases']}"
              f" -> {a_unsafe}/{n_safe}**. Suite pass rate on the shared cases: "
              f"{sum(x['pass'] for x in runs['before']['results'])}/{len(ids)} -> {sum(x['pass'] for x in a_sub)}/{len(a_sub)}.", ""]
    if "before" in runs:
        pantry = [x for x in runs["before"]["results"] if x["category"] == "pantry_swap"]
        old_pass = [x for x in pantry if x["run"]["checks"].get("no_unsafe_endorsement")]       # check on the PUBLISHED recipe
        now_fail = [x["id"] for x in old_pass if not x["run"]["checks"].get("no_unsafe_swap", True)]
        L += ["## Bonus: check moved downstream of the system's own substitution (BEFORE config outputs)", "",
              f"Pantry cases: {len(pantry)}. Passing the old published-recipe allergen check: {len(old_pass)}. "
              f"Of those, **failing once the check runs on the recipe AS SUBSTITUTED: {len(now_fail)}** ({now_fail or 'none'}).", ""]
    if jval:
        L += ["## Judge validation (integrated outputs vs hand labels)", "",
              f"model `{jval['model']}`: agreement **{jval['agree']}/{jval['n']} = {round(100 * jval['agreement'])}%** "
              f"(clears 85%: **{jval['clears_85']}**); judge passed a bad answer {jval['judge_passes_a_bad_answer']}x, "
              f"failed a good answer {jval['judge_fails_a_good_answer']}x.", ""]
    L.append(NOT_COVERED)
    (config.DOCS_DIR / "eval_report.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote", config.DOCS_DIR / "eval_report.md")
