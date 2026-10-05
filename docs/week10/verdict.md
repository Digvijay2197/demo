<!-- Soft Suave · The AI Engineering League -->
# Week 10 — verdict.md (KILL)

**KILL the orchestrator.** Pass rate: single agent 90% vs orchestrator 30% on the same 10 requests. Total tokens: single agent 80,204 vs orchestrator 50,783 — a 0.6x re-send multiplier (56.3% in orchestrator->nutrition_worker), but that is a lower bound: 5 of 10 requests died on worker budget stops with their wasted laps logged as 0 tokens.
P99 latency also moved: 62.86s single vs 113.13s orchestrator (the number a client screenshots, not p50).

Sunk-cost bias, named out loud: we just spent this task building the orchestrator, which pulls hard toward keeping it to justify the work already done — that pull is not evidence either arm is better.

None of the 10 requests need per-input branching the workflow (agent/workflow.py) cannot already express in three fixed steps; splitting those same three steps across two LLM-driven workers adds hand-off tax without adding a capability. Keep the orchestrator pattern only for a request an enumerable pipeline genuinely cannot express — none of these ten are that.
