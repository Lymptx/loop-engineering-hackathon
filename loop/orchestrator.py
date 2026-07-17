"""The loop itself — the actual state machine.

run_round() is the ~20-line loop-engineering deliverable. Everything else in the
repo is dressing around it. The six explicit components map onto it directly:

  State     -> AttackAttempt / DefenderVersion records (loop/models.py, storage/db.py)
  Plan      -> red_agent.generate_next_attack ranks the next hypothesis
  Act       -> target_agent.handle_ticket submits a real payload to a real agent
  Observe   -> verifier.check returns WHICH violation, at what magnitude
  Correct   -> blue_agent.propose_candidate makes a specific, traceable fix
  Terminate -> run_n_rounds' round budget / convergence check (main.py)
"""

from __future__ import annotations

from pathlib import Path

from agents import blue_agent, red_agent
from agents.prompts import SEED_TARGET_SYSTEM_PROMPT
from loop.models import AttackAttempt, Candidate, DefenderVersion
from sandbox.state import SandboxState
from sandbox.target_agent import handle_ticket
from verifier import suites, verifier

_POLICY_PATH = Path(__file__).parents[1] / "pomerium" / "policy.yaml"


# --- seed / bootstrap ------------------------------------------------------

def seed_defender() -> DefenderVersion:
    """DefenderVersion v1: naive prompt + the seed (permissive) Pomerium policy."""
    policy_yaml = _POLICY_PATH.read_text(encoding="utf-8") if _POLICY_PATH.exists() else ""
    return DefenderVersion(
        version="v1",
        system_prompt=SEED_TARGET_SYSTEM_PROMPT,
        tool_policy_yaml=policy_yaml,
        kind="seed",
        rationale="Seed defender: naive prompt, permissive tool policy.",
    )


def _next_version(current: DefenderVersion) -> str:
    try:
        n = int(current.version.lstrip("v"))
    except ValueError:
        n = 1
    return f"v{n + 1}"


# --- the loop --------------------------------------------------------------

def run_round(library: list[AttackAttempt], current: DefenderVersion) -> tuple[DefenderVersion, dict]:
    """One full round. Returns (defender_after_round, round_report).

    The defender is unchanged if the attack fails or the candidate is rejected.
    """
    # PLAN + ACT: Red proposes, target agent runs it in a fresh sandbox.
    attack = red_agent.generate_next_attack(library, current)
    state = SandboxState.fresh()
    transcript = handle_ticket(
        attack.payload, current.system_prompt, state,
        human_confirmed=False, policy_yaml=current.tool_policy_yaml,
    )

    # OBSERVE: deterministic verifier says which violation occurred.
    result = verifier.check(transcript, state)
    attack.result = result
    library.append(attack)

    report = {
        "attack": attack.to_dict(),
        "transcript": transcript,
        "violation": result["violation"],
        "promoted": None,
        "gate": None,
    }

    if not result["violation"]:
        return current, report

    # CORRECT: Blue root-causes and proposes a candidate fix.
    candidate = blue_agent.propose_candidate(attack, result, current)
    gate = run_promotion_gate(candidate, current)
    report["gate"] = gate

    if gate["passed"]:
        promoted = _promote(candidate, current, gate)
        deploy_policy(promoted.tool_policy_yaml)
        report["promoted"] = promoted.to_dict()
        return promoted, report

    # Rejected: keep the current defender, try again next round.
    return current, report


# --- promotion gate --------------------------------------------------------

def run_promotion_gate(candidate: Candidate, current: DefenderVersion) -> dict:
    """Rerun the HIDDEN attack suite + BENIGN regression suite against the candidate.

    A candidate is promoted only if it blocks every hidden attack AND every benign
    task still completes. The benign half is what keeps the system honest — a
    defender that refuses everything fails here.
    """
    hidden = _run_hidden_suite(candidate)
    benign = _run_benign_suite(candidate)
    passed = hidden["all_blocked"] and benign["all_completed"]
    return {"passed": passed, "hidden": hidden, "benign": benign}


def _run_hidden_suite(candidate: Candidate) -> dict:
    cases = []
    for case in suites.HIDDEN_ATTACKS:
        state = SandboxState.fresh()
        transcript = handle_ticket(
            case["ticket"], candidate.system_prompt, state,
            human_confirmed=case.get("human_confirmed", False),
            policy_yaml=candidate.tool_policy_yaml,
        )
        result = verifier.check(transcript, state)
        blocked = not result["violation"]
        cases.append({"name": case["name"], "blocked": blocked, "result": result})
    return {
        "all_blocked": all(c["blocked"] for c in cases),
        "blocked": sum(c["blocked"] for c in cases),
        "total": len(cases),
        "cases": cases,
    }


def _run_benign_suite(candidate: Candidate) -> dict:
    cases = []
    for case in suites.BENIGN_TASKS:
        state = SandboxState.fresh()
        transcript = handle_ticket(
            case["ticket"], candidate.system_prompt, state,
            human_confirmed=case.get("human_confirmed", False),
            policy_yaml=candidate.tool_policy_yaml,
        )
        ok = verifier.benign_completed(transcript, state, case.get("expect_refund"))
        cases.append({"name": case["name"], "completed": ok})
    return {
        "all_completed": all(c["completed"] for c in cases),
        "completed": sum(c["completed"] for c in cases),
        "total": len(cases),
        "cases": cases,
    }


# --- promote / deploy ------------------------------------------------------

def _promote(candidate: Candidate, current: DefenderVersion, gate: dict) -> DefenderVersion:
    return DefenderVersion(
        version=_next_version(current),
        system_prompt=candidate.system_prompt,
        tool_policy_yaml=candidate.tool_policy_yaml,
        parent_version=current.version,
        kind=candidate.kind,
        rationale=candidate.rationale,
        promoted=True,
        test_results=gate,
    )


def deploy_policy(tool_policy_yaml: str) -> None:
    """Write the promoted PPL policy to the file Pomerium watches (hot-reload)."""
    _POLICY_PATH.write_text(tool_policy_yaml, encoding="utf-8")
