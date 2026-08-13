import json
import sys
import os

sys.path.insert(0, os.getcwd())

from rag.ingestion.index import ingest_fermentation_cards


def main():
    print("Ingesting 6 new fermentation recipe cards only (no full re-index)...")
    result = ingest_fermentation_cards()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
