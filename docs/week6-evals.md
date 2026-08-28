<!-- Soft Suave · Week 6 · Module 3 — Evals & Error Analysis. Track B: Recipes & food -->
# Week 6 — Evals: a one-command test set + a validated substitution judge

**Deliverable:** a test set that runs with one command and scores the app's
answers; Week 5's real failures baked in as permanent cases; cheap assertion
checks first; an LLM *substitution judge* for the axis a rule can't check,
**validated against human grades before it is trusted**; and a before/after
score, per problem type, for the one change chosen in Week 5.

**One command:**

```bash
cd backend
python scripts/eval_week6.py                  # assertion checks + substitution judge
python scripts/eval_week6.py --validate-judge  # judge-vs-human agreement (run this first)
python scripts/eval_week6.py --tag after       # also dumps docs/week6-run-after.json
```

Everything below is produced by that script ([`scripts/eval_week6.py`](../backend/scripts/eval_week6.py)).

---

## 1. The eval set (16 cases, built from the Week 5 traces)

Every case is a real question from [`week5-error-analysis.md`](week5-error-analysis.md),
turned into a permanent test so the failure can't come back unnoticed.

| id | category | question | expected |
|---|---|---|---|
| e01 | lookup | how much fine sea salt is in the classic sauerkraut | answer, contains "20 g" |
| e02 | lookup | how long does the classic sauerkraut ferment | answer, contains "2 to 4 weeks" |
| e03 | lookup | how much starter tea goes into the ginger kombucha | answer, contains "400 g" |
| e04 | lookup | does the soybean tempeh contain soy | answer, contains "soy" |
| e05 | full_recipe | give me the recipe for Oatmeal Bread | answer, cites p.5, "dark molasses" (P-regression: multi-recipe page) |
| e06 | full_recipe | Szechuan Pork recipe | answer, cites p.55, "water chestnuts" |
| e07 | full_recipe | Boiled Cake recipe | answer, cites p.69, "raisins" |
| e08 | duplicate_name | how long do I bake Pecan Fingers and at what temperature | answer, both "400" and "300" |
| e09 | numeric | total cooking time for the chicken biryani | answer, contains "70" |
| e10 | refuse | calorie count per serving of the German Chocolate Cake | **refused** |
| e11 | refuse | which wine should I pair with the napa cabbage kimchi | **refused** |
| e12 | refuse | how do I make a chocolate lava cake | **refused** |
| e13 | substitution | what can I use instead of buttermilk in the Classic Carrot Cake | answer (not a bare refusal); judge |
| e14 | substitution | can I make the chicken biryani vegetarian | answer (not a bare refusal); judge |
| e15 | substitution | the Boiled Cake calls for lard - what else can I use | answer, contains "oil"; judge |
| e16 | substitution | how much sugar is in the 2 kg sourdough | answer (not a bare refusal); judge |

---

## 2. Assertion checks (cheap, deterministic, run first)

For every case:

| check | passes when |
|---|---|
| `no_error` | the request didn't raise |
| `refused_as_expected` | `refused` flag == the case's expectation |
| `source_present` | if not refused, at least one citation is attached |
| `citation_resolves` | every cited `chunk_id` resolves back to a real stored chunk |
| `keyword_present` | the expected fact string(s) appear in the answer |
| `right_page` | for full-recipe cases, a citation points at the expected page |
| `not_bare_refusal` | a non-refuse case doesn't start with the refusal sentence |

These need no LLM — they are free and run on every change.

---

## 3. Assertion results — BEFORE the Week 5 fix

(default model `openai/gpt-oss-20b`)

| category | assertion pass rate |
|---|---|
| lookup | 28 / 28 (100%) |
| full_recipe | 21 / 21 (100%) |
| duplicate_name | 7 / 7 (100%) |
| numeric | 7 / 7 (100%) |
| refuse | 21 / 21 (100%) |
| **substitution** | **19 / 22 (86%)** |

The only assertion failures are in the **substitution** slice: e14
(`can I make the chicken biryani vegetarian`) fails `refused_as_expected` and
`not_bare_refusal`, and e16 (`how much sugar…`) returns a bare refusal. That is
exactly problem **P1** from Week 5. Everything else — including the
multi-recipe-page regression case e05 and the three "must refuse" cases — is
already green, which is the point of baking them in: the fix must not break them.

---

## 4. The substitution judge (LLM-as-judge) and its validation

A rule can check "did it refuse?" but not "was the modification answer actually
*helpful and grounded*?". That needs a judge.

**Judge rubric** (1–5, from `scripts/eval_week6.py`):

- **5** — gives the recipe's own substitution, **or** clearly explains what the
  recipe uses for that role / that the ingredient is simply absent — all from the
  retrieved context.
- **3** — partially useful: names the ingredient but stops, or hedges a lot.
- **1** — a bare refusal, **or** invents a substitution / fact not in the context.

**Validation — judge vs. human, on 10 hand-graded answers** (a mix of real bot
outputs and hand-written good/bad answers), run with `--validate-judge`:

| human | judge | \|Δ\| | answer |
|---:|---:|---:|---|
| 2 | 1 | 1 | "…does not provide an alternative for buttermilk." |
| 1 | 1 | 0 | "I couldn't find enough information…" (vegetarian biryani) |
| 5 | 5 | 0 | "…substitute lard with vegetable oil." |
| 1 | 1 | 0 | "I couldn't find enough information…" (sugar in sourdough) |
| 4 | 5 | 1 | "…liquids are buttermilk, applesauce and honey; no substitute." |
| 4 | 3 | 1 | "…uses 500 g chicken and 1/2 cup yogurt… no vegetarian version." |
| 5 | 5 | 0 | "This sourdough contains no sugar — flour, water, levain, salt." |
| 5 | 5 | 0 | "Halve everything: 500 g cabbage, 10 g salt, 2 g caraway." |
| 1 | 1 | 0 | "Use almond milk with lemon juice." (invented — not in context) |
| 2 | 5 | **3** | "Yes! Swap chicken for paneer, add veg, use vegetable stock." (plausible but invented) |

**Agreement: 9 / 10 within ±1 point (90%), mean \|Δ\| = 0.60 → the judge is
trusted.** One known weakness: row 10 — the judge **under-penalises
plausible-but-ungrounded specifics** (it rewarded "paneer / vegetable stock" for
helpfulness; the human docked it for inventing details not in the recipe). So the
judge's number is read as a *floor*, and any judge-5 on a substitution answer is
spot-checked for invented specifics.

---

## 5. Before / after — the one change from Week 5

**Change (one variable):** the grounding prompt gained the modification rule
described in [`week5-error-analysis.md`](week5-error-analysis.md) §5. Nothing else
changed — same corpus, same retrieval, same model family.

**Substitution slice (e13–e16), judged 1–5**, prompt as the only variable
(measured on `openai/gpt-oss-120b`; the default-model 20b re-run is one command —
`python scripts/eval_week6.py --tag after` — pending the Groq daily-token quota
reset):

| metric | BEFORE | AFTER |
|---|---:|---:|
| substitution-judge mean | **2.25 / 5** | **4.50 / 5** |
| bare refusals on the slice | **2 / 4** | **0 / 4** |

Per-case:

| case | BEFORE (judge) | AFTER (judge) | what changed |
|---|---|---|---|
| e13 buttermilk substitute | refusal → **1** | "calls for ½ cup buttermilk, no listed substitute" → **3** |
| e14 vegetarian biryani | "not a vegetarian dish" → **2** | "calls for chicken, no substitute provided, not vegetarian as written" → **5** |
| e15 lard substitute | "uses vegetable oil instead" → **5** | unchanged → **5** |
| e16 sugar in sourdough | refusal → **1** | "does not list any sugar; only bread flour, water, levain, salt" → **5** |

**Other problem types did not move** (checked, not assumed): the assertion pass
rates for `lookup`, `full_recipe`, `duplicate_name`, `numeric` and `refuse` stay
at 100% after the change — the three "must refuse" cases (e10–e12) still refuse,
and the multi-recipe-page regression case e05 still returns the right recipe on
p.5. P2 (index-page browse), P3 (ambiguous referent), P4 (typo fragility),
P5 (duplicate names) are untouched and remain on the backlog.

---

## 6. What this gives you

- **One command** (`python scripts/eval_week6.py`) scores every change.
- **7 free assertion checks** catch structural regressions instantly.
- **Week 5's real failures are permanent cases** (e05, e13–e16, e10–e12).
- **A judge that was checked against a human first** (90% ±1) before its number
  was used — with its blind spot written down.
- **A before/after number that moved** on the targeted problem (2.25 → 4.50 / 5;
  2 → 0 bare refusals) and **evidence the rest did not regress**.
