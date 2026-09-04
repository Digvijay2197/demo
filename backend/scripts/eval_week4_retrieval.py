"""Week 4: debug retrieval on the Recipe RAG bot.

    python scripts/eval_week4_retrieval.py               # inspection view + before/after hit-rate@3
    python scripts/eval_week4_retrieval.py --tag before  # also writes docs/week4-retrieval-before.json
    python scripts/eval_week4_retrieval.py --tag after

For each question: retrieve top-3 twice (semantic-only, then hybrid
BM25+semantic via RRF) and run the full answer through the live pipeline both
ways. Labels every semantic-only failure as either "wrong document fetched"
(the expected source never made top-3) or "right document, wrong answer" (it
did, but the answer is still wrong) - the two kinds of retrieval-adjacent
failure this week is about telling apart. Then reports hit-rate@3 before vs.
after the one change (hybrid search), and which failures it did and didn't fix.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from rag.generation.answer_service import answer_question
from rag.retrieval.retriever import retrieve

DOCS = os.path.abspath(os.path.join(os.getcwd(), "..", "docs"))

# id, question, expected source file(s) (any one counts as a hit),
# category, keyword(s) a correct answer must contain (any-of)
CASES = [
    # --- exact code: a bare/near-bare code query. With 20 similarly-worded
    # recipes in the corpus, MiniLM's embedding of a short out-of-vocabulary
    # alphanumeric code doesn't align with the doc that contains it - this is
    # the textbook case hybrid/BM25 exists for (see week4-debugging-retrieval.md) ---
    ("r01", "SD-2041",
     ["sourdough-loaf-batch-sd-2041.pdf"], "exact_code", ["75", "SD-2041"]),
    ("r02", "hydration percentage SD-2041",
     ["sourdough-loaf-batch-sd-2041.pdf"], "exact_code", ["75"]),
    ("r03", "REC-118",
     ["pantry-chili-con-carne-rec-118.pdf"], "exact_code", ["beef", "chili", "chilli"]),
    ("r03b", "what temperature does REC-118 recommend",
     ["pantry-chili-con-carne-rec-118.pdf"], "exact_code", ["beef"]),
    ("r04", "how much gochugaru goes in the kimchi fried rice",
     ["kimchi-fried-rice-gochugaru.pdf"], "rare_ingredient", ["2 tablespoons"]),
    ("r05", "can I use cayenne instead of gochugaru",
     ["kimchi-fried-rice-gochugaru.pdf"], "rare_ingredient", ["half"]),
    ("r06", "how much mirin is in the miso glazed salmon",
     ["miso-glazed-salmon.pdf"], "rare_ingredient", ["2 tablespoons"]),
    ("r07", "what's the difference between shiro miso and red miso in the salmon recipe",
     ["miso-glazed-salmon.pdf"], "rare_ingredient", ["two-thirds", "milder", "sweeter"]),

    # --- duplicate name: the right doc(s) should be retrievable either way;
    #     this is the "right document, wrong answer" axis, not retrieval ---
    ("r08", "how long should the dough chill for Old Norwegian Lefse before rolling",
     ["old-norwegian-lefse.pdf"], "duplicate_name", ["overnight"]),
    ("r09", "what griddle temperature does Classic Lefse cook at",
     ["classic-lefse.pdf"], "duplicate_name", ["450"]),

    # --- controls: plain semantic queries that should already work well,
    #     to check the change doesn't regress the easy cases ---
    ("r10", "pizza dough hydration percentage",
     ["neapolitan-margherita-pizza.pdf"], "control", ["65"]),
    ("r11", "what's in the thai green curry paste and how spicy is it",
     ["thai-green-chicken-curry.pdf"], "control", ["curry paste"]),
    ("r12", "vegetarian version of the pantry chili",
     ["pantry-chili-con-carne-rec-118.pdf"], "control", ["beans"]),
    ("r13", "honey oat bread baking temperature",
     ["honey-oat-sandwich-bread.pdf"], "control", ["190"]),
    ("r14", "a simple everyday bread recipe that needs no starter",
     ["rustic-country-bread.pdf"], "control", ["starter"]),
]


def _hit_at_k(results, expected_sources, k=3):
    top = {d.metadata.get("source_file") for d, _ in results[:k]}
    return any(s in top for s in expected_sources)


def run_case(case, hybrid: bool) -> dict:
    cid, q, expected, cat, keywords = case
    retrieved = retrieve(q, top_k=3, hybrid=hybrid)
    hit = _hit_at_k(retrieved, expected)
    try:
        res = answer_question(q, hybrid=hybrid)
        error = None
    except Exception as exc:  # noqa: BLE001
        res = {"answer": "", "citations": [], "refused": None}
        error = repr(exc)

    ans = res["answer"]
    keyword_ok = (not keywords) or any(k.lower() in ans.lower() for k in keywords)
    correct = hit and keyword_ok and not res["refused"] and error is None
    return {
        "id": cid, "question": q, "category": cat, "expected": expected,
        "retrieved": [
            {"source_file": d.metadata.get("source_file"), "page": d.metadata.get("page"), "score": round(s, 4)}
            for d, s in retrieved
        ],
        "hit_at_3": hit, "answer": ans, "refused": res["refused"],
        "keyword_ok": keyword_ok, "correct": correct, "error": error,
    }


def label(before_row: dict) -> str:
    if before_row["correct"]:
        return "pass"
    if not before_row["hit_at_3"]:
        return "wrong document fetched"
    return "right document, wrong answer"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="also write docs/week4-retrieval-<tag>.json")
    args = ap.parse_args()

    before_rows, after_rows = [], []
    for case in CASES:
        b = run_case(case, hybrid=False)
        time.sleep(2)
        a = run_case(case, hybrid=True)
        time.sleep(2)
        before_rows.append(b)
        after_rows.append(a)
        lbl = label(b)
        print(f"{b['id']}  before_hit={str(b['hit_at_3']):5}  after_hit={str(a['hit_at_3']):5}  "
              f"label={lbl:26}  {b['question'][:55]}")

    before_hr = sum(r["hit_at_3"] for r in before_rows) / len(before_rows)
    after_hr = sum(r["hit_at_3"] for r in after_rows) / len(after_rows)
    print(f"\nhit-rate@3  BEFORE (semantic only) = {before_hr:.0%}   "
          f"AFTER (hybrid BM25 + semantic, RRF) = {after_hr:.0%}")

    print("\nsemantic-only failures, and what the hybrid change did to each:")
    any_failure = False
    for b, a in zip(before_rows, after_rows):
        if b["correct"]:
            continue
        any_failure = True
        lbl = label(b)
        if a["hit_at_3"] and not b["hit_at_3"]:
            outcome = "FIXED (now retrieved)"
        elif a["correct"]:
            outcome = "now correct"
        else:
            outcome = "still wrong - unaddressed"
        print(f"  {b['id']}  [{lbl}]  {outcome}  {b['question'][:55]}")
    if not any_failure:
        print("  (none)")

    if args.tag:
        os.makedirs(DOCS, exist_ok=True)
        path = os.path.join(DOCS, f"week4-retrieval-{args.tag}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"before": before_rows, "after": after_rows}, f, ensure_ascii=False, indent=2)
        print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
