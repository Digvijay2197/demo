<!-- Soft Suave · Week 5 · Module 3 — Error Analysis. Track B: Recipes & food -->
# Week 5 — Error Analysis: reading 22 traces of the Recipe RAG bot

**Deliverable:** ~20 real traces read, one honest note per trace, grouped into
named problem types, ranked by frequency × severity, with one chosen fix target
and a written prediction.

**System under test:** the Recipe RAG chatbot (LangChain + ChromaDB + Groq
`openai/gpt-oss-20b`), corpus = a 120-page multi-recipe cookbook PDF (*Nelson
Family Recipe Book*), a single-recipe biryani PDF, and 6 fermentation recipe
PDFs. Retrieval: cosine top-4, refuse below similarity 0.22.

---

## 1. Method

- **Trace = question + what was retrieved (top-4 chunks, scores, snippets) + the
  answer + refused flag.** Enough to replay any answer later.
- 22 questions were written to span the real usage mix — simple lookups, recipes
  that share a page, substitution / modification asks, cross-recipe comparisons,
  a typo-heavy query, a vague "list everything" ask, and questions the corpus
  genuinely cannot answer — **not** cherry-picked nice cases.
- Collected with one command: `python scripts/collect_traces.py` →
  [`week5-traces.jsonl`](week5-traces.jsonl) (full retrieved text + answers).
- Each trace was then read once and given **one honest sentence** about what went
  wrong, *before* any categories were decided (open coding).

---

## 2. The 22 traces — open-coded notes

`ok` = correct and grounded · `weak` = answers but unhelpfully / incompletely ·
`refuse` = returned the refusal sentence.

| # | Question | Outcome | Honest one-line note |
|---|---|---|---|
| t01 | how much fine sea salt is in the classic sauerkraut | ok | Correct ("20 g") but the answer is a bare fragment `Fine sea salt: 20 g`, not a sentence. |
| t02 | give me the recipe for Oatmeal Bread | ok | Full correct recipe, cited p.5; "Oatmeal Cake" and "Oatmeal Buns" ranked close behind but top-1 was right. |
| t03 | how do I make lefse | weak | Correct for *one* lefse, but there are two ("Lefse" p95, "Old Norwegian Lefse" p94) and it never says so. |
| t04 | Boiled Cake recipe | ok | Right recipe (not the neighbouring "Minnie's Boiled Spice Cake"); even reconstructed the frosting from prose. |
| t05 | how long do I bake Pecan Fingers and at what temperature | ok | Handled **both** versions on the page ("400°F 10-12 min" / "300°F 20 min"). |
| t06 | what can I use instead of buttermilk in the Classic Carrot Cake | weak | Grounded but a flat non-answer: "the recipe does not provide an alternative." No use of what the recipe *does* say. |
| t07 | can I make the chicken biryani vegetarian | refuse | Biryani chunk retrieved at 0.64, but the model refused instead of saying "as written it uses 500 g chicken + yogurt, no veg version given". |
| t08 | the Boiled Cake calls for lard - what else can I use | ok | Correct — used the recipe's own parenthetical "(I use vegetable oil)". |
| t09 | what is the calorie count per serving of the German Chocolate Cake | refuse | Correct refusal — no nutrition data for that recipe. |
| t10 | which wine should I pair with the napa cabbage kimchi | refuse | Correct refusal — no pairing info anywhere in the corpus. |
| t11 | which has more salt, the sauerkraut or the kimchi | ok | Both quantities quoted and cited; minor — doesn't note kimchi's salt is a brine that gets rinsed. |
| t12 | what recipes do you have | weak | **Broken.** Retrieved the book's Index pages (117-118); output is a garbled list where every item shows "(p.117)". |
| t13 | hw mch chikn in teh biryani | ok | Right answer ("500 g") but top retrieval score only **0.394** — barely above the 0.22 refuse line; fragile. |
| t14 | how long do I bake it | weak | "it" has no referent; answered confidently from the sourdough recipe (an arbitrary pick), no clarification. |
| t15 | Szechuan Pork recipe | ok | Full correct recipe, cited p.55. |
| t16 | how much sugar is in the 2 kg sourdough | refuse | The recipe has no sugar, so a bare refusal — reads as "retrieval failed" when the honest answer is "there is no sugar in it". |
| t17 | how long does the classic sauerkraut ferment | ok | Correct ("2 to 4 weeks"). |
| t18 | does the soybean tempeh contain soy | ok | Correct ("Yes… Dehulled soybeans 500 g"). |
| t19 | how do I make a chocolate lava cake | refuse | Correct refusal — retrieved German Chocolate Cake (0.62) but did not substitute a different recipe. |
| t20 | what temperature and how long for the Classic Carrot Cake | ok | Correct ("350°F for 30-35 minutes"). |
| t21 | how much starter tea goes into the ginger kombucha | ok | Correct ("400 g"). |
| t22 | total cooking time for the chicken biryani | ok | Correct arithmetic from stated values ("25 + 45 = 70 minutes"). |

**Tally:** 13 `ok`, 5 `weak`, 4 `refuse` (3 correct refusals + 1 that should not have refused, t07).
Net: **9 / 22 traces show a problem** (t01, t03, t06, t07, t11, t12, t13, t14, t16).

---

## 3. Named problem types

| Code | Name | What it is | Traces |
|---|---|---|---|
| **P1** | **Modification questions decline instead of answering from context** | Substitution / "make it vegetarian" / "how much X" when X is absent → a bare refusal or a flat "not provided", even though the recipe was retrieved. | t06, t07, t16 |
| **P2** | **"List all recipes" retrieves the index page** | Browse / overview questions pull the book's alphabetical Index (flat "name … page-number" text) and the model emits a mangled list with every page shown as 117. | t12 |
| **P3** | **Ambiguous-referent question answered with a confident guess** | "bake *it*", implicit recipe → answers from whatever chunk ranked top, no "which recipe?". | t14 |
| **P4** | **Typos push retrieval to the edge of the refuse threshold** | Heavy misspelling drops the top score from ~0.7 to ~0.39 (vs 0.22 cutoff); one notch worse would be a false refusal. | t13 |
| **P5** | **Duplicate-name recipes: one answered, the other ignored** | Two "Lefse" recipes; the bot answers from one and never mentions the second. (Note: t05 handled this well for "Pecan Fingers" — behaviour is inconsistent.) | t03 |
| **P6** | **Fragment-style answers** | Copies a table cell (`Fine sea salt: 20 g`) instead of writing a sentence. Cosmetic. | t01 |
| **P7** | **Comparison lacks context nuance** | Quotes stated quantities correctly but ignores that one is a rinsed brine. Minor correctness. | t11 |

---

## 4. Ranked taxonomy (frequency × severity)

Severity: **High** = wrong/unhelpful on a common ask; **Med** = degraded or fragile;
**Low** = cosmetic.

| Rank | Problem | Frequency | Severity | Why it ranks here |
|---:|---|---|---|---|
| 1 | **P1 — modification questions decline** | 3 / 22 (14%) | High | Most frequent real defect; "can I substitute…" is a top-3 user intent; it's the Week 6 Track-B judge axis. |
| 2 | **P2 — "list all recipes" → index garbage** | 1 / 22 | High | Extremely common *first* question; the output looks broken, not just unhelpful. |
| 3 | **P3 — ambiguous question, confident guess** | 1 / 22 | Med-High | Produces a wrong recipe stated with full confidence — worse than refusing. |
| 4 | **P4 — typos near the refuse threshold** | 1 / 22 | Med | Latent false-refusal risk; not yet a failure but one nudge away. |
| 5 | **P5 — duplicate-name recipes** | 1 / 22 | Med | Incomplete answer; inconsistent with t05. |
| 6 | **P6 — fragment answers** | 1 / 22 | Low | Cosmetic. |
| 7 | **P7 — comparison nuance** | 1 / 22 | Low | Edge correctness. |

---

## 5. Chosen fix target + written prediction

**Target: P1 — modification questions decline instead of answering from context.**
Highest frequency, high severity, and it is exactly the axis Week 6's *substitution
judge* measures — so fixing it here gives Week 6 a real before/after to report.

**The one change:** add a rule to the grounding prompt — *for a modification
question (substitute / vegetarian / scale / "how much X" when X is absent), do
not refuse if a retrieved recipe is about that dish; instead give the recipe's
own noted swap, or name what the recipe uses for that role, or state that the
ingredient is simply absent; never invent a substitute or amount; refuse only
when no retrieved recipe matches the dish.*

**Prediction (written before running Week 6's after-measurement):**

1. t07 ("vegetarian biryani") and t16 ("sugar in sourdough") flip from **refuse**
   → a grounded, helpful answer. Bare refusals on the substitution slice: 2 → 0.
2. t06 ("buttermilk substitute") goes from a flat "not provided" to naming the
   recipe's liquids and stating no substitute is given — partially better, not
   perfect (we still can't invent the common swap).
3. On a 4-question substitution eval slice, the LLM substitution-judge mean rises
   from roughly **2 / 5** to roughly **4 / 5**.
4. Risk: over-helpfulness could make the bot answer out-of-corpus modification
   asks ("make this keto"). Mitigation: the "refuse only when no retrieved recipe
   matches the dish" clause plus the existing nutrition/pairing refusal rule.
5. The other problems (P2–P7) are explicitly **not** addressed by this change —
   Week 6 must show they did not move.

The measured result is in [`week6-evals.md`](week6-evals.md) §5.
