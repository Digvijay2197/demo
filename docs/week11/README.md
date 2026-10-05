<!-- Soft Suave · Week 11 · Task Set B — index + honest status -->
# Week 11 · Task Set B — "Find the dairy-free swap that wasn't"

## Submission checklist → file

| required | file | status |
|---|---|---|
| drill.md (mm:ss + slice) | [drill.md](drill.md) | **00:18** via input type + answer text; bonus **00:03** via `answer_flags.dairy_free_violation`. ⚠ machine-timed, **not** by a named squadmate — re-run it (steps inside) |
| trace.json | [trace.json](trace.json) | per-span latency/tokens/cost, `prompt_version: v1`, 4 retrieved chunk ids |
| eval case file in the Week-6 suite | `backend/eval/w11_dairy_free_cases.json` (copy: [eval_cases_w11.json](eval_cases_w11.json)), loaded by `scripts/eval_week6.py` | done; each case must pass 3/3 repeats |
| RED output + counts | [suite_red.txt](suite_red.txt) | **17/20** (production model gpt-oss-20b, prompt v1) |
| GREEN output + counts | [suite_green.txt](suite_green.txt) | **in progress** — see below |
| cost_by_stage.md | [cost_by_stage.md](cost_by_stage.md) | generation = 100% of $0.000116/query; input tokens 73% of it |
| tenx.md | [tenx.md](tenx.md) | rate limit breaks first: 10x peak = 35,933 tok/min vs 8,000 ceiling (4.5x) |
| prompt version bump + canary/rollback | [prompt_versions.md](prompt_versions.md) | v1 → v3 |

## RED → GREEN, what is actually proven

**RED (before any fix, full suite, v1):** `17/20` — failures: **w11-01, w11-02** (real dairy endorsements: *"you can use either oil or ghee"*, *"Yes … you can substitute ghee for the oil"*) and **e05**.
The model is non-deterministic even at temperature 0 (v1 passes w11-01 1/5, w11-02 0/5), hence the 3/3-repeat rule.

**e05 is a pre-existing failure, not mine** (fails 5/5 on v1, before any change): "Oatmeal Buns" outranks "Oatmeal Bread" on p.5 and the model refuses. Left as is — retrieval is out of scope this week — so the best possible GREEN count is **19/20**, not 20/20. I did not hide it by deleting the case.

**GREEN (v3, production model) so far:** w11-02 **9/9** (was failing). The full-suite GREEN run is still executing: the Groq free tier's 200k-tokens/day cap was exhausted by my own eval reruns (`429 … TPD: Limit 200000, Used 199123`), so it is running with `--patient` at roughly one LLM call per 5–7 minutes (~3 more hours). It writes to `suite_green.txt`, ending with a `SUITE: x/20` line and `done`. **Nothing there is final until that line appears.**
To re-run later in one command (≈10 min once the quota is back):

```bash
cd backend && python scripts/eval_week6.py --tag w11-green > ../docs/week11/suite_green.txt
```

Regression coverage while waiting (no tokens): `scripts/w11_prompt_identity.py` → [prompt_identity_check.txt](prompt_identity_check.txt): **17 of the 20 cases get a byte-identical prompt under v3**, and the 3 restricted ones differ by exactly the reminder. So v3 cannot regress e16-style cases by construction — which is the point of choosing it over v2 (v2 *did* regress e16, 5/6 → 0/6).

Other runs kept for the record: `suite_green_v2-attempt1_gpt-oss-20b.txt` (17/20, new regression), `suite_partial_v2-final_gpt-oss-20b.txt` (w11-02 still 7/9), `suite_partial_v3_run1_checker-fp_gpt-oss-20b.txt` (8/9 caused by a false positive in my checker, fixed — "substitute oil *for* the ghee" is safe), `suite_red_gpt-oss-120b_unreliable-RED.txt` (a second model; its RED didn't reproduce, so not used as evidence).

## Things you should know before submitting

1. **Squadmate:** the checklist wants drill times from a named squadmate. Mine are machine-timed and not blind (drill.md §"What this drill is NOT"). Run `w11_plant.py` with a squadmate.
2. **Simulated traffic:** the week of logs is resampled from 30 real traced answers; the 10x "today" column inherits that. The ceiling numbers in tenx.md are measured.
3. **Prices are assumed** Groq list prices (the free tier bills $0); verify at groq.com/pricing.
4. **Test fixes after seeing RED, all disclosed:** w11-03 dropped the `oil` keyword (a safe answer was failing on wording); the dairy checker was corrected twice (negation direction; "substitute X *for* Y"; a stray backspace character in the `vegan` regex). `suite_red.txt` used the first checker; I re-scored every collected v1 answer with the final one and the same answers are flagged.
5. **Log-time latency finding:** the first request after boot spent 14.9 s in retrieval (embedding model cold start) — visible only because spans exist. Not fixed.
6. I printed fragments of two `GROQ_API_KEY` lines in my terminal output early on while checking `.env` (a mistake; ~13 chars each). Rotate the commented-out one if you care.

## Where things are

`backend/rag/observability/` (tracing, dairy check) · `backend/rag/generation/prompt.py` (v1/v2/v3, `PROMPT_VERSION`) · `backend/scripts/w11_*.py` (capture, seed, plant, drill, logsearch, backfill, costs, flaky, prompt_identity) · `backend/tests/test_observability_week11.py` (39 tests pass) · logs in `backend/logs/` (gitignored except `real_pool.jsonl`).
