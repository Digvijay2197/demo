"""Week 9 / Task Set B requirement 3: report the tool count before and after
adding the ingredient-db server, with names, straight from tools/list --
never from our own notes.

    python -m scripts.mcp_discovery_week9 --config mcp_servers/mcp_config.before.json
    python -m scripts.mcp_discovery_week9 --config mcp_servers/mcp_config.json
"""
from __future__ import annotations

import argparse
import json

from agent.mcp_client import discover_tools_sync


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="path to an mcp_config.json; "
                     "defaults to mcp_servers/mcp_config.json")
    args = ap.parse_args()

    tools = discover_tools_sync(args.config)
    names = sorted(t.name for t in tools)
    print(json.dumps({
        "config": args.config or "mcp_servers/mcp_config.json (default)",
        "tool_count": len(names),
        "tool_names": names,
    }, indent=2))


if __name__ == "__main__":
    main()
