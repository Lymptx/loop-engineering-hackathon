"""Load the subject source files into typed schema objects.

`load_subject()` parses every registry once. `materialize(subject, version)` folds
generation deltas from the root forward to produce the full CapabilityVersion for a
given generation — so onboarding a new generation is pure data, no code branch.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from subject.schema import (
    BenignWorkflow,
    CapabilityVersion,
    DataClass,
    DefenseOperator,
    Generation,
    Invariant,
    Role,
    Subject,
    Tool,
)

_DIR = Path(__file__).parent


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((_DIR / name).read_text(encoding="utf-8")) or {}


def load_subject(base_dir: Path | None = None) -> Subject:
    global _DIR
    if base_dir is not None:
        _DIR = base_dir

    tools_raw = _load_yaml("tool_registry.yaml")["tools"]
    tools = {
        name: Tool(
            name=name,
            generation=t["generation"],
            reads=tuple(t.get("reads") or []),
            produces=tuple(t.get("produces") or []),
            sink=t.get("sink"),
        )
        for name, t in tools_raw.items()
    }

    dc_raw = _load_yaml("data_catalog.yaml")["data_classes"]
    data_classes = {
        name: DataClass(
            name=name,
            sensitivity=d["sensitivity"],
            tenant_scoped=bool(d["tenant_scoped"]),
            generation=d["generation"],
        )
        for name, d in dc_raw.items()
    }

    roles_raw = _load_yaml("roles_and_permissions.yaml")["roles"]
    roles = {
        name: Role(name=name, tools=tuple(r.get("tools") or []))
        for name, r in roles_raw.items()
    }

    gens_raw = _load_yaml("capability_generations.yaml")["generations"]
    generations = [
        Generation(
            version=g["version"],
            parent_version=g.get("parent_version"),
            tools=tuple(g.get("tools") or []),
            roles=tuple(g.get("roles") or []),
            data_classes=tuple(g.get("data_classes") or []),
            adds_tools=tuple(g.get("adds_tools") or []),
            adds_roles=tuple(g.get("adds_roles") or []),
            adds_data_classes=tuple(g.get("adds_data_classes") or []),
        )
        for g in gens_raw
    ]

    inv_raw = _load_yaml("security_invariants.yaml")["invariants"]
    invariants = [
        Invariant(
            id=i["id"],
            generation=i["generation"],
            sink=i.get("sink"),
            restricted_data_classes=tuple(i.get("restricted_data_classes") or []),
            params=i.get("params") or {},
        )
        for i in inv_raw
    ]

    ops_raw = _load_yaml("defense_operators.yaml")["operators"]
    operators = {
        o["id"]: DefenseOperator(
            id=o["id"],
            control_layer=o["control_layer"],
            description=o.get("description", ""),
            params=o.get("params") or {},
        )
        for o in ops_raw
    }

    benign_workflows = []
    for line in (_DIR / "benign_workflows.jsonl").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        w = json.loads(line)
        benign_workflows.append(
            BenignWorkflow(
                workflow_id=w["workflow_id"],
                capability_version=w["capability_version"],
                actor_role=w["actor_role"],
                tenant_id=w["tenant_id"],
                user_goal=w["user_goal"],
                required_tools=tuple(w["required_tools"]),
                allowed_data=tuple(w["allowed_data"]),
                expected_state_change=w["expected_state_change"],
                expected_output_constraints=tuple(w["expected_output_constraints"]),
                confirmation_policy=w["confirmation_policy"],
            )
        )

    return Subject(
        tools=tools,
        data_classes=data_classes,
        roles=roles,
        generations=generations,
        invariants=invariants,
        operators=operators,
        benign_workflows=benign_workflows,
    )


def _chain(subject: Subject, version: str) -> list[Generation]:
    """Generations from the root down to `version`, in order."""
    by_version = {g.version: g for g in subject.generations}
    if version not in by_version:
        raise KeyError(f"unknown generation {version!r}")
    chain: list[Generation] = []
    cur: str | None = version
    while cur is not None:
        g = by_version[cur]
        chain.append(g)
        cur = g.parent_version
    chain.reverse()
    return chain


def materialize(subject: Subject, version: str, *, status: str = "candidate",
                activated_at: str | None = None) -> CapabilityVersion:
    """Fold deltas from the root to `version` into a full CapabilityVersion."""
    tools: set[str] = set()
    roles: set[str] = set()
    data_classes: set[str] = set()
    for g in _chain(subject, version):
        tools |= set(g.tools) | set(g.adds_tools)
        roles |= set(g.roles) | set(g.adds_roles)
        data_classes |= set(g.data_classes) | set(g.adds_data_classes)

    gen = subject.generation(version)
    return CapabilityVersion(
        version=version,
        parent_version=gen.parent_version,
        tools=frozenset(tools),
        roles=frozenset(roles),
        data_classes=frozenset(data_classes),
        status=status,
        activated_at=activated_at,
    )
