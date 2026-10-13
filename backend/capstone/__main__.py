"""One entry point:

    python -m capstone                       # end-to-end smoke: index, discover MCP tools, answer, show the trace
    python -m capstone ask "question"        # one traced question
    python -m capstone eval [--before] ...   # the whole eval suite + trajectory + taxonomy + report (see eval/run.py)
    python -m capstone trace <trace_id>      # one request across both hops, cost + latency per span
    python -m capstone serve                 # HTTP API with clickable citation links (port 8100)
    python -m capstone mcp                   # run our MCP server on stdio (for any other MCP client)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

DEMO_Q = ("My daughter is allergic to tree nuts and I have 25 minutes. "
          "Can she have the shortbread, and how much flour for 36 pieces?")


def _show(out: dict) -> None:
    print("\n=== ANSWER ===\n" + out["answer"])
    print(f"\ntrace_id={out['trace_id']}  laps={out['laps']}  tokens={out['tokens']}  "
          f"cost=${out['cost_usd']}  latency={out['latency_ms']}ms  guards={out['guards_fired']}")
    print("tools discovered over MCP:", ", ".join(out["tools_discovered"]))
    for c in out["citations"]:
        print(f"  citation: {c['recipe_id']}@{c['version']}  ->  {c['url']}")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "smoke"
    if cmd in ("smoke", "ask"):
        from capstone import agent
        q = " ".join(argv[1:]) if cmd == "ask" and len(argv) > 1 else DEMO_Q
        out = agent.ask(q, verbose=True)
        _show(out)
        print(f"\n(inspect: python -m capstone trace {out['trace_id']})")
        return 0 if not out["error"] else 1
    if cmd == "trace":
        from capstone import obs
        t = obs.load_trace(argv[1])
        print(json.dumps(t, indent=2, ensure_ascii=False) if t else "no such trace")
        return 0 if t else 1
    if cmd == "eval":
        from capstone.eval.run import main as eval_main
        return eval_main(argv[1:])
    if cmd == "serve":
        import uvicorn
        uvicorn.run("capstone.api:app", host="127.0.0.1", port=8100)
        return 0
    if cmd == "mcp":
        from capstone.mcp_server import mcp
        mcp.run(transport="stdio")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
