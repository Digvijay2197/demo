<!-- Soft Suave · The AI Engineering League -->
# Week 10 Practical — Task Set B

## Race the kitchen squad against your single agent

| | |
|---|---|
| Domain | Recipes & food |
| Week | 10 — Multi-Agent & A2A — With Evidence, Not Fashion |
| Module | M5 — MCP, Multi-agent & A2A |
| Sat on | Week 11 · Monday |
| Marks | 100 |

> **This is an extension of the app you already built in Week 10.** It is not a build from scratch, and it tests only this week's concepts. Bring your numbers written down.


---

## 1. Problem statement

You spent last week building an orchestrator that decomposes a cooking question, delegates to a substitution worker and an allergen/nutrition worker, and synthesises the answer. Your product lead wants to know whether it beats the single agent you already had, or just costs more per question. Race them today on the same 10 Week-6 eval cases and report the bill alongside the pass rate.


---

## 2. Requirements

1. Run the SAME 10 Week-6 eval cases through both the single agent and the orchestrator, with the same judge. Do not write new cases — a changed eval set voids the comparison.
2. Report all four numbers for BOTH arms in one table: pass rate, p50 and p99 latency, total tokens, cost per question.
3. Compute the context re-send multiplier (multi tokens / single tokens, one decimal place) and attribute the single largest token share to a named hand-off from your log — e.g. "orchestrator -> allergen worker resend, 41% of all tokens".
4. Inject one worker failure: make the allergen worker return a 500 on one case. Record what the orchestrator actually did — retried, degraded to a partial answer, or lied by synthesising an allergen claim the worker never made — and say which in one line.
5. Write the verdict: keep or kill, citing at least two of the four numbers, and name the sunk-cost bias out loud before you state it.


---

## 3. Expected output

race_table.md (4 metrics x 2 arms), handoffs.log with per-hand-off token counts, multiplier line with the attributed hand-off, failure_case.md, verdict.md (max 10 lines).


---

## 4. Evaluation rubric

| Criterion | Points |
|---|---|
| All four numbers reported for BOTH arms on the same 10 Week-6 cases: pass rate, p50/p99 latency, total tokens, cost per task | 30 |
| Context re-send multiplier computed and attributed to a specific hand-off from the log | 25 |
| Worker failure injected and the orchestrator's actual behaviour (retry / degrade / lie) recorded honestly | 20 |
| Verdict cites at least two of the four numbers and names the sunk-cost bias out loud | 15 |
| Hand-off log with per-hand-off token counts | 10 |
| **Total** | **100** |

*Zero points for polish, UI, or "it works". This mirrors the House rubric: failure-finding and a number that moved are what score.*


---

## 5. Bonus challenge

Publish the AgentCard your orchestrator would advertise (skills, input/output modes, auth), then map the failed case onto the A2A task lifecycle: state whether that case should have ended failed or paused at input-required to ask the user for their allergy list, and say in two lines what A2A buys you over a plain REST call to the worker.


---

## 6. Submission checklist

- [ ] race_table.md — 4 metrics x 2 arms, same 10 cases named
- [ ] handoffs.log — every hand-off with its token count
- [ ] Multiplier line: multi/single tokens to one decimal, with the dominant hand-off named
- [ ] failure_case.md — the injected 500 and what the orchestrator actually did
- [ ] verdict.md — keep/kill, two numbers cited, sunk-cost named


---

## 7. Common mistakes

- **Declaring multi-agent the winner on pass rate while ignoring a 9x token bill — either result clears the gate, but only with all four numbers.**
- **Building a fresh eval set because the Week-6 cases 'do not suit the orchestrator' — you have just changed the ruler mid-measurement and neither number means anything now.**
- **Passing the whole recipe corpus plus the full ingredient table to both workers, then concluding multi-agent is inherently expensive — you tested your context strategy, not the pattern.**
- **Giving the substitution worker every tool the single agent had, which deletes the narrow-prompt-fewer-tools constraint that was the only plausible source of a win.**
- **Reporting p50 only because p99 was embarrassing — the client notices the p99, which is exactly the question someone screenshots.**
- **Letting the synthesis prompt drop the allergen worker's caveat to keep the answer tidy — the quality loss is in synthesis, and this is how it hides from your pass rate.**


---

*Set B of 6. Sets A–F are equivalent in difficulty and objectives; only the domain differs.*
