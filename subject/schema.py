"""Typed schemas for the subject source files. Adapt-to-repo dataclass style.

These mirror references/contracts.md. Everything the loader parses becomes one of
these; nothing downstream touches raw YAML/JSON dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Sensitivity ordering (low -> high). Used by the risk-path ranker and by egress
# redaction (restricted must never leave; confidential is gated).
SENSITIVITY_ORDER = ["untrusted", "public", "internal", "confidential", "restricted"]


def sensitivity_rank(level: str) -> int:
    return SENSITIVITY_ORDER.index(level) if level in SENSITIVITY_ORDER else -1


@dataclass(frozen=True)
class Tool:
    name: str
    generation: str
    reads: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    sink: str | None = None


@dataclass(frozen=True)
class DataClass:
    name: str
    sensitivity: str
    tenant_scoped: bool
    generation: str


@dataclass(frozen=True)
class Role:
    name: str
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class Generation:
    version: str
    parent_version: str | None
    tools: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    data_classes: tuple[str, ...] = ()
    adds_tools: tuple[str, ...] = ()
    adds_roles: tuple[str, ...] = ()
    adds_data_classes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Invariant:
    id: str
    generation: str
    sink: str | None = None
    restricted_data_classes: tuple[str, ...] = ()
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DefenseOperator:
    id: str
    control_layer: str
    description: str = ""
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BenignWorkflow:
    workflow_id: str
    capability_version: str
    actor_role: str
    tenant_id: str
    user_goal: str
    required_tools: tuple[str, ...]
    allowed_data: tuple[str, ...]
    expected_state_change: str
    expected_output_constraints: tuple[str, ...]
    confirmation_policy: str


@dataclass(frozen=True)
class CapabilityVersion:
    """The fully-materialized capability set for one generation (deltas folded in)."""

    version: str
    parent_version: str | None
    tools: frozenset[str]
    roles: frozenset[str]
    data_classes: frozenset[str]
    status: str = "candidate"     # candidate | active
    activated_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "parent_version": self.parent_version,
            "tools": sorted(self.tools),
            "roles": sorted(self.roles),
            "data_classes": sorted(self.data_classes),
            "status": self.status,
            "activated_at": self.activated_at,
        }


@dataclass
class Subject:
    """The whole loaded subject: every registry, keyed for lookup."""

    tools: dict[str, Tool]
    data_classes: dict[str, DataClass]
    roles: dict[str, Role]
    generations: list[Generation]
    invariants: list[Invariant]
    operators: dict[str, DefenseOperator]
    benign_workflows: list[BenignWorkflow]

    def generation(self, version: str) -> Generation:
        for g in self.generations:
            if g.version == version:
                return g
        raise KeyError(f"unknown generation {version!r}")
