<!-- Plain-English companion to week5-error-analysis.md and week6-evals.md -->
# Weeks 5 & 6 explained — what it is, why, and how to demo it

This file is the narration. The two deliverables are:

- [`week5-error-analysis.md`](week5-error-analysis.md) — the error analysis
- [`week6-evals.md`](week6-evals.md) — the eval set + judge + before/after

---

## 1. The one-paragraph version

Week 5 is **reading**: run ~20 real questions through the bot, look at what it
actually retrieved and answered, write down what went wrong in plain words, then
group those notes into a handful of named problems and rank them so you know what
to fix first. Week 6 is **measuring**: turn those questions into an automatic
test that gives every future change a score instead of a gut feeling — cheap
yes/no checks first, and an AI "judge" for the fuzzy stuff, but only after you've
checked the judge agrees with your own grading. Then you make **one** change and
show the score went up, and that nothing else went down.

---

## 2. Week 5 — Error Analysis, step by step

| Step | What it means here | Where it is |
|---|---|---|
| **Trace** | A full record of one request: the question, the 4 chunks retrieval pulled (with scores), and the final answer. Complete enough to replay. | `scripts/collect_traces.py` → `week5-traces.jsonl` |
| **Fair sample** | 22 questions chosen to cover the real mix — lookups, recipes that share a page, "can I substitute…", comparisons, a typo query, "list everything", and things the corpus can't answer. Not 22 questions we knew would pass. | `week5-error-analysis.md` §1 |
| **Open coding** | Read each trace once and write **one honest sentence** about what went wrong — *before* inventing categories. This is the part no tool can do for you. | §2 (the table's "note" column) |
| **Name the problems** | Cluster the 22 notes into 7 named types (P1–P7): e.g. "modification questions decline", "list-all retrieves the index page". | §3 |
| **Rank them** | Sort by **how often** it happens × **how badly** it hurts. P1 is 3/22 and high-severity → rank 1. | §4 |
| **Pick one + predict** | Choose P1 to fix. **Write down what you expect to happen before you touch anything** — so the result can't be rationalised afterwards. | §5 |

**Why read by hand?** A smarter model or a bigger `top_k` doesn't help if the
problem is "the bot refuses when it should answer" — that's a prompt/policy bug,
and you only see it by reading. Three of our four refusals were *correct*; the
one that wasn't (t07) looks identical from the outside. Reading is how you tell
them apart.

**What Week 5 found (headline):** 13 of 22 traces are fine. The recurring real
defect is **P1 — "can I substitute X / make it vegetarian / how much X" gets a
refusal or a flat "not provided", even though the right recipe was retrieved.**

---

## 3. Week 6 — Evals, step by step

| Step | What it means here | Where it is |
|---|---|---|
| **Eval set** | 16 test cases, each a real Week 5 question + what a good answer must contain. | `scripts/eval_week6.py` `CASES`; `week6-evals.md` §1 |
| **Regression tests from failures** | The failures (e13–e16) and the correct refusals (e10–e12) and the fixed multi-recipe case (e05) are *in* the set, so they can't silently break again. | §1 |
| **Assertion checks first** | 7 free yes/no checks: did it refuse when it should? is a source attached? does the citation resolve? is the expected fact in the answer? Run on every change, no AI needed. | §2–§3 |
| **LLM-as-judge** | For "was the substitution answer actually helpful and grounded?" — a number a rule can't produce — one AI call grades the answer 1–5 against a rubric. | §4 |
| **Validate the judge** | Hand-grade 10 answers, run the judge on the same 10, check they agree. Ours: **9/10 within ±1 point (90%)** → trusted. We also wrote down its blind spot (it under-punishes plausible-but-invented specifics). | §4 |
| **Before / after, per problem type** | Make the one Week 5 change (the prompt rule). Re-score. Substitution-judge mean **2.25 → 4.50 / 5**, bare refusals **2 → 0**. And the other categories stay at 100% — proof the fix didn't cost anything elsewhere. | §5 |

**Why validate the judge first?** An AI judge you never checked is just a
confident number nobody should trust. We only used its score *after* showing it
lines up with human grades on a labelled sample.

**Why "one change"?** If you change the prompt *and* swap the model, and the
number moves, you've learned nothing about which one did it. Here the only
variable between BEFORE and AFTER is the prompt.

---

## 4. How this maps to the task briefs

### Week 5 brief checklist

- [x] ~20 complete traces, replayable → 22 in `week5-traces.jsonl`
- [x] Random/fair sample, not cherry-picked → §1
- [x] One honest note per failure, written before categories → §2
- [x] Grouped into named problem types a stranger would understand → §3 (P1–P7)
- [x] Ranked by frequency × severity → §4
- [x] One chosen fix target + a prediction written first → §5

### Week 6 brief checklist (Track B = "validate the substitution judge")

- [x] Test set runs with a single command → `python scripts/eval_week6.py`
- [x] Last week's real failures included as tests → e13–e16, e10–e12, e05
- [x] Cheap assertion checks (source present? refused when it should?) → §2
- [x] LLM judge for the axis a rule can't check → the substitution judge, §4
- [x] Judge checked against human grading before it's trusted → §4 (90% ±1)
- [x] Before/after score, per problem type, from one change → §5

---

## 5. Demo script (≈6 minutes)

1. **Frame it (30s).** "Week 5 is reading the bot's own answers to find real
   problems; Week 6 is building the test that scores every future fix."

2. **Show a trace (60s).** Open `week5-traces.jsonl`, pick **t07**
   (`can I make the chicken biryani vegetarian`). Point at: the biryani chunk was
   retrieved at score 0.64 — retrieval was fine — but the answer is the refusal
   sentence. "Retrieval worked; the bot just declined. You only catch that by
   reading."

3. **Show the taxonomy (60s).** `week5-error-analysis.md` §3–§4. "22 traces, 7
   named problems, ranked. Number one — 3 traces, high severity — is
   *modification questions decline*. That's what I'm fixing, and here's the
   prediction I wrote before touching anything." Read §5.

4. **Show the eval set (60s).** `week6-evals.md` §1–§2. "16 cases, all from real
   questions. Seven free yes/no checks — no AI. The failures are baked in so they
   can't come back." Show §3: everything green except the substitution slice at
   86%.

5. **Show the judge validation (60s).** §4 table. "For 'was the answer helpful',
   a rule can't decide, so an AI judges it 1–5. But first I checked it against my
   own grades: 9 out of 10 within one point. I also wrote down where it's weak."

6. **Show the number that moved (60s).** §5. "One change — a prompt rule. Same
   model, same corpus. Substitution judge mean 2.25 → 4.50 out of 5. Bare
   refusals 2 → 0. And every other category stayed at 100%, so the fix didn't
   break anything." Optionally run `python scripts/eval_week6.py --validate-judge`
   live.

7. **Close (20s).** "The deliverable isn't the bot — it's the loop: read →
   name → rank → change one thing → measure. That loop is now one command."

---

## 6. Files

| File | What |
|---|---|
| `docs/week5-error-analysis.md` | Week 5 deliverable — 22 traces, notes, taxonomy, ranked, target + prediction |
| `docs/week5-traces.jsonl` | the 22 raw traces (question + retrieved chunks + answer) |
| `docs/week6-evals.md` | Week 6 deliverable — eval set, assertions, judge + validation, before/after |
| `backend/scripts/collect_traces.py` | one command to regenerate the traces |
| `backend/scripts/eval_week6.py` | one command to run the eval set + judge (`--validate-judge`, `--tag`) |
