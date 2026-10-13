"""OUR MCP server: the recipe + allergen capability, exposed over MCP (stdio).

This is the 'MCP server of your own' - any MCP client can call it, including one
we did not write (scripts/capstone_external_client.py uses the raw `mcp` SDK, and a
fresh-eyes reviewer's own client can be pointed at the same command). No model runs
in here: each tool is the plain Python behind it (capstone/domain.py, retriever.py).

Every tool takes an optional `trace_id`. Our agent injects it; the server logs a span
with it, which is how one trace id survives the MCP hop (capstone/obs.py).

    python -m capstone.mcp_server        # stdio

Tool availability depends on config: `check_substituted_recipe` is only registered when
CAPSTONE_SUBSTITUTION=checked - the agent discovers the tool list at runtime.
"""
from __future__ import annotations

import json
import time
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP

from capstone import config, domain, obs, retriever

mcp = FastMCP("recipe-allergen")

Version = Literal["original", "reformulated-2025"]


def _run(tool: str, trace_id: str, fn):
    t0 = time.perf_counter()
    ok = True
    try:
        return fn()
    except domain.RecipeNotFound as exc:
        ok = False
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        ok = False
        return {"error": f"{tool} failed: {exc!r}"}
    finally:
        obs.log_server_span(trace_id, tool, (time.perf_counter() - t0) * 1000, ok)


@mcp.tool()
def search_recipes(query: str, trace_id: str = "") -> dict:
    """Search the recipe library (hybrid semantic + keyword) for a dish, ingredient or pantry list.
    Returns up to 4 hits, each with recipe_id, version, title and a ready-made `citation` string like
    [R-101@reformulated-2025]. Hits show the CURRENT version of each recipe. If no hit is the dish the
    user asked for, the library does not have it - say so; never invent a recipe."""
    return _run("search_recipes", trace_id, lambda: retriever.search_recipes(query))


@mcp.tool()
def get_recipe(recipe_id: str, version: Optional[Version] = None, trace_id: str = "") -> dict:
    """Fetch one recipe: ingredients with quantities, method, yield, prep/cook minutes, oven temperature
    and the minimum safe internal temperature (internal_temp_c) when it contains meat, fish or egg.
    Pass the `version` you got from search_recipes. Always cite the returned `citation`."""
    def go():
        r = domain.get_record(recipe_id, version)
        return {"citation": domain.cite(r), "recipe_id": r["recipe_id"], "version": r["version"],
                "status": r["status"], "title": r["title"], "servings": r["servings"],
                "prep_min": r["prep_min"], "cook_min": r["cook_min"], "oven_c": r["oven_c"],
                "internal_temp_c": r["internal_temp_c"], "internal_temp_for": r["internal_temp_for"],
                "ingredients": [f"{i['qty'] if i['qty'] is not None else ''} {i['unit']} {i['item']}".strip()
                                for i in r["ingredients"]],
                "method": r["method"], "version_note": r["version_note"],
                **({"warning": "SUPERSEDED version - not the recipe currently published"}
                   if r["status"] == "superseded" else {})}
    return _run("get_recipe", trace_id, go)


@mcp.tool()
def check_allergens(recipe_id: str, avoid: list[str], version: Optional[Version] = None, trace_id: str = "") -> dict:
    """Check a recipe against the allergens the user must avoid by EXACT-MATCHING the recipe's structured
    allergen and 'may contain' declaration fields (not the method text). `avoid` = the user's allergens
    (e.g. ["tree nuts", "peanut", "dairy"]). verdict is one of contains / may_contain / no_declared_conflict /
    cannot_verify. MANDATORY before telling anyone a recipe is safe or unsafe for an allergy. Pass the same
    `version` you cite. If verdict is cannot_verify the allergen is not covered by the library: say so."""
    return _run("check_allergens", trace_id, lambda: domain.check_allergens(recipe_id, version, avoid))


@mcp.tool()
def scale_recipe(recipe_id: str, servings: int, version: Optional[Version] = None, trace_id: str = "") -> dict:
    """Scale a recipe to a target number of servings. Returns scaled ingredient quantities. Cook/bake time and
    oven temperature are deliberately NOT scaled (cook_min stays per batch) and internal_temp_c is carried
    through. MANDATORY before stating any scaled quantity - never multiply amounts or times yourself."""
    return _run("scale_recipe", trace_id, lambda: domain.scale_recipe(recipe_id, version, int(servings)))


@mcp.tool()
def lookup_substitution(ingredient: str, avoid: Optional[list[str]] = None, trace_id: str = "") -> dict:
    """Look up test-kitchen substitutes for ONE missing ingredient. Each option lists the allergens the
    substitute itself carries. Pass the user's `avoid` allergens so unsafe options are filtered out."""
    return _run("lookup_substitution", trace_id, lambda: domain.lookup_substitution(ingredient, avoid))


if config.substitution_mode() == "checked":
    @mcp.tool()
    def check_substituted_recipe(recipe_id: str, swaps: list[dict], avoid: list[str],
                                 version: Optional[Version] = None, trace_id: str = "") -> dict:
        """Re-check a recipe's allergens AS SUBSTITUTED. `swaps` = [{"from_item": "whole milk", "to_item":
        "oat milk"}]. A swap can introduce an allergen the published recipe did not have, so the check
        must run on the recipe after your swaps, not on the recipe as published. MANDATORY whenever you
        propose any substitution to a user who has an allergy."""
        return _run("check_substituted_recipe", trace_id,
                    lambda: domain.check_substituted_recipe(recipe_id, version, swaps, avoid))


@mcp.resource("recipe://{recipe_id}/{version}")
def recipe_resource(recipe_id: str, version: str) -> str:
    """A recipe version as a readable MCP resource (what a citation points at)."""
    return json.dumps(domain.get_record(recipe_id, version), indent=1)


if __name__ == "__main__":
    # Load the embedding model + BM25 index BEFORE serving, on the main thread. Doing it lazily
    # inside the first tool call (on the stdio event loop) was ~10x slower on Windows.
    retriever.search_recipes("warm up")
    mcp.run(transport="stdio")
