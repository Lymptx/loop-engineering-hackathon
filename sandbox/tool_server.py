"""Exposes sandbox/tools.py as an MCP server (step 6 — gateway/AWS deployment).

In laptop mode target_agent -> gateway -> tools.py directly, and this file is not
needed. When you stand Pomerium up (USE_POMERIUM=1), Pomerium proxies tools/call
requests to THIS server, which holds the per-round SandboxState.

Left as a runnable skeleton so the MCP wiring is obvious to whoever owns step 6.
"""

from __future__ import annotations

from sandbox.state import SandboxState
from sandbox.tools import DISPATCH, TOOL_DEFS

# Per-process sandbox state. In the Fargate design each round gets a fresh task
# from a clean snapshot; here we just hold one and expose a /reset endpoint.
_STATE = SandboxState.fresh()


def reset_state() -> None:
    global _STATE
    _STATE = SandboxState.fresh()


def _to_mcp_tool(defn: dict) -> dict:
    """tools.py TOOL_DEFS are already MCP-shaped (name/description/input_schema)."""
    return defn


def list_tools() -> list[dict]:
    return [_to_mcp_tool(d) for d in TOOL_DEFS]


def call_tool(name: str, arguments: dict) -> dict:
    fn = DISPATCH.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    return fn(_STATE, **arguments)


# ---------------------------------------------------------------------------
# TODO(step 6): wire the above into an actual MCP server. With the `mcp` package:
#
#   from mcp.server.fastmcp import FastMCP
#   app = FastMCP("agent-immune-tools")
#
#   @app.tool()
#   def lookup_order(order_id: str) -> dict: ...
#   # ... one @app.tool() per capability, delegating to DISPATCH ...
#
#   if __name__ == "__main__":
#       app.run(transport="streamable-http")   # Pomerium proxies to this
#
# Pomerium's route (pomerium/policy.yaml) points `to:` at this server with
# mcp: true, so `mcp_tool` criteria match the tools/call requests.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Placeholder so `python -m sandbox.tool_server` doesn't error before step 6.
    for t in list_tools():
        print(t["name"], "-", t["description"])
