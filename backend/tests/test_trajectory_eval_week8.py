"""Ground-truth checks for the Week 8 trajectory eval
(scripts/trajectory_eval_week8.py).

These lock in `expected_trajectory()` -- the minimal tool multiset each of
the 10 recipe cases needs -- by hand-derived counts, with no network call.
If the cascade-walking logic itself regresses, this fails in CI without
needing a live agent run; the live run only has to verify what the agent
*actually* did against this already-verified ground truth.
"""
from scripts.trajectory_eval_week8 import REQUESTS, expected_trajectory

# id -> (SearchRecipes, GetNutrition, SubstituteIngredient, steps_needed, alternate_path)
# Every case needs >=1 substitution, so GetNutrition and SubstituteIngredient
# may legitimately land in either order -- that's what alternate_path=True
# records, and why the eval asserts counts (a set), never one fixed sequence.
EXPECTED = {
    "r01_p4":       (1, 1, 2, 4, True),   # milk + butter, both dairy, no cascade
    "r02_p8":       (1, 1, 4, 6, True),   # flour->almond flour; milk->oat milk->rice milk; butter->coconut oil
    "r03_mac6":     (1, 1, 2, 4, True),   # macaroni + roux flour, both gluten
    "r04_mac4nut":  (1, 1, 4, 6, True),   # milk->oat milk; butter->coconut oil; cheddar->cashew->yeast sauce
    "r05_curry4":   (1, 1, 1, 3, True),   # shrimp paste -> fish sauce (fish ok)
    "r06_curry2":   (1, 1, 3, 5, True),   # fish sauce->light soy; shrimp paste->fish sauce->light soy
    "r07_curry8":   (1, 1, 5, 7, True),   # depth-3 cascade on two ingredients
    "r08_bread8":   (1, 1, 2, 4, True),   # butter + egg, walnuts stay
    "r09_noodle4":  (1, 1, 3, 5, True),   # noodles + soy sauce + tofu, three independent swaps
    "r10_cookie12": (1, 1, 2, 4, True),   # butter + choc chips, both dairy
}


def test_all_ten_cases_covered():
    assert {r.id for r in REQUESTS} == set(EXPECTED)


def test_expected_trajectory_matches_hand_derived_counts():
    for req in REQUESTS:
        exp = expected_trajectory(req)
        search, nutrition, subs, steps, alt = EXPECTED[req.id]
        counts = exp["counts"]
        assert counts["SearchRecipes"] == search, req.id
        assert counts["GetNutrition"] == nutrition, req.id
        assert counts["SubstituteIngredient"] == subs, req.id
        assert exp["steps_needed"] == steps, req.id
        assert exp["alternate_path"] == alt, req.id


def test_every_case_accepts_more_than_one_valid_path():
    assert all(expected_trajectory(r)["alternate_path"] for r in REQUESTS)


def test_cascade_flag_implies_a_multi_hop_chain():
    # req.cascade (Week 7's own flag) should agree with there being at least
    # one chain longer than one hop in this week's ground truth.
    for req in REQUESTS:
        chains = expected_trajectory(req)["chains"]
        has_multi_hop = any(len(c) > 1 for c in chains)
        assert has_multi_hop == req.cascade, req.id
