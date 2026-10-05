<!-- Soft Suave · The AI Engineering League -->
# Week 10 — race execution notes (the quota story)

> **UPDATE 2026-09-30:** the quota refilled and the race was re-run live on
> all 10 requests, both arms. `docs/week10/` now reports n=10 (single 90%,
> orchestrator 30%); the 7-case reconstruction described below is superseded.
> Raw output: [week10/raw_run_full10.log](week10/raw_run_full10.log). The
> history below is kept for the record.

The live race against Groq (`openai/gpt-oss-20b`, same key every other week's
scripts use) hit the account's free-tier **200,000-tokens/day** quota
partway through the 10-request race. This is what happened and why the final
`docs/week10/` numbers cover 7 of the 10 requests rather than all 10.

**Timeline:**
1. First full attempt (`scripts/race_week10.py --pace 2`, no `--resume` yet —
   the flag didn't exist): completed r01-r07 on both arms with real,
   independent LLM calls; r08 got a partial single-agent attempt (1 lap)
   before the 429 hit; r09/r10 got zero attempts. Raw output:
   [docs/week10/raw_run.log](week10/raw_run.log).
2. A direct check confirmed the cause: `Rate limit reached ... tokens per day
   (TPD): Limit 200000, Used 199326` — a hard daily cap, not a bug.
3. A checkpoint/resume mechanism was added to `race_week10.py` (`--resume`)
   so a later re-run would not have to re-spend quota on the 7 cases that
   already completed cleanly — but it was added *after* the first run, so no
   checkpoint existed yet for that run.
4. A background watcher polled quota every 10 minutes with a near-zero-cost
   check call. It found quota briefly available (the daily bucket refills
   continuously, ~2.3 tokens/sec = 200000 ÷ 86400s) and auto-triggered
   `--resume`. Since no checkpoint existed, this re-ran r01-r02 from scratch
   (re-spending quota on cases already done) and then re-hit the wall
   immediately after, leaving r03-r10 empty this time — a worse outcome than
   the first attempt, on its own.
5. Given the refill rate, a full clean 10-request re-run needs on the order
   of 100,000-115,000 tokens of headroom, i.e. **~12-14 hours** of continuous
   refill from empty — not practical to wait out synchronously.
6. Decision (confirmed with the project owner): reconstruct the four
   required numbers from the FIRST run's real, complete data for the 7
   requests that did genuinely finish on both arms, and exclude r08-r10
   explicitly rather than fabricate or silently drop them. `docs/week10/`
   states this coverage caveat up front in every file it appears in.

**A real bug this surfaced and fixed:** r08's orchestrator result (excluded
from the final table anyway, but visible in `raw_run.log`) shows the
nutrition worker completing a real `SearchRecipes` call (588 tokens) and the
overall request still reporting `tok=0`. A genuine exception mid-worker (a
rate limit, not the malformed-tool-call retry pattern `agent/orchestrator.py`
already handled) was propagating out of the worker loop without preserving
what that worker had already spent — silently understating cost, the exact
failure mode the module's own `WorkerHTTPError` docstring warned against for
the *injected* case but did not yet cover for a *genuine* one. This is now
fixed (`WorkerRuntimeError`, same partial-usage-preservation pattern as
`BudgetExceeded` and `WorkerHTTPError`) and covered by
`tests/test_orchestrator.py`. It did not corrupt any number in the final
7-request table (r08 is excluded from it), but would have understated a
future run's token bill had it stayed unfixed.
