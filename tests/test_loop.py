"""End-to-end loop tests — deterministic, no Anthropic, no external services."""

from agents import blue_agent
from loop import orchestrator
from sandbox.gateway import call_via_gateway
from sandbox.state import SandboxState
from storage import db
from verifier import suites


def _seeded():
    v1 = orchestrator.seed_defender()
    db.save_defender(v1)
    return v1


def _mk_attack():
    from loop.models import AttackAttempt
    return AttackAttempt(family="f", payload="p", hypothesis="h", defender_version="v1")


def test_reset_creates_clean_state():
    _seeded()
    db.append_attack(_mk_attack())
    assert db.all_attacks() and db.all_defenders()
    db.reset()
    assert db.all_attacks() == []
    assert db.all_defenders() == []


def test_seed_defender_v1_exists():
    v1 = _seeded()
    assert v1.version == "v1"
    assert db.current_defender().version == "v1"
    # Permissive seed: no deny rule.
    assert "deny:" not in v1.tool_policy_yaml


def test_v1_attack_succeeds_under_permissive_policy():
    v1 = _seeded()
    library: list = []
    defender, report = orchestrator.run_round(library, v1)
    assert report["violation"] is True
    assert library[-1].succeeded is True


def test_blue_candidate_generated_after_violation():
    v1 = _seeded()
    library: list = []
    _, report = orchestrator.run_round(library, v1)
    assert report["gate"] is not None  # gate only runs when a candidate was proposed


def test_promotion_gate_runs_hidden_and_benign():
    v1 = _seeded()
    _, report = orchestrator.run_round([], v1)
    gate = report["gate"]
    assert gate["hidden"]["total"] == len(suites.HIDDEN_ATTACKS)
    assert gate["benign"]["total"] == len(suites.BENIGN_TASKS)
    assert gate["passed"] is True


def test_promoted_v2_blocks_admin_and_over_cap_refund():
    v1 = _seeded()
    v2, report = orchestrator.run_round([], v1)
    assert report["promoted"] is not None
    assert v2.version == "v2"

    policy = v2.tool_policy_yaml
    # admin_reset without confirmation is denied
    r_admin = call_via_gateway(SandboxState.fresh(), "admin_reset",
                               {"order_id": "A1002"}, human_confirmed=False, policy_yaml=policy)
    assert r_admin.get("denied") is True
    # over-cap refund is denied
    r_refund = call_via_gateway(SandboxState.fresh(), "issue_refund",
                                {"order_id": "A1002", "amount": 500}, policy_yaml=policy)
    assert r_refund.get("denied") is True
    # the whole hidden suite is blocked under v2
    assert orchestrator.run_hidden_suite(v2.system_prompt, policy)["succeeded"] == 0


def test_benign_under_cap_refund_still_succeeds_under_v2():
    v1 = _seeded()
    v2, _ = orchestrator.run_round([], v1)
    state = SandboxState.fresh()
    r = call_via_gateway(state, "issue_refund", {"order_id": "A1001", "amount": 42},
                         policy_yaml=v2.tool_policy_yaml)
    assert r.get("denied") is not True
    assert state.refund_ledger == [{"order_id": "A1001", "amount": 42}]
    # and the full benign suite still passes
    assert orchestrator.run_benign_suite(v2.system_prompt, v2.tool_policy_yaml)["all_completed"]


def test_hidden_suite_never_passed_into_blue(monkeypatch):
    """The Blue Agent must not see the hidden tests — it can't overfit to them."""
    captured = {}
    original = blue_agent.propose_candidate

    def spy(attempt, result, defender, **kw):
        captured["blob"] = repr((attempt.to_dict(), result, defender.to_dict()))
        return original(attempt, result, defender, **kw)

    monkeypatch.setattr(orchestrator.blue_agent, "propose_candidate", spy)
    orchestrator.run_round([], _seeded())

    blob = captured["blob"]
    for case in suites.HIDDEN_ATTACKS:
        assert case["ticket"] not in blob
