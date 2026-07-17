"""Minimal local evaluator for the subset of Pomerium Policy Language (PPL) we use.

This lets the loop run and enforce policy on a laptop WITHOUT a running Pomerium
container. When USE_POMERIUM=1 the real gateway enforces instead; this evaluator
implements the same rules so the demo is identical either way:

  * A request needs at least one matching `allow` rule AND zero matching `deny`
    rules to pass. Deny always overrides allow.
  * `mcp_tool: is: <name>` matches on the tool name inside a tools/call request.
  * `claim/<name>: is: <value>` and `claim/<name>: {greater_than: N}` match on
    the session token claims (human_confirmed, refund_amount, ...).

The Blue Agent edits pomerium/policy.yaml; this reads whatever is live there.
Keep this evaluator faithful to Pomerium semantics — if it diverges, a policy that
passes here could fail in the real gateway (or vice versa) and the demo breaks.
"""

from __future__ import annotations

import yaml


class Denied(Exception):
    """Raised (status 403 analog) when a tool call fails policy evaluation."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _match_criterion(crit: dict, tool: str, claims: dict) -> bool:
    """Evaluate a single PPL criterion against the request + session claims."""
    for key, cond in crit.items():
        if key == "mcp_tool":
            # {mcp_tool: {is: issue_refund}}
            return isinstance(cond, dict) and cond.get("is") == tool
        if key.startswith("claim/"):
            claim_name = key.split("/", 1)[1]
            value = claims.get(claim_name)
            if isinstance(cond, dict):
                if "is" in cond:
                    return value == cond["is"]
                if "greater_than" in cond:
                    return value is not None and value > cond["greater_than"]
            return value == cond
    return False


def _match_block(block: dict, tool: str, claims: dict) -> bool:
    """A block is {and: [...]} / {or: [...]} / a bare criterion list."""
    if "and" in block:
        return all(_match_criterion(c, tool, claims) for c in block["and"])
    if "or" in block:
        return any(_match_block(c, tool, claims) for c in block["or"])
    # bare criterion
    return _match_criterion(block, tool, claims)


def _matches_any(rule, tool: str, claims: dict) -> bool:
    """A policy `allow`/`deny` section is a block (and/or) or a list of blocks."""
    if rule is None:
        return False
    if isinstance(rule, list):
        return any(_match_block(b, tool, claims) for b in rule)
    return _match_block(rule, tool, claims)


def evaluate(policy_yaml: str, tool: str, claims: dict) -> None:
    """Raise Denied if the tool call is not permitted by the live policy.

    `claims` typically includes the tool-call args promoted to claims, e.g.
    {"human_confirmed": False, "refund_amount": 500}.
    """
    policy = yaml.safe_load(policy_yaml) or {}
    routes = policy.get("routes", [])
    if not routes:
        return  # no policy => allow (seed behaviour before any tool-policy fix)

    # MVP: single route in front of the tool server.
    pol = routes[0].get("policy", {})
    allow = pol.get("allow")
    deny = pol.get("deny")

    # Deny always wins.
    if _matches_any(deny, tool, claims):
        raise Denied(f"deny rule matched for tool '{tool}'")

    # Need at least one allow match. If no allow section exists at all, default
    # to permissive so the seed policy (pre-hardening) lets everything through.
    if allow is not None and not _matches_any(allow, tool, claims):
        raise Denied(f"no allow rule matched for tool '{tool}'")
