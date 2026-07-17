"""Persistent cockpit records.

These are presentation-facing records backed by real loop artifacts: verifier
results, blue candidate gate results, bundle entries, and generation history.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


def now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class LoopRun:
    run_id: str
    mode: str = "deterministic_demo"
    status: str = "idle"
    started_at: str | None = None
    finished_at: str | None = None
    current_evo: str = "evo0"
    active_defender: str = "def-v0"
    current_phase: str = "idle"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoopEvent:
    event_id: str
    run_id: str
    sequence: int
    type: str
    summary: str
    timestamp: str = field(default_factory=now)
    evo: str = "evo0"
    defender_version: str = "def-v0"
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AttackBundleEntry:
    bundle_id: str
    created_in_run: str
    evo: str
    family: str
    objective: str
    source_to_sink_path: list[str]
    payload_template: str
    lineage: list[str] = field(default_factory=list)
    novelty_reason: str = ""
    tested_defenders: list[str] = field(default_factory=list)
    latest_success: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DefenderBundleEntry:
    bundle_id: str
    defender_version: str
    created_in_run: str
    control_layer: str
    policy_diff_summary: str
    blocks_families: list[str] = field(default_factory=list)
    preserves_workflows: list[str] = field(default_factory=list)
    promotion_decision: str = "active"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AttackAttemptRecord:
    attempt_id: str
    run_id: str
    bundle_id: str
    evo: str
    defender_version: str
    family: str
    objective: str
    carrier: str
    target_path: str
    success: bool
    violated_invariant: str
    verifier_result_id: str
    trace_id: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DefenseCandidateRecord:
    candidate_id: str
    run_id: str
    base_defender: str
    status: str
    control_layer: str
    policy_diff_summary: str
    frontier_attack_success: float
    hidden_attack_success: float
    benign_success: float
    decision_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MetricSnapshot:
    metric_id: str
    run_id: str
    sequence: int
    evo: str
    defender_version: str
    attack_success_rate: float
    attack_success_rate_by_family: dict[str, float]
    benign_success_rate: float
    hidden_holdout_attack_success: float
    blocked_attack_count: int
    promoted_defender_count: int
    new_attack_family_count: int
    attacker_bundle_size: int
    defender_bundle_size: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GenerationHistoryRow:
    row_id: str
    run_id: str
    evo: str
    defender_version: str
    attack_family: str
    frontier_attack_success: float
    hidden_attack_success: float
    benign_success: float
    policy_diff_summary: str
    promotion_decision: str
    reason: str
    artifact_paths: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
