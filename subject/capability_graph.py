"""Model the subject as a capability graph and enumerate source-to-sink paths.

Graph = Sources x Identities x Assets x Tools/Sinks x Controls, built from a
materialized CapabilityVersion + the subject registries. The load-bearing operation
is source_to_sink_paths(): every way an untrusted source can reach an external sink
carrying a sensitive asset, given who can call what. The Evo1 email capability is
what first makes such a path exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from subject.schema import CapabilityVersion, Subject, sensitivity_rank

UNTRUSTED_SOURCE = "untrusted_customer_ticket"
_CONFIDENTIAL = sensitivity_rank("confidential")


def is_external_sink(sink: str | None) -> bool:
    return bool(sink) and sink.startswith("external_")


@dataclass(frozen=True)
class CapabilityGraph:
    version: str
    nodes: frozenset[tuple[str, str]]     # (kind, name): kind in data/tool/role/sink
    edges: frozenset[tuple[str, str, str]]  # (relation, src, dst)

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)


def build_graph(subject: Subject, cap: CapabilityVersion) -> CapabilityGraph:
    nodes: set[tuple[str, str]] = set()
    edges: set[tuple[str, str, str]] = set()

    for role in cap.roles:
        nodes.add(("role", role))
    for d in cap.data_classes:
        nodes.add(("data", d))
    for tool in cap.tools:
        nodes.add(("tool", tool))
        t = subject.tools[tool]
        for d in t.reads:
            if d in cap.data_classes:
                edges.add(("reads", tool, d))
        for d in t.produces:
            if d in cap.data_classes:
                edges.add(("produces", tool, d))
        if t.sink:
            nodes.add(("sink", t.sink))
            edges.add(("sinks_to", tool, t.sink))

    for role in cap.roles:
        for tool in subject.roles[role].tools:
            if tool in cap.tools:
                edges.add(("can_call", role, tool))

    return CapabilityGraph(version=cap.version, nodes=frozenset(nodes), edges=frozenset(edges))


def _guards(subject: Subject, sink: str) -> list[str]:
    return [inv.id for inv in subject.invariants if inv.sink == sink]


def source_to_sink_paths(subject: Subject, cap: CapabilityVersion) -> list[dict]:
    """Every (untrusted source -> sensitive asset -> external sink) reachable by one
    identity. Deduped by (identity, asset, sink)."""
    if UNTRUSTED_SOURCE not in cap.data_classes:
        return []

    paths: dict[tuple, dict] = {}
    for role in sorted(cap.roles):
        callable_tools = [t for t in subject.roles[role].tools if t in cap.tools]
        # sensitive assets this identity can read/produce
        read_assets = []
        for t in callable_tools:
            for asset in subject.tools[t].produces:
                if asset in cap.data_classes and \
                        sensitivity_rank(subject.data_classes[asset].sensitivity) >= _CONFIDENTIAL:
                    read_assets.append((asset, t))
        # external sinks this identity can reach
        sink_tools = [(subject.tools[t].sink, t) for t in callable_tools
                      if is_external_sink(subject.tools[t].sink)]

        for asset, t_read in read_assets:
            for sink, t_sink in sink_tools:
                key = (role, asset, sink)
                if key in paths:
                    continue
                paths[key] = {
                    "source": UNTRUSTED_SOURCE,
                    "identity": role,
                    "asset": asset,
                    "sink": sink,
                    "tool_read": t_read,
                    "tool_sink": t_sink,
                    "asset_sensitivity": subject.data_classes[asset].sensitivity,
                    "missing_controls": _guards(subject, sink),
                }
    return list(paths.values())
