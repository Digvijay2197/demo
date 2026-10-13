# Architecture — one page

```
                                  python -m capstone  (one entry point: ask | eval | trace | serve | mcp)
                                                   │
   question ──► deterministic allergen parse ──────┤  domain.extract_avoid(question)   regex, no LLM
                (independent of the model)         │
                                                   ▼
                          ┌───────────── agent.ask()  — hand-built lap loop (Week 7 shape) ─────────────┐
                          │  budget: 8 laps · 30k tokens · $0.03 · 120 s       trace id minted here      │
                          │                                                                              │
                          │   ① LLM CALL  (Groq gpt-oss-20b, tools = whatever tools/list returned)  $$$  │
                          │        │ tool_calls                                                          │
                          │        ▼                                                                     │
                          │   MCP client (mcp_conn.py)  ── stdio, ONE long-lived session ──┐             │
                          │     • tools/list at start = runtime discovery                  │ trace_id    │
                          │     • injects trace_id into every call                         │ in args     │
                          └────────────────────────────────────────────────────────────────┼─────────────┘
                                                                                           ▼
        ┌──────────────────── OUR MCP SERVER  capstone/mcp_server.py  (no model inside) ────────────────────┐
        │ search_recipes ─► Week 3-4 RAG: MiniLM embed → Chroma  ⊕  BM25 → RRF → version policy             │
        │ get_recipe · scale_recipe · lookup_substitution · check_substituted_recipe (when enabled)          │
        │ check_allergens ─► EXACT MATCH on structured `allergens` / `may_contain` fields (domain.py)        │
        │ every tool logs {trace_id, tool, latency} → logs/capstone_mcp_spans.jsonl                          │
        └────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                   │ tool results back into the loop (②…n LLM laps)
                                                   ▼
        final text ──► GUARDS (guards.py, no LLM): superseded version? allergen endorsed against the declaration?
                       swap introduced an allergen? safe temperature dropped? unsupported allergen? → rewrite/append
                                                   ▼
        answer + clickable citations [R-101@reformulated-2025] ──► trace (obs.py): redacted, cost + latency per span
```

**Where the model is called:** only in the agent loop (1 call per lap, typically 3–4 laps) and, offline, in the prose
judge. The MCP server, retrieval, allergen check, scaling, guards and every eval assertion are plain code.

**Where the money goes:** ~100% of the per-query cost is the loop's LLM laps, and most of *that* is input tokens —
each lap re-sends the system prompt + the six tool schemas + every prior tool result (≈1.1k tokens before the
user says anything). See [`tenx.md`](tenx.md) for the measured number.

**Why these boundaries**
- Allergens, versions, scaling and temperatures are decided by code reading structured fields; the model's job is
  choosing tools and phrasing. The model is never the last word on safety (guards re-check its claim).
- Versions are explicit (`id@version`) at every hop, so a citation is only valid if it names one.
- Both versions of every reformulated recipe stay in the index — the old one is filtered at query time by policy
  (and logged), not deleted, so the bug stays reproducible and a user can still ask what the *original* contained.

**Reused from earlier weeks:** W3-4 embeddings + Chroma + BM25 + RRF (`rag/`), W6 assertion-then-judge pattern,
W7 `Budget` and lap-loop shape, W8 trajectory metrics, W9 MCP discovery pattern, W11 tracing idea (rebuilt with a PII line).
