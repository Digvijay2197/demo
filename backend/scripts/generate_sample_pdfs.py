"""Generate sample recipe PDFs into data/pdfs/ for trying out the RAG bot.

These stand in for "any recipe PDF you drop in the folder" - text-based,
multi-section, with quantities the bot can be quizzed on. Regenerate any time:

    python scripts/generate_sample_pdfs.py

Then index them with:  python scripts/ingest.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())

import pymupdf  # PyMuPDF

from rag.config import PDF_DIR

RECIPES = [
    {
        "filename": "neapolitan-margherita-pizza.pdf",
        "title": "Neapolitan Margherita Pizza",
        "meta": {
            "Cuisine": "Italian",
            "Serves": "4 (two 30 cm pizzas)",
            "Prep time": "30 minutes, plus 24 hours cold proof",
            "Cook time": "90 seconds per pizza at 450 C (or 8-10 minutes at 250 C)",
            "Dietary": "vegetarian; contains gluten and dairy",
        },
        "sections": [
            (
                "Dough ingredients (makes 2 balls of 280 g)",
                [
                    "500 g Italian 00 flour (W300 strength if available)",
                    "325 g cold water (65% hydration)",
                    "10 g fine sea salt",
                    "2 g fresh yeast, or 0.7 g active dry yeast",
                ],
            ),
            (
                "Topping ingredients (per pizza)",
                [
                    "80 g San Marzano tomatoes, hand-crushed, lightly salted",
                    "70 g fresh cow's-milk mozzarella (fior di latte), torn and drained",
                    "4-5 fresh basil leaves",
                    "1 teaspoon extra-virgin olive oil",
                    "A pinch of sea salt",
                ],
            ),
            (
                "Method",
                [
                    "Dissolve the yeast in the water. Add the flour and mix until no dry spots remain, then rest 20 minutes.",
                    "Add the salt and knead 10-12 minutes until smooth and elastic. The dough should pass a windowpane test.",
                    "Bulk ferment at room temperature for 2 hours, then divide into two 280 g balls.",
                    "Place the balls in a covered container and cold-proof in the fridge for 24 hours (up to 72).",
                    "Remove the dough 2 hours before baking and let it come to room temperature.",
                    "Stretch one ball by hand to 30 cm, leaving a 1.5 cm border for the cornicione. Do not use a rolling pin.",
                    "Spread 80 g crushed tomato, add the mozzarella, drizzle with olive oil.",
                    "Bake at maximum heat until the crust is blistered and charred in spots. Finish with fresh basil.",
                ],
            ),
            (
                "Notes",
                [
                    "Allergens: wheat (gluten) in the dough, dairy in the mozzarella.",
                    "For a vegan version, replace the mozzarella with a cashew-based alternative; the dough is already vegan.",
                    "The 24-hour cold proof is what develops flavour and digestibility - do not skip it.",
                ],
            ),
        ],
    },
    {
        "filename": "thai-green-chicken-curry.pdf",
        "title": "Thai Green Chicken Curry (Gaeng Keow Wan Gai)",
        "meta": {
            "Cuisine": "Thai",
            "Serves": "4 with steamed jasmine rice",
            "Prep time": "20 minutes",
            "Cook time": "25 minutes",
            "Dietary": "gluten-free; contains fish and shellfish (in the curry paste)",
        },
        "sections": [
            (
                "Ingredients",
                [
                    "4 tablespoons Thai green curry paste (about 60 g)",
                    "400 ml full-fat coconut milk",
                    "500 g boneless chicken thigh, sliced 1 cm thick",
                    "2 tablespoons fish sauce",
                    "1 tablespoon palm sugar, chopped",
                    "150 g Thai apple eggplant, quartered",
                    "100 g bamboo shoots, drained and rinsed",
                    "4 kaffir lime leaves, torn",
                    "1 large red chilli, sliced on the bias",
                    "A handful of Thai sweet basil leaves",
                ],
            ),
            (
                "Method",
                [
                    "Spoon the thick coconut cream from the top of the can into a wok over medium heat and simmer 3-4 minutes until it splits and the oil surfaces.",
                    "Add the green curry paste and fry 2 minutes until deeply fragrant.",
                    "Add the chicken and stir to coat, cooking 3 minutes until the outside turns opaque.",
                    "Pour in the remaining coconut milk plus 150 ml water. Bring to a gentle simmer.",
                    "Season with the fish sauce and palm sugar. Add the eggplant, bamboo shoots and lime leaves.",
                    "Simmer 12-15 minutes until the eggplant is tender and the chicken is cooked through.",
                    "Turn off the heat, stir through the basil and sliced chilli, and serve with jasmine rice.",
                ],
            ),
            (
                "Notes",
                [
                    "Allergens: fish sauce (fish) and shrimp paste inside most green curry pastes (shellfish).",
                    "Vegetarian swap: use a shrimp-paste-free paste, replace fish sauce with light soy plus a little salt, and use firm tofu and vegetables instead of chicken.",
                    "Do not boil hard after adding the basil or the curry will dull in colour and aroma.",
                ],
            ),
        ],
    },
]

_CSS = """
* { font-family: sans-serif; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 4px 0; }
table { margin: 6px 0 14px 0; border-collapse: collapse; }
td { font-size: 10.5px; padding: 1px 10px 1px 0; vertical-align: top; }
td.k { color: #555; white-space: nowrap; }
h2 { font-size: 13px; margin: 14px 0 4px 0; border-bottom: 1px solid #bbb; padding-bottom: 2px; }
ol, ul { margin: 4px 0 4px 0; padding-left: 20px; }
li { font-size: 11px; margin: 3px 0; line-height: 1.35; }
"""


def _recipe_html(recipe: dict) -> str:
    meta_rows = "".join(
        f"<tr><td class='k'>{k}</td><td>{v}</td></tr>" for k, v in recipe["meta"].items()
    )
    blocks = [f"<h1>{recipe['title']}</h1>", f"<table>{meta_rows}</table>"]
    for heading, items in recipe["sections"]:
        tag = "ol" if heading.lower().startswith("method") else "ul"
        lis = "".join(f"<li>{it}</li>" for it in items)
        blocks.append(f"<h2>{heading}</h2><{tag}>{lis}</{tag}>")
    return f"<style>{_CSS}</style>" + "".join(blocks)


def _write_pdf(recipe: dict, out_dir: str) -> str:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 portrait, points
    rect = pymupdf.Rect(50, 50, 545, 792)
    result = page.insert_htmlbox(rect, _recipe_html(recipe))
    spare_height = result[0] if isinstance(result, (tuple, list)) else result
    if spare_height is not None and spare_height < 0:
        print(f"  warning: {recipe['filename']} content was scaled to fit one page")

    path = os.path.join(out_dir, recipe["filename"])
    doc.set_metadata({"title": recipe["title"], "subject": "Sample recipe for the RAG demo"})
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    return path


def main() -> None:
    os.makedirs(PDF_DIR, exist_ok=True)
    for recipe in RECIPES:
        path = _write_pdf(recipe, PDF_DIR)
        size_kb = os.path.getsize(path) / 1024
        print(f"wrote {path}  ({size_kb:.1f} KB)")
    print(f"\n{len(RECIPES)} sample PDFs in {PDF_DIR}")
    print("Next: python scripts/ingest.py")


if __name__ == "__main__":
    main()
