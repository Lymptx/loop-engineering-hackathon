"""Live cockpit tests: persisted events are backed by deterministic loop results."""

from cockpit import demo, store


def test_live_demo_emits_required_persistent_events():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    event_types = [e["type"] for e in state["events"]]

    for required in [
        "demo_started",
        "evo_started",
        "attack_bundle_added",
        "attack_attempt_started",
        "attack_attempt_finished",
        "defender_candidate_generated",
        "defender_candidate_evaluated",
        "defender_rejected",
        "defender_promoted",
        "metric_updated",
        "demo_finished",
    ]:
        assert required in event_types

    assert state["run"]["status"] == "finished"
    assert state["run"]["current_evo"] == "evo3"
    assert state["run"]["active_defender"] == "def-v3"


def test_live_demo_records_real_attack_results_and_bundle_growth():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    attempts = state["attempts"]

    assert len(attempts) >= 8
    assert any(a["success"] is True and a["defender_version"] == "def-v0" for a in attempts)
    assert any(a["success"] is False and a["defender_version"] == "def-v1" for a in attempts)
    assert all(a["verifier_result_id"].startswith("verify-") for a in attempts)

    assert len(state["attack_bundles"]) >= 5
    assert len(state["defender_bundles"]) >= 5
    assert any(b["family"] == "crm_email_exfiltration" for b in state["attack_bundles"])
    assert any(b["promotion_decision"] == "promoted" for b in state["defender_bundles"])


def test_live_demo_rejects_bad_candidate_and_promotes_refined_candidate():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    candidates = {c["candidate_id"]: c for c in state["candidates"]}

    bad = candidates["cand-evo1-deny-email"]
    assert bad["status"] == "rejected"
    assert bad["frontier_attack_success"] == 0.0
    assert bad["benign_success"] < 1.0

    refined = candidates["cand-evo1-refined-email-policy"]
    assert refined["status"] == "promoted"
    assert refined["frontier_attack_success"] == 0.0
    assert refined["benign_success"] == 1.0


def test_metrics_show_attack_success_drop_after_promotion():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    by_defender = {m["defender_version"]: m for m in state["metrics"]}

    assert by_defender["def-v0"]["attack_success_rate"] == 1.0
    assert by_defender["def-v3"]["attack_success_rate"] == 0.0
    assert by_defender["def-v3"]["benign_success_rate"] == 1.0


def test_live_demo_reaches_evo3_with_generation_history():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    evos = {row["evo"] for row in state["generation_history"]}
    defenders = {row["defender_version"] for row in state["generation_history"]}
    families = {row["attack_family"] for row in state["generation_history"]}

    assert {"evo1", "evo2", "evo3"} <= evos
    assert {"def-v1", "def-v2", "def-v3"} <= defenders
    assert "forged_approval_bulk_refund" in families
    assert "memory_poisoning_attachment_injection" in families


def test_cockpit_state_survives_fresh_reads():
    demo.run_live_demo(pace_seconds=0, reset=True)

    # The store has no in-memory cache; this is the same read path a restarted
    # server uses to reload existing cockpit history.
    fresh = store.state()
    assert fresh["run"]["status"] == "finished"
    assert fresh["events"]
    assert fresh["attempts"]
    assert fresh["generation_history"]
