"""The tool-call gateway the target agent goes through — never the tool server directly.

In laptop mode (USE_POMERIUM=0) this evaluates pomerium/policy.yaml locally via
pomerium/ppl.py, then dispatches to sandbox/tools.py. In gateway mode
(USE_POMERIUM=1) it forwards a tools/call MCP request to a running Pomerium, which
enforces the same policy and proxies to tool_server.py.

Either way, the contract is identical: a denied call returns a 403-style result,
and the verifier can tell an *enforced* block apart from the agent simply choosing
not to call the tool.

Session identity without an IdP: we mint a short-lived signed JWT carrying the
claims Pomerium evaluates (human_confirmed, refund_amount). The legitimate path
sets human_confirmed=true; the attacker path leaves it false. This gives real
policy evaluation without OIDC integration overhead.
"""

from __future__ import annotations

import os
from pathlib import Path

from pomerium.ppl import Denied, evaluate
from sandbox.state import SandboxState
from sandbox.tools import call_tool

_POLICY_PATH = Path(__file__).parents[1] / "pomerium" / "policy.yaml"


def _session_claims(tool: str, args: dict, human_confirmed: bool) -> dict:
    """Promote request context to the claims Pomerium's PPL evaluates.

    The refund amount is surfaced as a claim so a deny rule can compare it to the
    cap. `human_confirmed` comes from the (fake) signed session token.
    """
    claims: dict = {"human_confirmed": human_confirmed}
    if tool == "issue_refund":
        claims["refund_amount"] = args.get("amount")
    return claims


def call_via_gateway(
    state: SandboxState,
    tool: str,
    args: dict,
    *,
    human_confirmed: bool = False,
) -> dict:
    """Route a single tool call through policy enforcement.

    Returns the tool result on success, or {"error": "403 ...", "denied": True}
    when the policy blocks it. The target agent treats the 403 as a normal tool
    result and reasons about it; the verifier reads state to see what actually ran.
    """
    if os.getenv("USE_POMERIUM") == "1":
        return _call_real_pomerium(tool, args, human_confirmed)

    policy_yaml = _POLICY_PATH.read_text(encoding="utf-8") if _POLICY_PATH.exists() else ""
    claims = _session_claims(tool, args, human_confirmed)
    try:
        evaluate(policy_yaml, tool, claims)
    except Denied as d:
        return {"error": f"403 Forbidden: {d.reason}", "denied": True}
    return call_tool(state, tool, args)


def _call_real_pomerium(tool: str, args: dict, human_confirmed: bool) -> dict:
    """Gateway mode. Forward a tools/call MCP request through the running Pomerium.

    TODO(step 6): mint the session JWT (jwt.encode with POMERIUM_JWT_SECRET,
    claim human_confirmed) and POST the tools/call to POMERIUM_URL. Left as a stub
    so laptop mode has zero external dependencies.
    """
    raise NotImplementedError(
        "USE_POMERIUM=1 requires the Pomerium container (see pomerium/docker-compose.yaml). "
        "Use laptop mode (USE_POMERIUM=0) until step 6."
    )
