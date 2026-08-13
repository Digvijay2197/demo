import re
from rag.chunking.types import ParsedIngredient, ParsedRecipe

FRONT_MATTER_RE = re.compile(r"^([a-zA-Z_]+):\s*(.+)$")


def _parse_front_matter(block: str) -> dict:
    fields = {}
    for line in block.split("\n"):
        m = FRONT_MATTER_RE.match(line.strip())
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def _parse_ingredient_table(section: str):
    rows = [l.strip() for l in section.split("\n") if l.strip().startswith("|")]
    ingredients = []
    for row in rows:
        cells = [c.strip() for c in row.split("|") if c.strip()]
        if len(cells) < 3:
            continue
        if cells[0].lower() == "ingredient":
            continue
        if re.match(r"^-+$", cells[0]):
            continue
        ingredients.append(ParsedIngredient(name=cells[0], weight=cells[1], percentage=cells[2]))
    return ingredients


def parse_recipe_card(raw_text: str, source_file: str) -> ParsedRecipe:
    sections = raw_text.split("\n## ")
    front_matter = _parse_front_matter(sections[0])

    ingredients = []
    method = ""
    allergen_note = ""

    for section in sections[1:]:
        lines = section.split("\n")
        heading = lines[0].strip().lower()
        body = "\n".join(lines[1:]).strip()
        if heading.startswith("ingredients"):
            ingredients = _parse_ingredient_table(body)
        elif heading.startswith("method"):
            method = body
        elif heading.startswith("allergen"):
            allergen_note = body

    dietary_tags = [t.strip() for t in front_matter.get("dietary_tags", "").split(",") if t.strip()]

    return ParsedRecipe(
        recipe_id=front_matter.get("recipe_id", ""),
        title=front_matter.get("title", ""),
        cuisine=front_matter.get("cuisine", ""),
        dietary_tags=dietary_tags,
        source_file=source_file,
        ingredients=ingredients,
        method=method,
        allergen_note=allergen_note,
        raw_text=raw_text,
    )
