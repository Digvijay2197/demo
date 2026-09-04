"""Generate the Week 3 fermentation-chapter recipe cards into data/pdfs/.

Each card is structured (unlike the free-form recipes from
generate_sample_pdfs.py): a title, an ingredient TABLE (name / weight /
baker's percentage), a Method paragraph, and an Allergens line - the shape
rag/ingestion/card_splitter.py is built to recognise. Regenerate any time:

    python scripts/generate_fermentation_cards.py

Then index them the normal way: python scripts/ingest.py
"""
import os
import sys

sys.path.insert(0, os.getcwd())

import pymupdf  # PyMuPDF

from rag.config import PDF_DIR

# recipe_id, title, cuisine, dietary_tags, ingredient rows (name, weight, baker's %),
# method prose, allergens line
CARDS = [
    (
        "sourdough-2kg", "2kg Country Sourdough Loaf", "Western / Artisan Bread",
        ["vegan"],
        [
            ("Bread flour", "1000 g", "100%"),
            ("Water", "750 g", "75%"),
            ("Fine sea salt", "7 g", "0.35%"),
            ("Active starter", "200 g", "20%"),
        ],
        "Mix the flour and water and autolyse for 30 minutes. Add the starter and salt and "
        "combine thoroughly. Bulk ferment for 4 hours at room temperature, folding the dough "
        "every 30 minutes for the first 2 hours. Shape into a boule and cold-proof in the "
        "fridge overnight, at least 8 hours. Score and bake covered at 230 C for 20 minutes, "
        "then uncovered at 220 C for 25 minutes until deep brown.",
        "Contains gluten.",
    ),
    (
        "kimchi-napa", "Napa Cabbage Kimchi", "Korean",
        ["vegan", "gluten-free"],
        [
            ("Napa cabbage", "1000 g", "100%"),
            ("Coarse sea salt", "50 g", "5%"),
            ("Gochugaru", "60 g", "6%"),
            ("Fish sauce alternative (soy)", "30 g", "3%"),
            ("Garlic, minced", "20 g", "2%"),
        ],
        "Quarter and salt the cabbage, then let it sit for 2 hours until wilted, turning "
        "occasionally. Rinse thoroughly and drain well. Mix the gochugaru, soy-based fish "
        "sauce alternative and garlic into a paste. Rub the paste between every leaf of the "
        "drained cabbage. Pack tightly into a clean jar, pressing out air pockets, and "
        "ferment at room temperature for 3 to 5 days, then refrigerate.",
        "Contains soy. Gluten-free as written.",
    ),
    (
        "sauerkraut-classic", "Classic Sauerkraut", "German",
        ["vegan", "gluten-free"],
        [
            ("Green cabbage, shredded", "1000 g", "100%"),
            ("Fine sea salt", "20 g", "2%"),
            ("Caraway seeds", "4 g", "0.4%"),
        ],
        "Massage the salt into the shredded cabbage until it releases enough liquid to "
        "submerge itself, about 10 minutes. Stir in the caraway seeds. Pack tightly into a "
        "fermentation crock, weighting the cabbage below the brine line. Ferment at a cool "
        "room temperature for 2 to 4 weeks, skimming any surface scum, tasting weekly until "
        "the sourness suits you.",
        "Gluten-free. No common allergens.",
    ),
    (
        "kombucha-ginger", "Sweet Kombucha with Ginger", "American",
        ["vegan", "gluten-free"],
        [
            ("Water", "1000 g", "100%"),
            ("White sugar", "100 g", "10%"),
            ("Black tea leaves", "8 g", "0.8%"),
            ("SCOBY + starter tea", "200 g", "20%"),
            ("Fresh ginger, sliced", "15 g", "1.5%"),
        ],
        "Brew the tea, dissolve the sugar into it while hot, then cool completely to room "
        "temperature. Pour into a clean glass jar, add the SCOBY and starter tea, cover with "
        "a breathable cloth, and ferment 7 to 10 days away from direct sunlight. Strain into "
        "bottles with the fresh ginger for a second ferment of 2 to 3 days at room "
        "temperature before refrigerating.",
        "Gluten-free. Caffeine from black tea.",
    ),
    (
        "miso-soybean", "Homemade Soybean Miso Paste", "Japanese",
        ["vegan", "gluten-free"],
        [
            ("Dehulled soybeans", "500 g", "100%"),
            ("Koji rice", "500 g", "100%"),
            ("Sea salt", "150 g", "30%"),
            ("Reserved cooking liquid", "100 g", "20%"),
        ],
        "Soak and cook the soybeans until very tender, then mash while still warm. Mix the "
        "koji rice thoroughly with the salt. Combine the mashed soybeans, salted koji and "
        "reserved cooking liquid into a firm, moldable paste. Pack tightly into a clean "
        "crock, pressing out air pockets, weight it down, and ferment in a cool, dark place "
        "for 6 to 12 months, checking occasionally for surface mold to skim off.",
        "Contains soy. Produced with koji (Aspergillus oryzae); no gluten-containing grains used.",
    ),
    (
        "yogurt-dairy", "Homemade Dairy Yogurt", "Mediterranean / Middle Eastern",
        ["vegetarian", "gluten-free", "contains-dairy"],
        [
            ("Whole milk", "1000 g", "100%"),
            ("Live yogurt starter culture", "30 g", "3%"),
        ],
        "Heat the milk to 85 C, stirring occasionally to prevent scorching, then cool to "
        "43-46 C. Whisk in the live starter culture until fully dissolved. Pour into a clean "
        "container, cover, and incubate at 43-46 C for 6 to 8 hours until set, without "
        "disturbing it. Refrigerate for at least 4 hours before serving to thicken further.",
        "Contains dairy. Gluten-free.",
    ),
]

_CSS = """
* { font-family: sans-serif; color: #1a1a1a; }
h1 { font-size: 20px; margin: 0 0 4px 0; }
h3 { font-size: 11px; font-weight: normal; color: #555; margin: 0 0 12px 0; }
h2 { font-size: 13px; margin: 14px 0 4px 0; border-bottom: 1px solid #bbb; padding-bottom: 2px; }
table { margin: 6px 0 14px 0; border-collapse: collapse; }
td { font-size: 10.5px; padding: 1px 14px 1px 0; vertical-align: top; }
p { font-size: 11px; margin: 4px 0; line-height: 1.4; }
"""


def _card_html(cuisine: str, tags: list, rows: list, method: str, allergens: str) -> str:
    table_rows = "".join(
        f"<tr><td>{name}</td><td>{weight}</td><td>{pct}</td></tr>" for name, weight, pct in rows
    )
    return (
        f"<h3>Cuisine: {cuisine} &nbsp;|&nbsp; Dietary: {', '.join(tags)}</h3>"
        f"<h2>Ingredients</h2><table>{table_rows}</table>"
        f"<h2>Method</h2><p>{method}</p>"
        f"<h2>Allergens</h2><p>{allergens}</p>"
    )


def _write_pdf(recipe_id: str, title: str, cuisine: str, tags: list, rows, method, allergens, out_dir: str) -> str:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    rect = pymupdf.Rect(50, 50, 545, 792)
    html = f"<h1>{title}</h1>" + _card_html(cuisine, tags, rows, method, allergens)
    page.insert_htmlbox(rect, f"<style>{_CSS}</style>{html}")

    filename = f"{recipe_id}.pdf"
    path = os.path.join(out_dir, filename)
    # Structured metadata for the ingestion pipeline (see rag/ingestion/pdf_loader.py:
    # _structured_metadata parses "key=value;..." out of the keywords field).
    keywords = f"recipe_id={recipe_id};cuisine={cuisine};dietary_tags={','.join(tags)}"
    doc.set_metadata({"title": title, "subject": "Fermentation chapter recipe card", "keywords": keywords})
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    return path


def main() -> None:
    os.makedirs(PDF_DIR, exist_ok=True)
    for recipe_id, title, cuisine, tags, rows, method, allergens in CARDS:
        path = _write_pdf(recipe_id, title, cuisine, tags, rows, method, allergens, PDF_DIR)
        size_kb = os.path.getsize(path) / 1024
        print(f"wrote {path}  ({size_kb:.1f} KB)")
    print(f"\n{len(CARDS)} fermentation cards in {PDF_DIR}")
    print("Next: python scripts/ingest.py")


if __name__ == "__main__":
    main()
