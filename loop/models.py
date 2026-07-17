"""Persistent state objects for the loop.

These are plain dataclasses — NOT chat history. The single biggest mistake this
project avoids is building loop state inside one long conversation with the model.
State lives here, in our own Python objects; every LLM call is single-shot and
stateless (see agents/red_agent.py, agents/blue_agent.py).

Two assets get versioned on every promotion:
  1. AttackAttempt   — one Red Agent payload + the verifier's structured result.
  2. DefenderVersion — a bundle of (system-prompt diff, Pomerium policy diff, tests).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class AttackAttempt:
    """One attack the Red Agent tried against a specific DefenderVersion.

    `result` is filled in by the verifier and is the load-bearing "observe" signal:
    it says *which* violation occurred and at what magnitude, not just pass/fail.
    """

    family: str            # e.g. "prompt_injection_via_forwarded_email"
    payload: str           # the actual ticket text submitted to the target agent
    hypothesis: str        # why the Red Agent thinks this will work
    defender_version: str  # which DefenderVersion.version this ran against
    id: str = field(default_factory=lambda: _new_id("atk"))
    parent_id: str | None = None      # attack this one evolved from (lineage)
    result: dict | None = None        # verifier.check(...) output; None until run
    created_at: str = field(default_factory=_now)

    @property
    def succeeded(self) -> bool:
        """True when the verifier recorded a security violation."""
        return bool(self.result and self.result.get("violation"))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> AttackAttempt:
        return cls(**d)


@dataclass
class DefenderVersion:
    """A versioned defense bundle. MVP supports exactly two update operators:
    a system-prompt diff (prompt-policy) and a Pomerium PPL diff (tool-policy).

    Do not scope-creep into more operators until these two are solid.
    """

    version: str                 # e.g. "v1", "v2" — monotonically increasing
    system_prompt: str           # the target agent's full system prompt at this version
    tool_policy_yaml: str        # the full Pomerium PPL policy at this version
    id: str = field(default_factory=lambda: _new_id("def"))
    parent_version: str | None = None
    kind: str = "seed"           # "seed" | "prompt_only" | "tool_policy" | "both"
    rationale: str = ""          # Blue Agent's root-cause explanation for this fix
    promoted: bool = False
    test_results: dict | None = None  # hidden + benign suite results that justified promotion
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DefenderVersion:
        return cls(**d)


@dataclass
class Candidate:
    """A proposed fix from the Blue Agent, before the promotion gate runs.

    Carries the two possible diffs plus which operator(s) the Blue Agent chose.
    The orchestrator turns an accepted Candidate into a promoted DefenderVersion.
    """

    kind: str                    # "prompt_only" | "tool_policy" | "both"
    rationale: str               # root-cause analysis
    system_prompt: str           # proposed new system prompt (unchanged if tool-only)
    tool_policy_yaml: str        # proposed new PPL policy (unchanged if prompt-only)
    driven_by_attack_id: str     # the AttackAttempt.id that triggered this fix

    def to_dict(self) -> dict:
        return asdict(self)
