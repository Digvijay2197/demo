"""The three tools the agent loop and the workflow both call.

`search_recipes` and `get_nutrition` are the two that existed before this week.
`substitute_ingredient` is the Week 7 addition: one job (swap exactly one
allergen-bearing ingredient), enum-typed allergen parameter, and a description
that does not overlap the other two (see docs/week7-agent-vs-workflow.md for the
before/after of all three descriptions).

Tools are pure Python — no LLM, no network, no randomness — so the race times
and token counts reflect orchestration only. `run_tool` is the single dispatch
point used by both systems.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from agent.recipes import ALLERGENS, SUBSTITUTIONS, find

# Enum type for the allergen parameter — kept in sync with recipes.ALLERGENS.
AllergenClass = Literal[
    "dairy", "egg", "gluten", "peanut", "tree_nut", "soy", "shellfish", "fish", "sesame",
]
assert set(AllergenClass.__args__) == set(ALLERGENS), "AllergenClass out of sync with ALLERGENS"

# Very rough kcal per unit, only so get_nutrition returns something non-trivial.
_KCAL = {
    "all-purpose flour": 3.6, "almond flour": 5.8, "oat flour": 3.9, "rice flour": 3.6,
    "whole milk": 0.6, "oat milk": 0.5, "rice milk": 0.5, "butter": 7.2, "coconut oil": 8.6,
    "caster sugar": 4.0, "brown sugar": 3.8, "egg": 78.0, "flax egg": 37.0,
    "cheddar cheese": 4.0, "cashew cheese": 3.1, "nutritional-yeast sauce": 1.4,
    "chocolate chips": 5.0, "dairy-free chocolate chips": 5.0, "walnuts": 6.5, "pumpkin seeds": 5.6,
    "macaroni": 3.7, "brown-rice macaroni": 3.6, "wheat noodles": 3.4, "rice noodles": 3.6,
    "coconut milk": 2.3, "chicken thigh": 2.1, "green curry paste": 1.4, "fish sauce": 0.4,
    "light soy sauce": 0.6, "coconut aminos": 0.9, "shrimp paste": 0.9, "palm sugar": 3.8,
    "soy sauce": 0.6, "sesame oil": 8.8, "light olive oil": 8.8, "firm tofu": 1.4,
    "chickpea tofu": 1.2, "broccoli": 0.3, "thai basil": 0.2, "ripe banana": 0.9,
}


# ---------------------------------------------------------------- tool schemas


class SearchRecipes(BaseModel):
    """Locate a recipe by a free-text query (dish name, key ingredient, or
    cuisine) and return its full base record: ingredient list with quantities,
    method steps, and the allergen classes it contains. Call this ONCE at the
    start to pull the recipe you will work on; it does no scaling and no
    substitution. Do not call it again for a recipe you have already fetched."""

    query: str = Field(description="dish name, ingredient, or cuisine to search for")


class GetNutrition(BaseModel):
    """Scale one already-fetched recipe to a target serving count and return
    the recomputed ingredient amounts plus a per-serving calorie estimate.
    Requires an exact recipe name that search_recipes already returned — it
    does not search, and it does not change any ingredients."""

    recipe_name: str = Field(description="exact name from a prior search_recipes result")
    servings: int = Field(description="target number of servings to scale to", gt=0)


class SubstituteIngredient(BaseModel):
    """Swap exactly ONE allergen-bearing ingredient in a recipe for a safe
    alternative. Returns the single best substitute, its converted amount, and
    the allergen class the substitute itself carries (which may be another
    banned class — if so, call this again on the substitute). One swap per
    call: it does not search, scale, or return the method."""

    recipe_name: str = Field(description="exact recipe name")
    ingredient: str = Field(description="the ingredient to remove, e.g. 'whole milk'")
    avoid_allergen: AllergenClass = Field(description="allergen class the caller must avoid")


TOOL_SCHEMAS = [SearchRecipes, GetNutrition, SubstituteIngredient]


# ---------------------------------------------------------------- implementations


def _ing_public(ing: dict) -> dict:
    return {"item": ing["item"], "qty": ing["qty"], "unit": ing["unit"],
            "allergens": ing["allergens"]}


def search_recipes(query: str) -> dict:
    r = find(query)
    if not r:
        return {"matches": [], "error": f"no recipe matches {query!r}"}
    allergens = sorted({a for ing in r["ingredients"] for a in ing["allergens"]})
    return {"matches": [{
        "name": r["name"],
        "base_servings": r["base_servings"],
        "ingredients": [_ing_public(i) for i in r["ingredients"]],
        "method": list(r["method"]),
        "allergens": allergens,
    }]}


def get_nutrition(recipe_name: str, servings: int) -> dict:
    r = find(recipe_name)
    if not r:
        return {"error": f"unknown recipe {recipe_name!r}"}
    factor = servings / r["base_servings"]
    scaled, kcal = [], 0.0
    for ing in r["ingredients"]:
        q = ing["qty"]
        nq = round(q * factor, 2) if isinstance(q, (int, float)) else q
        scaled.append({"item": ing["item"], "qty": nq, "unit": ing["unit"],
                       "allergens": ing["allergens"]})
        if isinstance(q, (int, float)):
            kcal += _KCAL.get(ing["item"], 1.5) * q * factor
    return {
        "recipe": r["name"],
        "servings": servings,
        "scale_factor": round(factor, 3),
        "scaled_ingredients": scaled,
        "kcal_per_serving": round(kcal / servings),
    }


def substitute_ingredient(recipe_name: str, ingredient: str, avoid_allergen: str) -> dict:
    r = find(recipe_name)
    if not r:
        return {"error": f"unknown recipe {recipe_name!r}"}
    key = ingredient.strip().lower()
    sub = SUBSTITUTIONS.get(key)
    if not sub:
        return {"error": f"no substitution known for {ingredient!r}",
                "known": sorted(SUBSTITUTIONS)}
    carries = sub["allergens"]
    cascades = avoid_allergen in carries
    return {
        "recipe": r["name"],
        "removed": ingredient,
        "substitute": sub["to"],
        "amount_ratio": sub["ratio"],
        "substitute_allergens": carries,
        "cascade": cascades,
        "note": (
            f"'{sub['to']}' itself contains {', '.join(carries)} — "
            f"call substitute_ingredient again on it"
            if cascades else
            f"'{sub['to']}' carries no banned allergen; swap complete"
        ),
    }


_IMPLS = {
    "SearchRecipes": lambda a: search_recipes(a["query"]),
    "GetNutrition": lambda a: get_nutrition(a["recipe_name"], int(a["servings"])),
    "SubstituteIngredient": lambda a: substitute_ingredient(
        a["recipe_name"], a["ingredient"], a["avoid_allergen"]),
}


def run_tool(name: str, args: dict) -> str:
    """Execute a tool call and return its result as a JSON string (the form a
    ToolMessage carries). Unknown tools and bad arguments come back as an
    ``error`` payload rather than raising, so one malformed model call cannot
    crash the loop."""
    impl = _IMPLS.get(name)
    if impl is None:
        return json.dumps({"error": f"unknown tool {name!r}"})
    try:
        return json.dumps(impl(args))
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": f"{name} failed: {exc!r}", "args": args})
