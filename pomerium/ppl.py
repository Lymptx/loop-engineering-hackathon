"""Laptop simulator of Pomerium Policy Language (PPL) — NOT Pomerium itself.

This lets the loop run and enforce tool-policy on a laptop with NO running Pomerium
container and NO external services. It implements the claim-aware subset the
deterministic demo relies on. With USE_POMERIUM=1, live-policy calls instead traverse
the local Pomerium MCP proxy; see sandbox/gateway.py and pomerium/local_config.py.

The real local route can enforce native ``mcp_tool`` criteria. Request-context
claims such as refund amount are simulator-only until an IdP/service-account path
provides those claims to Pomerium.

Semantics implemented (matching Pomerium):
  * Deny always overrides allow.
  * `mcp_tool: {is: <name>}` matches the tool name inside a tools/call request.
  * `claim/<name>: {is: <value>}` and `claim/<name>: {greater_than: N}` match session
    claims (human_confirmed, refund_amount, ...).

Documented MVP boundaries (do not mistake for full PPL):
  * Only `routes[0]` is evaluated. One route in front of the tool server is enough
    for the MVP; multi-route dispatch is out of scope.
  * ABSENT `allow` block => PERMISSIVE (fail-open). This is deliberate: the seed
    policy has no allow/deny, so everything is allowed and the seed defender is
    vulnerable. A present `allow` block requires at least one matching allow rule.
  * MALFORMED policy => FAIL CLOSED. Unparseable YAML raises Denied rather than
    silently allowing.

The Blue Agent edits pomerium/policy.yaml; this reads whatever is live there.
"""

from __future__ import annotations

import yaml


class Denied(Exception):
    """Raised (a 403 analog) when a tool call fails policy evaluation."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _match_criterion(crit: dict, tool: str, claims: dict) -> bool:
    """Evaluate a single PPL criterion against the request + session claims."""
    for key, cond in crit.items():
        if key == "mcp_tool":
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
    """A block is {and: [...]} / {or: [...]} / a bare criterion."""
    if "and" in block:
        return all(_match_criterion(c, tool, claims) for c in block["and"])
    if "or" in block:
        return any(_match_block(c, tool, claims) for c in block["or"])
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

    `claims` includes request context promoted to claims, e.g.
    {"human_confirmed": False, "refund_amount": 500}.
    """
    if not (policy_yaml or "").strip():
        return  # empty policy => allow (pre-seed / no restrictions)

    try:
        policy = yaml.safe_load(policy_yaml) or {}
    except yaml.YAMLError as e:
        # Fail closed: an unparseable policy must not silently allow everything.
        raise Denied(f"malformed policy: {e}") from e

    routes = policy.get("routes") or []
    if not routes:
        return  # no routes => allow (seed behaviour before any tool-policy fix)

    # MVP: single route in front of the tool server.
    pol = routes[0].get("policy") or {}
    allow = pol.get("allow")
    deny = pol.get("deny")

    # Deny always wins.
    if _matches_any(deny, tool, claims):
        raise Denied(f"deny rule matched for tool '{tool}'")

    # A present allow block requires at least one match. Absent allow => permissive.
    if allow is not None and not _matches_any(allow, tool, claims):
        raise Denied(f"no allow rule matched for tool '{tool}'")
