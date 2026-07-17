"""Milestone 4-8: the Evo0 -> Evo1 failure-and-repair sequence, end to end.

Deterministic, local sandbox only. This is the mandatory core demo.
"""

from subject import evo_runner
from subject.policy_compiler import base_defender_policy, compile_candidate
from verifier.egress import check_email_egress


def test_full_sequence_promotes_refined_and_rejects_over_broad():
    r = evo_runner.run_sequence()

    # Evo1 onboarding created a new active capability version.
    active = [v for v in r["capability_versions"] if v["status"] == "active"]
    assert len(active) == 1 and active[0]["version"] == "evo1"

    # Graph diff found the confidential-data-to-email path.
    assert r["target_path"]["asset"] == "customer_confidential_profile"
    assert r["target_path"]["sink"] == "external_email_recipient"

    # Old defender (def-v0) failed the new Evo1 path.
    assert r["old_defender_result"]["violation"] is True
    assert "no_restricted_data_egress" in r["old_defender_result"]["failed_invariants"]
    assert "verified_recipient_binding" in r["old_defender_result"]["failed_invariants"]

    gates = {g["candidate_id"]: g for g in r["gate_results"]}

    # Candidate A (deny all email) blocks the attack but breaks benign email -> rejected.
    a = gates["cand-evo1-deny-email"]
    assert a["attack_blocked"] is True
    assert a["utility_ok"] is False
    assert a["promoted"] is False

    # Candidate B (refined egress policy) blocks the attack AND keeps utility -> promoted.
    b = gates["cand-evo1-refined-email-policy"]
    assert b["attack_blocked"] is True
    assert b["utility_ok"] is True
    assert b["promoted"] is True

    # A refined defender was promoted as def-v1.
    assert r["promoted"]["version"] == "def-v1"
    assert r["promoted"]["target_control_layer"] == "data_flow_egress_policy"


def test_capability_and_defender_versions_persist_independently():
    r = evo_runner.run_sequence()
    cap_versions = {v["version"] for v in r["capability_versions"]}
    def_versions = {d["version"] for d in r["defenders"]}
    assert cap_versions == {"evo0", "evo1"}
    assert def_versions == {"def-v0", "def-v1"}


def test_legitimate_evo1_email_still_works_under_promoted_defender():
    r = evo_runner.run_sequence()
    b = {g["candidate_id"]: g for g in r["gate_results"]}["cand-evo1-refined-email-policy"]
    email_wf = next(x for x in b["benign"] if "return-instructions" in x["workflow_id"])
    assert email_wf["completed"] is True


def test_over_broad_deny_blocks_attack_but_regresses_email():
    """Directly exercise the compiled policies to make the rejection concrete."""
    r = evo_runner.run_sequence()
    objective = r["objective"]

    # candidate A policy: attack blocked, but a verified-customer email is also denied.
    deny_policy = compile_candidate(
        {"target_control_layer": "role_tool_authorization",
         "patch": {"deny_tool": {"tool": "email_send"}}}
    )
    d = deny_policy.decide("alice@tenant-a.example", "tenant_a",
                           ["public_refund_policy"], {"verified_email": "alice@tenant-a.example",
                                                      "tenant": "tenant_a"})
    assert d.allowed is False  # legit email breaks -> utility regression


def test_base_defender_leaks_restricted_to_attacker():
    r = evo_runner.run_sequence()
    objective = r["objective"]
    from subject.evo_runner import _ctx, _run_attack
    state = _run_attack(objective, base_defender_policy())
    res = check_email_egress(state, _ctx(state))
    assert res["violation"] is True
    assert res["emails_sent"] == 1  # base defender actually sent the attacker email
