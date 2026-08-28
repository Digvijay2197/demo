# Architecture

## Two services

```
frontend/   Next.js 16 (App Router) + React + TypeScript + Tailwind
                 |
                 | HTTP (fetch), NEXT_PUBLIC_API_URL, CORS
                 v
backend/    FastAPI (Python) — the RAG engine and API
```

The frontend is a pure UI with no server-side routes. Every operation (chat, document
list, upload, citation resolution) is an HTTP call to the backend, so `GROQ_API_KEY` and
all RAG internals stay server-side.

## RAG stack

| Concern | Choice | Why |
|---|---|---|
| Framework | **LangChain** | Standard building blocks for loaders, splitters, vector stores, chat models; provider-agnostic |
| Vector DB | **ChromaDB** (persistent) | Real vector database, local, zero-config, survives restarts under `CHROMA_DIR` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` via `langchain-huggingface` | Free, local, offline, no API key; 384-dim |
| PDF parsing | `PyMuPDFLoader` (`langchain-community`) | Robust text extraction with per-page metadata; text-based PDFs only |
| Splitter | `RecursiveCharacterTextSplitter` (1000 / 150) | Paragraph-aware fixed-size chunks with overlap |
| LLM | Groq via `langchain-groq` (`ChatGroq`) | Fast, free tier; isolated behind one module so it can be swapped |

## Backend module layout (`backend/rag/`)

```
rag/
├── config.py                     all env-driven settings, read once
├── ingestion/
│   ├── pdf_loader.py             list_pdf_files() + load_pdf() -> one Document per page
│   └── pipeline.py               split_pages() + ingest(): split -> embed -> upsert to Chroma
├── embeddings/
│   └── embedding_service.py      get_embeddings() -> cached HuggingFaceEmbeddings
├── vectorstore/
│   └── store.py                  get_vectorstore() -> cached persistent Chroma;
│                                 collection_count(), reset_collection()
├── retrieval/
│   └── retriever.py              retrieve() (similarity + score) + has_sufficient_evidence()
├── generation/
│   ├── prompt.py                 grounding system prompt + context block builder
│   ├── groq_service.py           ChatGroq wrapper — the ONLY file that reads GROQ_API_KEY
│   └── answer_service.py         answer_question(): full RAG flow + citation extraction
└── citations/
    └── citations.py              chunk_id -> stored text + metadata
```

`app/main.py` (FastAPI) and `scripts/ingest.py` (CLI) are both thin callers of `rag/`.

## Idempotent ingestion

Each chunk id is `sha1(source_file + page + chunk_text)`. `ingest()` looks up those ids in
Chroma and inserts only the ones not already present, so:

- dropping a new PDF into `data/pdfs/` and re-running `scripts/ingest.py` adds only that
  PDF's chunks;
- `--rebuild` wipes the collection first for a clean re-index after removing/replacing PDFs;
- tests can call `ingest()` in setup without accumulating duplicates.

## Why the LLM is isolated

`rag/generation/groq_service.py` is the only module that imports `langchain_groq` or reads
`GROQ_API_KEY`. `answer_service.py` calls `generate_grounded_answer(question, results)`
without knowing the provider — swapping Groq for OpenAI/Anthropic/a local model is a
one-file change.
