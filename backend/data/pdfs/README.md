# Drop your recipe PDFs here

Put any **text-based** recipe PDF(s) in this folder (any filename), then index them:

```bash
cd backend
.venv\Scripts\activate
python scripts/ingest.py            # add new PDFs
python scripts/ingest.py --rebuild  # wipe the vector store and re-index everything
```

Notes:
- Scanned / photographed (image-only) PDFs are **not** supported — there is no OCR.
  A PDF with no selectable text will be skipped and reported.
- Re-running `ingest.py` is safe: unchanged chunks are detected by hash and not duplicated.
- Vectors are stored in `../chroma/` (ChromaDB, git-ignored).
