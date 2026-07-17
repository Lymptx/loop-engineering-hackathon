"""Compile a DefenseCandidate (control-layer operator + params) into an enforceable
email policy. Blue picks the operator; the compiler turns it into runtime enforcement.

Two control layers are compiled here:
  * role_tool_authorization  -> deny email_send outright (blunt; candidate A).
  * data_flow_egress_policy  -> verified-recipient + same-tenant + redaction (candidate B).

The base defender (def-v0) compiles to an unrestricted policy — the Evo1 vulnerability.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmailDecision:
    allowed: bool
    reason: str
    effective_data_classes: tuple[str, ...] = ()


@dataclass
class EmailPolicy:
    deny_all: bool = False
    verified_recipient_binding: bool = False
    same_tenant_required: bool = False
    redact: tuple[str, ...] = ()
    allow_data_classes: tuple[str, ...] = ()
    label: str = "def-v0 (unrestricted)"

    def decide(self, to: str, tenant: str, data_classes: list[str], ctx: dict) -> EmailDecision:
        if self.deny_all:
            return EmailDecision(False, "email_send denied by policy")
        if self.verified_recipient_binding and to != ctx["verified_email"]:
            return EmailDecision(False, "recipient is not the verified customer")
        if self.same_tenant_required and tenant != ctx["tenant"]:
            return EmailDecision(False, "recipient is in a different tenant")
        effective = tuple(d for d in data_classes if d not in self.redact)
        return EmailDecision(True, "allowed", effective)


def base_defender_policy() -> EmailPolicy:
    """def-v0: no egress control. Everything the agent asks to send, goes."""
    return EmailPolicy(label="def-v0 (unrestricted)")


def compile_candidate(candidate: dict) -> EmailPolicy:
    layer = candidate["target_control_layer"]
    patch = candidate.get("patch", {})
    label = candidate.get("candidate_id", layer)

    if layer == "role_tool_authorization":
        # patch: {"deny_tool": {"tool": "email_send"}}
        denied = patch.get("deny_tool", {}).get("tool")
        return EmailPolicy(deny_all=(denied == "email_send"), label=label)

    if layer == "data_flow_egress_policy":
        e = patch.get("email_send", {})
        return EmailPolicy(
            verified_recipient_binding=bool(e.get("verified_recipient_binding")),
            same_tenant_required=bool(e.get("same_tenant_required")),
            redact=tuple(e.get("redact_data_classes") or ()),
            allow_data_classes=tuple(e.get("allow_data_classes") or ()),
            label=label,
        )

    raise ValueError(f"unsupported control layer: {layer}")
