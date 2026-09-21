<!-- Soft Suave · The AI Engineering League -->
# Week 9 Task Set B — bolting on the ingredient database server

Full brief: [`docs/W9-Task-Set-B.md`](W9-Task-Set-B.md). Raw deliverables live
under [`docs/week9/`](week9/); this is the narrative tying them together.

Since no Week 9 base build existed yet in this repo, this submission first
built the minimal "Week 9 already done" state Task Set B assumes — the recipe
agent (`backend/agent/mcp_agent.py`) as an MCP client, discovering tools from
a recipe-search server (`backend/mcp_servers/recipe_server.py`) that wraps the
existing Week 7/8 tool implementations unchanged — committed separately
(`c590388`) from the Task Set B work itself, so the two could be diffed.

## 1. Config-only server swap (30 pts)

`backend/mcp_servers/mcp_config.json` gained one entry, `ingredient-db`,
pointing at the new `backend/mcp_servers/ingredient_server.py`. Nothing under
`backend/agent/` changed — see [`docs/week9/agent_diff.txt`](week9/agent_diff.txt)
(`git diff` against the pre-Task-B commit, scoped to the whole `agent/`
directory, produces zero lines) and
[`docs/week9/config_diff.txt`](week9/config_diff.txt) for the 6-line config
diff that did the work. `agent/mcp_client.py` reads whatever servers the
config lists and never names `recipe-search` or `ingredient-db` itself.

One query that provably calls the new server's tool, with the tool name
visible in the trace — [`docs/week9/ingredient_query_run.json`](week9/ingredient_query_run.json):

```
query: "What allergens and per-100g nutrition does peanut butter have?"
trace: [{"lap": 1, "tool": "lookup_ingredient", "args": {"name": "peanut butter"}, ...}]
```

## 2. Raw wire capture + model-call location (25 pts)

[`docs/week9/wire.json`](week9/wire.json) is a hand-annotated
initialize → tools/list → tools/call exchange against `ingredient-db`,
captured by [`backend/scripts/wire_capture_week9.py`](../backend/scripts/wire_capture_week9.py)
speaking newline-delimited JSON-RPC directly over the child process's stdio
pipes (no `mcp.ClientSession` in between, so every byte in
[`docs/week9/wire_raw.json`](week9/wire_raw.json) is exactly what crossed the
pipe). Every top-level field of all 7 frames is annotated in place.

**Where the model call happens, and where it does not:** the model call (a
Groq chat-completion request) happens in `agent/mcp_agent.py`'s
`llm.invoke(messages)`, between the tools/list result reaching the client and
the tools/call request it then issues — it does **not** happen inside either
MCP server process; `ingredient_server.py` and `recipe_server.py` execute
plain Python functions and never import or call an LLM.

## 3. Tool count before → after (15 pts)

From `tools/list`, not notes — [`docs/week9/config_diff.txt`](week9/config_diff.txt):

| | count | names |
|---|---|---|
| **Before** (`recipe-search` only) | 3 | `get_nutrition`, `search_recipe`, `substitute_ingredient` |
| **After** (+ `ingredient-db`) | 4 | `get_nutrition`, `lookup_ingredient`, `search_recipe`, `substitute_ingredient` |

## 4. Docstring-as-prompt + recoverable error (20 pts)

Rewrote `search_recipe`'s docstring and its no-match error path on **our own**
server (`backend/mcp_servers/recipe_server.py`) to name the closest known
recipe title (`difflib.get_close_matches` against the real recipe book) and
tell the model to retry once with it instead of guessing blindly or
inventing a recipe. Full before/after — real Groq transcripts, same failing
query both times — in [`docs/week9/error_before_after.md`](week9/error_before_after.md):

- **Before:** 4 blind retries, 5 laps, 5,132 tokens, found the right recipe
  only by a lucky substring match.
- **After:** 1 retry using the server-supplied suggestion, 3 laps, 3,163
  tokens, deterministic.

## 5. Third-party risk note (10 pts)

[`docs/week9/risk_note.md`](week9/risk_note.md) — exactly 5 lines, covering
authorship, reach, logging, stolen-token blast radius, and a ship/don't call.

## Bonus (not attempted)

The gateway-fan-out + audit-log + scoped-token bonus was not built for this
submission; the 100-point rubric above is what's covered.
