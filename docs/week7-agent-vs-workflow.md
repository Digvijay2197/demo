# Week 7 — Race: recipe agent loop vs a fixed workflow

**Task (identical for both systems):** given a recipe name, a target serving count and a set of banned allergen classes, return the recipe **scaled** and with every banned ingredient **substituted** (resolving cascades, where a substitute is itself a banned allergen), in one fixed JSON contract.

**One command:**

```bash
cd backend
python scripts/race_week7.py                 # 10 requests x 2 systems -> docs/week7-race.csv
python scripts/race_week7.py --only agent     # just the agent loop, one command
python scripts/race_week7.py --only workflow  # just the fixed workflow, one command
python scripts/race_week7.py --budget-demo    # two clean budget terminations -> docs/week7-budget-termination.log
python scripts/race_week7.py --pace 5         # sleep 5s between LLM calls (Groq free tier)
```

Everything below is produced by that script. Model: `openai/gpt-oss-20b` on Groq, `temperature=0`, `reasoning_effort=low`. Cost uses Groq list price $0.10 / $0.50 per 1M input / output tokens (groq.com/pricing, Feb 2026).

---

## 1. The two systems

|  | Agent loop (`agent/loop.py`) | Fixed workflow (`agent/workflow.py`) |
| --- | --- | --- |
| Control flow | model chooses the next tool every lap until it emits the final JSON | `search_recipes` -&gt; `get_nutrition` -&gt; `substitute_ingredient` per banned ingredient -&gt; 1 render call. Same order every request. |
| LLM calls | 3-7 (one per lap; the whole message list is re-sent each lap) | exactly 1 (render the adapted method) |
| Tools | same three | same three |
| Loop? | yes — `while True` | no — a `for` over the ingredient list, plus a fixed `CASCADE_DEPTH = 3` bound to walk a substitute chain (flour -&gt; almond flour -&gt; oat flour -&gt; rice flour). Not iterate-to-convergence. |
| Output contract | `{recipe, servings, ingredients[], substitutions[], method[]}` | identical |

The workflow's one bounded `for _ in range(CASCADE_DEPTH)` is not a hidden agent loop: its bound is a constant, it makes no model call, and it stops as soon as the substitute is clean. The structure of the run — which tools, in what order — is fixed before any input is seen.

---

## 2. Four numbers per system

One comparable table, same 10 inputs, `openai/gpt-oss-20b` on Groq, latency measured with the rate-limit pacing sleeps excluded:

| metric | agent loop | fixed workflow | ratio |
| --- | --- | --- | --- |
| **pass rate** (10 requests) | **9 / 10 (90%)** | **10 / 10 (100%)** | — |
| **p50 latency** | **7.50 s** | **0.66 s** | 11× |
| **total tokens** (all 10) | **72 759** | **4 201** | 17× |
| **mean cost / request** | **$0.001021** | **$0.000111** | 9× |
| mean LLM calls / request | 5.5 | 1.0 | — |
| mean tool calls / request | 4.5 | **4.8** | — |
| budget terminations | 0 | n/a | — |

Per-request rows: `week7-race.csv`; machine summary: `week7-race-summary.json`.

Note the workflow makes *more* tool calls (4.8 vs 4.5) and still costs 9× less — tool calls are free local Python; it is the LLM laps that cost, and the agent runs 5.5 of them where the workflow runs 1. The cost ratio (9×) is smaller than the token ratio (17×) because the agent's extra tokens are mostly re-sent input (billed at $0.10/M) while the workflow's one call is output-heavy ($0.50/M).

**The agent's one failure —** `r02_p8` (scale to 8, avoid dairy + gluten): it swaps whole milk → oat milk and moves on, even though the tool result flags `cascade=true` because oat milk is gluten. The final list still contains gluten; `allergen_free` fails. It failed this same case on a second run too, and an earlier run also lost `r09_noodle4` (skipped one of three swaps) — so the agent's real pass rate on this task is **80–90%, run to run**, against the workflow's flat 100%. It cleared the other three cascades (`r04`, `r06`, `r07`) — so this is not a capability gap, it is the loop being inconsistent on a shape it demonstrably can do.

**The 10 requests** (4 are cascades — a first-choice substitute is itself banned, so step 3 depends on what step 3 just returned):

| id | recipe | servings | avoid | cascade |
| --- | --- | --- | --- | --- |
| r01_p4 | Classic Pancakes | 4 | dairy |  |
| r02_p8 | Classic Pancakes | 8 | dairy, gluten | ✔ (milk→oat milk→rice milk) |
| r03_mac6 | Weeknight Mac and Cheese | 6 | gluten |  |
| r04_mac4nut | Weeknight Mac and Cheese | 4 | dairy, tree_nut | ✔ (cheddar→cashew cheese→yeast sauce) |
| r05_curry4 | Thai Green Curry | 4 | shellfish |  |
| r06_curry2 | Thai Green Curry | 2 | shellfish, fish | ✔ (shrimp paste→fish sauce→light soy) |
| r07_curry8 | Thai Green Curry | 8 | fish, soy, shellfish | ✔ (depth-3 on two ingredients) |
| r08_bread8 | Banana Bread | 8 | dairy, egg |  |
| r09_noodle4 | Veggie Stir-Fry Noodles | 4 | gluten, soy |  |
| r10_cookie12 | Chocolate Chip Cookies | 12 | dairy |  |

Pass = valid contract JSON, right recipe, `servings` applied, a scalable ingredient actually rescaled, every banned allergen absent from the final ingredient list, every originally-banned ingredient gone, and ≥3 method steps. All deterministic assertions — no LLM judge — so both systems face the same bar (`agent/contract.py` `passes`).

---

## 3. The four budgets, enforced

`agent/budget.py` — `Budget.check` runs at the top of **every** lap and tests all four; the first to trip raises `BudgetExceeded`, which the loop catches, logs, and returns from. It does not loop again.

| budget | default | checked as |
| --- | --- | --- |
| `max_iterations` | 10 | `iteration >= max_iterations` |
| `max_tokens` | 24 000 | cumulative prompt+completion over all laps |
| `max_cost_usd` | 0.020 | cumulative USD over all laps |
| `wall_clock_s` | 90 | `monotonic() - started` (excl. rate-limit pacing sleeps) |

Token/cost are summed **per lap** (`Usage.__add__` in `agent/llm.py`) because Groq re-bills the full, growing message list every lap — counting only the last call would understate the agent by multiples.

### Clean termination log (`--budget-demo`)

Two runs on `r07_curry8` (the deepest cascade), each with one budget starved so a *different* one fires — evidence all four are really checked, not just declared. Full log: `week7-budget-termination.log`.

```
=== expecting max_iterations to fire ===   Budget(max_iterations=3, max_tokens=50000, ...)
{"lap": 1, "tool_calls": ["SearchRecipes"],       "cum_tokens": 908,  "elapsed_s": 0.73}
{"lap": 2, "tool_calls": ["SubstituteIngredient"], "cum_tokens": 2010, "elapsed_s": 1.27}
{"lap": 3, "tool_calls": ["SubstituteIngredient"], "cum_tokens": 3242, "elapsed_s": 1.77}
{"lap": 4, "terminated_by": "max_iterations", "value": 3, "limit": 3}
RESULT: terminated_by='max_iterations'  ok=False  laps=3  tokens=3242  latency_s=1.774

=== expecting max_tokens to fire ===   Budget(max_iterations=20, max_tokens=4000, ...)
{"lap": 1, "tool_calls": ["SearchRecipes"],        "cum_tokens": 803,  "elapsed_s": 0.72}
{"lap": 2, "tool_calls": ["SubstituteIngredient"], "cum_tokens": 1905, "elapsed_s": 1.11}
{"lap": 3, "tool_calls": ["SubstituteIngredient"], "cum_tokens": 3138, "elapsed_s": 1.99}
{"lap": 4, "tool_calls": ["SubstituteIngredient"], "cum_tokens": 4464, "elapsed_s": 2.19}
{"lap": 5, "terminated_by": "max_tokens", "value": 4464, "limit": 4000}
RESULT: terminated_by='max_tokens'  ok=False  laps=4  tokens=4464  latency_s=2.19

Both runs: the loop caught BudgetExceeded, logged the firing budget, and returned
a partial result. It did not iterate again.
```

---

## 4. The third tool — description diff

The two tools that existed before this week are `search_recipes` and `get_nutrition`; the new one is `substitute_ingredient`. All three descriptions were tightened so the model can tell them apart from the text alone (Week 7 common mistake #5 — do not fix tool thrash with the system prompt). The `+`lines below are the live docstrings in `agent/tools.py`; the `-` lines are the vague first drafts they replaced.

```diff
  search_recipes
- "Search the recipe database and return recipe information, including
-  ingredients and other details."
+ "Locate a recipe by a free-text query (dish name, key ingredient, or
+  cuisine) and return its full base record: ingredient list with
+  quantities, method steps, and the allergen classes it contains. Call
+  this ONCE at the start to pull the recipe you will work on; it does no
+  scaling and no substitution. Do not call it again for a recipe you have
+  already fetched."

  get_nutrition
- "Get information about a recipe including its ingredients, servings and
-  nutrition facts."
+ "Scale one already-fetched recipe to a target serving count and return
+  the recomputed ingredient amounts plus a per-serving calorie estimate.
+  Requires an exact recipe name that search_recipes already returned — it
+  does not search, and it does not change any ingredients."
  params: recipe_name: str, servings: int (gt=0)

  substitute_ingredient          # NEW
- "Handle ingredients and allergies for a recipe — adjust ingredients
-  based on dietary needs and preferences."
+ "Swap exactly ONE allergen-bearing ingredient in a recipe for a safe
+  alternative. Returns the single best substitute, its converted amount,
+  and the allergen class the substitute itself carries (which may be
+  another banned class — if so, call this again on the substitute). One
+  swap per call: it does not search, scale, or return the method."
+ params:
+   recipe_name: str
+   ingredient: str
+   avoid_allergen: enum[dairy, egg, gluten, peanut, tree_nut, soy,
+                        shellfish, fish, sesame]
```

What changed and why:

- `search_recipes` **vs** `get_nutrition` **no longer both say "return recipe information".** Each now names its **one** job (locate / scale) and states what it does *not* do and its precondition. That is the overlap the model was tripping on.
- `substitute_ingredient` **went from a vague multi-verb blurb** ("handle", "adjust", "needs and preferences") **to one job** — one swap per call — with the cascade behaviour spelled out and a **typed** `avoid_allergen` **enum** (9 classes) instead of free text, so the model cannot pass `"nuts"` or `"lactose"`.

---

## 5. Verdict

The rule: reach for an agent only when the path varies by input in a way you cannot enumerate. It does not here. All ten requests — plain or cascade — run one shape: `search → scale → substitute each banned ingredient, walking the cascade → render`. Cascade depth varies from one swap to three, but that is bounded, data-driven repetition a `for` loop handles, not an unpredictable branch. The numbers agree: the workflow passed 10/10 to the agent's 9/10 (80–90% run to run), at 1/9 the cost, 1/11 the latency, 1/17 the tokens — while calling tools slightly *more* often. The agent's failure (`r02_p8`) was the loop dropping a substitution it had every tool to make — a failure mode added, not reach. **No request class among the ten needs an agent.** One would: an open-ended "make this dinner-party friendly", where which operations apply is unknown until the model reasons it out.

---

## 6. Reproducing

`python scripts/race_week7.py` regenerates `week7-race.csv`, `week7-race-summary.json` and the summary table; `--budget-demo` regenerates `week7-budget-termination.log`. Both call Groq for real.

Two caveats on the recorded numbers:

- **Groq free-tier limits.** The daily cap is 200 000 tokens and the per-minute cap is \~8 000; one full race is \~77 000 tokens, so two or three back-to-back runs exhaust the day. Use `--pace 8` (or higher) to stay under the minute cap; if you see `429`s, the daily budget is spent — wait for the UTC reset. The recorded run is a clean 10/10 completion with no `429`s.
- **Run-to-run variance.** `temperature=0`, but Groq tool-calling still varies slightly between runs. The agent's pass rate has come in at 80–90% across runs (always losing `r02_p8`, sometimes also `r09_noodle4`); the workflow is flat at 100%. Every other number moves by a few percent; none of the conclusions do.