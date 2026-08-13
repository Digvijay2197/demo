import json
import os
import sys

sys.path.insert(0, os.getcwd())

from evaluation.questions import KNOWN_ANSWER_QUESTIONS
from rag.retrieval.retriever import retrieve
from rag.retrieval.evaluation import build_search_dump, compute_hit_at_5
from rag.ingestion.index import BASELINE_COLLECTION, STRUCTURE_AWARE_COLLECTION

OUT_DIR = os.path.join(os.getcwd(), "evaluation", "search_results")


def run_strategy(collection: str, label: str):
    dumps = []
    directory = os.path.join(OUT_DIR, label)
    os.makedirs(directory, exist_ok=True)

    for q in KNOWN_ANSWER_QUESTIONS:
        results = retrieve(collection, q.question, top_k=5)
        dump = build_search_dump(q, results)
        dumps.append(dump)
        with open(os.path.join(directory, f"{q.id}.json"), "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2)
    return dumps


def main():
    print("Running search-only evaluation (no LLM calls) for both chunking strategies...")

    baseline_dumps = run_strategy(BASELINE_COLLECTION, "baseline")
    structure_dumps = run_strategy(STRUCTURE_AWARE_COLLECTION, "structure_aware")

    baseline_hits = compute_hit_at_5(baseline_dumps)
    structure_hits = compute_hit_at_5(structure_dumps)

    summary = {
        "total_questions": len(KNOWN_ANSWER_QUESTIONS),
        "baseline_hit_at_5": baseline_hits,
        "structure_aware_hit_at_5": structure_hits,
        "per_question": [
            {
                "id": q.id,
                "question": q.question,
                "expected_recipe_id": q.recipe_id,
                "expected_section": q.section,
                "ingredient_dependent": q.ingredient_dependent,
                "baseline_hit": baseline_dumps[i]["hit_at_5"],
                "structure_aware_hit": structure_dumps[i]["hit_at_5"],
            }
            for i, q in enumerate(KNOWN_ANSWER_QUESTIONS)
        ],
    }

    with open(os.path.join(os.getcwd(), "evaluation", "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
