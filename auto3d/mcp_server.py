"""MCP server (stdio) that lets an AI agent — Claude Code — work on the open Auto3DModeler part.

Started by Claude Code from the app's chat (see auto3d/agent.py), or by hand from any MCP client:

    py auto3d/mcp_server.py --url http://127.0.0.1:5173

It speaks MCP's JSON-RPC over stdin / stdout (one message per line) and forwards every tool call to the
running app (POST /api/agent/call), which applies it to the part open in the browser.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auto3d.agent_tools import LOCAL_TOOLS, mcp_tool_list  # noqa: E402
from auto3d.guides import guide, guides  # noqa: E402

SERVER_INFO = {"name": "auto3d", "version": "1.0"}
PROTOCOL = "2025-06-18"
CALL_TIMEOUT = 180  # seconds: building a part with many objects or tracing a big picture can take a while


def _unreachable(url: str, why) -> dict:
    return {"content": [{"type": "text", "text": f"Auto3DModeler is not reachable at {url} ({why}). "
                                                 "Is the app running and open in the browser?"}], "isError": True}


def call_app(url: str, name: str, args: dict) -> dict:
    """Forward a tool call to the app; returns an MCP tool result."""
    # connect quickly first: only the tool itself may take long (a refused connection can hang on Windows)
    u = urllib.parse.urlsplit(url)
    try:
        socket.create_connection((u.hostname, u.port or 80), timeout=3).close()
    except OSError as exc:
        return _unreachable(url, exc)
    body = json.dumps({"tool": name, "args": args}).encode()
    req = urllib.request.Request(f"{url}/api/agent/call", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode())
        except Exception:
            return {"content": [{"type": "text", "text": f"The app answered {exc.code}."}], "isError": True}
    except (urllib.error.URLError, TimeoutError) as exc:
        return _unreachable(url, exc)


def handle(msg: dict, url: str):
    """One JSON-RPC message -> response dict (or None for notifications)."""
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification (notifications/initialized, cancelled …)
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or PROTOCOL
        result = {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}, "prompts": {"listChanged": False}},
                  "serverInfo": SERVER_INFO,
                  "instructions": "Tools to inspect and change the parts open in Auto3DModeler: quick parts (drawings, pictures, imports) "
                                  "and 3D models (sketches -> extrude / revolve / hole / fillet / chamfer / shell). Before a task, read the "
                                  "matching guide with get_guide (model-a-part, change-a-model, from-picture, print-prep, assemble-parts). Pick faces "
                                  "and edges with find_refs."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": mcp_tool_list()}
    elif method == "tools/call":
        p = msg.get("params") or {}
        name, args = p.get("name", ""), p.get("arguments") or {}
        if name in LOCAL_TOOLS:  # the guides: no need for the app
            try:
                result = {"content": [{"type": "text", "text": guide(args.get("topic", ""))}]}
            except KeyError as exc:
                result = {"content": [{"type": "text", "text": str(exc.args[0])}], "isError": True}
        else:
            result = call_app(url, name, args)
    elif method == "prompts/list":
        result = {"prompts": [{"name": n, "description": g["description"]} for n, g in guides().items()]}
    elif method == "prompts/get":
        n = (msg.get("params") or {}).get("name", "")
        try:
            g = guides()[n]
        except KeyError:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"No prompt {n}"}}
        result = {"description": g["description"], "messages": [{"role": "user", "content": {"type": "text", "text": g["text"]}}]}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5173")
    url = ap.parse_args().url.rstrip("/")
    stdin = sys.stdin.buffer
    out = sys.stdout.buffer
    for raw in stdin:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            msgs = msg if isinstance(msg, list) else [msg]
            resps = [r for r in (handle(m, url) for m in msgs) if r is not None]
            if not resps:
                continue
            resp = resps if isinstance(msg, list) else resps[0]
        out.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
        out.flush()


if __name__ == "__main__":
    main()
