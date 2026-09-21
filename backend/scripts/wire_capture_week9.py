"""Week 9 / Task Set B requirement 4: capture the RAW JSON-RPC exchange
against the new (ingredient-db) server -- initialize -> tools/list ->
tools/call -- by speaking the wire protocol ourselves instead of going
through mcp.ClientSession, so every byte in wire.json is exactly what
crossed the pipe.

MCP's stdio transport is newline-delimited JSON-RPC 2.0: one message per
line, UTF-8, no Content-Length framing (verified against
mcp/client/stdio/__init__.py's stdout_reader/stdin_writer). This script
opens the server as a subprocess and writes/reads those lines directly.

    python -m scripts.wire_capture_week9 > docs/week9/wire.json
"""
from __future__ import annotations

import json
import subprocess
import sys

PROTOCOL_VERSION = "2025-11-25"


def send(proc: subprocess.Popen, msg: dict) -> str:
    line = json.dumps(msg)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    return line


def recv(proc: subprocess.Popen) -> str:
    line = proc.stdout.readline()
    return line.rstrip("\n")


def main() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "mcp_servers.ingredient_server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, encoding="utf-8",
    )
    frames = []

    # 1. initialize
    req = send(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "week9-wire-capture", "version": "0.1"},
        },
    })
    frames.append({"direction": "client->server", "raw": req})
    resp = recv(proc)
    frames.append({"direction": "server->client", "raw": resp})

    # 2. required notification, no response
    note = send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    frames.append({"direction": "client->server", "raw": note})

    # 3. tools/list
    req = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    frames.append({"direction": "client->server", "raw": req})
    resp = recv(proc)
    frames.append({"direction": "server->client", "raw": resp})

    # 4. tools/call -- deliberately the new server's tool, deliberately a
    # name close-but-not-exact to also exercise the recoverable-error path
    req = send(proc, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "lookup_ingredient", "arguments": {"name": "peanut butter"}},
    })
    frames.append({"direction": "client->server", "raw": req})
    resp = recv(proc)
    frames.append({"direction": "server->client", "raw": resp})

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)

    print(json.dumps(frames, indent=2))


if __name__ == "__main__":
    main()
