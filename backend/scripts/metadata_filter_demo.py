import json
import os
import sys

sys.path.insert(0, os.getcwd())

from rag.retrieval.retriever import retrieve
from rag.retrieval.filters import by_dietary_tag
from rag.ingestion.index import STRUCTURE_AWARE_COLLECTION

QUERY = "Which recipe uses a live starter culture incubated with milk to make a creamy fermented dish?"
DIETARY_TAG = "vegan"


def _serialize(results):
    return [
        {
            "chunk_id": r.chunk.chunk_id,
            "recipe_id": r.chunk.recipe_id,
            "dietary_tags": r.chunk.dietary_tags,
            "score": r.score,
            "text": r.chunk.text,
        }
        for r in results
    ]


def main():
    unfiltered = retrieve(STRUCTURE_AWARE_COLLECTION, QUERY, top_k=5)
    filtered = retrieve(STRUCTURE_AWARE_COLLECTION, QUERY, top_k=5, filter_fn=by_dietary_tag(DIETARY_TAG))

    result = {
        "query": QUERY,
        "dietary_tag_filter": DIETARY_TAG,
        "unfiltered": _serialize(unfiltered),
        "filtered": _serialize(filtered),
        "top1_changed": (unfiltered[0].chunk.recipe_id if unfiltered else None)
        != (filtered[0].chunk.recipe_id if filtered else None),
    }

    with open(os.path.join(os.getcwd(), "evaluation", "metadata_filter.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
