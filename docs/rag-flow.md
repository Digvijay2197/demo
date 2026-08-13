# Full Flow & Where RAG Is Used

This doc walks through everything that happens from a recipe card on disk to an answer on
screen, and points at the exact file/function responsible for each step. See also
[architecture.md](architecture.md) (module layout) and [evaluation.md](evaluation.md)
(why the metrics are defined the way they are).

## The three flows

There are three independent flows through this codebase. Only one of them (**B**) is what
a user triggers by typing in the chat box — the other two are offline/CLI steps.

```
A. Ingestion         backend/scripts/ingest.py            (run once, or after adding a recipe)
B. Chat (live RAG)    frontend -> POST /chat -> answer_question()   (every user message)
C. Evaluation         backend/scripts/evaluate.py etc.     (search-only, no LLM, measures retrieval quality)
```

---

## A. Ingestion — turning recipe cards into a searchable index

```
backend/data/recipes/fermentation/*.md   (6 files)
        |
        v
loader.py : load_recipe_cards()          reads each file
        |
        v
parser.py : parse_recipe_card()          splits front-matter (recipe_id / title / cuisine /
                                          dietary_tags) from the body; finds "## Ingredients"
                                          / "## Method" / "## Allergen Note"; parses the
                                          markdown table into (name, weight, percentage) rows
        |
        +--> baseline_chunker.py           --> RecipeChunk[] (chunk_strategy="baseline")
        +--> structure_aware_chunker.py    --> RecipeChunk[] (chunk_strategy="structure_aware")
        |
        v
metadata.py : assert_valid_chunks()       raises if any chunk is missing source_file /
                                          recipe_id / cuisine / dietary_tags
        |
        v
embedding_service.py : embed_texts()      This is RAG's "index-time embedding" step.
                                          sentence-transformers/all-MiniLM-L6-v2 turns each
                                          chunk's text into a 384-float vector. Same model,
                                          same code path, for both chunkers - the only
                                          variable between the two experiments is the text
                                          each chunker produced.
        |
        v
vectorstore/store.py : append_to_collection()   writes {chunk, embedding} pairs into
                                          backend/data/vectorstore/recipe_baseline.json or
                                          recipe_structure_aware.json, deduped by chunk_id
```

Entry point: `rag/ingestion/index.py: ingest_fermentation_cards()`, run via
`python scripts/ingest.py`. It only ever reads the 6 fermentation files and only ever
appends — nothing else in the corpus is touched, and re-running it is a no-op (chunk IDs
are deterministic, e.g. `structure-sourdough-2kg-ingredients-4`, so the dedup check catches
re-runs).

This is the **"index" half of RAG** — it happens before any user ever asks a question.

---

## B. Chat — the live RAG request (this is what the chat UI calls)

```
frontend/components/ChatWindow.tsx
        |  fetch(`${NEXT_PUBLIC_API_URL}/chat`, {question})
        v
backend/app/main.py : POST /chat            validates the request body (Pydantic),
                                             calls answer_question()
        |
        v
backend/rag/generation/answer_service.py : answer_question(question, dietary_tag?)
```

`answer_question()` is the orchestrator. It runs through several branches **in this
order**, each one either short-circuits with a fully-grounded answer or falls through to
the next:

### B.1 — Dietary-tag listing (deterministic, no retrieval, no LLM)

`_detect_dietary_tag_listing()` checks the question for a "which/what recipes ... are/have"
shape plus a real tag from the corpus (`vegan`, `vegetarian`, `gluten-free`,
`contains-dairy`). If it matches, `_list_recipes_by_dietary_tag()` filters the actual loaded
recipe cards by tag and returns their titles + citations to their metadata chunks — no
embedding search, no LLM call, so it can't hallucinate a tag.

*Example: "Which recipes are vegan?"*

### B.2 — Retrieval (the "R" in RAG) — `rag/retrieval/retriever.py: retrieve()`

If B.1 didn't match, the question is embedded (`embed_text()`, same model as ingestion) and
compared via cosine similarity against `PRODUCTION_COLLECTION`
(`recipe_structure_aware` — the winning chunker from the Hit@5 experiment, `results.md` §3).
This is the same `vectorstore/store.py: search()` function ingestion's evaluation scripts
use — retrieval logic lives in exactly one place.

How the query is shaped depends on what the question mentions
(`_retrieve_for_question()` / `_detect_recipe_ids()`):

- **One named recipe** ("what ingredients does the kimchi use?") → retrieval is filtered to
  *only that recipe's* chunks (`by_recipe_id`) with a larger `top_k=10`, so a broad ask
  gets that recipe's full ingredient list instead of losing most of it to unrelated
  recipes in a corpus-wide top-5.
- **Two+ named recipes** ("sourdough or sauerkraut, which has more salt?") → each recipe is
  retrieved separately (`top_k=4` each) and the results are merged, so both sides of the
  comparison make it into context.
- **Dietary filter set explicitly** (frontend passes `dietaryTag`) → retrieval is filtered
  by `by_dietary_tag()`.
- **Otherwise** → a normal corpus-wide search, `top_k=TOP_K` (5).

### B.3 — Grounding gate — `has_sufficient_evidence()`

`retrieve()` always returns *something* (cosine similarity is never truly zero), so a
second check enforces that the **best** result actually clears `SIMILARITY_THRESHOLD` (0.5).
If it doesn't:
- and the question looks like a generic "show me a recipe" browse request
  (`_is_recipe_listing_request()`) → answer with the real list of indexed recipes instead
  of refusing (still grounded — it's real metadata, just not what the embedding search
  itself matched).
- otherwise → refuse, **before ever calling the LLM**. This is the backend half of the
  two-layer refusal design (spec section 18/19) — retrieval-confidence is checked
  independently of whatever the LLM would have said.

### B.4 — Augmentation + Generation (the "AG" in RAG) — `groq_service.py: generate_grounded_answer()`

The retrieved chunks become the **context** — this is literally "augmenting" the LLM's
prompt with retrieved evidence instead of relying on its training data. Each chunk is
rendered as `[chunk:CHUNK_ID] (recipe: ..., section: ...)\n<text>` and joined into a single
block (`prompt.py: build_context_block()`), placed under the strict grounding system prompt
(`prompt.py: GROUNDING_SYSTEM_PROMPT` — "answer using ONLY the retrieved context... cite
every claim as `[chunk:ID]`... if insufficient, say the fixed refusal sentence"), and sent
to Groq. This is the second, independent line of refusal defense: even when retrieval
returns plausible-looking chunks (e.g. a real miso allergen note when someone asks about
miso's *vitamin B12* content), the LLM itself is told to say it can't find the answer rather
than guess — and `answer_question()` treats that exact sentence as a refusal too.

### B.5 — Citation extraction — back to `answer_service.py`

The raw answer text is scanned for `[chunk:ID]` markers (`_extract_cited_chunk_ids()`), and
each ID is resolved back to `{recipe_id, source_file, section}` via
`rag/citations/citations.py: resolve_citation()` — this is the
"chunk_id → recipe → source_file → text" resolution the spec requires. If the model
answered but left zero markers (observed on some multi-fact listing answers), the fallback
is to cite *every* chunk it was given rather than return an uncited claim — the answer was
still generated from nothing but those chunks, so that's still accurate grounding, just
coarser attribution.

### B.6 — Response back to the UI

```
{answer, citations: [{chunk_id, recipe_id, source_file, section}], refused}
        |
        v
frontend/components/ChatMessage.tsx    renders the answer + citation chips
frontend/components/SourcePanel.tsx    on click, GET /citations?chunkId=... resolves the
                                        full recipe/source_file/section/retrieved text
```

---

## C. Evaluation — measuring retrieval quality (search-only, no LLM)

```
backend/evaluation/questions.py         8 known-answer questions, written before any
                                        retrieval was run
        |
        v
scripts/evaluate.py                    for each question, calls retriever.py: retrieve()
                                        directly against BOTH collections (bypasses
                                        answer_service.py entirely - no recipe-scoping,
                                        no dietary-listing shortcut, no LLM)
        |
        v
rag/retrieval/evaluation.py : build_search_dump()   hit_at_5 = expected recipe_id present
                                        AND expected literal answer text found in that
                                        chunk - see evaluation.md for why
        |
        v
evaluation/summary.json + evaluation/search_results/{baseline,structure_aware}/qNN.json
```

This flow intentionally does **not** go through `answer_question()` — it measures the raw
chunking/embedding/retrieval quality (`results.md` §3-4), independent of any chat-layer
convenience features like recipe-name detection. Those two are complementary but separate:
C tells you which chunker is better at surfacing the right evidence; B is what a real user
actually experiences when they ask a question.

---

## Where exactly is "RAG" in this codebase?

| RAG stage | File | What it does here |
|---|---|---|
| **Chunking** (prep for retrieval) | `rag/chunking/baseline_chunker.py`, `structure_aware_chunker.py` | Splits recipe text into retrievable units — the independent variable in the whole experiment |
| **Embedding** (index-time and query-time) | `rag/embeddings/embedding_service.py` | `sentence-transformers/all-MiniLM-L6-v2`, one function used identically for indexing chunks and embedding live questions |
| **Retrieval** ("R") | `rag/retrieval/retriever.py`, `rag/vectorstore/store.py` | Cosine-similarity top-k search over the JSON vector store, with optional recipe/dietary-tag filters |
| **Augmentation** ("A") | `rag/generation/prompt.py: build_context_block()` | Formats retrieved chunks into the LLM's prompt context |
| **Generation** ("G") | `rag/generation/groq_service.py` | Groq LLM call, isolated behind one function so the provider can be swapped |
| **Grounding / refusal** | `rag/retrieval/retriever.py: has_sufficient_evidence()` + the LLM's own refusal wording | Two independent checks — see B.3/B.4 above |
| **Citations** | `rag/citations/citations.py` | Resolves a cited chunk_id back to its source recipe/file/section/text |

Everything under `rag/` is framework-agnostic plain Python — `app/main.py` (the FastAPI
layer) and `scripts/*.py` (the CLI experiment runners) are both just callers of the same
`rag/` package, which is why the evaluation numbers in `results.md` and the live chat
behavior are guaranteed to be using the same retrieval/embedding code.
