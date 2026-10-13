# Fresh-eyes note

**TO DO (human) — this cannot be produced by me and I have not invented it.** The brief requires a reviewer from
*another squad* to run the system and call our MCP server with *their* client. Fill this in after Thursday's session.

| | |
|---|---|
| Reviewer (name, squad) | _…_ |
| Date / duration | _…_ |
| Their MCP client | _(Claude Desktop / MCP Inspector / their own script / …)_ |
| Command they used | _…_ |

## Give the reviewer exactly this (and nothing else)

```bash
git clone <repo> && cd demo/backend
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt
copy .env.example .env     # + GROQ_API_KEY
python -m capstone         # does it run? how long until the first answer?
```
MCP server for their own client: `command: python  args: ["-m","capstone.mcp_server"]  cwd: backend`
(or run [`scripts/capstone_external_client.py`](../../backend/scripts/capstone_external_client.py) first to see the shape of the calls).
Ask them to call `check_allergens` for `R-101` with `version` = `original` then `reformulated-2025`, and to try one call
with a mistake on purpose (bad version, missing argument).

## Where they stumbled (fill in verbatim — do not tidy)
1. _…_

## What I changed because of it
1. _…_

## Pre-reviewer self-test (done by me, 2026-10-12 — NOT a substitute)
I ran `scripts/capstone_external_client.py` (raw `mcp` SDK, no capstone imports) against the server: it lists the six
tools and the two `check_allergens` calls return `contains` / `no_declared_conflict` for the two shortbread versions.
A mistake I'd expect a reviewer to make, and the server's answer: an unknown `version` returns
`{"error": "R-101 has no version '2019'; it has: original, reformulated-2025"}` rather than a stack trace.
