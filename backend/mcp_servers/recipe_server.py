"""Server one: the recipe-search MCP server.

This is *our own* server — it wraps the exact same pure-Python tool
implementations the Week 7/8 agent loop already calls directly
(``agent.tools.search_recipes`` / ``get_nutrition`` / ``substitute_ingredient``),
so the graded Week 7/8 numbers cannot move. What changes is the *transport*:
instead of the host importing these functions and binding hand-written pydantic
schemas (agent/tools.py's ``TOOL_SCHEMAS``), the host now discovers them over
MCP by calling tools/list on this process. FastMCP builds each tool's JSON
schema from the Python type hints below and sends the docstring as the tool's
``description`` — that description IS the prompt the model reads before ever
seeing an example, so it is written like one.

Run standalone for manual testing:
    python -m mcp_servers.recipe_server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from agent.tools import (
    AllergenClass,
    get_nutrition as _get_nutrition,
    search_recipes as _search_recipes,
    substitute_ingredient as _substitute_ingredient,
)

mcp = FastMCP("recipe-search")


@mcp.tool()
def search_recipe(query: str) -> dict:
    """Locate a recipe by a free-text query (dish name, key ingredient, or
    cuisine) and return its full base record: ingredient list with
    quantities, method steps, and the allergen classes it contains. Call this
    ONCE at the start to pull the recipe you will work on; it does no scaling
    and no substitution. Do not call it again for a recipe you have already
    fetched."""
    return _search_recipes(query)


@mcp.tool()
def get_nutrition(recipe_name: str, servings: int) -> dict:
    """Scale one already-fetched recipe to a target serving count and return
    the recomputed ingredient amounts plus a per-serving calorie estimate.
    Requires an exact recipe name that search_recipe already returned — it
    does not search, and it does not change any ingredients. MANDATORY: call
    this before writing ANY scaled quantity into your final answer — never
    compute or state a scaled amount from memory, even when the ratio looks
    obvious."""
    return _get_nutrition(recipe_name, servings)


@mcp.tool()
def substitute_ingredient(recipe_name: str, ingredient: str, avoid_allergen: AllergenClass) -> dict:
    """Swap exactly ONE allergen-bearing ingredient in a recipe for a safe
    alternative. Returns the single best substitute, its converted amount,
    and the allergen class the substitute itself carries (which may be
    another banned class — if so, call this again on the substitute). One
    swap per call: it does not search, scale, or return the method.
    MANDATORY: call this for EVERY ingredient you remove or replace before
    finalizing — never state a substitution from memory, even a common one
    you already know."""
    return _substitute_ingredient(recipe_name, ingredient, avoid_allergen)


if __name__ == "__main__":
    mcp.run(transport="stdio")
