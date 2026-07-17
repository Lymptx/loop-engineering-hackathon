"""Presentation snapshot for the protected target agent."""

from __future__ import annotations

from dataclasses import asdict

from cockpit import store
from sandbox.state import SandboxState
from subject import loader
from subject.schema import DataClass, Subject, Tool


def snapshot(evo: str | None = None) -> dict:
    subject = loader.load_subject()
    version = evo or _current_evo(subject)
    capability = loader.materialize(subject, version, status="active")
    sandbox = SandboxState.fresh()

    return {
        "evo": version,
        "active_defender": (store.latest_run() or {}).get("active_defender", "def-v0"),
        "summary": _summary(version),
        "tools": [
            _tool_row(subject, subject.tools[name])
            for name in sorted(capability.tools)
        ],
        "roles": [
            {
                "name": name,
                "tools": sorted(set(role.tools).intersection(capability.tools)),
            }
            for name, role in sorted(subject.roles.items())
            if set(role.tools).intersection(capability.tools)
        ],
        "data_classes": [
            _data_class_row(subject.data_classes[name])
            for name in sorted(capability.data_classes)
        ],
        "active_invariants": [
            {
                "id": invariant.id,
                "generation": invariant.generation,
                "sink": invariant.sink,
                "restricted_data_classes": list(invariant.restricted_data_classes),
                "params": invariant.params,
            }
            for invariant in subject.invariants
            if _generation_index(subject, invariant.generation)
            <= _generation_index(subject, version)
        ],
        "benign_workflows": [
            asdict(workflow)
            for workflow in subject.benign_workflows
            if _generation_index(subject, workflow.capability_version)
            <= _generation_index(subject, version)
        ],
        "customer_workspace": _customer_workspace(sandbox),
    }


def _current_evo(subject: Subject) -> str:
    latest = store.latest_run()
    version = (latest or {}).get("current_evo") or "evo0"
    valid = {generation.version for generation in subject.generations}
    return version if version in valid else "evo0"


def _summary(evo: str) -> str:
    summaries = {
        "evo0": (
            "Basic CustomerOps agent: tickets, order lookup, KB lookup, "
            "refunds, ticket updates."
        ),
        "evo1": "Adds CRM reads, support history, outbound email, and follow-up scheduling.",
        "evo2": (
            "Adds manager approval, bulk refunds, fraud/finance data, "
            "discounts, finance cases."
        ),
        "evo3": (
            "Adds memory, attachments, web/connector output, CRM note append, "
            "and MCP connectors."
        ),
    }
    return summaries.get(evo, "CustomerOps target agent")


def _generation_index(subject: Subject, evo: str) -> int:
    order = {generation.version: idx for idx, generation in enumerate(subject.generations)}
    return order.get(evo, 0)


def _tool_row(subject: Subject, tool: Tool) -> dict:
    reads = [_data_class_row(subject.data_classes[name]) for name in tool.reads]
    produces = [_data_class_row(subject.data_classes[name]) for name in tool.produces]
    return {
        "name": tool.name,
        "generation": tool.generation,
        "reads": reads,
        "produces": produces,
        "sink": tool.sink,
        "risk": _tool_risk(reads, tool.sink),
    }


def _data_class_row(data_class: DataClass) -> dict:
    return {
        "name": data_class.name,
        "sensitivity": data_class.sensitivity,
        "tenant_scoped": data_class.tenant_scoped,
        "generation": data_class.generation,
    }


def _tool_risk(reads: list[dict], sink: str | None) -> str:
    sensitivities = {row["sensitivity"] for row in reads}
    if sink and {"restricted", "confidential"}.intersection(sensitivities):
        return "critical"
    if sink:
        return "write_or_egress"
    if "restricted" in sensitivities:
        return "restricted_read"
    if "confidential" in sensitivities:
        return "confidential_read"
    return "standard"


def _customer_workspace(state: SandboxState) -> dict:
    return {
        "customers": [asdict(customer) for customer in state.customers.values()],
        "orders": [asdict(order) for order in state.orders.values()],
        "payments": [asdict(payment) for payment in state.payments.values()],
        "tickets": [asdict(ticket) for ticket in state.tickets.values()],
        "case_notes": [asdict(note) for note in state.case_notes],
        "knowledge": {
            "kb_articles": state.kb_articles,
            "runbooks": state.runbooks,
        },
        "protected_internal_values": {
            "canary": _redact(state.canary),
            "fake_api_token": _redact(state.fake_api_token),
        },
    }


def _redact(value: str) -> str:
    if len(value) <= 10:
        return "[redacted]"
    return f"{value[:8]}...{value[-6:]}"
