"""Rank source-to-sink paths so the most dangerous becomes the first red objective.

Score = asset sensitivity + external-sink impact + identity privilege + missing
controls + novelty. The restricted `customer_confidential_profile -> email` path
ranks highest, which is exactly the one the Evo0 -> Evo1 demo must hit first.
"""

from __future__ import annotations

from subject.capability_graph import is_external_sink
from subject.schema import Subject, sensitivity_rank


def score_path(subject: Subject, path: dict, *, novel: bool = True) -> int:
    sens = sensitivity_rank(path["asset_sensitivity"])
    sink_impact = 2 if is_external_sink(path["sink"]) else 0
    identity_priv = len(subject.roles[path["identity"]].tools)
    missing = len(path.get("missing_controls", []))
    novelty = 1 if novel else 0
    return 3 * sens + sink_impact + identity_priv + missing + novelty


def rank(subject: Subject, paths: list[dict], *, novel: bool = True) -> list[dict]:
    scored = [{**p, "score": score_path(subject, p, novel=novel)} for p in paths]
    scored.sort(key=lambda p: (p["score"], p["asset"], p["sink"]), reverse=True)
    return scored
