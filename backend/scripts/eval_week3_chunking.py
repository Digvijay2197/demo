"""Week 3: baseline vs. structure-aware chunking on the fermentation cards.

    python scripts/eval_week3_chunking.py

Builds two temporary, throwaway Chroma collections from the 6 fermentation
cards (data/pdfs/{sourdough-2kg,kimchi-napa,sauerkraut-classic,
kombucha-ginger,miso-soybean,yogurt-dairy}.pdf) - one with the plain
recursive splitter ("baseline"), one with the ingredient-table-aware
rag/ingestion/card_splitter.py ("structure-aware") - and runs the same 8
known-answer questions search-only against both, reporting hit-in-top-5 as a
number out of 8 for each. Nothing here touches the production index; those 6
cards are ALSO already ingested there via the normal `scripts/ingest.py`
(structure-aware wins per section 8 below, so that's what the live app uses),
which is what makes the "3 cited answers + 3 refusals" sections below real
live-pipeline output, not a separate simulation.

Writes docs/week3-results.md.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv

load_dotenv()

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.citations.citations import resolve_citation
from rag.embeddings.embedding_service import get_embeddings
from rag.generation.answer_service import answer_question
from rag.generation.groq_service import generate_grounded_answer
from rag.ingestion.card_splitter import split_cards
from rag.ingestion.pdf_loader import load_pdf

DOCS = os.path.abspath(os.path.join(os.getcwd(), "..", "docs"))
PDF_DIR = os.path.abspath(os.path.join(os.getcwd(), "data", "pdfs"))

CARD_FILES = [
    "sourdough-2kg.pdf", "kimchi-napa.pdf", "sauerkraut-classic.pdf",
    "kombucha-ginger.pdf", "miso-soybean.pdf", "yogurt-dairy.pdf",
]

# A word from the recipe's own title - used (instead of metadata) to check
# whether a chunk's TEXT is self-identifying, since a citation only ever
# shows the model/reader the chunk content, not a metadata sidecar.
_TITLE_MARKER = {
    "sourdough-2kg": "Sourdough", "kimchi-napa": "Kimchi", "sauerkraut-classic": "Sauerkraut",
    "kombucha-ginger": "Kombucha", "miso-soybean": "Miso", "yogurt-dairy": "Yogurt",
}

# id, question, expected recipe_id, expected section, keyword the answer chunk must contain
QUESTIONS = [
    ("q01", "How much fine sea salt does the 2kg sourdough recipe use?",
     "sourdough-2kg", "ingredients", "7 g"),
    ("q02", "What is the hydration percentage of the 2kg sourdough recipe?",
     "sourdough-2kg", "ingredients", "75%"),
    ("q03", "What is the weight of coarse sea salt used in the kimchi recipe?",
     "kimchi-napa", "ingredients", "50 g"),
    ("q04", "How much white sugar is used to brew the kombucha?",
     "kombucha-ginger", "ingredients", "100 g"),
    ("q05", "What temperature should the milk be heated to when making homemade yogurt?",
     "yogurt-dairy", "method", "85 C"),
    ("q06", "How long should the homemade miso ferment before it is ready?",
     "miso-soybean", "method", "6 to 12 months"),
    ("q07", "What is the allergen note for the homemade miso paste recipe?",
     "miso-soybean", "allergen", "soy"),
    ("q08", "Which cuisine is the classic sauerkraut recipe associated with?",
     "sauerkraut-classic", "ingredients", "German"),
]

# 3 answerable (recipe_id, keyword) + 3 out-of-corpus refusal questions
GROUNDED = [
    ("How much fine sea salt does the 2kg sourdough recipe use?", "sourdough-2kg", "7 g"),
    ("What temperature should the milk be heated to when making homemade yogurt?", "yogurt-dairy", "85"),
    ("What is the allergen note for the homemade miso paste recipe?", "miso-soybean", "soy"),
]
REFUSALS = [
    "What is the exact calorie count of the 2kg sourdough loaf?",
    "How many grams of protein does the napa cabbage kimchi recipe contain per serving?",
    "What is the vitamin B12 content of the homemade soybean miso paste?",
]


# A deliberately small fixed window (independent of the app's normal
# CHUNK_SIZE=550, which comfortably holds one of these short cards whole and
# so would never actually separate a row from its header - the exact
# failure this comparison is supposed to surface). 200/20 mirrors the size
# that made the pre-refactor run of this same task fail on a table lookup.
_BASELINE_CHUNK_SIZE = 200
_BASELINE_CHUNK_OVERLAP = 20


def _baseline_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=_BASELINE_CHUNK_SIZE, chunk_overlap=_BASELINE_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""], add_start_index=True,
    )


def build_collections(tmp_dir: str):
    baseline_chunks, structure_chunks = [], []
    for fname in CARD_FILES:
        pages = load_pdf(os.path.join(PDF_DIR, fname))
        baseline_chunks.extend(_baseline_splitter().split_documents(pages))
        structure_chunks.extend(split_cards(pages) or [])

    embeddings = get_embeddings()
    baseline_store = Chroma.from_documents(
        baseline_chunks, embeddings, collection_name="week3_baseline",
        persist_directory=os.path.join(tmp_dir, "baseline"),
        collection_metadata={"hnsw:space": "cosine"},
    )
    structure_store = Chroma.from_documents(
        structure_chunks, embeddings, collection_name="week3_structure_aware",
        persist_directory=os.path.join(tmp_dir, "structure"),
        collection_metadata={"hnsw:space": "cosine"},
    )
    return baseline_store, structure_store, baseline_chunks, structure_chunks


def _hit(results, recipe_id, keyword):
    """A hit needs the retrieved chunk's own TEXT (not its metadata sidecar -
    a citation only ever shows the model/reader the chunk content) to be
    self-identifying (contains a word from the recipe's title) AND contain
    the literal answer text. Recipe-level metadata match alone saturates at
    8/8 for both strategies with only 6 recipes in this corpus - it isn't
    informative, and it doesn't test what the task is actually asking:
    whether the chunk itself still says which recipe '7g' belongs to."""
    marker = _TITLE_MARKER[recipe_id].lower()
    for doc, score in results:
        text = doc.page_content.lower()
        if marker in text and keyword.lower() in text:
            return True, doc, score
    return False, None, None


def run_comparison(baseline_store, structure_store):
    rows = []
    for qid, question, recipe_id, section, keyword in QUESTIONS:
        b_results = baseline_store.similarity_search_with_score(question, k=5)
        s_results = structure_store.similarity_search_with_score(question, k=5)
        b_hit, b_doc, b_dist = _hit(b_results, recipe_id, keyword)
        s_hit, s_doc, s_dist = _hit(s_results, recipe_id, keyword)
        rows.append({
            "id": qid, "question": question, "recipe_id": recipe_id, "section": section, "keyword": keyword,
            "baseline_hit": b_hit,
            "baseline_top1": (b_results[0][0].metadata.get("recipe_id"), round(1 - b_results[0][1], 3)) if b_results else None,
            "structure_hit": s_hit,
            "structure_top1": (s_results[0][0].metadata.get("recipe_id"), round(1 - s_results[0][1], 3), s_results[0][0].metadata.get("section")) if s_results else None,
        })
    return rows


def run_metadata_filter(structure_store):
    query = "Which recipe uses a live starter culture incubated with milk to make a creamy fermented dish?"
    unfiltered = structure_store.similarity_search_with_score(query, k=5)
    filtered = structure_store.similarity_search_with_score(query, k=5, filter={"is_vegan": True})
    return query, unfiltered, filtered


def run_grounded_answers():
    out = []
    for question, recipe_id, keyword in GROUNDED:
        res = answer_question(question)
        cite = res["citations"][0] if res["citations"] else None
        resolved = resolve_citation(cite["chunk_id"]) if cite else None
        out.append({
            "question": question, "answer": res["answer"], "refused": res["refused"],
            "citation": cite, "resolved_recipe_id": (resolved or {}).get("recipe_id"),
            "claim_in_resolved_text": bool(resolved) and keyword.lower() in resolved["text"].lower(),
        })
    return out


def run_refusals():
    out = []
    for question in REFUSALS:
        res = answer_question(question)
        out.append({"question": question, "answer": res["answer"], "refused": res["refused"]})
    return out


def run_bonus(baseline_store, structure_store, top_k: int = 3):
    """A question spanning two sections (ingredient weight + method timing).
    Reports top-k (not top-1) from each collection: at top-1 both strategies
    turn out to return the same ingredients-only fragment for this corpus (no
    trade-off to show), so top-k is what actually reveals it - see the
    write-up for what this run found instead of the expected trade-off."""
    question = "How much fine sea salt does the sourdough recipe use, and at what point in the process is it added?"
    b_hits = baseline_store.similarity_search_with_score(question, k=top_k)
    s_hits = structure_store.similarity_search_with_score(question, k=top_k)
    b_result = [(d, 1 - s) for d, s in b_hits]
    s_result = [(d, 1 - s) for d, s in s_hits]
    b_answer = generate_grounded_answer(question, b_result)
    s_answer = generate_grounded_answer(question, s_result)
    return question, b_result, b_answer, s_result, s_answer


def main() -> None:
    tmp_dir = tempfile.mkdtemp(prefix="week3_chunking_")
    try:
        baseline_store, structure_store, baseline_chunks, structure_chunks = build_collections(tmp_dir)
        print(f"baseline chunks: {len(baseline_chunks)}   structure-aware chunks: {len(structure_chunks)}")

        rows = run_comparison(baseline_store, structure_store)
        b_hits = sum(r["baseline_hit"] for r in rows)
        s_hits = sum(r["structure_hit"] for r in rows)
        for r in rows:
            print(f"{r['id']}  baseline={'HIT' if r['baseline_hit'] else 'miss':4}  "
                  f"structure={'HIT' if r['structure_hit'] else 'miss':4}  {r['question'][:60]}")
        print(f"\nhit-in-top-5:  baseline = {b_hits}/8   structure-aware = {s_hits}/8")

        query, unfiltered, filtered = run_metadata_filter(structure_store)
        print(f"\nmetadata filter query: {query}")
        print("  unfiltered top-1:", unfiltered[0][0].metadata.get("recipe_id"))
        print("  filtered (is_vegan=True) top-1:", filtered[0][0].metadata.get("recipe_id"))

        grounded = run_grounded_answers()
        refusals = run_refusals()
        bonus = run_bonus(baseline_store, structure_store)

        with open(os.path.join(DOCS, "week3-run.md"), "w", encoding="utf-8") as f:
            f.write("(intermediate dump written by eval_week3_chunking.py; see week3-results.md for the real write-up)\n\n")
            f.write(f"baseline_hits={b_hits}/8 structure_hits={s_hits}/8\n\n")
            for r in rows:
                f.write(f"{r}\n\n")
            f.write(f"\nfilter query: {query}\n")
            f.write(f"unfiltered: {[(d.metadata.get('recipe_id'), round(1-s,3)) for d,s in unfiltered]}\n")
            f.write(f"filtered:   {[(d.metadata.get('recipe_id'), round(1-s,3)) for d,s in filtered]}\n\n")
            for g in grounded:
                f.write(f"{g}\n\n")
            for rr in refusals:
                f.write(f"{rr}\n\n")
            f.write(f"bonus question: {bonus[0]}\n")
            f.write(f"baseline top1: {[(d.metadata.get('recipe_id'), d.metadata.get('section'), round(s,3)) for d,s in bonus[1]]}\n")
            f.write(f"baseline answer: {bonus[2]}\n")
            f.write(f"structure top1: {[(d.metadata.get('recipe_id'), d.metadata.get('section'), round(s,3)) for d,s in bonus[3]]}\n")
            f.write(f"structure answer: {bonus[4]}\n")
        print(f"\nwrote {os.path.join(DOCS, 'week3-run.md')} (raw dump for write-up)")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
