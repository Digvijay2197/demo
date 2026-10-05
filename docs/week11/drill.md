<!-- Soft Suave · Week 11 · Module 6 — Production. Task Set B (Recipes & food): "Find the dairy-free swap that wasn't" -->
# Support drill — find the dairy-free swap that wasn't

**Complaint (verbatim, and all I got):** *"someone said it recommended a dairy-free substitution that wasn't dairy-free, sometime last week."*
No trace id, no timestamp, no recipe name.

## Result

| | Drill 1 (logs as they were) | Bonus drill 2 (after adding one field) |
|---|---|---|
| **time-to-find** | **00:18** (17.6 s) | **00:03** (3.3 s) |
| **slice that found it** | **input type** (`dietary_restriction`) **+ answer text** (a regex for *recommendation phrasing next to a dairy word*), over the last 7 days | **derived output flag** `answer_flags.dairy_free_violation = true` |
| trace found | `tr_6988ef145c4d` · 2026-10-03 00:07 UTC · user `u_004` | `tr_56b6f5307852` · 2026-09-29 18:10 UTC · user `u_015` |
| verified correct | yes — checked against a salted hash written by the planter, not by eye | yes — same mechanism |
| 5-minute rule | under 5:00, so no missing field has to be named to excuse the time | — |

Timer: `scripts/w11_drill.py` (a machine stopwatch: `start` → `found <id>` verifies the id against the planter's sealed hash and prints mm:ss).

### ⚠ What this drill is NOT (read before grading)

1. **It was not timed by a named squadmate.** The brief's checklist asks for that. I ran the planter, the clock and the search myself (I'm an AI assistant working in the repo), so the 00:18 is a *tooling* time, not a human's. The three scripts make the real thing a 2-minute setup — see "Re-run it with a squadmate" below. **Do that and replace this table's times before Monday.**
2. **It was not blind.** The planted answer is drawn from two real failures I had already captured while probing the app (the brief's "recognising the recipe you demoed on Friday" mistake). I deliberately wrote the search from the *complaint* and from generic dairy vocabulary, not from the trace id, and the planter picks randomly and prints nothing — but I knew the *shape* of these answers ("you can use either oil or ghee", "Yes … you can substitute ghee"), and my second regex used that shape. A colleague who doesn't know it would likely need longer — that is exactly the gap the bonus field closes.
3. **The week of background traffic is simulated.** `logs/traces.jsonl` holds 1,412 traces: 1,411 resampled from 30 *real* traced answers (genuine model text, spans, tokens; new ids/users/timestamps and ±12% jitter on latency/tokens) plus the planted one. The planted answer itself is a real model output. Nobody actually used this app last week.

## How I searched (drill 1) — three commands, every step

All of this uses only what the complaint gives: *dairy-free*, *substitution*, *last week*, and that it is about the **output**.

| # | slice | command (abridged) | hits |
|---|---|---|---|
| 1 | input type + output text | `w11_logsearch.py --since 7d --type dietary_restriction --a "ghee\|butter\|milk\|cream\|cheese\|yogurt\|curd\|paneer"` | **529** — far too many: most answers legitimately *mention* dairy words ("it does not list a dairy-free substitute for the butter") |
| 2 | …same, sharpened to recommendation phrasing | `--a "(can\|may\|yes\|allows?)\b[^.]{0,60}\b(ghee\|butter\|milk\|…)"`, glanced at the questions | ~30 shown, two question families, mostly *negated* answers |
| 3 | …sharpened again | `--a "(you can\|can use\|can substitute\|allows you to use\|yes)\b[^.]{0,60}\b(ghee\|butter\|milk\|…)"` | **1** → `tr_6988ef145c4d` |

Why the other slices did not help (so "which slice found it" is a real answer, not a label):

| slice | usable? |
|---|---|
| **time** (last 7 d) | narrows nothing — it is the whole log (1,412) |
| **user** | the complaint names nobody |
| **prompt version** | every trace is `v1`, so it cannot separate anything (it becomes the *regression* slice once v2 exists) |
| **cost outlier** | a wrong-but-cheap answer is not an outlier; the 2% cost outliers in the log are unrelated long answers |
| **input type** | **useful** — `dietary_restriction` cut 1,412 → ~530 |
| **output text** | **decisive** — the complaint describes the *output*, so the answer has to be searchable (the brief's "search only inputs" mistake). Both question and answer are stored in full |

### The one field whose absence cost the time

Drill 1 stayed under five minutes, so nothing has to be blamed — but the honest cost was **step 2 and 3 above: I had to hand-write a regex for "recommends a dairy ingredient" every time.** The log knew the *words* of the answer but not whether the answer was **unsafe**. The missing field was a **derived output verdict**.

## Bonus — wire the drill shut

**Added:** `answer_flags` on every trace, computed at log time by `rag/observability/dairy_check.py` — the *same function* the eval assertion uses (so the thing the drill searches on is the thing the test asserts):

```json
"answer_flags": {"dairy_restriction_in_question": true, "dairy_free_violation": true, "dairy_terms_in_answer": ["ghee"]}
```

`scripts/w11_backfill_flags.py` stamped the existing week (1,412 traces → **1** flagged, the drill-1 trace — no false positives across 30 distinct real answers). A second answer was then planted (random pick, random time/user) and found with one command:

```
w11_logsearch.py --since 7d --flag dairy_free_violation   →  2 hits (drill-1's trace + the new one)   00:03
```

| | time | the one field |
|---|---|---|
| drill 1 | 00:18 | — (three iterative regex passes) |
| drill 2 | **00:03** | **`answer_flags.dairy_free_violation`** |
| **gap closed** | **15 s faster (≈ 6x)** | and, more importantly, it no longer depends on knowing the failure's wording |

The same field is what makes the *canary* in `prompt_versions.md` measurable: "violations per 100 dietary queries" is one `--flag … --type …` query.

## Re-run it with a squadmate (≈ 2 min)

```bash
cd backend
python scripts/w11_seed_logs.py --days 7 --per-day 220   # only if you need a fresh week of traffic
python scripts/w11_backfill_flags.py                      # optional: only for the bonus run
# squadmate:
python scripts/w11_plant.py                               # or W11_FLAGS=1 python scripts/w11_plant.py  (post-bonus logger)
python scripts/w11_drill.py start
# you: search with scripts/w11_logsearch.py (see its docstring for every slice) ...
python scripts/w11_drill.py found tr_xxxxxxxxxxxx --slice "…" --timer-by "<squadmate name>"
```
