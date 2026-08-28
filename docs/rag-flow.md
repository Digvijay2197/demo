# Full Flow & Where RAG Is Used

From a recipe PDF on disk to an answer on screen, with the file/function for each step.
See also [architecture.md](architecture.md).

## Two flows

```
A. Ingestion   python scripts/ingest.py               (run after adding PDFs)
B. Chat        frontend -> POST /chat -> answer_question()   (every user message)
```

---

## A. Ingestion — PDFs into a searchable index

```
backend/data/pdfs/*.pdf   (any filename, text-based PDFs)
        |
        v
pdf_loader.py : load_all_pdfs()          PyMuPDFLoader reads each PDF; one Document per
                                         page that has extractable text (image-only pages
                                         are skipped and reported). metadata: source_file,
                                         page (1-indexed), title
        |
        v
pipeline.py : split_pages()              RecursiveCharacterTextSplitter (CHUNK_SIZE /
                                         CHUNK_OVERLAP). Adds chunk_id = sha1(source_file +
                                         page + text) and a short snippet to metadata
        |
        v
embedding_service.py : get_embeddings()  index-time embedding. all-MiniLM-L6-v2 -> 384-dim
                                         vector per chunk (run inside Chroma.add_documents)
        |
        v
vectorstore/store.py : get_vectorstore() Chroma (persist_directory=CHROMA_DIR,
pipeline.py : ingest()                    collection=CHROMA_COLLECTION). Upserts only chunk
                                         ids not already in the collection
```

Entry point: `rag/ingestion/pipeline.py: ingest()`, run via `python scripts/ingest.py`
(or `POST /ingest`). This is the **index half of RAG** — it happens before any question.

---

## B. Chat — the live RAG request

```
frontend/components/ChatWindow.tsx
        |  fetch(`${NEXT_PUBLIC_API_URL}/chat`, {question})
        v
backend/app/main.py : POST /chat          Pydantic-validates the body, calls answer_question()
        |
        v
backend/rag/generation/answer_service.py : answer_question(question)
```

### B.1 — Retrieval ("R") — `rag/retrieval/retriever.py: retrieve()`

The question is embedded with the same model used at index time and run through
`Chroma.similarity_search_with_relevance_scores(query, k=TOP_K)`, returning
`[(Document, score)]` with `score` normalised to `[0, 1]`.

### B.2 — Grounding gate — `has_sufficient_evidence()`

Similarity search always returns *something*, so a second check enforces that the best hit
clears `SIMILARITY_THRESHOLD`. If it doesn't, `answer_question()` returns the fixed refusal
**without calling the LLM**.

### B.3 — Augmentation ("A") — `prompt.py: build_context_block()`

Each retrieved chunk is rendered as `[source: FILENAME p.PAGE]\n<text>` and joined into one
context block under `GROUNDING_SYSTEM_PROMPT` ("answer using ONLY this context; cite every
sentence as `[source: FILE p.N]`; if insufficient, say the fixed refusal sentence").

### B.4 — Generation ("G") — `groq_service.py: generate_grounded_answer()`

`ChatGroq` (temperature 0) produces the answer. If the model returns the refusal sentence,
`answer_question()` treats it as a refusal too — a second, independent refusal line.

### B.5 — Citation extraction — `answer_service.py`

The answer text is scanned for `[source: FILE p.N]` markers; each is matched back to a
retrieved chunk to build `citations: [{chunk_id, source_file, page, snippet, score}]`. If
the model emitted no markers, every retrieved chunk is cited (the answer was still
generated only from those).

### B.6 — Response

```
{answer, citations: [{chunk_id, source_file, page, snippet, score}], refused}
        |
        v
frontend/components/ChatMessage.tsx    renders answer + citation chips
frontend/components/SourcePanel.tsx    on click, GET /citations?chunkId=... -> full chunk text
```

---

## Where exactly is "RAG" in this codebase?

| RAG stage | File | What it does |
|---|---|---|
| Load | `rag/ingestion/pdf_loader.py` | PDF pages -> `Document`s with source/page metadata |
| Chunk | `rag/ingestion/pipeline.py` | `RecursiveCharacterTextSplitter`, deterministic chunk ids |
| Embed (index + query) | `rag/embeddings/embedding_service.py` | `all-MiniLM-L6-v2`, one cached model |
| Store | `rag/vectorstore/store.py` | persistent ChromaDB collection |
| Retrieve ("R") | `rag/retrieval/retriever.py` | Chroma similarity search + score |
| Augment ("A") | `rag/generation/prompt.py` | formats chunks into the prompt context |
| Generate ("G") | `rag/generation/groq_service.py` | `ChatGroq`, swappable provider |
| Grounding / refusal | `retriever.has_sufficient_evidence()` + LLM refusal wording | two independent checks |
| Citations | `rag/citations/citations.py` | cited chunk_id -> source file / page / text |
