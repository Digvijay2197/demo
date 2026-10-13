"""Build capstone/data/recipes.json - the stand-in for the client's CMS export.

The real brief has a 600-recipe export. That export is not in this repo, so this
script generates a small corpus with the SAME STRUCTURE and the same traps:

  * every record carries structured `allergens` and `may_contain` fields
    (the declaration - an exact-match problem, never prose);
  * 8 recipes exist in BOTH an `original` and a `reformulated-2025` version
    after a "supplier change", and the reformulation changes the allergen
    declaration (butter -> nut-oil blend, new chocolate supplier, ...);
  * meat / fish / egg recipes carry the food-safety internal temperature.

Ingredient allergen tags come from a small lexicon (first match wins) unless a
recipe gives them explicitly; the declaration is derived from the tags, and
tests/test_capstone_domain.py asserts declaration == union(ingredient tags) so
the two can never drift apart silently.

    python -m capstone.build_corpus
"""
from __future__ import annotations

import json
import os
import re

OUT = os.path.join(os.path.dirname(__file__), "data", "recipes.json")

# (regex, classes) - first match wins. Order matters ("almond milk" before "milk").
LEXICON = [
    (r"\bnut-oil blend|\balmond[- ]oil|almond-wheat", None),  # explicit tags required
    (r"hazelnut spread", ["tree_nut", "dairy"]),
    (r"almond milk|almond flour|almond meal|almond butter|\bwalnut|\bpecan|\bcashew|"
     r"hazelnut|pine nut|pistachio|\balmond", ["tree_nut"]),
    (r"peanut", ["peanut"]),
    (r"oat milk|coconut milk|coconut cream|rice milk|oat cream", []),
    (r"soy milk|tofu|edamame", ["soy"]),
    (r"soy sauce", ["soy", "gluten"]),
    (r"tamari", ["soy"]),
    (r"coconut aminos", []),
    (r"chocolate chips", ["dairy", "soy"]),
    (r"cocoa", []),
    (r"whole milk|\bmilk\b|butter\b(?! ?bean)|cream\b|cheddar|parmesan|mozzarella|feta|yogurt|ghee",
     ["dairy"]),
    (r"sunflower seed butter|seed butter", []),
    (r"\begg(s)?\b(?!plant)", ["egg"]),
    (r"all-purpose flour|bread flour|wheat flour|flatbread dough|pasta|spaghetti|penne|breadcrumbs|"
     r"tortilla|couscous", ["gluten"]),
    (r"oat flour|rolled oats|rice flour|rice noodles|\brice\b", []),
    (r"shrimp|prawn|crab", ["shellfish"]),
    (r"salmon|\bcod\b|fish sauce|anchov", ["fish"]),
    (r"tahini|sesame", ["sesame"]),
]


def tag(item: str) -> list[str]:
    for pat, classes in LEXICON:
        if re.search(pat, item, re.I):
            if classes is None:
                raise ValueError(f"{item!r} needs explicit allergen tags")
            return sorted(classes)
    return []


def I(item, qty, unit="g", tags=None):  # noqa: E741 - short on purpose, used ~200 times
    return {"item": item, "qty": qty, "unit": unit,
            "allergens": sorted(tags) if tags is not None else tag(item)}


# ---------------------------------------------------------------------------
# Recipes. `reform` (optional) describes the reformulated-2025 version.
# ---------------------------------------------------------------------------
BASE = [
    dict(id="R-101", title="Classic Shortbread", cuisine="british", servings=12, prep=15, cook=20,
         oven_c=160, tags=["baking", "biscuit"],
         ing=[I("all-purpose flour", 250), I("butter", 175), I("caster sugar", 75),
              I("fine salt", None, "pinch")],
         steps=["Cream the butter and sugar until pale.", "Work in the flour and salt to a dough.",
                "Press into a tin, prick with a fork and chill 20 minutes.",
                "Bake at 160C for 20 minutes until pale gold; cool in the tin."],
         reform=dict(swap={"butter": I("nut-oil blend baking spread (almond oil)", 175, "g", ["tree_nut"])},
                     may_contain=[], note="Supplier change: butter replaced by an almond-oil blend baking spread.")),
    dict(id="R-102", title="Fluffy Pancakes", cuisine="american", servings=4, prep=10, cook=15,
         tags=["breakfast"],
         ing=[I("all-purpose flour", 200), I("whole milk", 300, "ml"), I("egg", 2, ""),
              I("butter", 30), I("caster sugar", 20), I("baking powder", 8)],
         steps=["Whisk the dry ingredients.", "Beat in milk and egg, then the melted fat.",
                "Rest the batter 10 minutes.", "Cook 2 minutes a side over medium heat."],
         reform=dict(swap={"whole milk": I("oat milk", 300, "ml"), "butter": I("sunflower oil", 30, "ml")},
                     may_contain=[], note="Reformulated dairy-free: oat milk and sunflower oil replace milk and butter.")),
    dict(id="R-103", title="Chocolate Chip Cookies", cuisine="american", servings=24, prep=20, cook=12,
         oven_c=180, tags=["baking", "biscuit"],
         ing=[I("all-purpose flour", 280), I("butter", 170), I("brown sugar", 150), I("egg", 2, ""),
              I("chocolate chips", 200), I("baking soda", 5)],
         steps=["Cream butter and sugar.", "Beat in the eggs, then fold in flour and soda.",
                "Stir in the chips and scoop onto trays.", "Bake at 180C for 12 minutes."],
         reform=dict(swap={"chocolate chips": I("chocolate chips (new supplier)", 200, "g", ["dairy", "soy"])},
                     may_contain=["peanut", "tree_nut"],
                     note="New chocolate supplier: shared line, 'may contain peanuts and tree nuts' declared.")),
    dict(id="R-104", title="Banana Bread", cuisine="american", servings=8, prep=15, cook=55,
         oven_c=175, tags=["baking", "loaf"],
         ing=[I("all-purpose flour", 250), I("ripe banana", 3, ""), I("butter", 100), I("egg", 2, ""),
              I("caster sugar", 120), I("baking soda", 5)],
         steps=["Mash the bananas and beat with butter, sugar and eggs.", "Fold in flour and soda.",
                "Pour into a lined loaf tin.", "Bake at 175C for 55 minutes until a skewer comes out clean."],
         reform=dict(swap={"all-purpose flour": I("almond-wheat flour blend", 250, "g", ["tree_nut", "gluten"])},
                     may_contain=[], note="Flour replaced by an almond-wheat blend for moisture.")),
    dict(id="R-105", title="Chicken Stir-Fry", cuisine="chinese", servings=4, prep=15, cook=12,
         tags=["dinner", "poultry"], temp=(74, "chicken"),
         ing=[I("chicken breast", 500), I("soy sauce", 45, "ml"), I("broccoli", 300), I("garlic", 3, "cloves"),
              I("vegetable oil", 30, "ml"), I("cooked rice", 600)],
         steps=["Slice the chicken and marinate in half the sauce.", "Stir-fry the chicken over high heat, 6 minutes.",
                "Add broccoli, garlic and the rest of the sauce; cook 5 minutes.", "Serve over rice."],
         reform=dict(swap={"soy sauce": I("coconut aminos", 45, "ml")}, may_contain=[],
                     note="Soy sauce replaced by coconut aminos (soy-free, gluten-free).")),
    dict(id="R-106", title="Peanut Noodle Bowl", cuisine="thai", servings=4, prep=15, cook=10,
         tags=["dinner", "noodles"],
         ing=[I("rice noodles", 250), I("peanut butter", 90), I("soy sauce", 30, "ml"), I("lime juice", 30, "ml"),
              I("cucumber", 1, ""), I("sesame oil", 10, "ml", ["sesame"])],
         steps=["Boil the noodles and rinse.", "Whisk peanut butter, soy sauce, lime and sesame oil into a sauce.",
                "Toss with noodles and sliced cucumber."],
         reform=dict(swap={"peanut butter": I("sunflower seed butter", 90, "g")}, may_contain=["peanut"],
                     note="Peanut butter replaced by sunflower seed butter; shared-facility 'may contain peanuts'.")),
    dict(id="R-107", title="Oat Granola Bars", cuisine="american", servings=12, prep=15, cook=25,
         oven_c=170, tags=["snack", "baking"],
         ing=[I("rolled oats", 250), I("honey", 120, "ml"), I("sunflower seeds", 60), I("butter", 80),
              I("brown sugar", 50)],
         steps=["Melt butter, honey and sugar together.", "Stir in oats and seeds and press into a tin.",
                "Bake at 170C for 25 minutes; cool fully before cutting."],
         reform=dict(swap={"butter": I("peanut butter", 80, "g")}, may_contain=[],
                     note="Binder changed from butter to peanut butter.")),
    dict(id="R-108", title="Fudgy Brownies", cuisine="american", servings=16, prep=15, cook=30,
         oven_c=175, tags=["baking", "dessert"],
         ing=[I("butter", 170), I("cocoa powder", 60), I("caster sugar", 200), I("egg", 3, ""),
              I("all-purpose flour", 100)],
         steps=["Melt the butter and beat in sugar and cocoa.", "Beat in eggs, fold in flour.",
                "Pour into a lined tin.", "Bake at 175C for 30 minutes - the centre should stay fudgy."],
         reform=dict(add=[I("hazelnut spread swirl", 80, "g")], may_contain=[],
                     note="A hazelnut-spread swirl added to the batter.")),
    # ---- recipes with a single (original) version -------------------------
    dict(id="R-201", title="Lemon Herb Roast Chicken Thighs", cuisine="mediterranean", servings=4, prep=15,
         cook=45, oven_c=200, tags=["dinner", "poultry"], temp=(74, "chicken"),
         ing=[I("chicken thighs", 8, ""), I("lemon", 1, ""), I("olive oil", 30, "ml"), I("thyme", 4, "sprigs"),
              I("garlic", 4, "cloves")],
         steps=["Toss the thighs with oil, lemon, thyme and garlic.", "Roast at 200C for 45 minutes.",
                "Rest 5 minutes before serving."]),
    dict(id="R-202", title="Pork Chops with Apples", cuisine="european", servings=4, prep=10, cook=20,
         tags=["dinner"], temp=(63, "pork"),
         ing=[I("pork chops", 4, ""), I("apples", 2, ""), I("olive oil", 20, "ml"), I("sage", 6, "leaves")],
         steps=["Sear the chops 4 minutes a side.", "Add sliced apples and sage and cook 8 minutes.", "Rest 3 minutes."]),
    dict(id="R-203", title="Beef Meatballs in Tomato Sauce", cuisine="italian", servings=4, prep=20, cook=30,
         tags=["dinner"], temp=(71, "ground beef"),
         ing=[I("ground beef", 500), I("breadcrumbs", 60), I("egg", 1, ""), I("parmesan", 40),
              I("passata", 500, "ml")],
         steps=["Mix beef, crumbs, egg and parmesan and roll into balls.", "Brown, then simmer in passata 25 minutes."]),
    dict(id="R-204", title="Baked Salmon with Dill", cuisine="nordic", servings=4, prep=10, cook=15,
         oven_c=200, tags=["dinner", "fish"], temp=(63, "fish"),
         ing=[I("salmon fillets", 4, ""), I("dill", 10), I("lemon", 1, ""), I("olive oil", 15, "ml")],
         steps=["Place the fillets on a tray with oil, dill and lemon.", "Bake at 200C for 15 minutes."]),
    dict(id="R-205", title="Turkey Burgers", cuisine="american", servings=4, prep=15, cook=12,
         tags=["dinner", "poultry"], temp=(74, "turkey"),
         ing=[I("ground turkey", 500), I("onion", 1, ""), I("breadcrumbs", 40), I("egg", 1, "")],
         steps=["Mix everything and shape four patties.", "Grill or pan-fry 6 minutes a side."]),
    dict(id="R-206", title="Creamy Tomato Soup", cuisine="european", servings=4, prep=10, cook=25,
         tags=["soup"],
         ing=[I("tinned tomatoes", 800), I("onion", 1, ""), I("cream", 100, "ml"), I("vegetable stock", 400, "ml")],
         steps=["Sweat the onion, add tomatoes and stock, simmer 20 minutes.", "Blend and stir in the cream."]),
    dict(id="R-207", title="Red Lentil Dal", cuisine="indian", servings=4, prep=10, cook=35,
         tags=["dinner", "vegan"],
         ing=[I("red lentils", 300), I("onion", 1, ""), I("turmeric", 5), I("tinned tomatoes", 400),
              I("coconut milk", 200, "ml")],
         steps=["Fry onion and turmeric.", "Add lentils, tomatoes and 600 ml water; simmer 30 minutes.",
                "Stir in the coconut milk."]),
    dict(id="R-208", title="Mushroom Risotto", cuisine="italian", servings=4, prep=10, cook=30,
         tags=["dinner"],
         ing=[I("arborio rice", 300), I("mushrooms", 300), I("butter", 40), I("parmesan", 50),
              I("vegetable stock", 1000, "ml")],
         steps=["Fry the mushrooms in butter.", "Add rice and ladle in hot stock for 25 minutes.", "Finish with parmesan."]),
    dict(id="R-209", title="Pesto Pasta", cuisine="italian", servings=4, prep=10, cook=12,
         tags=["dinner", "vegetarian"],
         ing=[I("spaghetti", 320), I("basil", 60), I("pine nuts", 40), I("parmesan", 50), I("olive oil", 80, "ml")],
         steps=["Boil the spaghetti.", "Blitz basil, pine nuts, parmesan and oil into pesto.", "Toss together."]),
    dict(id="R-210", title="Classic Hummus", cuisine="levantine", servings=6, prep=10, cook=0,
         tags=["dip", "vegan"],
         ing=[I("chickpeas", 400), I("tahini", 60), I("lemon juice", 40, "ml"), I("garlic", 1, "cloves")],
         steps=["Blend everything with 3 tablespoons of cold water until smooth."]),
    dict(id="R-211", title="Shrimp Tacos", cuisine="mexican", servings=4, prep=15, cook=6,
         tags=["dinner"],
         ing=[I("shrimp", 400), I("flour tortillas", 8, "", ["gluten"]), I("red cabbage", 150), I("lime", 2, "")],
         steps=["Sear the shrimp 3 minutes a side.", "Serve in warm tortillas with cabbage and lime."]),
    dict(id="R-212", title="Egg Fried Rice", cuisine="chinese", servings=4, prep=10, cook=10,
         tags=["dinner"], temp=(74, "egg dishes"),
         ing=[I("cooked rice", 600), I("egg", 3, ""), I("soy sauce", 30, "ml"), I("spring onion", 4, "")],
         steps=["Scramble the eggs in a hot wok until set.", "Add rice and soy sauce and fry 4 minutes."]),
    dict(id="R-213", title="Apple Crumble", cuisine="british", servings=6, prep=20, cook=40,
         oven_c=180, tags=["dessert", "baking"],
         ing=[I("apples", 800), I("all-purpose flour", 150), I("butter", 100), I("rolled oats", 50),
              I("brown sugar", 80)],
         steps=["Slice the apples into a dish.", "Rub butter into flour, oats and sugar and scatter over.",
                "Bake at 180C for 40 minutes."]),
    dict(id="R-214", title="Vegetable Coconut Curry", cuisine="thai", servings=4, prep=15, cook=25,
         tags=["dinner", "vegan"],
         ing=[I("coconut milk", 400, "ml"), I("mixed vegetables", 500), I("curry paste", 40), I("rice", 300)],
         steps=["Fry the paste, add coconut milk and vegetables, simmer 20 minutes.", "Serve over rice."]),
    dict(id="R-215", title="Margherita Flatbread", cuisine="italian", servings=2, prep=10, cook=12,
         oven_c=230, tags=["dinner", "vegetarian"],
         ing=[I("flatbread dough", 250), I("mozzarella", 125), I("tomato passata", 100, "ml"), I("basil", 10)],
         steps=["Stretch the dough, top with passata and cheese.", "Bake at 230C for 12 minutes; scatter basil."]),
    dict(id="R-216", title="Tofu Veggie Scramble", cuisine="american", servings=2, prep=5, cook=10,
         tags=["breakfast", "vegan"],
         ing=[I("firm tofu", 250), I("spinach", 100), I("turmeric", 2), I("olive oil", 15, "ml")],
         steps=["Crumble the tofu into hot oil with turmeric.", "Fold in spinach until wilted."]),
    dict(id="R-217", title="Overnight Oats", cuisine="american", servings=1, prep=5, cook=0,
         tags=["breakfast", "no-cook"],
         ing=[I("rolled oats", 50), I("whole milk", 150, "ml"), I("honey", 10, "ml"), I("chia seeds", 10)],
         steps=["Stir everything together in a jar and refrigerate overnight."]),
    dict(id="R-218", title="Vegetable Frittata", cuisine="european", servings=4, prep=10, cook=20,
         tags=["dinner", "vegetarian"], temp=(74, "egg dishes"),
         ing=[I("egg", 6, ""), I("whole milk", 100, "ml"), I("cheddar", 60), I("spinach", 100), I("onion", 1, "")],
         steps=["Soften the onion and spinach.", "Pour over beaten eggs, milk and cheese.",
                "Cook gently 15 minutes until set through."]),
]

# Test-kitchen substitutions table (ingredient -> options). Several options carry
# an allergen of their own - that is what makes the bonus (substitution chain) real.
SUBSTITUTIONS = {
    "whole milk": [
        {"to": "almond milk", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "oat milk", "ratio": 1.0, "allergens": []},
        {"to": "soy milk", "ratio": 1.0, "allergens": ["soy"]},
        {"to": "coconut milk", "ratio": 1.0, "allergens": []}],
    "butter": [
        {"to": "vegan butter (almond-oil blend)", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "coconut oil", "ratio": 0.8, "allergens": []},
        {"to": "sunflower oil", "ratio": 0.75, "allergens": []}],
    "egg": [
        {"to": "flax egg", "ratio": 1.0, "allergens": []},
        {"to": "applesauce", "ratio": 1.0, "allergens": []}],
    "all-purpose flour": [
        {"to": "almond flour", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "oat flour", "ratio": 1.0, "allergens": []},
        {"to": "rice flour", "ratio": 1.0, "allergens": []}],
    "cream": [
        {"to": "cashew cream", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "coconut cream", "ratio": 1.0, "allergens": []}],
    "peanut butter": [
        {"to": "almond butter", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "sunflower seed butter", "ratio": 1.0, "allergens": []},
        {"to": "tahini", "ratio": 1.0, "allergens": ["sesame"]}],
    "soy sauce": [
        {"to": "coconut aminos", "ratio": 1.0, "allergens": []},
        {"to": "tamari", "ratio": 1.0, "allergens": ["soy"]}],
    "parmesan": [
        {"to": "cashew parmesan", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "nutritional yeast", "ratio": 0.5, "allergens": []}],
    "pine nuts": [
        {"to": "sunflower seeds", "ratio": 1.0, "allergens": []},
        {"to": "walnuts", "ratio": 1.0, "allergens": ["tree_nut"]}],
    "cheddar": [
        {"to": "cashew cheese", "ratio": 1.0, "allergens": ["tree_nut"]},
        {"to": "nutritional yeast", "ratio": 0.3, "allergens": []}],
    "honey": [{"to": "maple syrup", "ratio": 1.0, "allergens": []}],
}

# Food-safety chart (minimum safe internal temperature, deg C).
SAFE_TEMPS = {"chicken": 74, "turkey": 74, "egg dishes": 74, "ground beef": 71, "pork": 63, "fish": 63}


def _record(base: dict, version: str, ingredients: list, may_contain: list, note: str, status: str) -> dict:
    declared = sorted({a for i in ingredients for a in i["allergens"]})
    rec = {
        "recipe_id": base["id"], "version": version, "status": status, "title": base["title"],
        "cuisine": base["cuisine"], "tags": base["tags"], "servings": base["servings"],
        "prep_min": base["prep"], "cook_min": base["cook"], "oven_c": base.get("oven_c"),
        "ingredients": ingredients,
        "method": base["steps"],
        "allergens": declared,
        "may_contain": sorted(may_contain),
        "internal_temp_c": base["temp"][0] if base.get("temp") else None,
        "internal_temp_for": base["temp"][1] if base.get("temp") else None,
        "version_note": note,
    }
    return rec


def build() -> dict:
    records = []
    for b in BASE:
        r = b.get("reform")
        orig_status = "superseded" if r else "current"
        records.append(_record(b, "original", [dict(i) for i in b["ing"]], b.get("may_contain", []),
                               "Original formulation.", orig_status))
        if r:
            ings = []
            for i in b["ing"]:
                ings.append(dict(r.get("swap", {}).get(i["item"], i)))
            ings += [dict(a) for a in r.get("add", [])]
            records.append(_record(b, "reformulated-2025", ings, r["may_contain"], r["note"], "current"))
    return {"corpus": "capstone-standin-v1", "n_recipes": len(BASE), "n_records": len(records),
            "records": records, "substitutions": SUBSTITUTIONS, "safe_temps": SAFE_TEMPS}


if __name__ == "__main__":
    data = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    print(f"wrote {OUT}: {data['n_recipes']} recipes, {data['n_records']} records "
          f"({data['n_records'] - data['n_recipes']} reformulated versions)")
