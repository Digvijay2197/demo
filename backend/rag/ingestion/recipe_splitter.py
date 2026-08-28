"""Recipe-aware splitting for cookbook-style PDFs (many recipes per page).

A blind character splitter cuts a page like

    Oatmeal Buns
    Harriet Stanley
    ... ingredients / method ...
    Oatmeal Bread              <-- next recipe, same page
    DoLores Kounovsky
    ...

so that the chunk holding "Oatmeal Bread"'s ingredients often does not even
contain the words "Oatmeal Bread" - and a search for it never finds it.

This splitter instead detects each recipe's start (a title line immediately
followed by a contributor/name line) and emits one chunk per recipe, each
prefixed with its title so the name always travels with the ingredients and
method. Long recipes are sub-split but every piece keeps the title.

If a document has no such structure (a single-recipe PDF, a form, prose), the
detector returns None and the caller falls back to the normal splitter.
"""
import re
from typing import List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE

_BLOCK_CAP = max(1400, CHUNK_SIZE * 2)

_SECTION_HEADERS = {
    "breads", "soups", "vegetables", "salads", "main dishes", "cake & frostings",
    "cookies, bars, and lefse", "cookies, bars, & lefse", "pies & desserts",
    "beverages, snacks, jam, & pickles", "index", "table of contents",
    "appetizers", "desserts", "beverages", "sauces", "side dishes",
}
_UNIT_WORDS = re.compile(
    r"\b(cup|cups|tsp|teaspoon|teaspoons|tbsp|tablespoon|tablespoons|oz|ounce|ounces|"
    r"lb|lbs|pound|pounds|g|kg|ml|l|pkg|package|packages|clove|cloves|pinch|dash|"
    r"quart|pint|gallon|stick|sticks|can|cans|slice|slices)\b",
    re.IGNORECASE,
)
_NAME_FIRST_LAST = re.compile(r"^[A-Z][A-Za-z.'\-]+\s+[A-Z][A-Za-z.'\-]+")


def _looks_like_title(s: str) -> bool:
    s = s.strip()
    if not s or re.fullmatch(r"\d+", s):
        return False
    if any(ch.isdigit() for ch in s):
        return False
    if s[-1] in ".,:;!":
        return False
    if not s[0].isupper():
        return False
    words = s.split()
    if not (1 <= len(words) <= 8):
        return False
    if s.lower() in _SECTION_HEADERS:
        return False
    if "continued" in s.lower():
        return False
    if _UNIT_WORDS.search(s):
        return False
    return True


def _looks_like_contributor(s: str) -> bool:
    s = s.strip()
    if not s or any(ch.isdigit() for ch in s):
        return False
    if len(s.split()) > 14:
        return False
    low = s.lower()
    if "recipe from" in low or "family" in low or "--" in s or "&" in s:
        return True
    return bool(_NAME_FIRST_LAST.match(s))


def _flatten(pages: List[Document]) -> List[tuple]:
    """[(line, page_number), ...] across the document, blank lines dropped."""
    out = []
    for pg in pages:
        page_no = pg.metadata.get("page")
        for ln in pg.page_content.split("\n"):
            if ln.strip():
                out.append((ln.strip(), page_no))
    return out


def _is_recipe_start(lines: List[tuple], i: int) -> bool:
    if not _looks_like_title(lines[i][0]):
        return False
    if i + 1 >= len(lines):
        return False
    return _looks_like_contributor(lines[i + 1][0])


def split_recipes(pages: List[Document]) -> Optional[List[Document]]:
    """One Document per recipe, or None if the doc isn't recipe-structured."""
    lines = _flatten(pages)
    starts = [i for i in range(len(lines)) if _is_recipe_start(lines, i)]
    if len(starts) < 3:
        return None  # not a multi-recipe cookbook - let the caller fall back

    source_file = pages[0].metadata.get("source_file")
    sub = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n", ". ", " ", ""],
    )

    docs: List[Document] = []
    bounds = starts + [len(lines)]
    for k, s in enumerate(starts):
        block = lines[s:bounds[k + 1]]
        title = block[0][0].strip()
        page = block[0][1]
        body = "\n".join(l for l, _ in block if not re.fullmatch(r"\d+", l))
        if not body.strip():
            continue

        pieces = [body] if len(body) <= _BLOCK_CAP else [
            p if p.lstrip().startswith(title) else f"{title}\n{p}"
            for p in sub.split_text(body)
        ]
        for idx, text in enumerate(pieces):
            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source_file": source_file,
                        "page": page,
                        "title": pages[0].metadata.get("title", source_file),
                        "recipe_title": title,
                        "section": "recipe",
                        "chunk_index": idx,
                    },
                )
            )
    return docs or None
