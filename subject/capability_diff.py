"""Diff two capability graphs and enumerate newly introduced source-to-sink paths.

The new_paths list is the whole point: onboarding Evo1 should surface the path
`untrusted_customer_ticket -> customer_confidential_profile -> external_email_recipient`
that did not exist at Evo0.
"""

from __future__ import annotations

from subject.capability_graph import CapabilityGraph, source_to_sink_paths
from subject.schema import CapabilityVersion, Subject


def _path_key(p: dict) -> tuple:
    return (p["source"], p["identity"], p["asset"], p["sink"])


def diff(
    subject: Subject,
    cap_from: CapabilityVersion,
    cap_to: CapabilityVersion,
    graph_from: CapabilityGraph,
    graph_to: CapabilityGraph,
) -> dict:
    added_nodes = sorted(f"{k}:{n}" for (k, n) in (graph_to.nodes - graph_from.nodes))
    added_edges = sorted(
        f"{rel}:{a}->{b}" for (rel, a, b) in (graph_to.edges - graph_from.edges)
    )

    from_keys = {_path_key(p) for p in source_to_sink_paths(subject, cap_from)}
    new_paths = [
        p for p in source_to_sink_paths(subject, cap_to)
        if _path_key(p) not in from_keys
    ]

    return {
        "from_version": cap_from.version,
        "to_version": cap_to.version,
        "added_nodes": added_nodes,
        "added_edges": added_edges,
        "new_paths": new_paths,
    }
