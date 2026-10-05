"""Week 11: prove v3 changes NOTHING for questions that state no dairy restriction.

    python scripts/w11_prompt_identity.py        # zero LLM calls, zero tokens

For every suite question, build the exact messages sent to the model under v1
and under v3 (same retrieval, same context) and compare them byte-for-byte.
Questions with no stated restriction must be identical, so v3 cannot regress
them *by construction* (any residual run-to-run difference is model noise that
v1 has too). Restricted questions must differ by exactly the reminder.
"""
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TRACE_LOG", "false")

from rag.generation.groq_service import build_messages  # noqa: E402
from rag.generation.prompt import DIETARY_REMINDER  # noqa: E402
from rag.observability.dairy_check import restriction_stated  # noqa: E402
from rag.retrieval.retriever import retrieve  # noqa: E402
from scripts.eval_week6 import CASES  # noqa: E402

if __name__ == "__main__":
    same = diff_ok = bad = 0
    for case in CASES:
        cid, q = case[0], case[1]
        results = retrieve(q)
        m1, m3 = build_messages(q, results, "v1"), build_messages(q, results, "v3")
        restricted = restriction_stated(q)
        identical = [m.content for m in m1] == [m.content for m in m3]
        if not restricted:
            ok = identical
            same += ok
        else:
            ok = (not identical) and m3[1].content == m1[1].content.replace(
                "Question: ", DIETARY_REMINDER + "Question: ", 1) and m3[0].content == m1[0].content
            diff_ok += ok
        bad += not ok
        print(f"{cid:7s} restricted={str(restricted):5s} v1==v3: {str(identical):5s} -> {'OK' if ok else 'MISMATCH'}   {q[:55]}")
    print(f"\n{same} unrestricted questions byte-identical under v3; {diff_ok} restricted differ by exactly the reminder; {bad} mismatches")
    sys.exit(1 if bad else 0)
