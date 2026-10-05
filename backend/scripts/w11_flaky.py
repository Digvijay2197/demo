"""Week 11: how flaky is an eval case? Run chosen case ids N times and report pass rate.

    PROMPT_VERSION=v1 python scripts/w11_flaky.py w11-01 w11-02 e05 --n 5

A case that passes 1/5 on the OLD prompt is not a trustworthy RED; one that
passes 5/5 on the NEW prompt is a trustworthy GREEN.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.getcwd())
os.environ.setdefault("TRACE_LOG", "false")

from scripts.eval_week6 import CASES, run_case  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    by_id = {c[0]: c for c in CASES}
    print(f"prompt_version={os.environ.get('PROMPT_VERSION', 'v1')}")
    for cid in a.ids:
        passes, bad = 0, []
        for _ in range(a.n):
            r = run_case(by_id[cid])
            ok = all(r["checks"].values())
            passes += ok
            if not ok:
                bad.append([k for k, v in r["checks"].items() if not v])
            time.sleep(3)
        print(f"{cid}: {passes}/{a.n} runs pass   failing checks on bad runs: {bad}")
