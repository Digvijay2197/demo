<!-- Soft Suave · Week 11 · prompt version bump + canary/rollback -->
# Prompt version bump: v1 → v3

Every trace records `prompt_version`; the active prompt is chosen by the `PROMPT_VERSION` env var
(`rag/generation/prompt.py`). Default is now **v3**.

| version | what it is | status |
|---|---|---|
| **v1** | the Week-5/6 grounding prompt | before |
| **v2** | v1 + a dietary-restriction rule **in the system prompt** (every query pays for it) | tried, **rejected** (below) |
| **v3** | system prompt **byte-identical to v1** + a short reminder placed **right next to the question**, added **only when the question states a dairy restriction** (`restriction_stated()`) | **shipped** |

**The failure it fixes** — drill trace `tr_6988ef145c4d`: *"I'm dairy-free – can I use the ghee in the chicken biryani"* → *"…you can use either oil or ghee."* Ghee is clarified butter.
**Layer: prompt, not retrieval** — the right chunk (`Chicken_Biryani_Recipe.pdf p.1`, "Oil or ghee – 3 tbsp") *was* retrieved (see `trace.json`); the model read "X or Y" as permission.

The v3 reminder (`DIETARY_REMINDER`, appended to the user message before `Question:`):

> SAFETY NOTE: this person has told you about a dairy restriction (dairy-free, milk allergy, lactose intolerance or vegan). Ghee, butter, buttermilk, milk, cream, yogurt, curd, paneer and cheese ALL contain dairy – ghee is clarified butter. Never call them dairy-free, never offer them, and never say they are fine for this person. If the recipe lists "X or Y" and X is dairy, say to use Y only and that X contains dairy.

## How it got to v3 — three attempts, each judged by the *whole* suite, not just the new case

| attempt | what happened | evidence |
|---|---|---|
| **v2, first draft** (long system rule incl. *"Do not invent a substitute the context does not give"*) | fixed w11-01, w11-02 still failed (the model even asserted *"ghee … is a dairy-free option … contains no milk solids"*), and **e16 regressed to a bare refusal** — a regression the new case alone would never show. e16 passes 5/6 on v1 but **0/6** on this draft: the "do not invent" sentence made the model refuse questions about absent ingredients. | `suite_green_v2-attempt1_gpt-oss-20b.txt` |
| **v2, final** (shorter, scoped to stated restrictions) | e16 fixed, w11-01 9/9, but **w11-02 still 7/9** — on this model a system-prompt rule alone is not strong enough. Also costs +114 tokens on *every* query. | `suite_partial_v2-final_gpt-oss-20b.txt` |
| **v3** | The instruction moves next to the question, and only fires for restricted questions → no behaviour change at all for the other 90%+ of queries (so no e16-style collateral), and ~free on average. | `suite_green.txt` |

Aggregate on the production model (gpt-oss-20b), every dietary-restriction answer I collected, scored by the same `dairy_free_violation` function that writes the log flag:

| prompt | answers to restricted questions | endorsed a dairy ingredient |
|---|---|---|
| v1 | 35 | **12** (34%) |
| v2 | 15 | **6** (40%) |
| **v3** | see `suite_green.txt` + `RESULTS` in the README | **0** |

(Those questions are deliberately adversarial — each asks about ghee in a recipe that lists "oil or ghee" — so 34% is not a production rate.)

## Canary and rollback (two lines)

- **Canary:** serve v3 to 10% of users (`hash(user_id) % 10 == 0`) for 24 h; promote only if, on that slice, `w11_logsearch.py --flag dairy_free_violation` returns 0 over ≥ 200 `dietary_restriction` queries *and* bare-refusal rate and cost/query stay within +15% of v1 in the same logs (compare by `prompt_version`).
- **Rollback:** set `PROMPT_VERSION=v1` and restart — no code deploy, and traces keep labelling which version answered; trigger on any `dairy_free_violation=true` in the canary, a refusal-rate rise > 5 pts, or p95 latency > +20%.

*(The 10% split is the plan; this repo implements the version switch and per-trace labelling, not the traffic splitter. The unit test `test_restriction_detector_and_v3_reminder_only_for_restricted_questions` proves `PROMPT_VERSION=v1` removes the reminder, i.e. rollback really is an env flip.)*

## Known limits of the fix (be honest about them)

- It is keyed on a **regex** (`restriction_stated`): "I'm dairy-free", "milk allergy", "lactose", "can't have dairy", "vegan". A user who writes *"I avoid anything from cows"* would not trigger it. Cheap and testable, not complete.
- It covers **dairy** only. Gluten, nut and egg restrictions have the same trap and no reminder yet (the eval suite has no case for them either).
- It does not make the model *right* — it makes the failure rarer and, via the log flag, *findable*. The log flag is the safety net; the prompt is the first line.
