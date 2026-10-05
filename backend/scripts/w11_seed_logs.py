"""Week 11: build a week of background traffic for the support drill.

Resamples the REAL traces in logs/real_pool.jsonl (genuine v1 answers, spans,
tokens) across the last 7 days: new trace ids, realistic daily/hourly volume,
40 users, latency/token jitter (+-12%), a few cost outliers. The two known
failing ("bank") answers are held back for w11_plant.py.

    python scripts/w11_seed_logs.py --days 7 --per-day 220 [--seed 11]
"""
import argparse
import copy
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.getcwd())
from eval.dairy_check import dairy_free_violation  # noqa: E402
from rag.observability.tracing import cost_usd  # noqa: E402

BANK_Q = [
    "I'm dairy-free - can I use the ghee in the chicken biryani",
    "I'm allergic to milk, can the chicken biryani be made with ghee",
]


def load_pool(path="logs/real_pool.jsonl"):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    return [r for r in rows if not r.get("error") and r["answer"]
            and r["question"] != "warm up the embedding model"]


def _retotal(r: dict) -> None:
    t = 0.0
    for s in r["spans"]:
        s["start_ms"] = round(t, 1)
        t += s["latency_ms"]
    r["latency_ms"] = round(t, 1)
    r["tokens_in"] = sum(s["tokens_in"] for s in r["spans"])
    r["tokens_out"] = sum(s["tokens_out"] for s in r["spans"])
    r["cost_usd"] = round(sum(s["cost_usd"] for s in r["spans"]), 8)


def rejitter(rec: dict, rnd: random.Random) -> dict:
    r = copy.deepcopy(rec)
    f = rnd.uniform(0.88, 1.12)
    for s in r["spans"]:
        s["latency_ms"] = round(s["latency_ms"] * rnd.uniform(0.88, 1.12), 1)
        if s["tokens_in"]:
            s["tokens_in"] = max(1, int(s["tokens_in"] * f))
            s["tokens_out"] = max(1, int(s["tokens_out"] * rnd.uniform(0.9, 1.1)))
            s["cost_usd"] = cost_usd(s["tokens_in"], s["tokens_out"])
    _retotal(r)
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--per-day", type=int, default=220)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default="logs/traces.jsonl")
    a = ap.parse_args()
    rnd = random.Random(a.seed)

    allrows = load_pool()
    pool = [r for r in allrows if r["question"] not in BANK_Q]
    bank = [r for r in allrows if r["question"] in BANK_Q]
    print(f"pool={len(pool)} real traces, bank={len(bank)} held back "
          f"(bank answers flagged unsafe: {sum(dairy_free_violation(r['answer']) for r in bank)})")
    users = [f"u_{i:03d}" for i in range(1, 41)]
    now = datetime.now(timezone.utc)
    out = []
    for d in range(a.days):
        for _ in range(int(a.per_day * rnd.uniform(0.8, 1.2))):
            hour = min(23, max(0, int(rnd.gauss(14, 4.5))))  # daytime-heavy
            ts = (now - timedelta(days=d + 1)).replace(
                hour=hour, minute=rnd.randrange(60), second=rnd.randrange(60),
                microsecond=rnd.randrange(1000) * 1000)
            r = rejitter(rnd.choice(pool), rnd)
            r["trace_id"] = "tr_" + uuid.UUID(int=rnd.getrandbits(128)).hex[:12]
            r["ts"] = ts.isoformat(timespec="milliseconds")
            r["user_id"] = rnd.choice(users)
            r["session_id"] = "s_" + uuid.UUID(int=rnd.getrandbits(128)).hex[:8]
            if rnd.random() < 0.02:  # cost outlier: a very long answer
                for s in r["spans"]:
                    if s["name"] == "generation":
                        s["tokens_out"] *= 6
                        s["cost_usd"] = cost_usd(s["tokens_in"], s["tokens_out"])
                        s["latency_ms"] = round(s["latency_ms"] * 4, 1)
                _retotal(r)
            out.append(r)
    out.sort(key=lambda r: r["ts"])
    with open(a.out, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open("logs/.bank.jsonl", "w", encoding="utf-8") as f:  # sealed apart from the log
        for r in bank:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} traces over {a.days} days -> {a.out}")


if __name__ == "__main__":
    main()
