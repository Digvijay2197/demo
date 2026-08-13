# Evaluation Methodology

Full numeric results, per-question tables, and transcripts live in [`results.md`](../results.md)
at the repo root. This file documents the *methodology* choices behind those numbers.

## Hit@5 definition

A naive definition — "does the expected `recipe_id` appear anywhere in the top 5
results?" — was tried first and scored 8/8 for **both** chunkers. With only 6 distinct
recipes in the corpus, recipe-level retrieval is too easy a task to be informative: almost
any chunk from the right recipe will out-score chunks from the other five.

The metric was tightened to require the retrieved chunk to also contain the literal
evidence text needed to answer the question (`expected_keyword`, e.g. `"7g"`, `"85c"`,
`"german"`), decided per-question at the same time the question itself was written — before
any retrieval was run — precisely so this refinement isn't data snooping on the actual
scores. This produced a real, reproducible split: Baseline 7/8, Structure-Aware 8/8 (see
`results.md` section 3–4 for the full breakdown and section 9 for the one failure).

## Why baseline uses a 200-character window

The baseline chunker represents "the existing chunking strategy carried over unchanged"
per the assignment brief — a generic fixed-size character splitter with no domain
awareness, which is what most naive RAG pipelines ship with by default. 200 characters
with 40-character overlap was chosen because it's short enough to sometimes split an
ingredient table row from its header (the exact failure mode the assignment calls out),
while still usually keeping short sentences intact — this is what a real "we shipped the
generic chunker" baseline looks like, rather than an artificially crippled one.

## Metadata filter query choice

The demo query ("Which recipe uses a live starter culture incubated with milk to make a
creamy fermented dish?") was chosen because its *unfiltered* top-1 result is
`yogurt-dairy` — the one recipe in the corpus that is not vegan. Filtering to
`dietary_tags=vegan` therefore visibly changes the top-1 result, which is the behavior the
assignment specifically asks to demonstrate. An earlier, more generic query
("fermented recipe with live culture") happened to already rank a vegan recipe first
unfiltered, which would have made the filter a no-op in the demo despite the filter
implementation being correct — so the query was changed, not the filter.

## Bonus (precision vs. completeness)

The bonus scenario required **top_k=1** to appear at all: at `top_k=3` (used for the main
grounded-answer demo), structure-aware's retriever pulled in both the ingredients chunk
and the method chunk for the sourdough recipe, so it could answer the salt-weight-and-timing
question completely. Restricting to the single best-scoring chunk per strategy is what
exposes the real trade-off — see `results.md` section 10.
