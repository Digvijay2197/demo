# Recipe RAG Assistant — M2 Retrieval & RAG

A Recipes & Food RAG chatbot demonstrating two chunking strategies (baseline vs.
structure-aware) over 6 fermentation recipe cards, with metadata filtering, grounded
citations, and refusal behavior. Full results and methodology: [results.md](results.md),
[docs/](docs/).

## Stack

- **Frontend**: `frontend/` — Next.js 16 (App Router), React, TypeScript, Tailwind CSS
- **Backend**: `backend/` — Python, FastAPI, sentence-transformers (`all-MiniLM-L6-v2`),
  a small local JSON vector store, Groq for generation

## Running locally

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell/Git Bash
pip install -r requirements.txt
cp .env.example .env          # then fill in GROQ_API_KEY
uvicorn app.main:app --reload --port 8000
```

Backend runs on `http://localhost:8000`.

### 2. Ingest the recipe cards (first run only)

```bash
cd backend
.venv\Scripts\activate
python scripts/ingest.py                # indexes the 6 fermentation cards into both collections
python scripts/evaluate.py              # search-only Hit@5 evaluation, writes evaluation/
python scripts/metadata_filter_demo.py  # dietary_tags filter demo
python scripts/grounded_answers.py      # 3 grounded answers + 3 refusals via Groq
python scripts/bonus_demo.py            # precision-vs-completeness bonus comparison
```

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) for the chat UI, and
[http://localhost:3000/evaluation](http://localhost:3000/evaluation) for the retrieval
evaluation dashboard.

### 4. Tests

```bash
cd backend
.venv\Scripts\activate
python -m pytest tests/ -v
```

## Project layout

```
backend/     FastAPI app + rag/ (ingestion, chunking, embeddings, retrieval, generation,
             citations, vectorstore) + scripts/ (CLI experiment runners) + tests/
frontend/    Next.js UI only — no server-side API routes, everything calls the backend
evaluation/  (inside backend/) generated Hit@5 dumps, metadata filter results, grounded
             answers, refusals, bonus comparison
docs/        architecture.md, rag-flow.md, evaluation.md
results.md   the full write-up: questions, Hit@5 table, per-question retrieval, metadata
             filter demo, grounded answers, refusals, chunker decision, retrieval failure
```
