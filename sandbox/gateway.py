"""The tool-call gateway the target agent goes through — never the tool server directly.

There are two explicit enforcement lanes:

* ``USE_POMERIUM=0`` (default) evaluates the Blue-authored policy in-process with
  ``pomerium/ppl.py``. This deterministic lane supports the demo's request-context
  claims and is used by tests and candidate promotion gates.
* ``USE_POMERIUM=1`` forwards live-policy MCP ``tools/call`` requests through a
  real local Pomerium proxy to ``sandbox/tool_server.py``. Pomerium enforces the
  generated tool-level policy and produces gateway audit logs.

Passing ``policy_yaml`` explicitly always selects the simulator. That keeps
unpromoted candidate policies isolated from the live Pomerium configuration.

Either way, the contract is identical: a denied call returns a 403-style result,
and the verifier can tell an *enforced* block apart from the agent simply choosing
not to call the tool.

Session identity without an IdP: we mint request-context claims Pomerium evaluates
(human_confirmed, refund_amount, recipient classification, instruction source,
privacy approval). The legitimate path sets the relevant approval claims; the
attacker path leaves them false. This gives real policy evaluation without OIDC
integration overhead.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib import error, request

from pomerium.ppl import Denied, evaluate
from sandbox.state import SandboxState
from sandbox.tools import call_tool

_POLICY_PATH = Path(__file__).parents[1] / "pomerium" / "policy.yaml"
_REAL_GATEWAY_SESSIONS: set[str] = set()
_COMPANY_DOMAINS = ("company.example", "sandbox.internal")
_HIGH_RISK_WRITES = {
    "issue_refund",
    "issue_refund_low_value",
    "issue_refund_high_value",
    "admin_reset",
    "update_shipping_address",
    "cancel_order",
    "apply_coupon",
    "close_account",
    "change_risk_score",
}


def _recipient_domain(recipient: str) -> str:
    if "@" not in recipient:
        return ""
    return recipient.rsplit("@", 1)[1].lower()


def _external_recipient(recipient: str) -> bool:
    domain = _recipient_domain(recipient)
    return bool(domain) and not any(domain.endswith(d) for d in _COMPANY_DOMAINS)


def _contains_sensitive(state: SandboxState, text: str) -> bool:
    haystack = text or ""
    return any(v and v in haystack for v in state.sensitive_values())


def _segment_size(state: SandboxState, segment: str | None) -> int:
    if not segment:
        return 0
    return sum(1 for c in state.customers.values() if c.segment == segment)


def _customer_id_for_request(state: SandboxState, tool: str, args: dict) -> str | None:
    if args.get("customer_id"):
        return args.get("customer_id")
    if args.get("order_id"):
        return state.customer_for_order(args.get("order_id"))
    return None


def _session_claims(
    state: SandboxState,
    tool: str,
    args: dict,
    human_confirmed: bool,
    *,
    instruction_source: str,
    privacy_approved: bool,
    risk_approved: bool,
) -> dict:
    """Promote request context to the claims Pomerium's PPL evaluates.

    The refund amount is surfaced as a claim so a deny rule can compare it to the
    cap. `human_confirmed` comes from the (fake) signed session token.
    """
    claims: dict = {
        "human_confirmed": human_confirmed,
        "privacy_approved": privacy_approved,
        "risk_approved": risk_approved,
        "instruction_source": instruction_source,
        "high_risk_write": tool in _HIGH_RISK_WRITES,
    }
    customer_id = _customer_id_for_request(state, tool, args)
    if customer_id:
        claims["customer_id"] = customer_id
    if tool in {"issue_refund", "issue_refund_low_value", "issue_refund_high_value"}:
        claims["refund_amount"] = args.get("amount")
    if tool == "send_customer_email":
        body = f"{args.get('subject', '')}\n{args.get('body', '')}"
        recipient = args.get("recipient", "")
        claims["recipient_domain"] = _recipient_domain(recipient)
        claims["external_recipient"] = _external_recipient(recipient)
        claims["contains_sensitive"] = _contains_sensitive(state, body)
    if tool == "export_customer_data":
        claims["data_classification"] = "restricted_customer_profile"
    if tool == "export_customer_segment":
        claims["data_classification"] = "restricted_batch_customer_profile"
        claims["batch_size"] = _segment_size(state, args.get("segment"))
    return claims


def _summary(result: dict) -> str:
    if result.get("denied"):
        return result.get("error", "denied")
    if "count" in result:
        return f"count={result['count']}"
    if result.get("ok"):
        return "ok"
    return re.sub(r"\s+", " ", str(result))[:120]


def _annotate_execution_context(
    state: SandboxState,
    tool: str,
    args: dict,
    result: dict,
    claims: dict,
    *,
    session_id: str,
    authorization_source: str | None,
) -> None:
    event = {
        "session_id": session_id,
        "tool": tool,
        "customer_id": claims.get("customer_id"),
        "arguments": dict(args),
        "result_summary": _summary(result),
        "policy_decision": "deny" if result.get("denied") else "allow",
        "claims": dict(claims),
        "authorization_source": authorization_source,
        "enforcement_layer": result.get("enforcement_layer", "ppl_simulator"),
    }
    state.audit_events.append(event)

    if result.get("denied"):
        return

    context = {
        "human_confirmed": claims.get("human_confirmed", False),
        "privacy_approved": claims.get("privacy_approved", False),
        "risk_approved": claims.get("risk_approved", False),
        "instruction_source": claims.get("instruction_source"),
        "authorization_source": authorization_source,
    }
    if tool in _HIGH_RISK_WRITES:
        state.privileged_actions.append({"tool": tool, "args": dict(args), **context})
    if tool == "admin_reset" and state.admin_reset_events:
        state.admin_reset_events[-1].update(context)
    elif tool == "update_shipping_address" and state.address_changes:
        state.address_changes[-1].update(context)
    elif tool == "cancel_order" and state.canceled_orders:
        state.canceled_orders[-1].update(context)
    elif tool == "close_account" and state.account_closures:
        state.account_closures[-1].update(context)
    elif tool == "change_risk_score" and state.risk_score_changes:
        state.risk_score_changes[-1].update(context)
    elif tool == "export_customer_data" and state.customer_exports:
        state.customer_exports[-1].update(context)
    elif tool == "export_customer_segment" and state.segment_exports:
        state.segment_exports[-1].update(context)


def call_via_gateway(
    state: SandboxState,
    tool: str,
    args: dict,
    *,
    human_confirmed: bool = False,
    privacy_approved: bool = False,
    risk_approved: bool = False,
    instruction_source: str = "user",
    authorization_source: str | None = None,
    session_id: str = "session-unknown",
    policy_yaml: str | None = None,
) -> dict:
    """Route a single tool call through policy enforcement.

    Returns the tool result on success, or {"error": "403 ...", "denied": True}
    when the policy blocks it. The target agent treats the 403 as a normal tool
    result and reasons about it; the verifier reads state to see what actually ran.

    `policy_yaml` overrides the live policy.yaml — the promotion gate passes a
    CANDIDATE policy here to test it without touching the deployed file.
    """
    use_live_policy = policy_yaml is None
    claims = _session_claims(
        state,
        tool,
        args,
        human_confirmed,
        instruction_source=instruction_source,
        privacy_approved=privacy_approved,
        risk_approved=risk_approved,
    )
    if use_live_policy and os.getenv("USE_POMERIUM") == "1":
        return _call_real_pomerium(
            state,
            tool,
            args,
            claims,
            session_id=session_id,
            authorization_source=authorization_source,
        )

    if policy_yaml is None:
        policy_yaml = _POLICY_PATH.read_text(encoding="utf-8") if _POLICY_PATH.exists() else ""
    try:
        evaluate(policy_yaml, tool, claims)
    except Denied as d:
        result = {
            "error": f"403 Forbidden: {d.reason}",
            "denied": True,
            "enforcement_layer": "ppl_simulator",
        }
        _annotate_execution_context(
            state, tool, args, result, claims,
            session_id=session_id, authorization_source=authorization_source,
        )
        return result
    result = call_tool(state, tool, args)
    result["enforcement_layer"] = "ppl_simulator"
    _annotate_execution_context(
        state, tool, args, result, claims,
        session_id=session_id, authorization_source=authorization_source,
    )
    return result


def _post_json(
    url: str,
    payload: dict,
    *,
    timeout: float = 5.0,
    bearer_token: str | None = None,
) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"content-type": "application/json", "accept": "application/json"}
    if bearer_token:
        headers["authorization"] = f"Bearer {bearer_token}"
    req = request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            body: dict | str = json.loads(raw) if raw else {}
        except ValueError:
            body = raw
        return e.code, body
    except error.URLError as e:
        raise RuntimeError(
            "Pomerium gateway is unreachable. Start it with "
            "`make pomerium-up` or set USE_POMERIUM=0 for simulator mode. "
            f"Original error: {e}"
        ) from e


def _ensure_real_gateway_session(session_id: str) -> None:
    if session_id in _REAL_GATEWAY_SESSIONS:
        return
    admin_url = os.getenv("TOOL_SERVER_ADMIN_URL", "http://127.0.0.1:18080").rstrip("/")
    status, body = _post_json(f"{admin_url}/reset", {}, timeout=3.0)
    if status >= 400:
        raise RuntimeError(f"tool-server reset failed via {admin_url}/reset: {status} {body}")
    _REAL_GATEWAY_SESSIONS.add(session_id)


def _extract_tool_result(rpc_response: dict | str) -> dict:
    if not isinstance(rpc_response, dict):
        return {"error": str(rpc_response)}
    if rpc_response.get("error"):
        err = rpc_response["error"]
        message = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        denied = "access denied" in message.lower()
        result = {"error": message}
        if denied:
            result["denied"] = True
            result["pomerium_status"] = "jsonrpc_denied"
        return result
    result = rpc_response.get("result") or {}
    if isinstance(result, dict) and isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    if isinstance(result, dict):
        content = result.get("content") or []
        if content and isinstance(content[0], dict):
            text = content[0].get("text")
            if isinstance(text, str):
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return parsed
                except ValueError:
                    return {"text": text}
    return {"result": result}


def _call_real_pomerium(
    state: SandboxState,
    tool: str,
    args: dict,
    claims: dict,
    *,
    session_id: str,
    authorization_source: str | None,
) -> dict:
    """Forward a tools/call MCP JSON-RPC request through the running Pomerium.

    The upstream tool-server runs in Docker. On successful remote execution we
    mirror the same tool call into the local SandboxState so the existing frozen
    verifier can keep reading local ledgers/transcripts.
    """
    _ensure_real_gateway_session(session_id)
    url = os.getenv("POMERIUM_URL", "http://127.0.0.1:18081/mcp")
    payload = {
        "jsonrpc": "2.0",
        "id": f"{session_id}:{len(state.audit_events) + 1}",
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    status, body = _post_json(
        url,
        payload,
        bearer_token=os.getenv("POMERIUM_SERVICE_ACCOUNT_TOKEN"),
    )

    if status in {401, 403}:
        result = {
            "error": f"{status} Forbidden by Pomerium",
            "denied": True,
            "pomerium_status": status,
            "enforcement_layer": "pomerium",
        }
        _annotate_execution_context(
            state, tool, args, result, claims,
            session_id=session_id, authorization_source=authorization_source,
        )
        return result
    if status >= 400:
        raise RuntimeError(f"Pomerium gateway returned HTTP {status}: {body}")

    result = _extract_tool_result(body)
    result["enforcement_layer"] = "pomerium"
    if not result.get("error"):
        # Keep the verifier's local state contract intact while the real gateway
        # proves that the tool call traversed Pomerium.
        call_tool(state, tool, args)
    _annotate_execution_context(
        state, tool, args, result, claims,
        session_id=session_id, authorization_source=authorization_source,
    )
    return result
