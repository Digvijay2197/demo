# Bonus — allergen safety through the substitution chain

**Claim to test:** the allergen check must run on the recipe *as substituted*, not as published.

## The mechanism (code, all deterministic)

- `domain.lookup_substitution(ingredient, avoid)` — the test-kitchen table. Several safe-looking options carry an
  allergen of their own (`whole milk → almond milk` = tree_nut, `butter → almond-oil vegan butter`, `peanut butter → almond butter`, …).
- **Plain (pre-bonus) mode** — `CAPSTONE_SUBSTITUTION=plain`: a bare table lookup; the only allergen check is
  `check_allergens` on the *published* recipe; the MCP server does not even expose `check_substituted_recipe`
  (the agent discovers the smaller tool list at runtime).
- **Checked mode** — options clashing with the user's allergens are filtered out, the tool
  `check_substituted_recipe(recipe_id, swaps, avoid)` recomputes the allergen union after the swap, and the
  post-answer guard re-runs the same recomputation on every substitute that appears in the answer.

## The case that goes red, then green

`tests/test_capstone.py::test_nut_free_recipe_becomes_unsafe_after_the_systems_own_swap`:
Overnight Oats `R-217` is **declared nut-free** (`check_allergens(..., ["nuts"]) → no_declared_conflict`). The
plain lookup's *first* option for `whole milk` is `almond milk`. Check as published → "safe". Check as substituted →
`introduced_by_swap: ["tree_nut"]`, `safe_as_substituted: false`. Eval cases: `c21` (toddler allergic to nuts, pantry
has almond milk), `c22`, `c23` (vegan butter made of almond oil), `c26`.

## Numbers

See [`eval_report.md`](eval_report.md) §"Before → after" and [`closed_loop.md`](closed_loop.md) for the measured
count of pantry cases that pass the old (published-recipe) check but fail the substituted-recipe check.
