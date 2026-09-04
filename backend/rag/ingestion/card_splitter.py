"""Structure-aware splitting for single-recipe "card" PDFs: a title, an
ingredient table (name / weight / baker's %), a method paragraph, and an
allergen note (see scripts/generate_fermentation_cards.py).

A blind character splitter cuts a card wherever chunk_size lands, which can
separate an ingredient row ("Fine sea salt   7 g   0.35%") from the table
header or the recipe title that gives it meaning - "7 g" of *what*, in
*which* recipe? This splitter instead recognises the card's own section
structure and keeps each section whole: the entire ingredient table becomes
one title-prefixed chunk (a row is never split from its header), and method /
allergen sections each become their own title-prefixed chunk.

If a document doesn't look like this kind of card (no ingredient-table rows
alongside a "Method" section), the detector returns None and the caller
falls back to the normal splitter - see rag/ingestion/pipeline.py.
"""
import re
from typing import List, Optional

from langchain_core.documents import Document

_SECTION_RE = re.compile(r"^(Ingredients?|Method|Allergens?|Notes?)\s*:?\s*$", re.IGNORECASE)
# A PDF table's cells extract one-per-line (row, not line, granularity), so a
# table row like "Fine sea salt | 7 g | 0.35%" comes out as three consecutive
# lines: a name line, then a bare weight line, then a bare percentage line.
_WEIGHT_RE = re.compile(r"^\d+(?:\.\d+)?\s?(?:g|kg|ml|l)$", re.IGNORECASE)
_PCT_RE = re.compile(r"^\d+(?:\.\d+)?%$")
_BARE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")
_BARE_UNIT_RE = re.compile(r"^(?:g|kg|ml|l|%)$", re.IGNORECASE)


def _flatten(pages: List[Document]) -> List[str]:
    lines: List[str] = []
    for pg in pages:
        lines.extend(ln.strip() for ln in pg.page_content.split("\n") if ln.strip())
    return lines


def _merge_split_numbers(lines: List[str]) -> List[str]:
    """A number and its unit can land on separate lines depending on how the
    PDF wrapped the cell ("500" / "g" instead of "500 g") - rejoin them
    before row-matching so it doesn't matter which way it came out."""
    merged, i = [], 0
    while i < len(lines):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if _BARE_NUMBER_RE.match(lines[i]) and nxt and _BARE_UNIT_RE.match(nxt):
            merged.append(lines[i] + ("" if nxt == "%" else " ") + nxt)
            i += 2
        else:
            merged.append(lines[i])
            i += 1
    return merged


def _table_rows(lines: List[str]) -> List[str]:
    """Reassemble (name, weight, percentage) triples out of the flattened
    per-cell lines into one "name  weight  (percentage)" row of text each."""
    lines = _merge_split_numbers(lines)
    rows, name_buf = [], []
    for i, line in enumerate(lines):
        if _PCT_RE.match(line) and i > 0 and _WEIGHT_RE.match(lines[i - 1]):
            name = " ".join(name_buf).strip()
            if name:
                rows.append(f"{name}  {lines[i - 1]}  ({line})")
            name_buf = []
        elif _WEIGHT_RE.match(line):
            continue  # consumed as part of the next percentage line above
        else:
            name_buf.append(line)
    return rows


def _sectionize(lines: List[str], title: str) -> Optional[dict]:
    """{"ingredient_rows": [...], "method": "prose", "allergens": "line"} or
    None if this isn't a recognisable card."""
    sections: dict = {"_preamble": []}
    current = "_preamble"
    for line in lines:
        m = _SECTION_RE.match(line)
        if m:
            current = "ingredients" if m.group(1).lower().startswith("ingredient") else m.group(1).lower().rstrip("s")
            sections.setdefault(current, [])
            continue
        if line != title:  # the title line itself is already carried separately
            sections[current].append(line)

    rows = _table_rows(sections.get("ingredients", []))
    if len(rows) < 2 or "method" not in sections:
        return None  # not a card with a real ingredient table - let the caller fall back

    # Anything before the first recognised section (e.g. a "Cuisine: X |
    # Dietary: Y" line) still belongs with the card - fold it into the
    # ingredients chunk rather than silently dropping it.
    preamble = " ".join(sections.get("_preamble", []))

    return {
        "preamble": preamble,
        "ingredient_rows": rows,
        "method": " ".join(sections.get("method", [])),
        "allergens": " ".join(sections.get("allergen", [])),
        "notes": " ".join(sections.get("note", [])),
    }


def split_cards(pages: List[Document]) -> Optional[List[Document]]:
    """One chunk per section (ingredients / method / allergens), each
    prefixed with the recipe title, or None if `pages` isn't a single
    structured recipe card."""
    if not pages:
        return None
    title = (pages[0].metadata.get("title") or pages[0].metadata.get("source_file", "")).strip()
    base_meta = {k: v for k, v in pages[0].metadata.items() if k != "page"}
    page_no = pages[0].metadata.get("page")

    card = _sectionize(_flatten(pages), title)
    if card is None:
        return None

    def _chunk(section: str, body: str) -> Document:
        return Document(
            page_content=f"{title}\n{body}",
            metadata={**base_meta, "page": page_no, "recipe_title": title, "section": section},
        )

    ingredients_body = "Ingredients:\n" + "\n".join(card["ingredient_rows"])
    if card["preamble"]:
        ingredients_body = card["preamble"] + "\n" + ingredients_body
    docs = [_chunk("ingredients", ingredients_body)]
    if card["method"]:
        docs.append(_chunk("method", "Method: " + card["method"]))
    tail = " ".join(x for x in (card["allergens"], card["notes"]) if x)
    if tail:
        docs.append(_chunk("allergen", "Allergens: " + tail))
    return docs
