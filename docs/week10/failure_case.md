<!-- Soft Suave · The AI Engineering League -->
# Week 10 — failure_case.md

**Case:** `r05_curry4` — "thai green curry" -> 4 servings, avoid `['shellfish']`
**Injected failure:** the nutrition/allergen worker's `GetNutrition` tool call
returns a simulated HTTP 500 on every attempt (persistent, not transient —
the injection does not clear on retry). Captured live against Groq
(`openai/gpt-oss-20b`) via `run_orchestrator(req, inject_failure={"tool":
"GetNutrition", "status": 500})`.

## What the orchestrator actually did

- **Retried: true** — one full re-run of the nutrition/allergen worker from a
  fresh message history. Its own first `SearchRecipes` call succeeded again;
  `GetNutrition` failed again, identically to the first attempt (the
  injection is persistent by design, so a retry cannot out-wait it).
- **Behaviour after the retry also failed: DEGRADED to a partial answer.** It
  did not call the substitution worker on unconfirmed data, and it did not
  synthesize an allergen-free claim the failed worker never made. It fell
  back to the *unscaled base recipe* (a plain dict lookup in
  `agent/recipes.py`, no LLM call at all) with `"degraded": true` and the
  real error attached in `"degraded_reason"`.
- **It did not lie.** `output.substitutions` is `[]` — nothing claims
  shellfish was ever removed. `shrimp paste` (the request's one banned
  ingredient) is honestly still sitting in the returned ingredient list,
  unsubstituted.

Full recorded failure note:
```json
{
  "worker": "nutrition_allergen",
  "tool": "GetNutrition",
  "status_code": 500,
  "retried": true,
  "behavior": "retried_then_degraded_partial_answer",
  "detail": "GetNutrition failed: simulated upstream HTTP 500 (injected for Week 10 demo)"
}
```

Tokens spent on the failed hand-off before giving up: **2,984** (2,792 prompt
+ 192 completion), across 4 laps and 2 real tool calls — one failed attempt
plus one failed retry, both counted. A failed hand-off is not free.

Deterministic judge (`agent/contract.py` `passes()`) on the degraded output:
`{"is_object": true, "right_recipe": true, "servings_set": true,
"has_ingredients": true, "has_method": true, "allergen_free": false,
"originals_removed": false, "scaled": true}` — fails `allergen_free` and
`originals_removed`, exactly as it should for an answer that is honestly
incomplete rather than falsely clean. (`servings_set` and `scaled` pass only
because this recipe's base serving count already equals the requested
count — 4 — so "never scaled" happens to look identical to "scaled
correctly" here; that coincidence does not change that the allergen was
never removed.)
