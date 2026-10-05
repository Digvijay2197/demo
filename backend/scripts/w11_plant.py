"""Week 11: plant ONE bad answer in the logs - for a squadmate to run.

    python scripts/w11_plant.py          # prints nothing about WHICH one or WHEN

Draws a real failing trace from the sealed bank, gives it a random time in the
last 7 days (not the last 12 h), a random user, a fresh trace id, and inserts it
in time order. Only a salted hash of the planted trace id is kept (to verify
the find) - the planter's output deliberately reveals nothing.
"""
import hashlib
import json
import os
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
LOG, BANK, SEAL = "logs/traces.jsonl", "logs/.bank.jsonl", "logs/.plant_seal.json"


def main() -> None:
    bank = [json.loads(line) for line in open(BANK, encoding="utf-8")]
    rnd = random.SystemRandom()
    rec = rnd.choice(bank)
    now = datetime.now(timezone.utc)
    ts = now - timedelta(hours=rnd.uniform(12, 24 * 7 - 1))
    rec["trace_id"] = "tr_" + uuid.uuid4().hex[:12]
    rec["ts"] = ts.isoformat(timespec="milliseconds")
    rec["user_id"] = f"u_{rnd.randint(1, 40):03d}"
    rec["session_id"] = "s_" + uuid.uuid4().hex[:8]
    if os.environ.get("W11_FLAGS", "0") == "1":  # post-bonus logger: flag is written at log time
        from rag.observability.dairy_check import answer_flags
        rec["answer_flags"] = answer_flags(rec["question"], rec["answer"])
    rows = [json.loads(line) for line in open(LOG, encoding="utf-8")]
    rows.append(rec)
    rows.sort(key=lambda r: r["ts"])
    with open(LOG, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    salt = secrets.token_hex(8)
    seals = json.load(open(SEAL)) if os.path.exists(SEAL) else []
    seals.append({"salt": salt,
                  "sha256": hashlib.sha256((salt + rec["trace_id"]).encode()).hexdigest(),
                  "planted_at": now.isoformat(timespec="seconds")})
    json.dump(seals, open(SEAL, "w"))
    print("planted 1 bad answer. Do not look. Complaint: 'it recommended a dairy-free "
          "substitution that wasn't dairy-free, sometime last week'.")


if __name__ == "__main__":
    main()
