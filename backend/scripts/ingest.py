"""CLI: index every PDF in data/pdfs/ into the Chroma vector store.

Usage:
    python scripts/ingest.py            # add new PDFs / chunks only
    python scripts/ingest.py --rebuild  # wipe the collection and re-index everything
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from rag.config import PDF_DIR
from rag.ingestion.pipeline import ingest


def main() -> None:
    rebuild = "--rebuild" in sys.argv[1:]
    print(f"PDF source folder: {PDF_DIR}")
    if not os.path.isdir(PDF_DIR) or not [f for f in os.listdir(PDF_DIR) if f.lower().endswith(".pdf")]:
        print("No PDF files found. Drop your recipe PDF(s) into that folder and re-run.")
        return
    print("Rebuild" if rebuild else "Incremental", "ingest starting...")
    result = ingest(rebuild=rebuild)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
