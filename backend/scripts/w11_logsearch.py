"""Week 11: find a past answer from logs alone - no trace id needed.

Slices (combine freely):
  time            --since 7d --until 12h  (or ISO timestamps)
  user            --user u_017
  prompt version  --prompt v1
  input type      --type dietary_restriction
  cost outlier    --min-cost 0.0003  / --min-tokens 2000
  question text   --q "dairy"          (regex, case-insens.)
  answer text     --a "ghee|butter"    (regex, case-insens.)   <- the complaint is about the OUTPUT
  derived flag    --flag dairy_free_violation                  <- added in the bonus
  --show TRACE_ID  print the full record

    python scripts/w11_logsearch.py --since 7d --a "ghee|butter|milk" --type dietary_restriction
"""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone

LOG = os.environ.get("TRACE_LOG_PATH") or os.path.join(os.getcwd(), "logs", "traces.jsonl")
_UNITS = {"d": "days", "h": "hours", "m": "minutes"}


def _when(v: str) -> datetime:
    m = re.fullmatch(r"(\d+)([dhm])", v)
    if m:
        return datetime.now(timezone.utc) - timedelta(**{_UNITS[m.group(2)]: int(m.group(1))})
    return datetime.fromisoformat(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--user")
    ap.add_argument("--prompt")
    ap.add_argument("--type")
    ap.add_argument("--min-cost", type=float)
    ap.add_argument("--min-tokens", type=int)
    ap.add_argument("--q")
    ap.add_argument("--a")
    ap.add_argument("--flag")
    ap.add_argument("--show")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--log", default=LOG)
    a = ap.parse_args()
    since = _when(a.since) if a.since else None
    until = _when(a.until) if a.until else None
    qre = re.compile(a.q, re.I) if a.q else None
    are = re.compile(a.a, re.I) if a.a else None

    hits = 0
    with open(a.log, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if a.show:
                if r["trace_id"] == a.show:
                    print(json.dumps(r, indent=2, ensure_ascii=False))
                    return
                continue
            ts = datetime.fromisoformat(r["ts"])
            if since and ts < since:
                continue
            if until and ts > until:
                continue
            if a.user and r["user_id"] != a.user:
                continue
            if a.prompt and r["prompt_version"] != a.prompt:
                continue
            if a.type and r["input_type"] != a.type:
                continue
            if a.min_cost is not None and r["cost_usd"] < a.min_cost:
                continue
            if a.min_tokens is not None and r["tokens_in"] + r["tokens_out"] < a.min_tokens:
                continue
            if qre and not qre.search(r["question"] or ""):
                continue
            if are and not are.search(r["answer"] or ""):
                continue
            if a.flag and not (r.get("answer_flags") or {}).get(a.flag):
                continue
            hits += 1
            if hits <= a.limit:
                print(f"{r['ts'][:19]}  {r['trace_id']}  {r['user_id']:7s} {r['input_type']:19s} "
                      f"${r['cost_usd']:.6f}\n    Q: {(r['question'] or '')[:100]}\n"
                      f"    A: {(r['answer'] or '')[:140]!r}")
    if not a.show:
        print(f"-- {hits} match(es)" + (f" (showing {a.limit})" if hits > a.limit else ""))


if __name__ == "__main__":
    main()
