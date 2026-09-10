"""The recipe book the tools read from, plus the substitution table.

Deliberately tiny and in-code: the Week 7 race is about agent-loop vs fixed
workflow orchestration cost, so the data layer is a dict lookup with zero
latency and zero variance. Every ingredient carries its allergen classes, and
``SUBSTITUTIONS`` is what makes the allergen cascade real — several safe
substitutes themselves carry a *different* allergen, so a request that bans two
classes forces a second swap.
"""
from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

# Allergen classes used everywhere (tool enum, request specs, pass checks).
ALLERGENS = [
    "dairy", "egg", "gluten", "peanut", "tree_nut", "soy", "shellfish", "fish", "sesame",
]


class Ingredient(TypedDict):
    item: str
    qty: Optional[float]   # None = "to taste" / unscalable
    unit: str
    allergens: List[str]


class Recipe(TypedDict):
    name: str
    base_servings: int
    ingredients: List[Ingredient]
    method: List[str]


def _ing(item: str, qty, unit: str, allergens: List[str] = None) -> Ingredient:
    return {"item": item, "qty": qty, "unit": unit, "allergens": allergens or []}


RECIPES: Dict[str, Recipe] = {
    "classic pancakes": {
        "name": "Classic Pancakes",
        "base_servings": 4,
        "ingredients": [
            _ing("all-purpose flour", 200, "g", ["gluten"]),
            _ing("whole milk", 300, "ml", ["dairy"]),
            _ing("egg", 2, "", ["egg"]),
            _ing("butter", 30, "g", ["dairy"]),
            _ing("caster sugar", 20, "g"),
            _ing("baking powder", 8, "g"),
            _ing("fine salt", None, "pinch"),
        ],
        "method": [
            "Whisk the flour, sugar, baking powder and salt in a large bowl.",
            "Beat in the milk and egg until just smooth, then stir in the melted butter.",
            "Rest the batter 10 minutes while a non-stick pan heats over medium heat.",
            "Cook 3 tablespoons of batter per pancake, about 2 minutes a side, until golden.",
        ],
    },
    "weeknight mac and cheese": {
        "name": "Weeknight Mac and Cheese",
        "base_servings": 4,
        "ingredients": [
            _ing("macaroni", 300, "g", ["gluten"]),
            _ing("whole milk", 400, "ml", ["dairy"]),
            _ing("butter", 40, "g", ["dairy"]),
            _ing("all-purpose flour", 30, "g", ["gluten"]),
            _ing("cheddar cheese", 200, "g", ["dairy"]),
            _ing("fine salt", None, "pinch"),
        ],
        "method": [
            "Boil the macaroni in salted water until just al dente, then drain.",
            "Melt the butter in the pot, stir in the flour and cook 1 minute to a paste.",
            "Whisk in the milk and simmer until it thickens enough to coat a spoon.",
            "Off the heat, stir in the cheddar until glossy, fold in the macaroni and season.",
        ],
    },
    "thai green curry": {
        "name": "Thai Green Curry",
        "base_servings": 4,
        "ingredients": [
            _ing("coconut milk", 400, "ml"),
            _ing("chicken thigh", 500, "g"),
            _ing("green curry paste", 60, "g"),
            _ing("fish sauce", 2, "tbsp", ["fish"]),
            _ing("shrimp paste", 1, "tsp", ["shellfish"]),
            _ing("palm sugar", 1, "tbsp"),
            _ing("thai basil", 20, "g"),
        ],
        "method": [
            "Fry the curry paste and shrimp paste in the thick coconut cream until it splits and smells fragrant.",
            "Add the chicken and turn it in the paste until the outside is opaque.",
            "Pour in the rest of the coconut milk, then season with fish sauce and palm sugar.",
            "Simmer 15 minutes until the chicken is cooked, then stir the basil through off the heat.",
        ],
    },
    "banana bread": {
        "name": "Banana Bread",
        "base_servings": 8,
        "ingredients": [
            _ing("all-purpose flour", 250, "g", ["gluten"]),
            _ing("butter", 100, "g", ["dairy"]),
            _ing("egg", 2, "", ["egg"]),
            _ing("ripe banana", 3, ""),
            _ing("caster sugar", 150, "g"),
            _ing("walnuts", 60, "g", ["tree_nut"]),
            _ing("baking soda", 5, "g"),
        ],
        "method": [
            "Cream the butter and sugar, then beat in the eggs one at a time.",
            "Mash the bananas and mix them in, then fold in the flour and baking soda.",
            "Stir through the chopped walnuts and scrape into a lined loaf tin.",
            "Bake at 175 C for about 55 minutes, until a skewer comes out clean.",
        ],
    },
    "veggie stir-fry noodles": {
        "name": "Veggie Stir-Fry Noodles",
        "base_servings": 2,
        "ingredients": [
            _ing("wheat noodles", 200, "g", ["gluten"]),
            _ing("soy sauce", 3, "tbsp", ["soy", "gluten"]),
            _ing("sesame oil", 1, "tbsp", ["sesame"]),
            _ing("firm tofu", 200, "g", ["soy"]),
            _ing("broccoli", 150, "g"),
            _ing("garlic", 3, "cloves"),
        ],
        "method": [
            "Boil the noodles until just done, drain and toss with a little of the sesame oil.",
            "Fry the garlic in the rest of the oil, then add the tofu and colour it on all sides.",
            "Add the broccoli with a splash of water and stir-fry until bright and just tender.",
            "Return the noodles, pour over the soy sauce and toss over high heat for a minute.",
        ],
    },
    "chocolate chip cookies": {
        "name": "Chocolate Chip Cookies",
        "base_servings": 24,
        "ingredients": [
            _ing("all-purpose flour", 300, "g", ["gluten"]),
            _ing("butter", 170, "g", ["dairy"]),
            _ing("egg", 1, "", ["egg"]),
            _ing("brown sugar", 150, "g"),
            _ing("chocolate chips", 200, "g", ["dairy"]),
            _ing("vanilla extract", 1, "tsp"),
        ],
        "method": [
            "Cream the butter and brown sugar, then beat in the egg and vanilla.",
            "Fold in the flour, then the chocolate chips, to a stiff dough.",
            "Scoop walnut-sized balls onto lined trays, spaced well apart.",
            "Bake at 180 C for 11 minutes, until the edges are set but the centres still look soft.",
        ],
    },
}


class Sub(TypedDict):
    to: str
    allergens: List[str]   # allergen classes the *substitute* carries
    ratio: float           # multiply the original amount by this


# ingredient (lower-case, as it appears in RECIPES) -> its one best substitute.
# The allergens list on the RHS is what drives the cascade: e.g. banning
# "dairy" turns whole milk into oat milk, which is "gluten"; a request that
# also bans gluten must then swap oat milk again.
SUBSTITUTIONS: Dict[str, Sub] = {
    "whole milk":        {"to": "oat milk", "allergens": ["gluten"], "ratio": 1.0},
    "butter":            {"to": "coconut oil", "allergens": [], "ratio": 0.8},
    "egg":               {"to": "flax egg", "allergens": [], "ratio": 1.0},
    "all-purpose flour": {"to": "almond flour", "allergens": ["tree_nut"], "ratio": 1.0},
    "almond flour":      {"to": "oat flour", "allergens": ["gluten"], "ratio": 1.0},
    "oat flour":         {"to": "rice flour", "allergens": [], "ratio": 1.0},
    "oat milk":          {"to": "rice milk", "allergens": [], "ratio": 1.0},
    "macaroni":          {"to": "brown-rice macaroni", "allergens": [], "ratio": 1.0},
    "cheddar cheese":    {"to": "cashew cheese", "allergens": ["tree_nut"], "ratio": 1.0},
    "cashew cheese":     {"to": "nutritional-yeast sauce", "allergens": [], "ratio": 0.6},
    "chocolate chips":   {"to": "dairy-free chocolate chips", "allergens": [], "ratio": 1.0},
    "walnuts":           {"to": "pumpkin seeds", "allergens": [], "ratio": 1.0},
    "wheat noodles":     {"to": "rice noodles", "allergens": [], "ratio": 1.0},
    "soy sauce":         {"to": "coconut aminos", "allergens": [], "ratio": 1.0},
    "sesame oil":        {"to": "light olive oil", "allergens": [], "ratio": 1.0},
    "firm tofu":         {"to": "chickpea tofu", "allergens": [], "ratio": 1.0},
    "fish sauce":        {"to": "light soy sauce", "allergens": ["soy", "gluten"], "ratio": 1.0},
    "light soy sauce":   {"to": "coconut aminos", "allergens": [], "ratio": 1.0},
    "shrimp paste":      {"to": "fish sauce", "allergens": ["fish"], "ratio": 0.5},
}


def find(name: str) -> Optional[Recipe]:
    """Look a recipe up by loose name match (exact key, else substring)."""
    key = name.strip().lower()
    if key in RECIPES:
        return RECIPES[key]
    for k, r in RECIPES.items():
        if key in k or key in r["name"].lower():
            return r
    return None
