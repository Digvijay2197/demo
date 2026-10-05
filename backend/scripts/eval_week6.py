"""Week 6: a one-command eval set for the Recipe RAG bot.

    python scripts/eval_week6.py                 # assertion checks + substitution judge, all cases
    python scripts/eval_week6.py --validate-judge # check the judge against hand grades first
    python scripts/eval_week6.py --tag before     # also write docs/week6-run-before.json

Cases come from the Week 5 traces (real failures made permanent). Cheap
assertion checks run first (source present? refused when it should? citation
resolves? expected fact in the answer?). The "substitution judge" - an LLM
grading how helpful+grounded a modification answer is - runs only for the
substitution slice, and only after --validate-judge shows it agrees with a
human.
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

# Week 11: eval/traces from this suite go to their own log, not the prod one.
os.environ.setdefault("TRACE_LOG_PATH", os.path.join(os.getcwd(), "logs", "eval_traces.jsonl"))

from eval.dairy_check import dairy_free_violation, mentions_dairy_awareness
from rag.citations.citations import resolve_citation
from rag.generation.answer_service import answer_question
from rag.generation.groq_service import _get_llm

DOCS = os.path.abspath(os.path.join(os.getcwd(), "..", "docs"))

# id, question, category, expect_refused, keywords (any-of must appear), expect_page
CASES = [
    ("e01", "how much fine sea salt is in the classic sauerkraut", "lookup", False, ["20 g"], None),
    ("e02", "how long does the classic sauerkraut ferment", "lookup", False, ["2 to 4 weeks"], None),
    ("e03", "how much starter tea goes into the ginger kombucha", "lookup", False, ["400 g"], None),
    ("e04", "does the soybean tempeh contain soy", "lookup", False, ["soy"], None),
    ("e05", "give me the recipe for Oatmeal Bread", "full_recipe", False, ["dark molasses"], 5),
    ("e06", "Szechuan Pork recipe", "full_recipe", False, ["water chestnuts"], 55),
    ("e07", "Boiled Cake recipe", "full_recipe", False, ["raisins"], 69),
    ("e08", "how long do I bake Pecan Fingers and at what temperature", "duplicate_name", False,
     ["400", "300"], 80),
    ("e09", "total cooking time for the chicken biryani", "numeric", False, ["70"], None),
    ("e10", "what is the calorie count per serving of the German Chocolate Cake", "refuse", True, [], None),
    ("e11", "which wine should I pair with the napa cabbage kimchi", "refuse", True, [], None),
    ("e12", "how do I make a chocolate lava cake", "refuse", True, [], None),
    ("e13", "what can I use instead of buttermilk in the Classic Carrot Cake", "substitution", False, [], None),
    ("e14", "can I make the chicken biryani vegetarian", "substitution", False, [], None),
    ("e15", "the Boiled Cake calls for lard - what else can I use", "substitution", False, ["oil"], None),
    ("e16", "how much sugar is in the 2 kg sourdough", "substitution", False, [], None),
]

# Week 11: failures from the support drill, kept as data in eval/ so a new case
# is a JSON edit. Each becomes a 7th tuple element: extra checks to run.
W11_FILE = os.path.join(os.getcwd(), "eval", "w11_dairy_free_cases.json")
if os.path.exists(W11_FILE):
    with open(W11_FILE, encoding="utf-8") as _f:
        for _c in json.load(_f)["cases"]:
            CASES.append((_c["id"], _c["question"], _c["category"], _c["expect_refused"],
                          _c["keywords"], _c["expect_page"], _c.get("extra", {})))

JUDGE_SYSTEM = """You grade a recipe assistant's answer to a MODIFICATION question
(substitute an ingredient, make it vegetarian, scale it, or "how much X" when X
is not in the recipe). Score 1-5 for helpful AND grounded:

5 = gives the recipe's own substitution, OR clearly explains what the recipe uses
    for that role / that the ingredient is simply absent - all from the context.
3 = partially useful: names the ingredient but stops there, or hedges a lot.
1 = a bare refusal ("I couldn't find enough information..."), OR invents a
    substitution or fact that is not in the provided context.

Reply as JSON: {"score": <1-5>, "reason": "<one sentence>"}"""

# Hand grades for judge validation (graded by a human before trusting the judge).
JUDGE_VALIDATION = [
    {"q": "what can I use instead of buttermilk in the Classic Carrot Cake",
     "a": "The Classic Carrot Cake recipe does not provide an alternative for buttermilk.",
     "human": 2},
    {"q": "can I make the chicken biryani vegetarian",
     "a": "I couldn't find enough information in the provided recipes to answer that question.",
     "human": 1},
    {"q": "the Boiled Cake calls for lard - what else can I use",
     "a": "The recipe notes that you can substitute lard with vegetable oil.",
     "human": 5},
    {"q": "how much sugar is in the 2 kg sourdough",
     "a": "I couldn't find enough information in the provided recipes to answer that question.",
     "human": 1},
    {"q": "what can I use instead of buttermilk in the Classic Carrot Cake",
     "a": "The carrot cake's liquids are buttermilk, applesauce and honey; the recipe gives no buttermilk substitute.",
     "human": 4},
    {"q": "can I make the chicken biryani vegetarian",
     "a": "The recipe as written uses 500 g chicken and 1/2 cup yogurt and gives no vegetarian version; you would need to replace the chicken yourself.",
     "human": 4},
    {"q": "how much sugar is in the 2 kg sourdough",
     "a": "This sourdough contains no sugar - its ingredients are bread flour, water, active levain and fine sea salt.",
     "human": 5},
    {"q": "can I halve the sauerkraut recipe",
     "a": "Sure, halve everything: 500 g cabbage, 10 g fine sea salt, 2 g caraway seeds.",
     "human": 5},
    {"q": "what can I use instead of buttermilk in the Classic Carrot Cake",
     "a": "Use almond milk with a tablespoon of lemon juice as a buttermilk substitute.",
     "human": 1},  # invented - not in context
    {"q": "can I make the chicken biryani vegetarian",
     "a": "Yes! Just swap the chicken for paneer and add extra vegetables, and use vegetable stock.",
     "human": 2},  # partly invented specifics
]


def _judge(question: str, answer: str) -> dict:
    msg = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nAssistant answer: {answer}"},
    ]
    raw = _get_llm().invoke(msg).content or ""
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception:  # noqa: BLE001
        return {"score": None, "reason": f"unparseable: {raw[:80]}"}


def _patient(fn, wait_s: int = 150, max_wait_s: int = 6 * 3600):
    """Wrap an LLM-calling fn: on rate-limit, sleep and retry (failed calls cost 0 tokens)."""
    def wrapped(*a, **kw):
        waited = 0
        while True:
            try:
                return fn(*a, **kw)
            except Exception as exc:  # noqa: BLE001
                msg = (str(exc) + str(exc.__cause__ or "")).lower()
                if ("rate" in msg or "429" in msg) and waited < max_wait_s:
                    print(f"  [patient] rate-limited, sleeping {wait_s}s (waited {waited}s)", flush=True)
                    time.sleep(wait_s)
                    waited += wait_s
                    continue
                raise
    return wrapped


def validate_judge() -> None:
    print("Judge validation (human vs judge, 1-5):\n")
    diffs, agree1 = [], 0
    for row in JUDGE_VALIDATION:
        j = _judge(row["q"], row["a"])
        s = j.get("score")
        d = abs(s - row["human"]) if isinstance(s, int) else None
        if d is not None:
            diffs.append(d)
            agree1 += d <= 1
        print(f"  human={row['human']}  judge={s}  |Δ|={d}  {row['q'][:45]}")
        time.sleep(2)
    n = len(diffs)
    print(f"\n  within +/-1 point: {agree1}/{n} ({100*agree1/n:.0f}%)   mean |Δ| = {statistics.mean(diffs):.2f}")
    print("  -> trust the judge" if agree1 / n >= 0.8 else "  -> DO NOT trust the judge yet")


def run_case(case) -> dict:
    """Run a case once - or `extra.repeat` times, passing only if EVERY run passes
    (the model is non-deterministic even at temperature 0, so a lucky single
    pass must not hide a real failure)."""
    extra = case[6] if len(case) > 6 else {}
    n = int(extra.get("repeat", 1))
    first = _run_once(case)
    if n == 1:
        return first
    merged, worst = dict(first["checks"]), first
    for _ in range(n - 1):
        time.sleep(2)
        nxt = _run_once(case)
        for k, v in nxt["checks"].items():
            merged[k] = merged.get(k, True) and v
        if not all(nxt["checks"].values()) and all(worst["checks"].values()):
            worst = nxt
    worst = dict(worst)
    worst["checks"] = merged
    worst["repeats"] = n
    return worst


def _run_once(case) -> dict:
    cid, q, cat, exp_ref, keywords, exp_page, *rest = case
    extra = rest[0] if rest else {}
    try:
        res = answer_question(q, user_id="eval")
        err = None
    except Exception as exc:  # noqa: BLE001
        return {"id": cid, "category": cat, "question": q, "error": repr(exc),
                "checks": {"no_error": False}}

    ans, refused, cites = res["answer"], res["refused"], res["citations"]
    checks = {
        "no_error": True,
        "refused_as_expected": (refused == exp_ref),
        "source_present": refused or len(cites) >= 1,
        "citation_resolves": refused or all(resolve_citation(c["chunk_id"]) for c in cites),
        "keyword_present": (not keywords) or any(k.lower() in ans.lower() for k in keywords),
        "right_page": (exp_page is None) or any(c.get("page") == exp_page for c in cites),
        "not_bare_refusal": exp_ref or not ans.startswith("I couldn't find enough information"),
    }
    if extra.get("no_dairy_endorsement"):
        checks["no_dairy_endorsement"] = not dairy_free_violation(ans)
    if extra.get("flags_dairy"):
        checks["flags_dairy"] = mentions_dairy_awareness(ans)
    return {"id": cid, "category": cat, "question": q, "answer": ans,
            "refused": refused, "citations": cites, "checks": checks, "error": err}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate-judge", action="store_true")
    ap.add_argument("--tag", help="also write docs/week6-run-<tag>.json")
    ap.add_argument("--first", help="comma-separated case ids to run first (e.g. w11-01,w11-02); "
                                    "the full suite still runs - this only changes the order")
    ap.add_argument("--patient", action="store_true",
                    help="on a Groq 429 (e.g. daily token cap) sleep and retry instead of failing the case")
    args = ap.parse_args()
    if args.patient:
        g = globals()
        g["answer_question"] = _patient(answer_question)
        g["_judge"] = _patient(_judge)

    if args.validate_judge:
        validate_judge()
        return

    results = []
    cases = list(CASES)
    if args.first:
        front = args.first.split(",")
        cases.sort(key=lambda c: (front.index(c[0]) if c[0] in front else len(front)))
    for case in cases:
        r = run_case(case)
        results.append(r)
        passed = sum(r["checks"].values())
        total = len(r["checks"])
        print(f"{r['id']}  {r['category']:14s}  {passed}/{total}  {r['question'][:50]}")
        time.sleep(2)

    # suite-level pass count: a case passes only if EVERY one of its checks passes
    passed_cases = [r["id"] for r in results if all(r["checks"].values())]
    failed_cases = [r["id"] for r in results if not all(r["checks"].values())]
    print(f"\nSUITE: {len(passed_cases)}/{len(results)} cases pass"
          + (f"   FAILED: {', '.join(failed_cases)}" if failed_cases else ""))
    for r in results:
        bad = [k for k, v in r["checks"].items() if not v]
        if bad:
            print(f"  FAIL {r['id']}  failing checks: {', '.join(bad)}\n       A: {r.get('answer','')[:200]!r}")

    # assertion summary by category
    print("\nassertion pass rate by category:")
    cats = sorted({r["category"] for r in results})
    for c in cats:
        rs = [r for r in results if r["category"] == c]
        p = sum(sum(r["checks"].values()) for r in rs)
        t = sum(len(r["checks"]) for r in rs)
        print(f"  {c:14s}  {p}/{t}  ({100*p/t:.0f}%)")

    # substitution judge (only if you have already validated it)
    subs = [r for r in results if r["category"] == "substitution" and not r.get("error")]
    print("\nsubstitution judge (1-5):")
    scores = []
    for r in subs:
        j = _judge(r["question"], r["answer"])
        r["judge"] = j
        scores.append(j.get("score"))
        print(f"  {r['id']}  score={j.get('score')}  {j.get('reason','')[:70]}")
        time.sleep(2)
    numeric = [s for s in scores if isinstance(s, int)]
    if numeric:
        print(f"  substitution slice mean = {statistics.mean(numeric):.2f} / 5   "
              f"(bare refusals: {sum(1 for r in subs if r['answer'].startswith('I couldn'))})")

    if args.tag:
        os.makedirs(DOCS, exist_ok=True)
        path = os.path.join(DOCS, f"week6-run-{args.tag}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
