"""The number behind the 10x plan: how many tool calls per second can ONE MCP stdio session serve?

No LLM involved. Fires N concurrent search_recipes + check_allergens calls at the single long-lived session
the agent uses, and reports throughput and latency. Result is written to docs/capstone/results/tenx_bench.json.

    cd backend && python scripts/capstone_tenx_bench.py
"""
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CAPSTONE_TRACE"] = "off"

from capstone import config  # noqa: E402
from capstone.mcp_conn import McpConnection  # noqa: E402

N_SEQ, N_CONC = 60, 60
QUERIES = ["shortbread", "chicken thighs", "pancakes", "dal", "granola bars", "pork chops"]


def main() -> None:
    t0 = time.time()
    c = McpConnection()
    cold = time.time() - t0

    def one(i):
        t = time.perf_counter()
        c.call("search_recipes", {"query": QUERIES[i % len(QUERIES)]})
        c.call("check_allergens", {"recipe_id": "R-101", "avoid": ["tree nuts"], "version": "reformulated-2025"})
        return (time.perf_counter() - t) * 1000

    seq = [one(i) for i in range(N_SEQ)]
    t = time.perf_counter()
    with ThreadPoolExecutor(16) as ex:
        conc = list(ex.map(one, range(N_CONC)))
    wall = time.perf_counter() - t
    out = {
        "cold_start_s": round(cold, 1),
        "pair_latency_ms_sequential_p50": round(statistics.median(seq), 1),
        "pair_latency_ms_concurrent_p50": round(statistics.median(conc), 1),
        "pair_latency_ms_concurrent_p95": round(sorted(conc)[int(len(conc) * 0.95) - 1], 1),
        "pairs_per_second_concurrent": round(N_CONC / wall, 1),
        "note": "a 'pair' = search_recipes + check_allergens through ONE shared stdio session, 16 client threads",
    }
    d = config.DOCS_DIR / "results"
    d.mkdir(parents=True, exist_ok=True)
    (d / "tenx_bench.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    c.close()


if __name__ == "__main__":
    main()
