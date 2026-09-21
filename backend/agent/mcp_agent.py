"""The Week 9 agent: same lap-loop shape as agent/loop.py, but the tool list
comes from MCP discovery (agent/mcp_client.py) instead of a hard-coded
TOOL_SCHEMAS import. Nothing here names "recipe-search" or "ingredient-db" --
it binds whatever tools/list returns, from however many servers
mcp_servers/mcp_config.json lists.

    python -m agent.mcp_agent "look up the allergens and nutrition for peanut butter"

The model call happens ONLY at the `llm.invoke(messages)` line below -- once
per lap, inside this process. Every MCP server (recipe_server.py,
ingredient_server.py) runs no model of its own; it only executes the plain
Python function behind whichever tool the model picked and hands back data.
"""
from __future__ import annotations

import sys
import time
from typing import List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agent.budget import Budget, BudgetExceeded
from agent.llm import Usage, _base_llm, usage_of
from agent.mcp_client import call_tool_sync, discover_tools_sync

SYSTEM_PROMPT = """You are a recipe and ingredient assistant. Use whichever
tools below fit the request -- search and adapt recipes, or look up an
ingredient's allergens and nutrition -- and call a tool again if its result
suggests a corrected name to retry with. Once you have everything the user
asked for, reply in plain text with the answer and stop calling tools."""


def run_mcp_agent(query: str, budget: Optional[Budget] = None,
                   config_path: Optional[str] = None, verbose: bool = False) -> dict:
    budget = budget or Budget()
    tools = discover_tools_sync(config_path)
    llm = _base_llm().bind_tools(tools)

    messages: List = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)]
    usage = Usage()
    started = time.monotonic()
    lap = 0
    trace: List[dict] = []

    while True:
        budget.check(iteration=lap, tokens=usage.total_tokens,
                     cost_usd=usage.cost_usd, started_at=started)
        resp: AIMessage = llm.invoke(messages)
        lap += 1
        usage = usage + usage_of(resp)
        messages.append(resp)

        called = [tc["name"] for tc in (resp.tool_calls or [])]
        if verbose:
            print(f"  lap {lap}: {called or 'final answer'}")

        if resp.tool_calls:
            for tc in resp.tool_calls:
                result = call_tool_sync(tc["name"], tc.get("args") or {}, config_path)
                trace.append({"lap": lap, "tool": tc["name"], "args": tc.get("args") or {},
                              "result": result})
                messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
            continue

        return {
            "query": query,
            "final_text": resp.content or "",
            "trace": trace,
            "tool_names_discovered": sorted(t.name for t in tools),
            "laps": lap,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
        }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    q = " ".join(sys.argv[1:]) or "look up the allergens and nutrition for peanut butter"
    try:
        out = run_mcp_agent(q, verbose=True)
    except BudgetExceeded as be:
        print(f"BUDGET STOP: {be}")
        raise SystemExit(1)
    import json
    print(json.dumps(out, indent=2))
