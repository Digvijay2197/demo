# Recipe RAG Assistant

An AI chatbot that answers cooking questions **only** from recipe PDFs you provide,
using retrieval-augmented generation (RAG). Every answer is grounded in the source
documents and comes with page-level citations; if the PDFs don't contain the answer,
the bot refuses instead of guessing.

## Stack

| Layer | Technology |
|---|---|
| RAG framework | **LangChain** |
| Vector database | **ChromaDB** (persistent, on disk) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` — local, free, no API key |
| PDF parsing | PyMuPDF (text-based PDFs) |
| LLM (generation) | Groq (`openai/gpt-oss-20b` by default) via `langchain-groq` |
| Backend API | FastAPI |
| Frontend | Next.js 16 (App Router), React, TypeScript, Tailwind CSS |

## How it works

```
recipe PDFs ─► PyMuPDF loader ─► split (recipe-aware / card / recursive) ─► MiniLM embeddings ─► ChromaDB
                                                                                                   │
question ─► embed ─► Chroma semantic search ─┐                                                    │
                                              ├─► RRF fusion (hybrid) ─► grounding gate ─► Groq LLM ─► answer + citations
question ─► BM25 keyword search ─────────────┘
```

- **Recipe-aware splitting**: a cookbook PDF with many recipes per page is split on
  recipe boundaries (a title line followed by a contributor name), so each recipe becomes
  one chunk with its **title prefixed** — a search for "Oatmeal Bread" then reliably finds
  the chunk that holds its ingredients.
- **Card splitting**: a single structured recipe card (title + an ingredient table + a
  method paragraph + an allergens line) is split one chunk per section, so a table row is
  never separated from its header or its title (`rag/ingestion/card_splitter.py`). Plain
  single-recipe PDFs, forms and prose fall back to the plain recursive splitter.
- **Hybrid retrieval**: semantic (Chroma cosine) and keyword (BM25) search are fused by
  rank via Reciprocal Rank Fusion, so an exact code / rare ingredient name that a dense
  embedding underweights can still surface (`rag/retrieval/keyword_search.py`,
  `rag/retrieval/retriever.py`). Toggle with `HYBRID_SEARCH`.
- **Grounding gate**: if no retrieved chunk scores at or above `SIMILARITY_THRESHOLD`,
  the bot refuses without calling the LLM.
- **Idempotent ingestion**: each chunk's id is a hash of its source file, page, recipe
  title and text, so re-running ingestion after adding a PDF only inserts new chunks.

## Running locally

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell / Git Bash)
pip install -r requirements.txt
copy .env.example .env            # then set GROQ_API_KEY (free: https://console.groq.com/keys)
```

### 2. Add recipe PDFs

Just drop text-based recipe PDF(s) into `backend/data/pdfs/` (any filename). The API
**auto-indexes** them: once on startup, and then live whenever a file in that folder is
added, changed, or removed while the server runs — no manual step, no restart. Watch the
server log for `[watch] indexed [...]`.

To try it without your own files: `python scripts/generate_sample_pdfs.py`.

Manual indexing is still available (and needed if you set `AUTO_INGEST_ON_STARTUP=false`):

```bash
python scripts/ingest.py            # index new PDFs / chunks
python scripts/ingest.py --rebuild  # wipe the vector store and re-index everything
```

### 3. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

Key endpoints: `POST /chat`, `GET /documents`, `POST /documents/upload` (PDF),
`POST /ingest`, `GET /health`, `GET /citations?chunkId=...`.

### 4. Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open <http://localhost:3006> (the dev server port is set in `frontend/package.json`).

### 5. Tests

```bash
cd backend
.venv\Scripts\activate
python -m pytest tests/ -v
```

The tests build a small in-memory PDF, run a real ingest into a temporary Chroma
collection, and mock only the Groq call.

## Project layout

```
backend/
  app/main.py                 FastAPI app
  rag/
    config.py                 all env-driven settings
    ingestion/pdf_loader.py   load text PDFs -> per-page Documents (+ NFKC cleanup, recipe_id/cuisine/dietary_tags)
    ingestion/recipe_splitter.py  one chunk per recipe for cookbook-style PDFs
    ingestion/card_splitter.py    one chunk per section for a structured recipe card (title + ingredient table + method + allergens)
    ingestion/pipeline.py     split (recipe-aware / card / recursive) -> embed -> upsert (idempotent)
    embeddings/embedding_service.py   MiniLM HuggingFaceEmbeddings
    vectorstore/store.py      Chroma client (persistent)
    retrieval/retriever.py    semantic + BM25 hybrid search (RRF) + grounding gate
    retrieval/keyword_search.py   BM25 index over the corpus
    generation/prompt.py      grounded system prompt
    generation/groq_service.py    ChatGroq wrapper
    generation/answer_service.py   full RAG flow + citation extraction
    citations/citations.py    chunk_id -> stored text
  scripts/ingest.py           CLI indexer
  scripts/generate_sample_pdfs.py   writes sample recipe PDFs to data/pdfs/
  scripts/generate_fermentation_cards.py   writes 6 structured recipe-card PDFs (Week 3)
  data/pdfs/                   <-- put your PDFs here (git-ignored)
  data/chroma/                 persistent vector DB (git-ignored)
frontend/                      Next.js chat UI (calls the backend, no server routes)
```

## Configuration (`backend/.env`)

| Var | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | required for answer generation |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq chat model (must be one your key can access) |
| `GROQ_REASONING_EFFORT` | `low` | reasoning models (gpt-oss, qwen) burn hidden tokens; keeps you under the free-tier limit |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | local embedding model |
| `CHROMA_DIR` | `./data/chroma` | vector DB location |
| `CHROMA_COLLECTION` | `recipes` | collection name |
| `PDF_DIR` | `./data/pdfs` | source PDF folder |
| `AUTO_INGEST_ON_STARTUP` | `true` | index any new/changed PDFs when the API starts |
| `WATCH_PDF_DIR` | `true` | keep watching `PDF_DIR` and index changes live while the API runs |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `550` / `80` | small chunks ≈ one recipe each; also keeps LLM context small |
| `TOP_K` | `4` | chunks retrieved per question |
| `MAX_CONTEXT_CHARS` | `4000` | hard cap on retrieved context sent to the LLM (~1k tokens) |
| `SIMILARITY_THRESHOLD` | `0.22` | min relevance before the bot answers |
| `HYBRID_SEARCH` | `true` | fuse BM25 keyword search with semantic search (RRF) so exact codes/rare terms aren't missed — see [`docs/week4-debugging-retrieval.md`](docs/week4-debugging-retrieval.md) |

### Large / multi-recipe PDFs

A whole cookbook in one PDF works — the recipe-aware splitter gives each recipe its own
titled chunk (e.g. the 120-page Nelson Family Recipe Book → ~300 recipe chunks), so
"give me the Oatmeal Bread recipe" retrieves that exact recipe even when three recipes
share a page.

The one limit is Groq's **free tier: 8,000 tokens/minute**. The defaults above keep a
typical question at ~900–1,300 tokens, and the client retries `429`s with backoff. If you
still hit the limit (rapid-fire questions, a huge retrieved context), the API returns
`503` "the model is rate-limited, wait a few seconds" rather than failing silently —
lower `MAX_CONTEXT_CHARS` / `TOP_K`, or upgrade the Groq tier.
