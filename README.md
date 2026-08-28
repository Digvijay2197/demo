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
recipe PDFs ─► PyMuPDF loader ─► RecursiveCharacterTextSplitter ─► MiniLM embeddings ─► ChromaDB
                                                                                          │
question ─► embed ─► Chroma similarity search (top-k) ─► grounding gate ─► Groq LLM ─► answer + citations
```

- **Grounding gate**: if the best retrieved chunk scores below `SIMILARITY_THRESHOLD`,
  the bot refuses without calling the LLM.
- **Idempotent ingestion**: each chunk's id is a hash of its source file, page and text,
  so re-running ingestion after adding a PDF only inserts new chunks.

## Running locally

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell / Git Bash)
pip install -r requirements.txt
copy .env.example .env            # then set GROQ_API_KEY (free: https://console.groq.com/keys)
```

### 2. Add recipe PDFs and index them

Drop any text-based recipe PDF(s) into `backend/data/pdfs/` (any filename). To try it
without your own files, generate two sample recipes first:

```bash
python scripts/generate_sample_pdfs.py   # writes 2 sample recipe PDFs into data/pdfs/
```

Then index whatever is in the folder:

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
    ingestion/pdf_loader.py   load text PDFs -> per-page Documents
    ingestion/pipeline.py     split -> embed -> upsert into Chroma (idempotent)
    embeddings/embedding_service.py   MiniLM HuggingFaceEmbeddings
    vectorstore/store.py      Chroma client (persistent)
    retrieval/retriever.py    similarity search + grounding gate
    generation/prompt.py      grounded system prompt
    generation/groq_service.py    ChatGroq wrapper
    generation/answer_service.py   full RAG flow + citation extraction
    citations/citations.py    chunk_id -> stored text
  scripts/ingest.py           CLI indexer
  scripts/generate_sample_pdfs.py   writes 2 sample recipe PDFs to data/pdfs/
  data/pdfs/                   <-- put your PDFs here (git-ignored)
  data/chroma/                 persistent vector DB (git-ignored)
frontend/                      Next.js chat UI (calls the backend, no server routes)
```

## Configuration (`backend/.env`)

| Var | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | required for answer generation |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq chat model (must be one your key can access) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | local embedding model |
| `CHROMA_DIR` | `./data/chroma` | vector DB location |
| `CHROMA_COLLECTION` | `recipes` | collection name |
| `PDF_DIR` | `./data/pdfs` | source PDF folder |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `150` | splitter settings |
| `TOP_K` | `4` | chunks retrieved per question |
| `SIMILARITY_THRESHOLD` | `0.3` | min relevance before the bot answers |
