"""The deterministic kitchen logic: no LLM, no retrieval, no network.

Everything safety-relevant lives here so it can be asserted, never judged:

  * allergens are EXACT-MATCHED against the structured `allergens` / `may_contain`
    declaration fields - never inferred from method prose or embedding scores;
  * version resolution (original vs reformulated-2025) is explicit and its
    policy is switchable so the BEFORE/AFTER of the superseded-citation bug is
    measurable (config.version_policy);
  * scaling multiplies quantities and deliberately does NOT multiply cook time;
  * the substituted-recipe check recomputes the declaration AFTER a swap.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from capstone import config

ALLERGEN_CLASSES = ["dairy", "egg", "gluten", "peanut", "tree_nut", "soy", "shellfish", "fish", "sesame"]

# surface form -> classes. Longest alias is matched first. "nut(s)" is read
# conservatively as BOTH peanut and tree_nut (a parent saying "nut-free" means both).
ALIASES = {
    "tree nut": ["tree_nut"], "tree nuts": ["tree_nut"], "tree_nut": ["tree_nut"], "treenut": ["tree_nut"],
    "almond": ["tree_nut"], "almonds": ["tree_nut"], "walnut": ["tree_nut"], "walnuts": ["tree_nut"],
    "cashew": ["tree_nut"], "cashews": ["tree_nut"], "hazelnut": ["tree_nut"], "hazelnuts": ["tree_nut"],
    "pecan": ["tree_nut"], "pecans": ["tree_nut"], "pistachio": ["tree_nut"], "pistachios": ["tree_nut"],
    "peanut": ["peanut"], "peanuts": ["peanut"], "groundnut": ["peanut"],
    "nut": ["peanut", "tree_nut"], "nuts": ["peanut", "tree_nut"],
    "dairy": ["dairy"], "milk": ["dairy"], "lactose": ["dairy"], "cheese": ["dairy"],
    "egg": ["egg"], "eggs": ["egg"],
    "gluten": ["gluten"], "wheat": ["gluten"], "coeliac": ["gluten"], "celiac": ["gluten"],
    "soy": ["soy"], "soya": ["soy"], "soybean": ["soy"],
    "shellfish": ["shellfish"], "shrimp": ["shellfish"], "prawn": ["shellfish"], "crab": ["shellfish"],
    "fish": ["fish"], "sesame": ["sesame"],
}
# Allergens a user may name that the declaration fields do NOT cover. We must say
# "cannot verify" for these - never guess.
UNSUPPORTED = {"mustard", "celery", "lupin", "lupine", "sulphite", "sulphites", "sulfite", "sulfites",
               "mollusc", "molluscs", "corn", "garlic", "onion", "kiwi"}

_ALIAS_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, list(ALIASES) + list(UNSUPPORTED)),
                                                key=len, reverse=True)) + r")\b", re.I)


def normalize_allergens(words) -> tuple[list[str], list[str]]:
    """Free-text allergen words -> (supported classes, unsupported words)."""
    classes: set[str] = set()
    unsupported: set[str] = set()
    for w in words or []:
        w = str(w).strip().lower().replace("-", " ")
        if not w:
            continue
        hits = _ALIAS_RE.findall(w)
        if not hits and w in ALLERGEN_CLASSES:
            classes.add(w)
        for h in hits:
            h = h.lower()
            if h in ALIASES:
                classes.update(ALIASES[h])
            else:
                unsupported.add(h)
        if not hits and w not in ALLERGEN_CLASSES:
            unsupported.add(w)
    return sorted(classes), sorted(unsupported)


# cue patterns: the window of text that follows/precedes an allergy cue
_CUES_AFTER = re.compile(r"(?:allerg(?:ic|y|ies)|intoleran(?:t|ce)|anaphyla\w*|avoid(?:ing)?|"
                         r"can'?t (?:have|eat)|cannot (?:have|eat)|without)\s+(?:to\s+|of\s+)?"
                         r"([^.;?!\n]{0,70})", re.I)
_CLAUSE_END = re.compile(r"\s[-\u2013\u2014]\s|\bI(?:'ve| have| had)\b|\bbut\b|\bso\b", re.I)
_CUES_BEFORE = re.compile(r"([^.;?!\n]{0,40}?)[\s-](?:free|allerg(?:ic|y|ies)|intolerant)\b", re.I)


def extract_avoid(text: str) -> tuple[list[str], list[str]]:
    """Deterministically read the allergens a USER STATED from their question -
    independent of the LLM, so the post-answer guard cannot be talked out of it.
    Only allergen words inside an allergy-cue window count ('I have almond milk'
    alone is a pantry item, not an allergy)."""
    windows = []
    for m in _CUES_AFTER.finditer(text):
        windows.append(_CLAUSE_END.split(m.group(1))[0])
    for m in _CUES_BEFORE.finditer(text):
        windows.append(m.group(1).split()[-1] if m.group(1).split() else "")
        windows.append(m.group(1)[-24:])
    classes: set[str] = set()
    unsupported: set[str] = set()
    for w in windows:
        c, u = normalize_allergens(_ALIAS_RE.findall(w))
        classes.update(c)
        unsupported.update(u)
    return sorted(classes), sorted(unsupported)


# --------------------------------------------------------------------- corpus


@lru_cache(maxsize=1)
def _data() -> dict:
    if not config.RECIPES_JSON.exists():
        from capstone.build_corpus import build
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.RECIPES_JSON.write_text(json.dumps(build(), indent=1, ensure_ascii=False), encoding="utf-8")
    return json.loads(config.RECIPES_JSON.read_text(encoding="utf-8"))


def records() -> list[dict]:
    return _data()["records"]


def substitutions() -> dict:
    return _data()["substitutions"]


def versions_of(recipe_id: str) -> list[dict]:
    return [r for r in records() if r["recipe_id"].lower() == recipe_id.strip().lower()]


class RecipeNotFound(KeyError):
    pass


def get_record(recipe_id: str, version: str | None = None) -> dict:
    """Resolve (id, version) -> one record. With no version the policy decides:
    'naive'    -> the first row indexed for that id (the original);
    'resolved' -> the CURRENT version."""
    vs = versions_of(recipe_id)
    if not vs:
        raise RecipeNotFound(f"no recipe with id {recipe_id!r}")
    if version:
        for r in vs:
            if r["version"] == version:
                return r
        raise RecipeNotFound(f"{recipe_id} has no version {version!r}; it has: "
                             f"{', '.join(r['version'] for r in vs)}")
    if config.version_policy() == "naive":
        return vs[0]
    return next((r for r in vs if r["status"] == "current"), vs[-1])


def cite(rec: dict) -> str:
    return f"[{rec['recipe_id']}@{rec['version']}]"


def citation_url(rec: dict, base: str = "http://localhost:8100") -> str:
    return f"{base}/recipes/{rec['recipe_id']}?version={rec['version']}"


# --------------------------------------------------------------------- allergens


def check_allergens(recipe_id: str, version: str | None, avoid) -> dict:
    """EXACT-MATCH the user's allergens against the structured declaration."""
    rec = get_record(recipe_id, version)
    classes, unsupported = normalize_allergens(avoid)
    per = {}
    for c in classes:
        per[c] = ("contains" if c in rec["allergens"] else
                  "may_contain" if c in rec["may_contain"] else "not_declared")
    conflicts = sorted(c for c, v in per.items() if v != "not_declared")
    if unsupported:
        verdict = "cannot_verify"
    elif any(v == "contains" for v in per.values()):
        verdict = "contains"
    elif any(v == "may_contain" for v in per.values()):
        verdict = "may_contain"
    else:
        verdict = "no_declared_conflict"
    out = {
        "recipe_id": rec["recipe_id"], "version_used": rec["version"], "status": rec["status"],
        "title": rec["title"], "citation": cite(rec), "avoid_classes": classes,
        "per_allergen": per, "conflicts": conflicts, "verdict": verdict,
        "declaration": {"allergens": rec["allergens"], "may_contain": rec["may_contain"]},
        "unsupported_allergens": unsupported,
    }
    if version is None:
        out["version_note"] = f"no version given; policy '{config.version_policy()}' picked {rec['version']}"
    if rec["status"] == "superseded":
        out["warning"] = ("SUPERSEDED version: the current recipe was reformulated. Do not give allergen "
                          "advice from this version.")
    if unsupported:
        out["cannot_verify_reason"] = (f"{', '.join(unsupported)} is not a declared allergen field in this "
                                       "library - say you cannot verify it; do not guess.")
    if verdict == "no_declared_conflict":
        out["caveat"] = "Based on the declaration fields only; this is not a cross-contamination guarantee."
    return out


# --------------------------------------------------------------------- scaling


def _fmt(q: float):
    q = round(q, 2)
    return int(q) if float(q).is_integer() else q


def scale_recipe(recipe_id: str, version: str | None, servings: int) -> dict:
    rec = get_record(recipe_id, version)
    if servings <= 0:
        raise ValueError("servings must be positive")
    f = servings / rec["servings"]
    out = {
        "recipe_id": rec["recipe_id"], "version_used": rec["version"], "citation": cite(rec),
        "title": rec["title"], "base_servings": rec["servings"], "servings": servings,
        "scale_factor": round(f, 3),
        "ingredients": [{"item": i["item"], "qty": _fmt(i["qty"] * f) if i["qty"] is not None else None,
                         "unit": i["unit"]} for i in rec["ingredients"]],
        # NOT scaled - oven time depends on tin/tray depth, not on batch size.
        "cook_min": rec["cook_min"], "oven_c": rec["oven_c"], "scaled_cook_time": False,
        "time_note": ("Cook/bake time is NOT multiplied by the scale factor: it stays about "
                      f"{rec['cook_min']} min per batch; bake in more tins/trays rather than a deeper one, "
                      "and check for doneness."),
        "internal_temp_c": rec["internal_temp_c"], "internal_temp_for": rec["internal_temp_for"],
    }
    if f > 2:
        out["batch_note"] = "Over 2x: cook in several batches/pans; crowding a pan lengthens the time."
    return out


# --------------------------------------------------------------------- substitutions


def lookup_substitution(ingredient: str, avoid=None) -> dict:
    """Test-kitchen table lookup. In 'checked' mode options that carry a class the
    user must avoid are removed (and reported); in 'plain' mode it is a bare table
    lookup - the pre-bonus behaviour."""
    key = ingredient.strip().lower()
    table = substitutions()
    hit = key if key in table else next((k for k in table if k in key or key in k), None)
    if hit is None:
        return {"ingredient": ingredient, "options": [], "error": f"no substitution on file for {ingredient!r}"}
    classes, unsupported = normalize_allergens(avoid)
    opts = [dict(o) for o in table[hit]]
    excluded = []
    if config.substitution_mode() == "checked" and classes:
        kept = []
        for o in opts:
            clash = sorted(set(o["allergens"]) & set(classes))
            (excluded if clash else kept).append({**o, "clashes_with": clash} if clash else o)
        opts = kept
    return {"ingredient": ingredient, "matched": hit, "options": opts,
            "excluded_for_allergen": excluded,
            "note": ("Each option's own allergens are listed. A swap changes the recipe's allergen profile - "
                     "re-check the recipe AS SUBSTITUTED." if config.substitution_mode() == "checked"
                     else "Each option's own allergens are listed.")}


def _allergens_of_substitute(to_item: str) -> list[str]:
    for opts in substitutions().values():
        for o in opts:
            if o["to"].lower() == to_item.strip().lower():
                return list(o["allergens"])
    from capstone.build_corpus import tag
    try:
        return tag(to_item)
    except ValueError:
        return ["tree_nut"]  # explicit-tag item we cannot resolve: assume the worst


def check_substituted_recipe(recipe_id: str, version: str | None, swaps: list[dict], avoid) -> dict:
    """The bonus: recompute the allergen declaration for the recipe AS SUBSTITUTED."""
    rec = get_record(recipe_id, version)
    classes, unsupported = normalize_allergens(avoid)
    ings = [dict(i) for i in rec["ingredients"]]
    applied, unmatched = [], []
    for s in swaps or []:
        frm, to = str(s.get("from_item", s.get("from", ""))).lower(), str(s.get("to_item", s.get("to", "")))
        idx = next((n for n, i in enumerate(ings) if i["item"].lower() == frm), None)
        if idx is None:
            idx = next((n for n, i in enumerate(ings) if frm and (frm in i["item"].lower())), None)
        if idx is None:
            unmatched.append(frm)
            continue
        ings[idx] = {**ings[idx], "item": to, "allergens": _allergens_of_substitute(to)}
        applied.append({"from": rec["ingredients"][idx]["item"], "to": to})
    new_alg = sorted({a for i in ings for a in i["allergens"]})
    introduced = sorted(set(new_alg) - set(rec["allergens"]))
    now_conflicts = sorted(set(new_alg) & set(classes))
    mc_conflicts = sorted(set(rec["may_contain"]) & set(classes))
    safe = not now_conflicts and not mc_conflicts and not unsupported and not unmatched
    return {
        "recipe_id": rec["recipe_id"], "version_used": rec["version"], "citation": cite(rec),
        "swaps_applied": applied, "swaps_unmatched": unmatched,
        "allergens_as_published": rec["allergens"], "may_contain": rec["may_contain"],
        "allergens_as_substituted": new_alg, "introduced_by_swap": introduced,
        "conflicts_with_avoid": sorted(set(now_conflicts) | set(mc_conflicts)),
        "safe_as_substituted": safe,
        "unsupported_allergens": unsupported,
    }


def safe_temp_for(rec: dict) -> int | None:
    return rec.get("internal_temp_c")
