"""Deterministic, no-network checks for the Week 10 orchestrator
(agent/orchestrator.py) — the degrade-on-failure fallback and the
WorkerHTTPError partial-usage bookkeeping the retry/degrade path depends on.
No Groq call: these lock in the ground truth the live race script is scored
against."""
from agent.contract import RecipeRequest, passes
from agent.llm import Usage
from agent.orchestrator import WorkerHTTPError, WorkerRuntimeError, _degrade_from_partial_recipe


def test_degrade_falls_back_to_the_unscaled_base_recipe():
    req = RecipeRequest("t1", "classic pancakes", 8, ["dairy"])
    err = WorkerHTTPError("GetNutrition", 500, "(test)")
    out = _degrade_from_partial_recipe(req, err)

    assert out["recipe"] == "Classic Pancakes"
    assert out["servings"] == 4          # base servings, NOT the requested 8 — never scaled
    assert out["substitutions"] == []    # never delegated to the substitution worker
    assert out["degraded"] is True
    assert "500" in out["degraded_reason"]


def test_degraded_output_honestly_fails_the_same_judge_as_everyone_else():
    # the degraded fallback still carries the original banned allergen (dairy,
    # via whole milk/butter) and the wrong serving count -- passes() must
    # catch both, exactly as it would for a lying answer, since a degrade
    # that quietly satisfied the checks would be indistinguishable from a lie.
    req = RecipeRequest("t2", "classic pancakes", 8, ["dairy"])
    out = _degrade_from_partial_recipe(req, WorkerHTTPError("GetNutrition", 500))
    checks = passes(req, out)
    assert checks["servings_set"] is False
    assert checks["allergen_free"] is False
    assert not all(checks.values())


def test_worker_http_error_carries_the_tokens_already_spent():
    partial = Usage(prompt_tokens=120, completion_tokens=30)
    err = WorkerHTTPError("GetNutrition", 500, partial_usage=partial, partial_laps=1,
                          partial_tool_calls=1, partial_laps_log=[{"lap": 1}])
    assert err.partial_usage.total_tokens == 150
    assert err.partial_laps == 1 and err.partial_tool_calls == 1
    assert err.status == 500 and err.tool == "GetNutrition"
    assert "HTTP 500" in str(err)


def test_unknown_recipe_degrades_to_empty_not_a_crash():
    req = RecipeRequest("t3", "nonexistent dish", 4, ["dairy"])
    out = _degrade_from_partial_recipe(req, WorkerHTTPError("GetNutrition", 500))
    assert out == {}


def test_worker_runtime_error_carries_the_tokens_already_spent():
    # a genuine mid-loop failure (rate limit, network error, ...) that this
    # module did not inject must still preserve whatever the worker already
    # spent -- observed live: a Groq RateLimitError on lap 2 was silently
    # dropping lap 1's real tokens before this wrapper existed.
    partial = Usage(prompt_tokens=588, completion_tokens=0)
    original = RuntimeError("Error code: 429 - rate_limit_exceeded")
    err = WorkerRuntimeError(original, partial, 1, 1, [{"lap": 1}])
    assert err.partial_usage.total_tokens == 588
    assert err.partial_laps == 1 and err.partial_tool_calls == 1
    assert err.original is original
    assert "429" in str(err)
