"""Deterministic tests for the capstone: no LLM, no network, no embeddings."""
import json

import pytest

from capstone import config, domain, guards, obs


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    monkeypatch.setenv("CAPSTONE_VERSION_POLICY", "resolved")
    monkeypatch.setenv("CAPSTONE_SUBSTITUTION", "checked")
    monkeypatch.setenv("CAPSTONE_TRACE", "off")


# ---- corpus integrity ---------------------------------------------------------------------------
def test_declaration_equals_union_of_ingredient_tags():
    for r in domain.records():
        assert r["allergens"] == sorted({a for i in r["ingredients"] for a in i["allergens"]}), r["recipe_id"]


def test_eight_recipes_have_both_versions_and_old_one_is_superseded():
    pairs = {}
    for r in domain.records():
        pairs.setdefault(r["recipe_id"], []).append(r)
    versioned = {k: v for k, v in pairs.items() if len(v) == 2}
    assert len(versioned) == 8
    for v in versioned.values():
        assert {x["version"]: x["status"] for x in v} == {"original": "superseded", "reformulated-2025": "current"}


# ---- allergen exact match -----------------------------------------------------------------------
def test_shortbread_versions_differ_on_tree_nut():
    assert domain.check_allergens("R-101", "original", ["tree nuts"])["verdict"] == "no_declared_conflict"
    assert domain.check_allergens("R-101", "reformulated-2025", ["tree nuts"])["verdict"] == "contains"


def test_may_contain_is_a_conflict_not_prose():
    r = domain.check_allergens("R-103", "reformulated-2025", ["peanut"])
    assert r["verdict"] == "may_contain" and r["per_allergen"]["peanut"] == "may_contain"


def test_nuts_means_both_peanut_and_tree_nut():
    assert domain.normalize_allergens(["nuts"])[0] == ["peanut", "tree_nut"]


def test_unsupported_allergen_is_cannot_verify_never_a_guess():
    r = domain.check_allergens("R-105", None, ["mustard"])
    assert r["verdict"] == "cannot_verify" and r["unsupported_allergens"] == ["mustard"]


def test_allergen_check_ignores_method_prose():
    # R-206's method says nothing about dairy but its declaration does.
    assert domain.check_allergens("R-206", None, ["dairy"])["verdict"] == "contains"


# ---- version policy (the BEFORE/AFTER switch) ---------------------------------------------------
def test_resolved_policy_defaults_to_current_version():
    assert domain.get_record("R-101")["version"] == "reformulated-2025"


def test_naive_policy_returns_superseded_original(monkeypatch):
    monkeypatch.setenv("CAPSTONE_VERSION_POLICY", "naive")
    assert domain.get_record("R-101")["version"] == "original"   # the bug the client lived with
    assert domain.check_allergens("R-101", None, ["tree nuts"])["verdict"] == "no_declared_conflict"


def test_unknown_version_names_the_valid_ones():
    with pytest.raises(domain.RecipeNotFound, match="reformulated-2025"):
        domain.get_record("R-101", "2019")


# ---- scaling ------------------------------------------------------------------------------------
def test_scaling_multiplies_quantities_but_not_cook_time():
    s = domain.scale_recipe("R-101", "reformulated-2025", 36)
    flour = next(i for i in s["ingredients"] if i["item"] == "all-purpose flour")
    assert flour["qty"] == 750
    assert s["cook_min"] == 20 and s["scaled_cook_time"] is False and "NOT multiplied" in s["time_note"]


def test_scaling_carries_safe_internal_temperature():
    s = domain.scale_recipe("R-201", None, 12)
    assert s["internal_temp_c"] == 74 and s["cook_min"] == 45


# ---- substitution chain (bonus) -----------------------------------------------------------------
def test_checked_lookup_filters_options_that_carry_an_avoided_allergen():
    r = domain.lookup_substitution("whole milk", ["nuts"])
    assert "almond milk" not in [o["to"] for o in r["options"]]
    assert "almond milk" in [o["to"] for o in r["excluded_for_allergen"]]


def test_plain_lookup_still_offers_the_unsafe_swap(monkeypatch):
    monkeypatch.setenv("CAPSTONE_SUBSTITUTION", "plain")
    r = domain.lookup_substitution("whole milk", ["nuts"])
    assert r["options"][0]["to"] == "almond milk"          # the pre-bonus system's first suggestion


def test_nut_free_recipe_becomes_unsafe_after_the_systems_own_swap():
    assert domain.check_allergens("R-217", None, ["nuts"])["verdict"] == "no_declared_conflict"
    c = domain.check_substituted_recipe("R-217", None, [{"from_item": "whole milk", "to_item": "almond milk"}], ["nuts"])
    assert c["safe_as_substituted"] is False and c["introduced_by_swap"] == ["tree_nut"]


def test_safe_swap_stays_safe():
    c = domain.check_substituted_recipe("R-217", None, [{"from_item": "whole milk", "to_item": "oat milk"}], ["nuts"])
    assert c["safe_as_substituted"] is True


# ---- deterministic parse of what the USER stated ------------------------------------------------
@pytest.mark.parametrize("q,classes", [
    ("My daughter is allergic to tree nuts. Can she have the shortbread?", ["tree_nut"]),
    ("Is the classic shortbread nut-free?", ["peanut", "tree_nut"]),
    ("I have almond milk and butter, nothing else", []),            # pantry items are not allergies
    ("dairy-free and nut-free please", ["dairy", "peanut", "tree_nut"]),
])
def test_extract_avoid(q, classes):
    assert domain.extract_avoid(q)[0] == classes


def test_mustard_is_reported_unsupported():
    assert domain.extract_avoid("my son has a mustard allergy") == ([], ["mustard"])


# ---- guards -------------------------------------------------------------------------------------
Q = "My daughter is allergic to tree nuts. Can she have the shortbread?"


def test_guard_rewrites_an_endorsement_of_a_conflicting_recipe():
    ans = "Yes, she can have the Classic Shortbread [R-101@reformulated-2025]."
    final, fired, _ = guards.apply_guards(Q, ans, [])
    assert "allergen_endorsement" in fired and "can't recommend" in final


def test_guard_leaves_a_correct_warning_alone():
    ans = "No - the shortbread [R-101@reformulated-2025] contains tree nuts, so it is not safe."
    final, fired, _ = guards.apply_guards(Q, ans, [])
    assert fired == [] and final == ans


def test_guard_catches_superseded_citation():
    ans = "The shortbread [R-101@original] has no nut ingredients, so it is fine."
    final, fired, a = guards.apply_guards(Q, ans, [])
    assert "superseded_version" in fired and "[R-101@reformulated-2025]" in final


def test_explicit_request_for_the_original_may_cite_it():
    a = guards.assess("What did the original shortbread contain?", "It used butter [R-101@original].", [])
    assert a["superseded_cited"] == []


def test_negated_contain_is_not_a_warning():
    ans = "The shortbread [R-101@reformulated-2025] does not contain nuts."
    assert guards.endorses(ans, "R-101", "reformulated-2025")


def test_safe_temperature_is_appended_when_dropped():
    q = "How do I cook the lemon herb chicken thighs?"
    final, fired, _ = guards.apply_guards(q, "Roast until golden and cooked through [R-201@original].", [])
    assert "safe_temp_appended" in fired and "74°C" in final


def test_safe_temperature_present_is_left_alone():
    q = "How do I cook the lemon herb chicken thighs?"
    _, fired, _ = guards.apply_guards(q, "Roast to 74°C inside [R-201@original].", [])
    assert fired == []


def test_unsafe_swap_proposed_by_the_system_is_caught():
    calls = [{"tool": "lookup_substitution", "args": {}, "result": domain.lookup_substitution("whole milk", None)}]
    q = "I have oats, almond milk, honey. My toddler is allergic to nuts. What can I make?"
    ans = "Make overnight oats [R-217@original] using almond milk instead of whole milk."
    final, fired, a = guards.apply_guards(q, ans, calls)
    assert "substitution_introduced_allergen" in fired and "introduce" in final


def test_citation_normalisation_of_typographic_hyphens():
    assert guards.citations(guards.norm("see [R‑01@x] and (R-101@reformulated‑2025)"))[0][1] == "reformulated-2025"


# ---- observability: PII line + trace id across the hop ------------------------------------------
def test_redaction_strips_names_relationships_ages_contacts():
    t = "My daughter Priya (aged 6) is allergic to peanuts, email me at mum@example.com or +44 7700 900123"
    r = obs.redact(t)
    for leaked in ("Priya", "daughter", "mum@example.com", "7700", "aged 6"):
        assert leaked not in r
    assert "peanuts" in r          # the allergen class itself is kept - it is what we need to debug


def test_trace_never_stores_raw_question_or_user_id(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPSTONE_TRACE", "on")
    monkeypatch.setenv("CAPSTONE_TRACE_LOG", str(tmp_path / "t.jsonl"))
    monkeypatch.delenv("CAPSTONE_LOG_USER", raising=False)
    tr = obs.start_trace("My son Arjun has a nut allergy", ["tree_nut"], [], user_id="alice@example.com")
    obs.finish_trace(answer="Hi Arjun's mum", raw_answer="x", refused=False)
    text = (tmp_path / "t.jsonl").read_text()
    assert "Arjun" not in text and "alice" not in text and "tree_nut" in text
    assert tr.trace_id in text


def test_trace_id_joins_client_and_server_spans(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPSTONE_TRACE", "on")
    monkeypatch.setenv("CAPSTONE_TRACE_LOG", str(tmp_path / "t.jsonl"))
    monkeypatch.setenv("CAPSTONE_MCP_SPAN_LOG", str(tmp_path / "s.jsonl"))
    tr = obs.start_trace("q", [], [])
    with obs.span("mcp:check_allergens", "mcp_call"):
        obs.log_server_span(tr.trace_id, "check_allergens", 1.5)   # what the server process does
    obs.finish_trace(answer="a")
    t = obs.load_trace(tr.trace_id)
    assert t["trace_id_survived_mcp_hop"] and t["mcp_server_spans"][0]["tool"] == "check_allergens"


# ---- regressions found by the first full eval run (see docs/capstone/closed_loop.md) -------------
def test_correct_warning_phrased_as_conflict_is_not_rewritten():
    ans = ("I'm sorry, but the recipe contains tree nuts. The allergen check for the current version "
           "(R-101@reformulated-2025) shows a conflict with tree nuts.")
    _, fired, _ = guards.apply_guards(Q, ans, [])
    assert fired == []


def test_bare_recipe_id_gets_the_version_the_tools_used():
    calls = [{"tool": "check_allergens", "args": {"recipe_id": "R-104"},
              "result": {"recipe_id": "R-104", "version_used": "reformulated-2025"}}]
    final, fired, _ = guards.apply_guards("Do you have nut-free banana bread?",
                                          "The banana bread (R-104) contains tree nuts, so it is not nut-free.", calls)
    assert "citation_version_added" in fired and "[R-104@reformulated-2025]" in final


def test_swap_that_removes_the_allergen_is_not_flagged_as_endorsement():
    q = "Pesto pasta without the pine nuts please - I have sunflower seeds. My kid is allergic to tree nuts."
    calls = [{"tool": "lookup_substitution", "args": {}, "result": domain.lookup_substitution("pine nuts", ["tree nuts"])}]
    final, fired, a = guards.apply_guards(q, "Use sunflower seeds instead [R-209@original]; it is safe after the swap.", calls)
    assert a["unsupported"] == [] and "allergen_endorsement" not in fired


def test_pantry_item_after_a_dash_is_not_an_allergen():
    assert domain.extract_avoid("without the pine nuts please - I have sunflower seeds")[1] == []
