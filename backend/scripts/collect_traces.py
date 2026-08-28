"""Week 5 helper: run a batch of questions through the live RAG pipeline and
record a complete trace for each (question -> what was retrieved -> the answer).

    python scripts/collect_traces.py            # uses the built-in question set
    python scripts/collect_traces.py q.txt      # one question per line

Writes docs/week5-traces.jsonl (one JSON object per line) and prints a summary.
A trace is enough to replay any answer later.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from rag.generation.answer_service import answer_question
from rag.retrieval.retriever import retrieve

OUT = os.path.abspath(os.path.join(os.getcwd(), "..", "docs", "week5-traces.jsonl"))

# A fair spread: simple lookups, multi-recipe pages, substitutions, comparisons,
# typos, vague asks, and things the corpus genuinely cannot answer.
QUESTIONS = [
    "how much fine sea salt is in the classic sauerkraut",
    "give me the recipe for Oatmeal Bread",
    "how do I make lefse",
    "Boiled Cake recipe",
    "how long do I bake Pecan Fingers and at what temperature",
    "what can I use instead of buttermilk in the Classic Carrot Cake",
    "can I make the chicken biryani vegetarian",
    "the Boiled Cake calls for lard - what else can I use",
    "what is the calorie count per serving of the German Chocolate Cake",
    "which wine should I pair with the napa cabbage kimchi",
    "which has more salt, the sauerkraut or the kimchi",
    "what recipes do you have",
    "hw mch chikn in teh biryani",
    "how long do I bake it",
    "Szechuan Pork recipe",
    "how much sugar is in the 2 kg sourdough",
    "how long does the classic sauerkraut ferment",
    "does the soybean tempeh contain soy",
    "how do I make a chocolate lava cake",
    "what temperature and how long for the Classic Carrot Cake",
    "how much starter tea goes into the ginger kombucha",
    "total cooking time for the chicken biryani",
]


def main() -> None:
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            questions = [l.strip() for l in f if l.strip()]
    else:
        questions = QUESTIONS

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    traces = []
    for i, q in enumerate(questions, 1):
        retrieved = retrieve(q)
        try:
            res = answer_question(q)
            error = None
        except Exception as exc:  # noqa: BLE001
            res = {"answer": "", "citations": [], "refused": None}
            error = repr(exc)
        trace = {
            "id": f"t{i:02d}",
            "question": q,
            "retrieved": [
                {
                    "recipe_title": d.metadata.get("recipe_title"),
                    "source_file": d.metadata.get("source_file"),
                    "page": d.metadata.get("page"),
                    "score": round(s, 4),
                    "snippet": d.page_content[:200].replace("\n", " "),
                }
                for d, s in retrieved
            ],
            "answer": res["answer"],
            "refused": res["refused"],
            "citations": res["citations"],
            "error": error,
        }
        traces.append(trace)
        tag = "ERR" if error else ("REFUSED" if res["refused"] else "ok")
        print(f"{trace['id']}  {tag:8s}  {q[:60]}")
        time.sleep(2)  # stay under the Groq free-tier rate limit

    with open(OUT, "w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"\nwrote {len(traces)} traces -> {OUT}")


if __name__ == "__main__":
    main()
