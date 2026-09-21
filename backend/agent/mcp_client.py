"""MCP client wiring for the Week 9 agent.

This module reads mcp_servers/mcp_config.json and hands every server listed
there to langchain_mcp_adapters, which speaks the MCP handshake
(initialize -> tools/list) for us and returns LangChain-bindable tool
objects. It is the ONLY place server config is read.

Task Set B's whole point: bolting on a second server means editing
mcp_config.json, never this file. Nothing here names "recipe-search" or
"ingredient-db" — it iterates whatever the config contains.
"""
from __future__ import annotations

import asyncio
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BACKEND_DIR / "mcp_servers" / "mcp_config.json"


def load_connections(config_path: Optional[Path] = None) -> dict:
    """Read the server list out of an mcp_config.json and normalize each
    entry into the shape langchain_mcp_adapters expects: relative `cwd`
    resolved against the backend directory (so it doesn't matter where the
    caller's process happens to be running from), and a bare "python"
    command pointed at the interpreter actually running us (so the child
    server uses the same virtualenv, not whatever "python" resolves to on
    PATH)."""
    path = config_path or DEFAULT_CONFIG_PATH
    raw = json.loads(path.read_text())
    connections = {}
    for name, cfg in raw["mcpServers"].items():
        cfg = dict(cfg)
        if cfg.get("command") in ("python", "python3"):
            cfg["command"] = sys.executable
        cwd = cfg.get("cwd")
        if cwd is not None and not Path(cwd).is_absolute():
            cfg["cwd"] = str(BACKEND_DIR / cwd)
        connections[name] = cfg
    return connections


@lru_cache(maxsize=8)
def _client(config_path: Optional[str] = None) -> MultiServerMCPClient:
    connections = load_connections(Path(config_path) if config_path else None)
    return MultiServerMCPClient(connections)


async def discover_tools(config_path: Optional[str] = None) -> list:
    """The tools/list step, merged across every configured server. Returns
    LangChain BaseTool objects whose name/description/args_schema came
    straight from each server's own tool definitions -- nothing here
    hand-declares a tool."""
    return await _client(config_path).get_tools()


def discover_tools_sync(config_path: Optional[str] = None) -> list:
    return asyncio.run(discover_tools(config_path))


async def call_tool(name: str, args: dict, config_path: Optional[str] = None) -> str:
    """Invoke one already-discovered tool by name (tools/call) and return its
    content as a string."""
    tools = await discover_tools(config_path)
    for t in tools:
        if t.name == name:
            result = await t.ainvoke(args)
            return result if isinstance(result, str) else json.dumps(result)
    raise ValueError(f"unknown tool {name!r}")


def call_tool_sync(name: str, args: dict, config_path: Optional[str] = None) -> str:
    return asyncio.run(call_tool(name, args, config_path))
