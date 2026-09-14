<!-- Soft Suave · Week 8 · Module 4 — Agent Failure Modes & Trajectory Evals. Track B: Recipes & food -->
# Week 8 — Trajectory eval: the recipe agent's outcome-vs-path gap

**Task:** the Week 7 agent (`agent/loop.py`) passes its outcome eval at 80-100%
run to run. That number can't see *how* it got there. This scores the path,
names the gap as a number, and closes one failure mode with the price tag
attached.

**Three commands:**

```bash
cd backend
python scripts/trajectory_eval_week8.py --tag before   # baseline, 10 cases -> docs/week8-trajectory-before.json
# ... apply exactly one mitigation to agent/tools.py ...
python scripts/trajectory_eval_week8.py --tag after     # same 10 cases, post-mitigation -> docs/week8-trajectory-after.json
python scripts/trajectory_eval_week8.py --compare       # before/after + regression table -> docs/week8-mitigation-report.json
python -m pytest tests/test_trajectory_eval_week8.py -v # deterministic ground-truth checks, no network
```

Model: `openai/gpt-oss-20b` on Groq, `temperature=0`, `reasoning_effort=low` —
same model and same 10 requests as [week7-agent-vs-workflow.md](week7-agent-vs-workflow.md)
(imported from `scripts/race_week7.py`), so this is a same-agent, same-day
follow-up, not a new benchmark.

---

## 1. The 10 cases and their expected tool multiset

`expected_trajectory()` in
[`scripts/trajectory_eval_week8.py`](../backend/scripts/trajectory_eval_week8.py)
derives the *minimal* tool calls each case needs by walking the substitution
table the same way `agent/workflow.py` resolves cascades — pure Python, no
LLM call, so the ground truth can't itself hallucinate. It is asserted in
code and locked in by
[`tests/test_trajectory_eval_week8.py`](../backend/tests/test_trajectory_eval_week8.py)
(4 tests, no network, run in 0.25s).

| id | recipe | avoid | search | get_nutrition | substitute | steps needed | alternate path? |
|---|---|---|---:|---:|---:|---:|:--:|
| r01_p4 | Classic Pancakes | dairy | 1 | 1 | 2 | 4 | ✔ |
| r02_p8 | Classic Pancakes | dairy, gluten | 1 | 1 | 4 | 6 | ✔ |
| r03_mac6 | Weeknight Mac and Cheese | gluten | 1 | 1 | 2 | 4 | ✔ |
| r04_mac4nut | Weeknight Mac and Cheese | dairy, tree_nut | 1 | 1 | 4 | 6 | ✔ |
| r05_curry4 | Thai Green Curry | shellfish | 1 | 1 | 1 | 3 | ✔ |
| r06_curry2 | Thai Green Curry | shellfish, fish | 1 | 1 | 3 | 5 | ✔ |
| r07_curry8 | Thai Green Curry | fish, soy, shellfish | 1 | 1 | 5 | 7 | ✔ |
| r08_bread8 | Banana Bread | dairy, egg | 1 | 1 | 2 | 4 | ✔ |
| r09_noodle4 | Veggie Stir-Fry Noodles | gluten, soy | 1 | 1 | 3 | 5 | ✔ |
| r10_cookie12 | Chocolate Chip Cookies | dairy | 1 | 1 | 2 | 4 | ✔ |

**Every one of the 10 legitimately accepts more than one valid path** — each
needs at least one substitution, so whether `get_nutrition` runs before or
after the substitution calls is free, and multiple original ingredients can
be substituted in either order. The eval therefore asserts each case as a
**multiset of required tool counts** (`Counter({"SearchRecipes": 1,
"GetNutrition": 1, "SubstituteIngredient": N})`), never a fixed sequence —
the only hard order constraint is `SearchRecipes` first (you cannot scale or
substitute a recipe you have not fetched) and, within one ingredient's own
cascade chain, that a substitute cannot be named before the tool has
returned it.

---

## 2. Four trajectory numbers (baseline, before mitigation)

10 live runs against Groq, `Budget()` defaults (10 laps / 24k tokens /
$0.02 / 90s):

| metric | before |
|---|---:|
| tool-choice accuracy | **100.0%** |
| argument validity rate | **100.0%** |
| step efficiency (mean, taken/needed) | **0.841** |
| cost / request — p50 | **$0.00092** |
| cost / request — max | **$0.00126** |

Tool-choice accuracy and argument validity both read 100% — every call the
agent *did* make was a real, on-schema call to a tool it needed. Neither
number can see a call that never happened; that is exactly the blind spot
step efficiency (0.841, i.e. the agent averaged fewer calls than the minimum
needed) and the trajectory pass rate below expose. `argument_validity`
checks that every `recipe_name` / `ingredient` the model wrote resolves to a
real entry in `agent/recipes.py::RECIPES` / `SUBSTITUTIONS` (see `_arg_valid`
in the script) — no fluent fiction was observed in this run, but the check
runs on every case regardless.

Full per-case rows: [`week8-trajectory-before.json`](week8-trajectory-before.json).

---

## 3. The outcome-vs-trajectory gap

| | before |
|---|---:|
| outcome pass rate (`agent/contract.py::passes`) | **80%** (8/10) |
| trajectory pass rate (all required tools called, valid args, search first) | **60%** (6/10) |
| **gap** | **+20 points** |

**The named right-answer-wrong-path case: `r09_noodle4`** (Veggie Stir-Fry
Noodles, 4 servings, avoid gluten + soy). The recipe needs three independent
swaps (wheat noodles, soy sauce, firm tofu are all banned) plus a scaling
call — 5 steps minimum. The agent called `search_recipes` once, then went
straight to its final JSON:

```
expected (minimal): {SearchRecipes: 1, GetNutrition: 1, SubstituteIngredient: 3}   (5 steps)
actual call sequence: [SearchRecipes]                                              (1 step)
outcome checks: is_object, right_recipe, servings_set, has_ingredients, has_method,
                allergen_free, originals_removed, scaled  -> ALL PASSED
```

It never called `get_nutrition` and never called `substitute_ingredient` —
not once — yet produced a scaled, fully substituted, allergen-free recipe
that passes every outcome assertion. This is the exact failure named in the
brief: a correct answer produced from the model's own memory of this small,
fixed recipe book, with zero evidence in the trajectory that it checked
anything. An outcome-only eval would have shipped this run as a clean pass.

---

## 4. The mitigation: tighter tool descriptions

**Failure-mode count, baseline (10 cases, modes can co-occur):**

| mode | count |
|---|---:|
| **tool_skipped** | **4** |
| hallucinated_args | 0 |
| redundant_calls | 0 |
| wrong_tool_choice | 0 |
| budget_exceeded | 0 |

`tool_skipped` (a required tool called fewer times than the minimum) is the
only mode observed, in 4 of 10 cases (`r02_p8`, `r05_curry4`, `r07_curry8`,
`r09_noodle4`) — so it is trivially also the top mode. One mitigation
applied, from the Week 8 list: **tighter tool description** on the two tools
being skipped, `get_nutrition` and `substitute_ingredient`
([`agent/tools.py`](../backend/agent/tools.py)). Nothing else changed — no
argument validation, no step limit, no re-planning, no swap to the workflow.

```diff
  get_nutrition
  "Scale one already-fetched recipe to a target serving count and return
   the recomputed ingredient amounts plus a per-serving calorie estimate.
   Requires an exact recipe name that search_recipes already returned — it
-  does not search, and it does not change any ingredients."
+  does not search, and it does not change any ingredients. MANDATORY: call
+  this before writing ANY scaled quantity into your final answer — never
+  compute or state a scaled amount from memory, even when the ratio looks
+  obvious."

  substitute_ingredient
  "Swap exactly ONE allergen-bearing ingredient in a recipe for a safe
   alternative. Returns the single best substitute, its converted amount, and
   the allergen class the substitute itself carries (which may be another
   banned class — if so, call this again on the substitute). One swap per
-  call: it does not search, scale, or return the method."
+  call: it does not search, scale, or return the method. MANDATORY: call
+  this for EVERY ingredient you remove or replace before finalizing — never
+  state a substitution from memory, even a common one you already know."
```

**`tool_skipped` count, before -> after:**

| | before | after |
|---|---:|---:|
| tool_skipped cases | **4 / 10** | **1 / 10** |
| trajectory pass rate | 60% | **90%** |
| outcome pass rate | 80% | **100%** |
| gap | +20 pts | **+10 pts** |
| step efficiency (mean) | 0.841 | **0.971** |

Three of the four skips closed outright (`r02_p8`, `r05_curry4`, `r09_noodle4`
now call every required tool). One remains — `r07_curry8` (the depth-3,
two-ingredient cascade: 5 substitution calls needed, agent made 3) — still
outcome-passes by coincidence, still trajectory-fails. **The mitigation did
not eliminate the mode, it cut it 4→1**; that is reported honestly rather
than rounded up to "fixed."

**Price paid** (measured, not asserted free):

| | before | after | delta |
|---|---:|---:|---:|
| cost / request p50 | $0.00092 | $0.001041 | **+$0.000121/req (+13%)** |
| cost / request max | $0.00126 | $0.00139 | +$0.00013 |
| total tokens, 10 requests | — | — | **+14,175 tokens** (~+177 tokens/lap, longer schema sent every lap, plus the extra calls the mitigation now forces) |

The added text lives in the tool schema, which Groq re-bills on **every**
lap of every request (`agent/llm.py`'s per-lap `Usage` accounting, same
reason Week 7 warned against reading only the last call's tokens). Forcing
three previously-skipped cases to actually make their calls adds real laps
on top of that. Full before/after rows + machine-readable delta:
[`week8-trajectory-after.json`](week8-trajectory-after.json),
[`week8-mitigation-report.json`](week8-mitigation-report.json).

---

## 5. Regression check

| mode | before | after | delta |
|---|---:|---:|---:|
| tool_skipped | 4 | 1 | −3 |
| hallucinated_args | 0 | 0 | +0 |
| redundant_calls | 0 | 0 | +0 |
| wrong_tool_choice | 0 | 0 | +0 |
| budget_exceeded | 0 | 0 | +0 |

All five modes in the taxonomy were checked. **No mode got worse and no new
mode appeared.** The longer, more directive tool descriptions did not push
the model into over-calling (`redundant_calls` stayed at 0), inventing
identities under the added pressure (`hallucinated_args` stayed at 0), or
blowing any budget (`budget_exceeded` stayed at 0).

---

## 6. Why this matters more than the outcome number alone

The two evals tell different stories on the same 10 requests:

- Outcome eval, baseline: "80% pass, pretty good."
- Trajectory eval, baseline: "60% actually did the work; the other 20 points
  of that 80% got the right answer by not checking." That 20-point gap is
  the number the food team's trust problem lives in (Section 1 of
  [W8-Task-Set-B.md](W8-Task-Set-B.md)) — a correct nut-free substitution
  produced without ever calling the allergen tool is a passing outcome test
  and a real liability, because the next request this same model "just
  knows" wrong is indistinguishable from this one until it ships.

One mitigation, measured before and after, with the price named, closed most
but not all of that gap — which is the honest result a trajectory eval is
for.

<!-- 210 words -->
