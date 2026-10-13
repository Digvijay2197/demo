"""The ONE LLM judge in the suite - and what it is NOT allowed to judge.

It grades prose quality (helpful + faithful to the tool results) as PASS/FAIL. It never sees a
question about allergen safety as a thing to decide: allergen correctness is asserted in
assertions.py. A different model family from the generator is used on purpose (it has its own
rate-limit quota and does not grade its own homework).

Validated against hand labels on INTEGRATED outputs (eval/judge_labels.json); the suite reports
the agreement number and refuses to call the judge 'trusted' below 85%.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

JUDGE_MODEL = os.environ.get("CAPSTONE_JUDGE_MODEL", "llama-3.3-70b-versatile")

SYSTEM = """You grade ONE answer from a recipe assistant. Grade ONLY prose quality:
PASS = the answer is helpful for what the user asked AND every recipe fact it states (ingredients,
quantities, times, temperatures) is supported by the TOOL RESULTS shown. A clear honest refusal
('not in the library', 'cannot verify') is a PASS when the tool results show the thing is missing.
FAIL = it ignores part of the question, invents a fact not in the tool results, or is evasive.
Do NOT judge whether a recipe is allergen-safe - that is checked elsewhere.
Reply ONLY as JSON: {"verdict": "PASS" or "FAIL", "reason": "<one sentence>"}"""


@lru_cache(maxsize=1)
def _judge_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model=JUDGE_MODEL, temperature=0, api_key=os.environ["GROQ_API_KEY"], max_retries=4)


def _compact(tool_calls: list[dict], limit: int = 2200) -> str:
    return json.dumps([{"tool": t["tool"], "args": t["args"], "result": t["result"]} for t in tool_calls],
                      separators=(",", ":"))[:limit]


def judge(question: str, answer: str, tool_calls: list[dict]) -> dict:
    msg = [{"role": "system", "content": SYSTEM},
           {"role": "user", "content": f"QUESTION: {question}\n\nTOOL RESULTS: {_compact(tool_calls)}\n\nANSWER: {answer}"}]
    raw = _judge_llm().invoke(msg).content or ""
    try:
        d = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        v = str(d.get("verdict", "")).upper()
        return {"verdict": v if v in ("PASS", "FAIL") else None, "reason": d.get("reason", "")}
    except Exception:  # noqa: BLE001
        return {"verdict": None, "reason": f"unparseable: {raw[:80]}"}


def validate(labels_path: str) -> dict:
    """Agreement between the judge and hand labels (label 1 = PASS, 0 = FAIL)."""
    labels = json.load(open(labels_path, encoding="utf-8"))["labels"]
    rows, agree = [], 0
    for lab in labels:
        j = judge(lab["question"], lab["answer"], lab.get("tool_calls", []))
        got = {"PASS": 1, "FAIL": 0}.get(j["verdict"])
        ok = got == lab["human"]
        agree += ok
        rows.append({"id": lab["id"], "human": lab["human"], "judge": got, "agree": ok, "reason": j["reason"]})
    n = len(labels)
    fp = sum(1 for r in rows if r["judge"] == 1 and r["human"] == 0)
    fn = sum(1 for r in rows if r["judge"] == 0 and r["human"] == 1)
    return {"n": n, "agree": agree, "agreement": round(agree / n, 3) if n else None,
            "judge_passes_a_bad_answer": fp, "judge_fails_a_good_answer": fn,
            "clears_85": bool(n) and agree / n >= 0.85, "model": JUDGE_MODEL, "rows": rows}
