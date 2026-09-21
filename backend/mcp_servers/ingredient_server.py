"""Server two: the third-party ingredient database MCP server.

Stands in for "the content team's" server (Task Set B section 1): lookup by
ingredient name, returning allergen flags and per-100g nutrition. It is a
brand-new file — bolting it onto the agent should require editing
mcp_servers/mcp_config.json only, never backend/agent/*.py. See
docs/week9/agent_diff.txt for the proof.

Run standalone for manual testing:
    python -m mcp_servers.ingredient_server
"""
from __future__ import annotations

import difflib

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ingredient-db")

# name -> {allergens, per_100g: {kcal, protein_g, fat_g, carbs_g}}
INGREDIENTS: dict[str, dict] = {
    "whole milk":        {"allergens": ["dairy"], "per_100g": {"kcal": 61, "protein_g": 3.2, "fat_g": 3.3, "carbs_g": 4.8}},
    "oat milk":          {"allergens": [], "per_100g": {"kcal": 47, "protein_g": 1.0, "fat_g": 1.5, "carbs_g": 7.0}},
    "butter":            {"allergens": ["dairy"], "per_100g": {"kcal": 717, "protein_g": 0.9, "fat_g": 81.0, "carbs_g": 0.1}},
    "coconut oil":       {"allergens": [], "per_100g": {"kcal": 862, "protein_g": 0.0, "fat_g": 100.0, "carbs_g": 0.0}},
    "egg":               {"allergens": ["egg"], "per_100g": {"kcal": 155, "protein_g": 13.0, "fat_g": 11.0, "carbs_g": 1.1}},
    "flax egg":          {"allergens": [], "per_100g": {"kcal": 92, "protein_g": 3.2, "fat_g": 6.7, "carbs_g": 6.3}},
    "all-purpose flour": {"allergens": ["gluten"], "per_100g": {"kcal": 364, "protein_g": 10.3, "fat_g": 1.0, "carbs_g": 76.3}},
    "almond flour":      {"allergens": ["tree_nut"], "per_100g": {"kcal": 571, "protein_g": 21.0, "fat_g": 50.0, "carbs_g": 21.0}},
    "cheddar cheese":    {"allergens": ["dairy"], "per_100g": {"kcal": 403, "protein_g": 25.0, "fat_g": 33.0, "carbs_g": 1.3}},
    "cashew cheese":     {"allergens": ["tree_nut"], "per_100g": {"kcal": 296, "protein_g": 9.0, "fat_g": 24.0, "carbs_g": 14.0}},
    "creme fraiche":     {"allergens": ["dairy"], "per_100g": {"kcal": 292, "protein_g": 2.4, "fat_g": 30.0, "carbs_g": 3.0}},
    "peanut butter":     {"allergens": ["peanut"], "per_100g": {"kcal": 588, "protein_g": 25.0, "fat_g": 50.0, "carbs_g": 20.0}},
    "walnuts":           {"allergens": ["tree_nut"], "per_100g": {"kcal": 654, "protein_g": 15.0, "fat_g": 65.0, "carbs_g": 14.0}},
    "shrimp paste":      {"allergens": ["shellfish"], "per_100g": {"kcal": 92, "protein_g": 15.0, "fat_g": 1.5, "carbs_g": 5.0}},
    "fish sauce":        {"allergens": ["fish"], "per_100g": {"kcal": 35, "protein_g": 5.1, "fat_g": 0.0, "carbs_g": 3.6}},
    "soy sauce":         {"allergens": ["soy", "gluten"], "per_100g": {"kcal": 53, "protein_g": 8.1, "fat_g": 0.1, "carbs_g": 4.9}},
    "sesame oil":        {"allergens": ["sesame"], "per_100g": {"kcal": 884, "protein_g": 0.0, "fat_g": 100.0, "carbs_g": 0.0}},
    "firm tofu":         {"allergens": ["soy"], "per_100g": {"kcal": 144, "protein_g": 15.8, "fat_g": 8.7, "carbs_g": 2.8}},
}


@mcp.tool()
def lookup_ingredient(name: str) -> dict:
    """Look up one ingredient by name and return its allergen classes plus
    nutrition per 100g (kcal, protein_g, fat_g, carbs_g). This is a database
    lookup, not a search — pass the ingredient exactly as it appears in a
    recipe (e.g. "whole milk", not "milk products"). If the name is not on
    file, the error names the closest known ingredient so you can retry with
    that exact name instead of guessing its nutrition or allergens."""
    key = name.strip().lower()
    hit = INGREDIENTS.get(key)
    if hit is not None:
        return {"name": key, **hit}
    close = difflib.get_close_matches(key, INGREDIENTS.keys(), n=1, cutoff=0.5)
    if close:
        return {"error": f"no ingredient matched {name!r}: try {close[0]!r}"}
    return {"error": f"no ingredient matched {name!r}; none of the known names are close — "
                      f"do not assume its allergens or nutrition"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
