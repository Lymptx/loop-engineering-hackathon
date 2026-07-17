"""Run application tool calls through Pomerium and print verifier-grade evidence."""

from __future__ import annotations

import json
import os

from sandbox.gateway import call_via_gateway
from sandbox.state import SandboxState


def main() -> int:
    os.environ["USE_POMERIUM"] = "1"
    state = SandboxState.fresh()
    session_id = "judge-pomerium-proof"

    allowed = call_via_gateway(
        state,
        "lookup_order",
        {"order_id": "A1001"},
        session_id=session_id,
        authorization_source="judge_demo",
    )
    denied = call_via_gateway(
        state,
        "internal_diagnostics",
        {"query": "canary"},
        session_id=session_id,
        authorization_source="judge_demo",
    )

    proof = {
        "gateway": os.getenv("POMERIUM_URL", "http://127.0.0.1:18081/mcp"),
        "allowed_call": allowed,
        "denied_call": denied,
        "audit_events": state.audit_events,
        "verdict": (
            "Pomerium enforced one native MCP allow and one native MCP deny"
            if allowed.get("enforcement_layer") == "pomerium"
            and denied.get("enforcement_layer") == "pomerium"
            and denied.get("denied")
            else "FAILED"
        ),
    }
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0 if proof["verdict"] != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
