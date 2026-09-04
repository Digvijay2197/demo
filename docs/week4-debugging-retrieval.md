<!-- Soft Suave · Week 4 · Module 2 — Retrieval & RAG. Track B: Recipes & food -->
# Week 4 — Debugging Retrieval: hybrid search (BM25 + RRF), and what it did and didn't fix

**Deliverable:** an inspection view (question / what was fetched / final answer, side by
side), each failure labeled as either **"wrong document fetched"** (retrieval) or **"right
document, wrong answer"** (generation), one retrieval change (hybrid BM25 + semantic search
via Reciprocal Rank Fusion), and a before/after **hit-rate@3** number — plus which failures
the change did and did not fix.

**System under test:** the Recipe RAG chatbot, corpus = 20 free-form recipe PDFs (see
[`week4-retrieval-final.json`](week4-retrieval-final.json) for the full run). Retrieval was
previously pure Chroma cosine similarity, top-4, refuse below 0.22.

---

## 1. Why this corpus is new

The corpus behind earlier weeks' traces (a 120-page cookbook + a few single recipes) isn't
in this checkout — `backend/data/pdfs/` is git-ignored by design (see
[`architecture.md`](architecture.md)) and those PDFs live only on whoever ran Weeks 5-6
locally. Retrieval debugging needs a corpus that actually contains hard cases — exact codes,
rare ingredient names, near-duplicate recipe titles — so a synthetic 20-recipe set was
generated for this week specifically to include them
([`scripts/generate_sample_pdfs.py`](../backend/scripts/generate_sample_pdfs.py)): two
near-duplicate "Lefse" recipes with different numbers, several recipes carrying an exact
code (`SD-2041`, `REC-118`), rare ingredients (gochugaru, shiro miso, mirin), and enough
same-topic "decoy" recipes (extra breads, extra glazed proteins, extra chilis) that a plain
topical query has real competition in the top-3 — a 6-10 recipe corpus turned out to be too
easy to fail on (see §2).

## 2. The inspection view (question / retrieved / answer, before the change)

12 questions were run through the live pipeline; the first attempt used natural phrasing
("what is the hydration percentage for batch SD-2041") and every one landed the right
document anyway — MiniLM's subword tokenizer partially decodes short alphanumeric codes, so
with a small corpus there wasn't enough competition to fail. The genuinely hard case turned
out to be a **bare or near-bare code with no topical words around it** ("SD-2041" alone) —
that's what actually breaks pure semantic search, and it's realistic: a user pasting an
error code or an order number types exactly that, not a full sentence about it.

Full retrieved-chunks + answers for all 15 final cases are in
[`week4-retrieval-final.json`](week4-retrieval-final.json), produced by
[`scripts/eval_week4_retrieval.py`](../backend/scripts/eval_week4_retrieval.py). The failing
ones (semantic-only, before the change):

| id | Question | Top-3 retrieved (semantic only) | Answer | Label |
|---|---|---|---|---|
| r01 | `SD-2041` | weeknight-beef-and-bean-chili (0.14), teriyaki-glazed-chicken-thighs (0.13), korean-bulgogi-rice-bowl (0.12) — **sourdough-loaf-batch-sd-2041.pdf never appears** | *refused* | **wrong document fetched** |
| r02 | hydration percentage SD-2041 | kimchi-fried-rice-gochugaru (0.19), **sourdough-loaf-batch-sd-2041 (0.16)**, sourdough-loaf-batch-sd-2041 (0.15) | *refused* | **right document, wrong answer** |
| r03 | `REC-118` | teriyaki-glazed-chicken-thighs (0.20), **pantry-chili-con-carne-rec-118 (0.15)**, weeknight-beef-and-bean-chili (0.12) | *refused* | **right document, wrong answer** |
| r03b | what temperature does REC-118 recommend | sourdough-loaf-batch-sd-2041 (0.24), **pantry-chili-con-carne-rec-118 (0.22 & 0.20)** | *refused* | **right document, wrong answer** |
| r05 | can I use cayenne instead of gochugaru | **kimchi-fried-rice-gochugaru (0.37 & 0.26)**, pantry-chili-con-carne-rec-118 (0.22) | "do not substitute cayenne 1:1" (omits the recipe's "use about half as much") | **right document, wrong answer** (incomplete) |

The other 10 questions (control queries, the duplicate-name Lefse pair, rare-ingredient
lookups with fuller phrasing) already passed with semantic-only retrieval — see the full
table in the JSON. **Semantic-only hit-rate@3 across all 15 cases: 14/15 = 93%** — only r01
is a pure retrieval miss (the document never appears in the top-3 at all); r02/r03/r03b/r05
all *do* retrieve the right document in the top-3, but fail downstream.

## 3. The two kinds of wrong, with evidence

- **Wrong document fetched (r01):** `sourdough-loaf-batch-sd-2041.pdf` is absent from the
  top-6 entirely for the bare query `SD-2041` — verified directly against the retriever, not
  inferred from the refusal. This is a genuine ranking failure: MiniLM's embedding of a short
  out-of-vocabulary code, with no other words to anchor it, just doesn't align with the
  document that contains it.
- **Right document, wrong answer (r02, r03, r03b):** the correct chunk is in the top-3 by
  rank in all three cases (confirmed in the retrieved lists above), but the pipeline still
  refuses. The cause is a *different* mechanism: the grounding gate refuses unless the
  top-scoring semantic similarity clears `SIMILARITY_THRESHOLD=0.22`, and a bare-code-heavy
  query produces weak absolute similarity scores (0.15-0.24) even for the right document —
  ranking and absolute confidence are not the same thing, and this is the gate's, not
  retrieval's, gap.
- **Right document, wrong answer (r05):** the correct chunk is top-1 (0.37), the answer is
  grounded and not wrong, but it's incomplete — the recipe's note says "do not substitute
  cayenne 1:1... use about half as much," and the model's answer states the "don't do 1:1"
  part but drops the actionable "half as much" part. A minor generation-completeness gap.

## 4. The one change: hybrid search (BM25 + semantic, fused by rank)

Added [`rag/retrieval/keyword_search.py`](../backend/rag/retrieval/keyword_search.py) (BM25
over the full corpus via `rank_bm25`) and rewrote
[`rag/retrieval/retriever.py`](../backend/rag/retrieval/retriever.py) to fuse it with the
existing Chroma semantic search via **Reciprocal Rank Fusion** (`retrieve(query, hybrid=True)`,
now the default via `HYBRID_SEARCH` in `rag/config.py`). RRF combines by *rank position*, not
raw score, so BM25's unbounded scores never have to be normalised against cosine similarity.
The document's *semantic* similarity is still what's attached to each returned result (not the
fusion score) — that's what keeps `has_sufficient_evidence`'s threshold meaningful either way;
it was changed from checking only the top-ranked result to checking the max across the
returned set, since in hybrid mode the top-ranked-by-fusion result isn't necessarily the
top-ranked-by-meaning one.

This is the only variable changed for the numbers below — same corpus, same embedding model,
same generation prompt.

## 5. Before / after — hit-rate@3

| metric | BEFORE (semantic only) | AFTER (hybrid BM25 + semantic, RRF) |
|---|---:|---:|
| hit-rate@3 (15 cases) | **14 / 15 (93%)** | **15 / 15 (100%)** |

| id | Question | Before hit@3 | After hit@3 | What happened |
|---|---|:---:|:---:|---|
| r01 | `SD-2041` | ✗ | ✓ | **FIXED** — BM25's exact-token match pulls `sourdough-loaf-batch-sd-2041.pdf` to rank 1-2; RRF promotes it into the fused top-3 |
| r02 | hydration percentage SD-2041 | ✓ | ✓ | already a hit; unaffected |
| r03 | `REC-118` | ✓ | ✓ | already a hit; unaffected |
| r03b | what temperature does REC-118 recommend | ✓ | ✓ | already a hit; unaffected |
| r05 | can I use cayenne instead of gochugaru | ✓ | ✓ | already a hit; unaffected |

Retrieval verified directly (not through the chat answer) via
`retrieve(query, top_k=3, hybrid=True/False)` — e.g. for `SD-2041`, `keyword_search` alone
scores `sourdough-loaf-batch-sd-2041.pdf` at 2.67 / 2.45 (its two chunks), clearly top of the
BM25 ranking, and the fused hybrid result puts both of that file's chunks in the top-2.

## 6. What this change did NOT fix — checked, not assumed

Retrieval hit-rate@3 went from 93% to 100%, but re-running the **full answer pipeline**
after the change shows only 1 of the 5 original failures actually resolved end-to-end:

| id | Before → After (full answer) | Fixed? |
|---|---|---|
| r01 | refused → **still refused** | retrieval fixed (doc now in top-3), but its semantic score (0.07/0.05) is far below the 0.22 grounding threshold, so the gate still refuses — **hybrid search doesn't raise absolute similarity, only rank/presence** |
| r02 | refused → **still refused** | same threshold gap (top score 0.16, still < 0.22) — was already a hit@3 before the change, so hybrid changes nothing here |
| r03 | refused → **still refused** | same threshold gap (top score 0.15) |
| r03b | refused → **still refused** | same threshold gap (top score 0.22-0.24, borderline but still under) |
| r05 | incomplete → **still incomplete** | a generation completeness issue, not a retrieval issue — untouched by a retrieval-side change, as expected |

**This is the honest headline finding, not a footnote:** hybrid search measurably fixed the
one pure *retrieval* failure (r01), exactly what it's for. It did **not** fix any of the
refusals, because those are gated by absolute semantic-similarity confidence
(`SIMILARITY_THRESHOLD`), a mechanism hybrid search doesn't touch — reordering *which*
document ranks where doesn't change how confidently the embedding model thinks it matches.
Fixing r02/r03/r03b would need a different, generation-side change (e.g. gating on the fused
rank/BM25 evidence too, not semantic score alone) — explicitly out of scope for "one
change," and correctly so: conflating the two would have made it impossible to tell which
change fixed what.

## 7. What shipped

- [`rag/retrieval/keyword_search.py`](../backend/rag/retrieval/keyword_search.py) — new,
  BM25 index over the corpus, cache-invalidated on ingest
  ([`rag/ingestion/pipeline.py`](../backend/rag/ingestion/pipeline.py)).
- [`rag/retrieval/retriever.py`](../backend/rag/retrieval/retriever.py) — `retrieve()` gained
  `hybrid` (defaults to the `HYBRID_SEARCH` config flag, on); RRF fusion;
  `has_sufficient_evidence` now checks the max score in the returned set.
- [`rag/generation/answer_service.py`](../backend/rag/generation/answer_service.py) —
  `answer_question()` gained a pass-through `hybrid` param so before/after can be measured
  against the real end-to-end pipeline, not just retrieval in isolation.
- [`rag/config.py`](../backend/rag/config.py) — `HYBRID_SEARCH` flag.
- `rank_bm25` added to `requirements.txt`.
