"""Generate a runnable local Pomerium config from the live tool-policy file.

The loop stores just the policy route in ``pomerium/policy.yaml`` because that is
the artifact Blue edits and the in-process PPL simulator evaluates. Real Pomerium
needs a complete config file with runtime flags, address, and a local upstream.

This generator keeps those concerns separate:

* ``policy.yaml`` remains the versioned defense artifact.
* ``generated-config.yaml`` is the local Docker config Pomerium actually reads.

Pomerium's current MCP PPL support authorizes by MCP tool name. The simulator has
extra hackathon-only request claims such as ``refund_amount`` and
``human_confirmed``. For the real local gateway, claim-gated deny branches are
best-effort normalized to tool-name denies where the demo needs an actual
gateway block. The original policy file is not modified.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "pomerium" / "policy.yaml"
GENERATED_CONFIG_PATH = ROOT / "pomerium" / "generated-config.yaml"

LOCAL_FROM = "http://127.0.0.1:18081"
UPSTREAM_MCP = "http://tool-server:8080"


def _load_policy(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _route_policy(policy_doc: dict) -> dict:
    routes = policy_doc.get("routes") or []
    if not routes:
        return {}
    return routes[0].get("policy") or {}


def _criterion_tool_name(criterion: dict) -> str | None:
    if not isinstance(criterion, dict):
        return None
    cond = criterion.get("mcp_tool")
    if isinstance(cond, dict) and isinstance(cond.get("is"), str):
        return cond["is"]
    if isinstance(cond, str):
        return cond
    return None


def _normalize_deny_block(block):
    """Convert simulator-oriented deny rules into real-MCP tool-name rules.

    Native Pomerium MCP policy can match the JSON-RPC ``tools/call`` tool name.
    It does not automatically receive this demo's in-process request claims, so
    claim-gated branches like ``admin_reset AND human_confirmed=false`` would not
    fire in local unauthenticated mode. For the real gateway smoke demo we turn
    those high-risk branches into direct tool-name denies while preserving direct
    ``mcp_tool`` rules.
    """
    if not block:
        return None
    if isinstance(block, list):
        normalized = [_normalize_deny_block(item) for item in block]
        return [item for item in normalized if item]
    if not isinstance(block, dict):
        return None
    if "or" in block:
        normalized = [_normalize_deny_block(item) for item in block["or"]]
        normalized = [item for item in normalized if item]
        return {"or": normalized} if normalized else None
    if "and" in block:
        tool_names = [
            name for name in (_criterion_tool_name(item) for item in block["and"]) if name
        ]
        if not tool_names:
            return None
        # Real local mode has no browser/OIDC claim context. If a rule is scoped
        # to one high-risk tool plus claims, block that tool at the gateway.
        return {"mcp_tool": {"is": tool_names[0]}}
    tool_name = _criterion_tool_name(block)
    if tool_name:
        return {"mcp_tool": {"is": tool_name}}
    return None


def build_config(policy_doc: dict) -> dict:
    source_policy = _route_policy(policy_doc)
    deny = _normalize_deny_block(source_policy.get("deny"))

    route_policy: dict = {
        "allow": {"and": [{"accept": True}]},
    }
    if deny:
        route_policy["deny"] = deny

    return {
        "address": ":18081",
        "insecure_server": True,
        "runtime_flags": {"mcp": True},
        "log_level": "info",
        "authorize_log_fields": [
            "request-id",
            "method",
            "path",
            "mcp-method",
            "mcp-tool",
            "mcp-tool-parameters",
        ],
        "routes": [
            {
                "from": LOCAL_FROM,
                "to": UPSTREAM_MCP,
                "mcp": {"server": {}},
                "policy": route_policy,
            }
        ],
    }


def write_config(
    policy_path: Path = POLICY_PATH,
    output_path: Path = GENERATED_CONFIG_PATH,
) -> Path:
    config = build_config(_load_policy(policy_path))
    output_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return output_path


def main() -> None:
    path = write_config()
    print(path)


if __name__ == "__main__":
    main()
