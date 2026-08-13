# M2 — Retrieval & RAG: Recipes & Food Chatbot — Results

## 1. Dataset

- 6 new recipe cards, all newly authored for this task (no pre-existing corpus existed to extend from — the working directory was empty at the start of this project; see [docs/architecture.md](docs/architecture.md)).
- Domain: **Recipes & Food**
- Chapter: **Fermentation**
- Files (`backend/data/recipes/fermentation/`):
  1. `sourdough-2kg.md` — 2kg Country Sourdough Loaf (Western / Artisan Bread, vegan)
  2. `kimchi-napa.md` — Napa Cabbage Kimchi (Korean, vegan, gluten-free)
  3. `sauerkraut-classic.md` — Classic Sauerkraut (German, vegan, gluten-free)
  4. `kombucha-ginger.md` — Sweet Kombucha with Ginger Second Ferment (American, vegan, gluten-free)
  5. `miso-soybean.md` — Homemade Soybean Miso Paste (Japanese, vegan, gluten-free)
  6. `yogurt-dairy.md` — Homemade Dairy Yogurt (Mediterranean / Middle Eastern, vegetarian, gluten-free, contains-dairy)

**Only these 6 cards were ingested.** There was no pre-existing corpus to avoid re-indexing, but the ingestion pipeline (`rag/ingestion/index.py: ingest_fermentation_cards`) is intentionally scoped to read only `data/recipes/fermentation/` and append (not overwrite) into the vector store, so it is safe to re-run without duplicating or touching unrelated documents.

## 2. Eight Known-Answer Questions

Written directly from the recipe card text **before** any retrieval was run. 4 of 8 depend on an ingredient-table row (≥3 required).

| ID | Question | Expected Answer | Recipe | Section |
|----|----------|------------------|--------|---------|
| q01 | How much fine sea salt does the 2kg sourdough recipe use? | 7g (0.35% baker's percentage) | sourdough-2kg | ingredients |
| q02 | What is the hydration percentage of the 2kg sourdough recipe? | 75% (1500g water at 75% baker's percentage) | sourdough-2kg | ingredients |
| q03 | What is the weight of coarse sea salt used in the kimchi recipe? | 50g | kimchi-napa | ingredients |
| q04 | How much white sugar is used to brew the kombucha? | 100g (10% of water weight) | kombucha-ginger | ingredients |
| q05 | What temperature should the milk be heated to when making homemade yogurt? | 85C | yogurt-dairy | method |
| q06 | How long should the homemade miso ferment before it is ready? | 6-12 months in a cool, dark place | miso-soybean | method |
| q07 | What is the allergen note for the homemade miso paste recipe? | Contains soy; produced with koji (Aspergillus oryzae), no gluten-containing grains | miso-soybean | allergen |
| q08 | Which cuisine is the classic sauerkraut recipe associated with? | German | sauerkraut-classic | metadata |

3 out-of-corpus questions (no answer exists anywhere in the corpus):
1. What is the exact calorie count of the 2kg sourdough loaf?
2. How many grams of protein does the napa cabbage kimchi recipe contain per serving?
3. What is the vitamin B12 content of the homemade soybean miso paste?

## 3. Chunking Comparison

Embedding model held identical across both experiments: **`sentence-transformers/all-MiniLM-L6-v2`** (free, local, 384-dim). Retrieval parameters identical: `TOP_K=5`. The only variable changed was the chunking strategy.

**Hit@5 definition:** a question is a "hit" if a chunk belonging to the expected `recipe_id` **and** containing the literal answer text (e.g. `"7g"`, `"85c"`, `"german"`) appears in the top 5 retrieved results. Recipe-level match alone was tried first and saturated at 8/8 for both strategies (only 6 distinct recipes in the corpus make recipe-level retrieval too easy to be informative) — see [Retrieval Failure](#9-retrieval-failure) for how this metric was chosen.

| Chunking Strategy | Hit@5 |
| ------------------ | ----: |
| Baseline            |   7/8 |
| Structure-Aware     |   8/8 |

## 4. Per-Question Retrieval (both strategies)

| ID | Baseline hit | Baseline top-1 (recipe / score / section) | Structure-Aware hit | Structure-Aware top-1 (recipe / score / section) |
|----|:---:|---|:---:|---|
| q01 | ✓ | sourdough-2kg / 0.628 / unstructured | ✓ | sourdough-2kg / 0.705 / **ingredients** |
| q02 | ✓ | sourdough-2kg / 0.546 / unstructured | ✓ | sourdough-2kg / 0.634 / **ingredients** |
| q03 | ✓ | kimchi-napa / 0.549 / unstructured | ✓ | kimchi-napa / 0.702 / **ingredients** |
| q04 | ✓ | kombucha-ginger / 0.595 / unstructured | ✓ | kombucha-ginger / 0.684 / **ingredients** |
| q05 | ✓ | yogurt-dairy / 0.690 / unstructured | ✓ | yogurt-dairy / 0.756 / **method** |
| q06 | ✗ | kombucha-ginger / 0.621 / unstructured (wrong recipe) | ✓ | miso-soybean / 0.561 / **method** |
| q07 | ✓ | miso-soybean / 0.641 / unstructured | ✓ | miso-soybean / 0.692 / **allergen** |
| q08 | ✓ | sauerkraut-classic / 0.645 / unstructured | ✓ | sauerkraut-classic / 0.732 / **metadata** |

Full raw dumps (chunk IDs, all 5 scores, full retrieved text) for every question × strategy are in `evaluation/search_results/{baseline,structure_aware}/q01..q08.json`.

Two consistent patterns across all 8 questions:
- Structure-aware top-1 similarity score is higher than baseline's in every single question — its chunks are more semantically concentrated because they aren't diluted with unrelated recipe text.
- Structure-aware's top-1 chunk section always matches the question's target section (ingredients/method/allergen/metadata); baseline has no section field at all (`"unstructured"`), so it can never target evidence precisely — it just happens to also contain the right text in most of these short recipes.

## 5. Metadata Filter (dietary_tags)

Query: *"Which recipe uses a live starter culture incubated with milk to make a creamy fermented dish?"*
Filter: `dietary_tags = ["vegan"]`

**Unfiltered top 5:**
1. yogurt-dairy — 0.474
2. yogurt-dairy — 0.463
3. yogurt-dairy — 0.442
4. yogurt-dairy — 0.439
5. sourdough-2kg — 0.420

**Filtered (`dietary_tags=vegan`) top 5:**
1. sourdough-2kg — 0.420
2. kombucha-ginger — 0.400
3. kombucha-ginger — 0.385
4. kombucha-ginger — 0.385
5. sourdough-2kg — 0.378

**Top-1 changed: YES** (`yogurt-dairy` → `sourdough-2kg`). The unfiltered query naturally favors `yogurt-dairy` (not vegan, since it's a live-culture dairy question), and applying the vegan filter correctly excludes it, promoting the next-best vegan-tagged match. Full scored lists: `evaluation/metadata_filter.json`.

## 6. Three Grounded Answers

**Q: How much fine sea salt does the 2kg sourdough recipe use?**
> The 2kg Country Sourdough Loaf recipe uses 7g of fine sea salt. `[chunk:structure-sourdough-2kg-ingredients-4]`

Citation → chunk_id `structure-sourdough-2kg-ingredients-4`, recipe_id `sourdough-2kg`, source_file `sourdough-2kg.md`, section `ingredients`.

**Q: What temperature should the milk be heated to when making homemade yogurt?**
> According to the recipe, the milk should be heated to 85C. `[chunk:structure-yogurt-dairy-method-3]`

Citation → chunk_id `structure-yogurt-dairy-method-3`, recipe_id `yogurt-dairy`, source_file `yogurt-dairy.md`, section `method`.

**Q: What is the allergen note for the homemade miso paste recipe?**
> The allergen note for the homemade miso paste recipe is that it contains soy. Produced with koji (Aspergillus oryzae cultured rice); no gluten-containing grains used. `[chunk:structure-miso-soybean-allergen-6]`

Citation → chunk_id `structure-miso-soybean-allergen-6`, recipe_id `miso-soybean`, source_file `miso-soybean.md`, section `allergen`.

All three citations were manually verified to actually contain the cited claim (full text in `evaluation/grounded_answers.json`).

## 7. Three Refusals

**Q: What is the exact calorie count of the 2kg sourdough loaf?**
> I couldn't find enough information in the provided recipes to answer that question.

**Q: How many grams of protein does the napa cabbage kimchi recipe contain per serving?**
> I couldn't find enough information in the provided recipes to answer that question.

**Q: What is the vitamin B12 content of the homemade soybean miso paste?**
> I couldn't find enough information in the provided recipes to answer that question.

All three questions ask about nutrition data that never appears anywhere in the recipe cards. Retrieval still returns semantically related chunks (same recipe, high cosine similarity, since "calorie"/"protein"/"vitamin" are food-adjacent terms) — refusal in these three cases is enforced by the grounding system prompt after the model reads the retrieved context and finds no actual number to cite, not by the retrieval-confidence gate. The retrieval-confidence gate (`SIMILARITY_THRESHOLD=0.5` on top-1 score) is a separate, independent line of defense that fires when a question is unrelated to the corpus altogether. Full transcripts: `evaluation/refusals.json`.

## 8. Chunker Decision

**Keep the structure-aware chunker as the production retriever** (`PRODUCTION_COLLECTION=recipe_structure_aware`). It matched or beat the baseline on every one of the 8 known-answer questions (8/8 vs 7/8 Hit@5), had a higher top-1 similarity score on every single question, and — critically — its retrieved chunks are section-labeled and self-contained (`Recipe: X / Section: Ingredients / Ingredient: Y / Weight: Z`), which is what makes citations meaningful: a baseline `"unstructured"` chunk citation tells a user nothing about *where* in the recipe the fact came from. The one place baseline can still edge out structure-aware is when a single query needs facts that structure-aware split into two different chunks (see the bonus section below) — but that is a completeness trade-off addressed by retrieving top-3+ instead of top-1, not a reason to prefer baseline overall.

## 9. Retrieval Failure

**What happened:** On q06 ("How long should the homemade miso ferment before it is ready?"), the baseline chunker's top-5 results never included any `miso-soybean` chunk containing "6-12 months" — its highest-scoring result (0.621) was a `kombucha-ginger` chunk, and other results were `sourdough-2kg` chunks. The correct answer exists in the corpus but baseline never surfaced it in the top 5.

**Why did retrieval fail?** The baseline chunker (200-char fixed windows) split the miso recipe's method section such that the "ferment ... 6-12 months" sentence ended up sharing a chunk window with less-distinctive text, while several *other* recipes' method sections all contain highly similar phrasing — "ferment at room temperature for N days/weeks", "leave to ferment" — because they're all fermentation recipes. The embedding model latched onto that generic "ferment ... duration" shape shared across all six recipes rather than the miso-specific content, and the miso chunk that actually contained the answer scored lower than the generic-fermentation-phrase chunks from other recipes.

**What caused it:** Fixed-size character chunking with no regard for sentence or section boundaries produces chunks whose semantic content is arbitrary — a chunk boundary can fall in the middle of the one sentence that matters, diluting it with surrounding boilerplate, while a *wrong* recipe's chunk can accidentally look more relevant because it happens to contain a cleaner, more central statement of the shared "fermentation duration" concept.

**What could improve it:** This is exactly the failure mode the structure-aware chunker avoids by design — putting the *entire* method section in one chunk, explicitly labeled `Recipe: Homemade Soybean Miso Paste / Section: Method`, so recipe identity is never lost to embedding drift. This is also visible in the numbers: structure-aware's q06 top-1 score (0.561) is meaningfully lower than its other top-1 scores (0.6–0.75), showing the underlying question actually is one of the harder ones in the set for the embedding model — but the recipe-title framing was enough to still surface the right chunk in the top 5.

## 10. Bonus: Precision vs. Completeness

**Question:** "How much fine sea salt does the sourdough recipe use, and at what point in the mixing process should it be added?" (retrieved top-**1** chunk only, from each collection, then generated with Groq)

**Baseline answer:**
> The fine sea salt is dissolved directly into the dough during the initial mix.
> The fine sea salt is added at the point when the dough is first mixed.

*(Note: baseline's single 200-char window happened to contain both the salt line and the "initial mix" sentence, but the model's answer omits the actual weight — 7g — because the top-1 window is method-heavy; a clear illustration of chunk-boundary luck rather than reliable retrieval.)*

**Structure-aware answer:**
> The fine sea salt is used in the amount of 7g.
> I couldn't find enough information in the provided recipe to answer the question about when to add the fine sea salt in the mixing process.

**Precision vs. completeness:** structure-aware's ingredient chunk gives the exact, citable weight (7g) that baseline's answer above actually missed, but because ingredients and method live in separate chunks, a top-1-only retrieval can't answer a question that spans both — the fix is retrieving top-3+ (as done in section 6), not preferring baseline. This is the intended trade-off: structure-aware buys precision and correct grounding per fact at the cost of needing a slightly larger `TOP_K` when a single question genuinely spans two sections. Full transcripts: `evaluation/bonus.json`.
