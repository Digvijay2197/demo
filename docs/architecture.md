# Architecture

## Why built from scratch

This task was framed as an extension of an existing M1 RAG application, but the working
directory was empty when the project started — there was no prior frontend, backend, vector
store, or ingestion pipeline to inspect or reuse. A minimal-but-complete RAG stack was built
from scratch, then the full M2 requirements (dual chunking strategies, evaluation harness,
metadata filtering, grounded generation, refusal logic) were layered on top of it.

## Two services, two languages

```
frontend/   Next.js 16 (App Router) + React + TypeScript + Tailwind CSS
                 |
                 | HTTP (fetch), NEXT_PUBLIC_API_URL, CORS
                 v
backend/    FastAPI (Python) — the RAG engine and API
```

The frontend is a pure UI: it has no server-side API routes of its own. Every data
operation (chat, document list, evaluation dashboard, citation resolution, document upload)
is an HTTP call to the backend, whose base URL is `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`). This keeps the `GROQ_API_KEY` and all RAG internals entirely
server-side in the backend process — the browser never sees it.

The backend is a FastAPI app (`backend/app/main.py`) built on top of a plain-Python `rag/`
package with no framework dependencies of its own, so the retrieval/chunking/generation
logic can be imported directly by the CLI scripts (`backend/scripts/*.py`) used to run the
chunking experiment, independent of the HTTP layer.

## Backend module layout (`backend/rag/`)

```
rag/
├── ingestion/       loader.py (reads .md recipe cards), parser.py (front-matter +
│                    ingredient-table parsing), metadata.py (required-field validation),
│                    index.py (ingest_fermentation_cards — the ONLY entry point that writes
│                    to the vector store, and only for the 6 fermentation cards)
├── chunking/        types.py (RecipeChunk / ParsedRecipe dataclasses),
│                    baseline_chunker.py (fixed-size sliding window, no structure awareness),
│                    structure_aware_chunker.py (title -> ingredient rows -> method -> allergen)
├── embeddings/       embedding_service.py — sentence-transformers, one shared model instance
│                    used identically by both chunking strategies
├── vectorstore/       store.py — a small JSON-file-backed store with cosine-similarity search,
│                    one file per collection (recipe_baseline.json, recipe_structure_aware.json)
├── retrieval/        retriever.py (top-k + threshold), filters.py (dietary_tags predicate),
│                    evaluation.py (Hit@5 scoring logic used by scripts/evaluate.py)
├── generation/        prompt.py (grounding system prompt), groq_service.py (isolated LLM
│                    client), answer_service.py (retrieve -> threshold-gate -> generate ->
│                    extract citations -> return)
└── citations/        citations.py — chunk_id -> recipe -> source_file -> text resolution
```

## Why two separate vector collections

`recipe_baseline` and `recipe_structure_aware` are two independent JSON files under
`backend/data/vectorstore/`, populated by the same `ingest_fermentation_cards()` call using
the same embedding model but two different chunkers. This makes the chunking experiment
reproducible and keeps the only intentional variable between the two experiments the
chunking strategy itself (see `results.md` section 3).

## Why the LLM is isolated behind a service

`rag/generation/groq_service.py` is the only file that imports the `groq` SDK or reads
`GROQ_API_KEY`. `answer_service.py` calls `generate_grounded_answer(question, context_chunks)`
without knowing which provider backs it — swapping Groq for another provider means editing
one file.

## Deterministic chunk IDs

Chunk IDs are derived from `(strategy, recipe_id, section, index)` rather than a random
UUID, e.g. `structure-sourdough-2kg-ingredients-4`. This makes `ingest_fermentation_cards()`
idempotent: re-running it appends nothing new (`append_to_collection` dedupes by
`chunk_id`), which matters both for the "index only the 6 new cards, never re-index"
requirement and for automated tests that call ingestion as test setup.
