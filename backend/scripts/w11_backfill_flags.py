"""Week 11 bonus: backfill the derived `answer_flags` field onto historic traces.

    python scripts/w11_backfill_flags.py        # rewrites logs/traces.jsonl in place

New traces get the field at write time (answer_service._answer_flags); this
catches up the week already on disk so `w11_logsearch.py --flag
dairy_free_violation` works across all of it.
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from rag.observability.dairy_check import answer_flags  # noqa: E402

LOG = "logs/traces.jsonl"

if __name__ == "__main__":
    force = "--force" in sys.argv   # recompute even where a flag exists (e.g. after fixing the detector)
    rows = [json.loads(line) for line in open(LOG, encoding="utf-8")]
    n = 0
    for r in rows:
        if force or "dairy_restriction_in_question" not in (r.get("answer_flags") or {}):
            r["answer_flags"] = answer_flags(r["question"], r["answer"] or "")
            n += 1
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    bad = sum(1 for r in rows if r["answer_flags"]["dairy_free_violation"])
    print(f"backfilled {n}/{len(rows)} traces; {bad} carry dairy_free_violation=true")
