<!-- Soft Suave · The AI Engineering League -->
# Week 10 — race_table.md

Same 10 requests as Week 7/8 (`scripts/race_week7.REQUESTS`), same judge (`agent/contract.py` `passes()` — deterministic assertions, no LLM judge, per the Week 7 precedent): r01_p4, r02_p8, r03_mac6, r04_mac4nut, r05_curry4, r06_curry2, r07_curry8, r08_bread8, r09_noodle4, r10_cookie12

| metric | single agent (`agent/loop.py`) | orchestrator (`agent/orchestrator.py`) |
|---|---:|---:|
| pass rate | 90% (9/10) | 30% (3/10) |
| p50 latency | 41.56s | 101.70s |
| p99 latency | 62.86s | 113.13s |
| total tokens | 80,204 | 50,783 |
| cost / question (mean) | $0.001048 | $0.000750 |
| total cost (10 requests) | $0.010480 | $0.007499 |

**Context re-send multiplier: 0.6x** (orchestrator total tokens / single-agent total tokens) — attributed to **orchestrator->nutrition_worker**, 56.3% of all orchestrator tokens across the 10 requests.

hand-off token share (sum over all 10 requests):

| hand-off | tokens | % of orchestrator total |
|---|---:|---:|
| orchestrator->nutrition_worker | 28,578 | 56.3% |
| orchestrator->substitution_worker | 20,043 | 39.5% |
| orchestrator->synthesis | 2,162 | 4.3% |

Per-request rows: [race.csv](race.csv).

Methodology note: the single agent runs one shared `Budget()` (max 10 laps / 24k tokens / $0.02 / 90s) for the whole request. The orchestrator gives each worker its OWN fresh `Budget()` with the same limits — three independent allowances, not one shared ceiling.

**This asymmetry DID decide the race.** In 5 of the 10 orchestrator requests (r03_mac6, r04_mac4nut, r07_curry8, r09_noodle4, r10_cookie12) the substitution worker hit its 90s `wall_clock_s` budget after ~9 laps without a single successful call (mostly mis-cased tool names retried round after round), so the request never reached synthesis and failed the judge. Those aborted laps are logged with `total=0` tokens, so **the orchestrator's 50,783 tokens / 0.6x multiplier is a lower bound**: real spend on the failed laps is uncounted. Read 0.6x as "cheaper only because half of it died early", not as a genuine saving. Reliability and latency are the trustworthy numbers here.

Coverage: all 10 cases ran live on both arms (a first attempt hit the Groq 200k-tokens/day quota; see [../week10-race-notes.md](../week10-race-notes.md)).
