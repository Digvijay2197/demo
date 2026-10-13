# Week 12 Capstone (Variant B) — Pantry-to-Plate Assistant

One repo, one entry point, one command. Everything lives in [`backend/capstone/`](../../backend/capstone/); this folder is the paperwork.

## Run it (a stranger's path)

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate          # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements.txt
copy .env.example .env                                  # set GROQ_API_KEY (free: console.groq.com/keys)

python -m capstone                # smoke: index -> MCP discovery -> a live pantry+allergy question -> traced answer
python -m capstone eval           # the whole suite: 30 cases, assertions, trajectory, taxonomy, cost, report
python -m capstone eval --before  # the same safety cases on the BEFORE config (the bug the client lived with)
python -m capstone eval --validate-judge   # judge vs hand labels on integrated outputs
python -m capstone trace <trace_id>        # one request across the agent hop and the MCP hop
python -m capstone serve          # HTTP: POST /ask, clickable citations GET /recipes/R-101?version=reformulated-2025
python -m pytest tests/test_capstone.py    # 33 deterministic tests, no network/LLM
python scripts/capstone_external_client.py # a client that shares no code with ours calling our MCP server
```

First start takes ~1 minute (loads the embedding model and indexes 34 recipe records into Chroma); later starts ~10 s.
Each eval case costs ~5k Groq tokens, so a full suite is ~150k tokens — the free tier's 200k/day cap is real
(`--patient` sleeps through 429s).

## What is where

| Requirement | Where |
|---|---|
| 1 RAG behind one entry point, version-bearing citations | [`retriever.py`](../../backend/capstone/retriever.py) (Week 3-4 hybrid: Chroma + BM25 + RRF, reused from `rag/`), [`agent.py`](../../backend/capstone/agent.py) `ask()` |
| 2 Hand-built agent loop, ≥3 tools, MCP tools discovered at runtime | [`agent.py`](../../backend/capstone/agent.py) (budgeted lap loop), [`mcp_conn.py`](../../backend/capstone/mcp_conn.py) (`tools/list` → model tools; nothing names a tool) |
| 3 Our own MCP server, called by a client that isn't ours | [`mcp_server.py`](../../backend/capstone/mcp_server.py), [`scripts/capstone_external_client.py`](../../backend/scripts/capstone_external_client.py), [`fresh_eyes.md`](fresh_eyes.md) |
| 4 Eval suite, one command, 25-40 cases, assertions before judges | [`eval/`](../../backend/capstone/eval/) — 30 cases, [`eval_report.md`](eval_report.md) |
| 5 Re-scored taxonomy, one mode created by integration | [`taxonomy.md`](taxonomy.md) |
| 6 Trajectory eval ≥10 cases, outcome-vs-trajectory gap | [`trajectory.md`](trajectory.md) |
| 7 One trace id across both hops, cost+latency per span, PII line | [`obs.py`](../../backend/capstone/obs.py), [`trace_example.json`](trace_example.json) |
| 8 Closed failure→test loop, cost/query, 10× plan | [`closed_loop.md`](closed_loop.md), [`tenx.md`](tenx.md) |
| Bonus: allergen check through the substitution chain | [`bonus_substitution.md`](bonus_substitution.md) |
| Submission checklist | [`seams.md`](seams.md), [`architecture.md`](architecture.md), [`weaknesses.md`](weaknesses.md), [`fresh_eyes.md`](fresh_eyes.md), [`demo_script.md`](demo_script.md) |

## Honest scope notes (read these first)

- **The corpus is a stand-in.** The client's 600-recipe CMS export is not in this repo. `build_corpus.py` generates
  26 recipes / 34 versioned records with the *same structure and traps* (structured `allergens` + `may_contain`
  fields, 8 recipes in both `original` and `reformulated-2025`, food-safety temperatures). Every claim below is
  about that corpus.
- **Not done by software alone:** the fresh-eyes reviewer from another squad, the squad-timed demo, and the
  human audit of the judge's hand labels. Those are marked `TO DO (human)` in the files that need them.
- Model: `openai/gpt-oss-20b` on Groq (the course default); judge: `llama-3.3-70b-versatile`.
