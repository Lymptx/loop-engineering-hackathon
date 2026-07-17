"""Judge-facing proof that real MCP traffic is allowed and denied by Pomerium."""

from __future__ import annotations

import json
import os
import sys
import time
from urllib import error, request

URL = os.getenv("POMERIUM_URL", "http://127.0.0.1:18081/mcp")
TOKEN = os.getenv("POMERIUM_SERVICE_ACCOUNT_TOKEN")


def call(tool: str, arguments: dict) -> tuple[int, dict | str]:
    payload = {
        "jsonrpc": "2.0",
        "id": f"judge-{tool}",
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    headers = {"content-type": "application/json", "accept": "application/json"}
    if TOKEN:
        headers["authorization"] = f"Bearer {TOKEN}"
    req = request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body: dict | str = json.loads(raw) if raw else {}
        except ValueError:
            body = raw
        return exc.code, body


def denied(status: int, body: dict | str) -> bool:
    if status in {401, 403}:
        return True
    text = json.dumps(body).lower() if isinstance(body, dict) else str(body).lower()
    return "denied" in text or "forbidden" in text or "access denied" in text


def main() -> int:
    last_error: Exception | None = None
    for _ in range(20):
        try:
            allow_status, allow_body = call("lookup_order", {"order_id": "A1001"})
            break
        except (error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(1)
    else:
        print(f"FAIL: Pomerium is unreachable at {URL}: {last_error}", file=sys.stderr)
        return 1

    if allow_status >= 400 or denied(allow_status, allow_body):
        print(
            f"FAIL: safe lookup_order was not allowed: {allow_status} {allow_body}", file=sys.stderr
        )
        return 1
    print(f"PASS allow: lookup_order traversed Pomerium (HTTP {allow_status})")

    deny_status, deny_body = call("internal_diagnostics", {"query": "canary"})
    if not denied(deny_status, deny_body):
        print(
            f"FAIL: internal_diagnostics was not denied: {deny_status} {deny_body}",
            file=sys.stderr,
        )
        return 1
    print(f"PASS deny: internal_diagnostics blocked by Pomerium (HTTP {deny_status})")
    print("Pomerium enforcement proof complete: one native MCP allow + one native MCP deny.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
