"""MCP client for the capstone agent: ONE long-lived stdio session, tools DISCOVERED at runtime.

Nothing here names a tool. `tools/list` is called on connect and the result becomes the
model's tool list, so a server that registers a different set (e.g. without
check_substituted_recipe) changes what the agent can do with no agent edit.

The session lives on a background event-loop thread so the sync agent loop can call it,
and the embedding model inside the server loads once instead of once per call.
`trace_id` is stripped from the schema the MODEL sees and injected by us on every call.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from capstone import config

DEFAULT_CONFIG = Path(__file__).resolve().parent / "mcp_config.json"


class McpConnection:
    def __init__(self, config_path: Path = DEFAULT_CONFIG):
        raw = json.loads(Path(config_path).read_text())["mcpServers"]
        self._servers = raw
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tool_owner: dict[str, str] = {}
        self.tools: list[dict] = []        # raw MCP tool defs discovered at runtime
        self._run(self._connect())
        self.call("search_recipes", {"query": "warm up"})   # load the embedding model once, off the request clock

    def _run(self, coro, timeout: float = 900):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _connect(self):
        for name, cfg in self._servers.items():
            cmd = sys.executable if cfg["command"] in ("python", "python3") else cfg["command"]
            cwd = str(config.BACKEND_DIR / cfg.get("cwd", "."))
            env = {**os.environ, "PYTHONPATH": str(config.BACKEND_DIR), "PYTHONIOENCODING": "utf-8"}
            params = StdioServerParameters(command=cmd, args=cfg.get("args", []), cwd=cwd, env=env)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[name] = session
            for t in (await session.list_tools()).tools:      # <- runtime discovery
                self._tool_owner[t.name] = name
                self.tools.append({"name": t.name, "description": t.description or "",
                                   "inputSchema": t.inputSchema})

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._tool_owner)

    def model_tools(self) -> list[dict]:
        """OpenAI-style function specs for bind_tools, minus the plumbing arg."""
        out = []
        for t in self.tools:
            schema = json.loads(json.dumps(t["inputSchema"]))
            schema.get("properties", {}).pop("trace_id", None)
            schema["required"] = [r for r in schema.get("required", []) if r != "trace_id"]
            out.append({"type": "function", "function": {
                "name": t["name"], "description": t["description"], "parameters": schema}})
        return out

    def call(self, name: str, args: dict, trace_id: str = "") -> dict:
        owner = self._tool_owner.get(name)
        if owner is None:
            return {"error": f"unknown tool {name!r}"}
        payload = {**(args or {}), "trace_id": trace_id}

        async def go():
            res = await self._sessions[owner].call_tool(name, payload)
            if getattr(res, "structuredContent", None) is not None:
                sc = res.structuredContent
                return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
            text = "".join(getattr(c, "text", "") for c in res.content)
            try:
                return json.loads(text)
            except ValueError:
                return {"error": text or "empty tool result"}

        try:
            return self._run(go())
        except Exception as exc:  # noqa: BLE001
            return {"error": f"mcp call failed: {exc!r}"}

    def close(self):
        try:
            self._run(self._stack.aclose(), timeout=20)
        except Exception:  # noqa: BLE001
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
