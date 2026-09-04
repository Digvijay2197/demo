<!-- Soft Suave · Week 3 Practical — Task Set B. Track B: Recipes & food -->
# Week 3 — Results: baseline vs. structure-aware chunking on the fermentation cards

**Deliverable:** ingest 6 new fermentation-chapter recipe cards into the existing index with
real metadata; measure hit-in-top-5 for 8 known-answer questions under two chunking
strategies over the *same* corpus; show a metadata filter changing a top-1 result; ground
3 answers with resolvable citations and force 3 honest refusals; defend one chunker.

**Note on history:** an earlier version of this task was completed against a different,
now-deleted architecture (a hand-written markdown corpus under `data/recipes/fermentation/`,
its own ingestion path, and a `results.md` at the repo root — removed in the
"Refactor Recipe RAG Assistant" commit when the app moved to the current PDF + ChromaDB
pipeline). This is a fresh run against *that* pipeline — same 6 recipes and question set for
continuity, all numbers below measured against the app as it exists today.

**System under test:** the same Recipe RAG chatbot as the other weekly write-ups
(LangChain + ChromaDB + Groq), corpus = the existing 26-PDF collection plus 6 new
fermentation cards, embeddings `sentence-transformers/all-MiniLM-L6-v2`, `TOP_K=5` for
this comparison (the app's normal chat `TOP_K` is 4).

---

## 1. Dataset

6 new recipe cards, newly authored as PDFs (`backend/data/pdfs/`), each with a title, a
**structured ingredient table** (name / weight / baker's %), a Method paragraph, and an
Allergens line — see [`scripts/generate_fermentation_cards.py`](../backend/scripts/generate_fermentation_cards.py):

| recipe_id | Title | Cuisine | Dietary tags |
|---|---|---|---|
| `sourdough-2kg` | 2kg Country Sourdough Loaf | Western / Artisan Bread | vegan |
| `kimchi-napa` | Napa Cabbage Kimchi | Korean | vegan, gluten-free |
| `sauerkraut-classic` | Classic Sauerkraut | German | vegan, gluten-free |
| `kombucha-ginger` | Sweet Kombucha with Ginger | American | vegan, gluten-free |
| `miso-soybean` | Homemade Soybean Miso Paste | Japanese | vegan, gluten-free |
| `yogurt-dairy` | Homemade Dairy Yogurt | Mediterranean / Middle Eastern | vegetarian, gluten-free, contains-dairy |

**Ingested into the existing index only for these 6 files** — `python scripts/ingest.py` is
incremental by chunk hash, so it added exactly these cards' chunks without re-processing the
20 recipes already indexed from earlier weeks (see [`architecture.md`](architecture.md)).
Each PDF carries `recipe_id` / `cuisine` / `dietary_tags` as PDF-level custom metadata
(`keywords="recipe_id=...;cuisine=...;dietary_tags=..."`), parsed by
[`pdf_loader.py`](../backend/rag/ingestion/pdf_loader.py) and attached to **every chunk**
from that file, plus derived filterable booleans (`is_vegan`, `is_vegetarian`,
`is_gluten_free`, `is_contains_dairy`) since Chroma's `where` filter needs scalar equality,
not list membership.

## 2. Eight known-answer questions

Written from the card content **before** running any retrieval. 4 of 8 depend on a row
inside the ingredient table (≥3 required):

| id | Question | Expected answer | Recipe | Section |
|---|---|---|---|---|
| q01 | How much fine sea salt does the 2kg sourdough recipe use? | 7 g (0.35%) | sourdough-2kg | ingredients |
| q02 | What is the hydration percentage of the 2kg sourdough recipe? | 75% (750 g water) | sourdough-2kg | ingredients |
| q03 | What is the weight of coarse sea salt used in the kimchi recipe? | 50 g | kimchi-napa | ingredients |
| q04 | How much white sugar is used to brew the kombucha? | 100 g (10%) | kombucha-ginger | ingredients |
| q05 | What temperature should the milk be heated to when making homemade yogurt? | 85 C | yogurt-dairy | method |
| q06 | How long should the homemade miso ferment before it is ready? | 6 to 12 months | miso-soybean | method |
| q07 | What is the allergen note for the homemade miso paste recipe? | Contains soy; koji; no gluten grains | miso-soybean | allergen |
| q08 | Which cuisine is the classic sauerkraut recipe associated with? | German | sauerkraut-classic | ingredients (cuisine line) |

3 out-of-corpus questions (no answer exists anywhere in the corpus) are in §6.

## 3. Chunking comparison

Two chunkers, same 6 cards, same embedding model — the only variable changed:

- **Baseline** — the plain `RecursiveCharacterTextSplitter`, blind to section or table
  boundaries. Run at a deliberately small **200-char window** (vs. the app's normal 550):
  at 550 chars one of these short cards fits almost whole in one chunk, which would never
  actually test whether the chunker separates a row from its header — the exact failure the
  task is about. 200 chars is small enough to cut mid-table and mid-section, which is the
  point of a "baseline" here.
- **Structure-aware** — [`card_splitter.py`](../backend/rag/ingestion/card_splitter.py)
  (new this week): detects the card's own section structure and emits one chunk per section
  (ingredients / method / allergens), each **prefixed with the recipe title**. A table row is
  never separated from its header or its title. This is now wired into the production
  pipeline (`rag/ingestion/pipeline.py: split_pages()`) as a third strategy alongside the
  existing multi-recipe cookbook splitter — it's what actually indexed these 6 cards into the
  live app.

**Hit@5 definition:** a chunk counts as a hit only if its own **text** — not its metadata —
both names the recipe (a word from its title) and contains the literal answer. Checking
metadata's `recipe_id` alone saturates at 8/8 for *both* strategies (with only 6 recipes,
metadata-assisted matching is too easy to be informative) and misses the actual question this
task asks: whether the retrieved *chunk*, the thing a citation shows a reader, still says
which recipe the number belongs to.

| Chunking strategy | Hit@5 |
|---|---:|
| Baseline (200-char blind window) | **6 / 8** |
| Structure-aware (card_splitter) | **8 / 8** |

## 4. Per-question retrieval (both strategies)

| id | Baseline hit | Baseline top-1 (recipe / score) | Structure-aware hit | Structure-aware top-1 (recipe / score / section) |
|---|:---:|---|:---:|---|
| q01 | ✓ | sourdough-2kg / 0.615 | ✓ | sourdough-2kg / 0.597 / **ingredients** |
| q02 | ✓ | sourdough-2kg / 0.566 | ✓ | sourdough-2kg / 0.563 / **ingredients** |
| q03 | ✓ | kimchi-napa / 0.565 | ✓ | kimchi-napa / 0.564 / **ingredients** |
| q04 | ✓ | kombucha-ginger / 0.631 | ✓ | kombucha-ginger / 0.660 / **method** |
| q05 | ✗ | yogurt-dairy / 0.597 (top chunk has no "85 C" line) | ✓ | yogurt-dairy / 0.721 / **method** |
| q06 | ✗ | miso-soybean / 0.528 (top chunk has no "6-12 months" line) | ✓ | miso-soybean / 0.507 / **method** |
| q07 | ✓ | miso-soybean / 0.618 | ✓ | miso-soybean / 0.629 / **ingredients** |
| q08 | ✓ | sauerkraut-classic / 0.765 | ✓ | sauerkraut-classic / 0.766 / **ingredients** |

Full raw dump (all 5 results, both strategies, every question) is in
[`week3-run.md`](week3-run.md), written directly by
[`scripts/eval_week3_chunking.py`](../backend/scripts/eval_week3_chunking.py) — nothing here
is hand-transcribed.

**Both q05 and q06 miss for the same reason:** the 200-char baseline window that scores
highest for the recipe is *right*, but its content window lands on the tail of the
ingredient table plus the section header ("...200 g / 20% / Method"), not the method prose
one chunk later that actually states "85 C" or "6 to 12 months" — that chunk exists but
ranks lower and never surfaces as *the* answer-bearing hit in the top-5 the definition
requires. Structure-aware never has this problem: the whole method paragraph is always one
complete, title-prefixed chunk.

## 5. Metadata filter (dietary_tags)

Query: *"Which recipe uses a live starter culture incubated with milk to make a creamy
fermented dish?"* — semantically this is a dead ringer for the yogurt recipe (live culture +
milk), which is exactly what makes it a good filter test.

Filter: `where={"is_vegan": True}` (against the structure-aware collection, which is what's
actually live in production for these cards)

**Unfiltered top 5:**

| rank | recipe | score |
|---:|---|---:|
| 1 | yogurt-dairy | 0.535 |
| 2 | yogurt-dairy | 0.527 |
| 3 | miso-soybean | 0.381 |
| 4 | sourdough-2kg | 0.379 |
| 5 | kombucha-ginger | 0.356 |

**Filtered (`is_vegan=True`) top 5:**

| rank | recipe | score |
|---:|---|---:|
| 1 | miso-soybean | 0.381 |
| 2 | sourdough-2kg | 0.379 |
| 3 | kombucha-ginger | 0.356 |
| 4 | sourdough-2kg | 0.354 |
| 5 | miso-soybean | 0.326 |

**Top-1 changed: YES** (`yogurt-dairy` → `miso-soybean`). The unfiltered query naturally
favours `yogurt-dairy` — it's a live-culture *dairy* question and yogurt is the one card
that actually uses milk — and the vegan filter correctly excludes it (yogurt-dairy carries
`contains-dairy`, not `vegan`), promoting the next-best vegan-tagged match instead of
silently keeping a non-vegan result at the top.

## 6. Three grounded answers

**Q: How much fine sea salt does the 2kg sourdough recipe use?**
> The 2 kg sourdough recipe uses **7 g of fine sea salt**. [source: sourdough-2kg.pdf p.1]

Citation → `chunk_id 66f924e04426674c6c705fb191b3a85cbe0fa365`, `recipe_id sourdough-2kg`,
`source_file sourdough-2kg.pdf`, resolves via `GET /citations?chunkId=...` to the full
ingredients chunk, which does contain "7 g" — verified, not assumed.

**Q: What temperature should the milk be heated to when making homemade yogurt?**
> The milk should be heated to 85 °C. [source: yogurt-dairy.pdf p.1]

Citation → `chunk_id d8100cb58ce96833b171ef66fb12fd5505762580`, `recipe_id yogurt-dairy`,
resolves to the method chunk, which contains "Heat the milk to 85 C" — verified.

**Q: What is the allergen note for the homemade miso paste recipe?**
> Allergens: Contains soy. Produced with koji (Aspergillus oryzae); no gluten-containing
> grains used. [source: miso-soybean.pdf p.1]

Citation → `chunk_id e55c9e6a2e61dd487890ef19ab4cfbebe07f99f2`, `recipe_id miso-soybean`,
resolves to the allergen chunk, which contains "soy" — verified.

All three `chunk_id`s resolve through the real `resolve_citation()` path (not simulated),
and each cited chunk's text was checked to actually contain the claim
(`claim_in_resolved_text: True` for all three in [`week3-run.md`](week3-run.md)). This also
closes a real gap found while building this: `resolve_citation()` didn't return `recipe_id`
until this week — fixed in
[`rag/citations/citations.py`](../backend/rag/citations/citations.py).

## 7. Three refusals

**Q: What is the exact calorie count of the 2kg sourdough loaf?**
> I couldn't find enough information in the provided recipes to answer that question.

**Q: How many grams of protein does the napa cabbage kimchi recipe contain per serving?**
> I couldn't find enough information in the provided recipes to answer that question.

**Q: What is the vitamin B12 content of the homemade soybean miso paste?**
> I couldn't find enough information in the provided recipes to answer that question.

All three ask for nutrition data that appears on no card. Retrieval still returns the
semantically-related recipe (same corpus, plausible top score) — the refusal is enforced by
the grounding prompt after the model reads real context and finds no number to cite, not by
the retrieval-confidence gate. That gate is a separate line of defense for questions
unrelated to the corpus altogether.

## 8. Chunker decision

**Structure-aware ships as production** for single structured recipe cards — it's already
wired into `split_pages()` and is what indexed these 6 cards for real. It matched or beat
baseline on every one of the 8 questions (8/8 vs. 6/8), and unlike baseline its chunks are
section-labeled and self-contained: a citation from it tells a reader *where* in the recipe
a fact came from, not just which file. Baseline's failure mode (§4, q05/q06) is exactly the
one the task warned about — a window boundary landing between a fact and the section header
that would explain it — and it isn't a rare edge case: it hit 2 of 8 questions in a
6-recipe corpus on the first try.

## 9. One retrieval that embarrassed me

Built for the bonus (§10) expecting the opposite: I picked a question that needs facts from
*two* sections ("how much salt, and when is it added?") on the theory that structure-aware's
clean separation would hurt it here — precise per-fact, but each fact lives in its own
chunk. What actually happened, at top-3, was worse for **baseline**: its top-3 for that query
were `sourdough-2kg` (0.547), then **`sauerkraut-classic`** (0.514) and **`miso-soybean`**
(0.454) — two *other* recipes' salting/method chunks outranked sourdough's own method chunk
(0.438, rank 4, not even in the top-3). Baseline's small blind windows strip the recipe title
out of most fragments, so a generic "salt goes in during the process" chunk from a
completely different recipe reads as more relevant than the correct recipe's second
fragment. Structure-aware's top-3 for the same query, by contrast, were sourdough's own
ingredients / method / allergen chunks, ranks 1–3 — every result on-topic, because every
chunk carries the title. See §10 for the answer quality this produced.

**Diagnosis:** losing the title from a chunk doesn't just cost completeness — it costs
*rank*, because other recipes' generically-worded chunks (many of these fermentation cards
share phrasing like "ferment... at room temperature") can out-score the correct recipe's own
weaker-worded fragment. Keeping the title in every chunk, as structure-aware does, is a
retrieval fix, not just a display nicety.

## 10. Bonus: precision vs. completeness — not the trade-off I expected

**Question:** "How much fine sea salt does the sourdough recipe use, and at what point in
the process is it added?" — top-**3** from each collection (top-1 gives the *same* limited
answer either way: both top-1 hits are the ingredients-only fragment, so top-1 alone shows
no contrast at all).

**Baseline answer (top-3, contaminated by 2 other recipes — §9):**
> The sourdough recipe calls for **7 g of fine sea salt**. The recipe does not specify a
> particular point in the process where the salt is added.

**Structure-aware answer (top-3, all 3 = sourdough's own sections):**
> The recipe calls for **7 g of fine sea salt** (0.35% of the flour). It is added together
> with the starter and mixed in after the initial autolyse, before the bulk fermentation
> begins.

**What this actually shows:** the anticipated trade-off — tight chunks win precision but
lose completeness — didn't hold in this corpus. Structure-aware won **both**: it was precise
(one clean fact per chunk) *and*, because every one of its chunks stays on-topic by title,
it filled out the complete answer at top-3 for free. Baseline lost on both counts for the
same root cause as §9: without a title anchor, 2 of its top-3 "slots" went to the wrong
recipe entirely, crowding out the one chunk (the ingredients/method boundary fragment) that
would have answered the "when" half. The real trade-off structure-aware pays for isn't
completeness — it's that a single **top-1** retrieval can't answer a cross-section question
under either strategy; the fix is `TOP_K >= 3` for compound questions, not choosing baseline.

---

**Time reality note:** only the 6 new cards were indexed (`chunks_new: 18` on top of the
existing 43 from earlier weeks — see the `ingest.py` output in git history); the recipe
corpus from Weeks 4-6 was never re-indexed.
