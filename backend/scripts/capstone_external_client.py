"""A client that shares NO code with the capstone agent: raw `mcp` SDK only (no capstone imports).

Requirement 3 says our MCP server must be called live by a client that isn't ours - Thursday's
fresh-eyes reviewer from another squad. This script is the stand-in you run yourself (and the
thing a reviewer can copy): it speaks the MCP handshake, lists the tools, and calls three of them.
Point ANY other MCP client (Claude Desktop, MCP Inspector, a reviewer's own script) at:

    command: <python>   args: -m capstone.mcp_server   cwd: <repo>/backend

    cd backend && python scripts/capstone_external_client.py
"""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "capstone.mcp_server"], cwd=BACKEND,
                                   env={**os.environ, "PYTHONPATH": BACKEND})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            print("tools/list ->", [t.name for t in tools])
            tid = "ext_client_demo"
            for name, args in [
                ("search_recipes", {"query": "shortbread"}),
                ("check_allergens", {"recipe_id": "R-101", "avoid": ["tree nuts"], "version": "reformulated-2025"}),
                ("check_allergens", {"recipe_id": "R-101", "avoid": ["tree nuts"], "version": "original"}),
            ]:
                res = await s.call_tool(name, {**args, "trace_id": tid})
                body = res.structuredContent or json.loads(res.content[0].text)
                print(f"\n{name}({args}) ->")
                print(json.dumps(body, indent=1)[:700])
            print(f"\nserver-side spans for trace_id={tid} are in backend/logs/capstone_mcp_spans.jsonl")


if __name__ == "__main__":
    asyncio.run(main())
