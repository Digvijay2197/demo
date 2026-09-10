"""The four budgets the agent loop enforces, checked together every lap.

An unenforced budget is a comment with ambition (Week 7 common mistake #4), so
``Budget.check`` tests all four each iteration and raises ``BudgetExceeded`` the
moment any one is hit. The loop catches it, logs one structured line, and
returns a partial result flagged ``terminated_by`` — it stops, it does not spin.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    def __init__(self, which: str, value, limit):
        self.which, self.value, self.limit = which, value, limit
        super().__init__(f"budget '{which}' exceeded: {value} >= {limit}")


@dataclass
class Budget:
    max_iterations: int = 10         # LLM laps before we stop
    max_tokens: int = 24_000        # cumulative prompt+completion across all laps
    max_cost_usd: float = 0.020     # cumulative USD across all laps
    wall_clock_s: float = 90.0      # since the loop started

    def check(self, *, iteration: int, tokens: int, cost_usd: float, started_at: float) -> None:
        elapsed = time.monotonic() - started_at
        if iteration >= self.max_iterations:
            raise BudgetExceeded("max_iterations", iteration, self.max_iterations)
        if tokens >= self.max_tokens:
            raise BudgetExceeded("max_tokens", tokens, self.max_tokens)
        if cost_usd >= self.max_cost_usd:
            raise BudgetExceeded("max_cost_usd", round(cost_usd, 5), self.max_cost_usd)
        if elapsed >= self.wall_clock_s:
            raise BudgetExceeded("wall_clock_s", round(elapsed, 1), self.wall_clock_s)
