import json
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from rag.retrieval.retriever import retrieve
from rag.generation.groq_service import generate_grounded_answer
from rag.ingestion.index import BASELINE_COLLECTION, STRUCTURE_AWARE_COLLECTION

# Bonus challenge: find a question where structure-aware retrieves the
# precise ingredient value (better retrieval) but the isolated ingredient
# chunk lacks method prose explaining when it's used, producing a less
# complete final answer than the baseline chunk (which happens to bundle
# ingredients and method prose together in one bigger window).
QUESTION = (
    "How much fine sea salt does the sourdough recipe use, and at what point in the "
    "mixing process should it be added?"
)


def run_strategy(collection: str):
    results = retrieve(collection, QUESTION, top_k=1)
    context_chunks = [
        {
            "chunk_id": r.chunk.chunk_id,
            "recipe_id": r.chunk.recipe_id,
            "recipe_title": r.chunk.recipe_title,
            "section": r.chunk.section,
            "text": r.chunk.text,
        }
        for r in results
    ]
    answer = generate_grounded_answer(QUESTION, context_chunks)
    return {"retrieved": context_chunks, "answer": answer}


def main():
    baseline = run_strategy(BASELINE_COLLECTION)
    structure_aware = run_strategy(STRUCTURE_AWARE_COLLECTION)

    output = {"question": QUESTION, "baseline": baseline, "structure_aware": structure_aware}
    with open(os.path.join(os.getcwd(), "evaluation", "bonus.json"), "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("BASELINE ANSWER:\n", baseline["answer"])
    print("\nSTRUCTURE-AWARE ANSWER:\n", structure_aware["answer"])


if __name__ == "__main__":
    main()
