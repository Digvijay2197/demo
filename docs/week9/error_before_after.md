<!-- Soft Suave · The AI Engineering League -->
# Week 9 Task Set B — requirement 5: docstring-as-prompt + recoverable error

Same tool (`search_recipe`, our own server: `mcp_servers/recipe_server.py`),
same failing call, same model (`openai/gpt-oss-20b` via Groq), before and
after one docstring + error-path rewrite. Full raw transcripts are in
`before_transcript_raw.json` / `after_transcript_raw.json` in this folder.

**Query sent to the agent (identical both times):**
> "Search for banana walnut muffins and tell me its allergens."

The only real title in the book is *Community Walnut Banana Muffins* — a
substring/generic-knowledge match cannot find it from that phrasing.

## Before

```python
def search_recipe(query: str) -> dict:
    """Locate a recipe by a free-text query ..."""
    return _search_recipes(query)   # error: "no recipe matches 'X'"
```

| lap | tool call | result |
|---|---|---|
| 1 | `search_recipe("banana walnut muffins")` | `{"error": "no recipe matches 'banana walnut muffins'"}` |
| 2 | `search_recipe("banana walnut muffin")` | `{"error": "no recipe matches 'banana walnut muffin'"}` |
| 3 | `search_recipe("banana walnut muffin recipe")` | `{"error": "no recipe matches 'banana walnut muffin recipe'"}` |
| 4 | `search_recipe("banana muffin")` | **matches** *Community Walnut Banana Muffins* (found by luck — the substring "banana muffin" happens to appear in the recipe's lowercased name) |
| 5 | — | final answer |

4 tool calls, 5 laps, 5,132 tokens. The error carries no information beyond
"not found," so the model can only guess variations of its own query
blind — it happened to land on a working substring on its fourth try. A
less lucky rephrasing (e.g. "muffins with walnut and banana") would have
kept missing indefinitely up to the loop's iteration budget, and a weaker
model could just as easily have given up or invented ingredients instead.

## After

```python
def search_recipe(query: str) -> dict:
    """... If nothing matches, the error names the closest known recipe
    title on file -- retry ONCE with that exact title. Never guess a second
    rephrasing of your own query and never invent a recipe ..."""
    result = _search_recipes(query)
    if result.get("error"):
        close = difflib.get_close_matches(query, titles, n=1, cutoff=0.4)
        result["error"] = (f"no recipe matches {query!r}: try {close[0]!r}"
                            if close else f"no recipe matches {query!r}; known recipes: ...")
    return result
```

| lap | tool call | result |
|---|---|---|
| 1 | `search_recipe("banana walnut muffins")` | `{"error": "no recipe matches 'banana walnut muffins': try 'Community Walnut Banana Muffins'"}` |
| 2 | `search_recipe("Community Walnut Banana Muffins")` | **matches** *Community Walnut Banana Muffins* |
| 3 | — | final answer |

2 tool calls, 3 laps, 3,163 tokens — a 38% drop in laps and ~38% drop in
tokens on this one call, and the retry is now deterministic (the exact
title the server named) instead of a guess that happened to work.

## What changed, precisely

1. **The error payload** gained one field of real information: the nearest
   known title (`difflib.get_close_matches` against the recipe book's real
   names), computed server-side where the ground truth lives — never
   fabricated by the model.
2. **The docstring** (= the prompt the model reads, verbatim, from
   `tools/list`) now tells the model what that field means and what to do
   with it: retry once with the suggested title, don't rephrase blindly,
   don't invent a recipe. Section 7's "common mistake" this fixes:
   *"Swallowing the unknown-ingredient case into 'Error: lookup failed,' so
   the model cannot tell a spelling miss from a dead server."*
