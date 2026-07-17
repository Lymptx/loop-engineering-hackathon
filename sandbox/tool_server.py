"""Expose sandbox/tools.py as a small HTTP MCP-style server.

In laptop mode target_agent -> gateway -> tools.py directly, and this file is not
needed. When USE_POMERIUM=1, Pomerium can proxy JSON-RPC tools/list and tools/call
requests to this server, which holds one synthetic SandboxState.

This intentionally uses the Python standard library instead of a framework so the
Docker path stays simple for the hackathon demo.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sandbox.state import SandboxState
from sandbox.tools import DISPATCH, TOOL_DEFS

_STATE = SandboxState.fresh()


def reset_state() -> None:
    global _STATE
    _STATE = SandboxState.fresh()


def list_tools() -> list[dict]:
    return list(TOOL_DEFS)


def call_tool(name: str, arguments: dict) -> dict:
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    return fn(_STATE, **arguments)


def _jsonable(value):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def snapshot_state() -> dict:
    return _jsonable(_STATE)


def _mcp_tool_result(result: dict) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
        "structuredContent": result,
        "isError": bool(result.get("error")),
    }


def handle_rpc(request: dict) -> dict:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "agent-immune-tools", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        }
    elif method == "notifications/initialized":
        result = {}
    elif method == "tools/list":
        result = {"tools": list_tools()}
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or params.get("input") or {}
        result = _mcp_tool_result(call_tool(name, arguments))
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"method not found: {method}"},
        }

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentImmuneToolServer/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send_json({"ok": True})
            return
        if self.path == "/state":
            self._send_json(snapshot_state())
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/reset":
            reset_state()
            self._send_json({"ok": True})
            return
        if self.path.rstrip("/") != "/mcp":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            length = int(self.headers.get("content-length", "0") or 0)
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json({"error": f"bad json: {exc}"}, status=HTTPStatus.BAD_REQUEST)
            return

        response = [handle_rpc(item) for item in payload] if isinstance(payload, list) else handle_rpc(payload)
        self._send_json(response)

    def log_message(self, fmt: str, *args) -> None:
        if os.getenv("TOOL_SERVER_ACCESS_LOG") == "1":
            super().log_message(fmt, *args)

    def _send_json(self, payload, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    host = os.getenv("TOOL_SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("TOOL_SERVER_PORT", "8080"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"tool-server listening on http://{host}:{port}/mcp", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
