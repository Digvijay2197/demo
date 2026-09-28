<!-- Soft Suave · The AI Engineering League -->
# Week 10 — verdict.md (KILL)

**KILL the orchestrator.** Pass rate: single agent 100% (7/7) vs orchestrator 29% (2/7) on the same 7 completed requests — a collapse, not a wobble, driven by three separate real failure modes (a worker budget stop, a transient rate-limit error, and two cases that ran clean end-to-end and still dropped a substitution). P99 latency: 51.67s single vs 112.34s orchestrator — more than double, and p99 is the number a client screenshots.
Tokens actually favor the orchestrator here (37,061 vs 60,672, a 0.6x multiplier) — cheaper per token, but that is not the same as cheaper per *correct answer*, and reliability, not the bill, is what broke this race.
Sunk-cost bias, named out loud: we just spent this task building the orchestrator, which pulls hard toward keeping it to justify the work already done — that pull is not evidence either arm is better.
None of these 7 requests need per-input branching the fixed workflow (`agent/workflow.py`) cannot already express in three deterministic steps; splitting those same steps across two LLM-driven workers adds a hand-off tax and a new-failure surface without adding a capability.
