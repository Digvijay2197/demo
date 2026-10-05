"""Week 11: stopwatch for the support drill.

    python scripts/w11_drill.py start                  # right after the squadmate plants
    python scripts/w11_drill.py found tr_xxxx --slice "answer text + input type"
    python scripts/w11_drill.py found tr_xxxx --slice "..." --timer-by "<squadmate name>"

Verifies the id against the sealed hash and prints elapsed mm:ss.
"""
import argparse
import hashlib
import json
import time

SEAL, STATE = "logs/.plant_seal.json", "logs/.drill_state.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "found"])
    ap.add_argument("trace_id", nargs="?")
    ap.add_argument("--slice", default="")
    ap.add_argument("--timer-by", default="machine stopwatch (no squadmate)")
    a = ap.parse_args()
    if a.cmd == "start":
        json.dump({"t0": time.time()}, open(STATE, "w"))
        print("clock started")
        return
    elapsed = time.time() - json.load(open(STATE))["t0"]
    seal = json.load(open(SEAL))[-1]
    ok = hashlib.sha256((seal["salt"] + a.trace_id).encode()).hexdigest() == seal["sha256"]
    mm, ss = divmod(int(round(elapsed)), 60)
    print(json.dumps({"correct": ok, "time_to_find": f"{mm:02d}:{ss:02d}", "seconds": round(elapsed, 1),
                      "slice": a.slice, "timed_by": a.timer_by, "trace_id": a.trace_id}, indent=2))


if __name__ == "__main__":
    main()
