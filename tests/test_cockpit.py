"""Live cockpit tests: persisted events are backed by deterministic loop results."""

from collections import Counter

from cockpit import demo, store, subject_view


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
    by_evo = Counter(a["evo"] for a in attempts)

    assert len(attempts) >= 120
    assert by_evo["evo0"] >= 30
    assert by_evo["evo1"] >= 30
    assert by_evo["evo2"] >= 30
    assert by_evo["evo3"] >= 30
    assert any(a["success"] is True and a["defender_version"] == "def-v0" for a in attempts)
    assert any(a["success"] is False and a["defender_version"] == "def-v1" for a in attempts)
    assert all(a["verifier_result_id"].startswith("verify-") for a in attempts)

    assert len(state["attack_bundles"]) >= 20
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

    assert by_defender["def-seed"]["attack_success_rate"] == 1.0
    assert by_defender["def-v3"]["attack_success_rate"] == 0.0
    assert by_defender["def-v3"]["benign_success_rate"] == 1.0


def test_live_demo_reaches_evo3_with_generation_history():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    evos = {row["evo"] for row in state["generation_history"]}
    defenders = {row["defender_version"] for row in state["generation_history"]}
    families = {row["attack_family"] for row in state["generation_history"]}

    assert {"evo0", "evo1", "evo2", "evo3"} <= evos
    assert {"def-v1", "def-v2", "def-v3"} <= defenders
    assert "finance_data_exfiltration" in families
    assert "memory_connector_exfiltration" in families


def test_red_and_blue_agents_make_persisted_decisions():
    state = demo.run_live_demo(pace_seconds=0, reset=True)
    event_types = [e["type"] for e in state["events"]]
    red_events = [e for e in state["events"] if e["type"] == "red_strategy_selected"]
    mutation_events = [e for e in state["events"] if e["type"] == "red_mutation_selected"]
    blue_events = [e for e in state["events"] if e["type"] == "blue_rca_completed"]

    assert "red_strategy_selected" in event_types
    assert "red_mutation_selected" in event_types
    assert "blue_rca_completed" in event_types
    assert {e["evo"] for e in red_events} >= {"evo1", "evo2", "evo3"}
    assert {e["evo"] for e in blue_events} >= {"evo0", "evo1", "evo2", "evo3"}
    assert {e["evo"] for e in mutation_events} >= {"evo0", "evo1", "evo2", "evo3"}
    assert all(e["payload"]["score_path"]["source"] == "untrusted_customer_ticket"
               for e in red_events)


def test_cockpit_state_survives_fresh_reads():
    demo.run_live_demo(pace_seconds=0, reset=True)

    # The store has no in-memory cache; this is the same read path a restarted
    # server uses to reload existing cockpit history.
    fresh = store.state()
    assert fresh["run"]["status"] == "finished"
    assert fresh["events"]
    assert fresh["attempts"]
    assert fresh["generation_history"]


def test_target_agent_snapshot_tracks_current_evo_and_customer_workspace():
    demo.reset_demo()
    baseline = subject_view.snapshot()
    assert baseline["evo"] == "evo0"
    assert any(tool["name"] == "refund_create" for tool in baseline["tools"])
    assert not any(tool["name"] == "memory_write" for tool in baseline["tools"])

    demo.run_live_demo(pace_seconds=0, reset=True)
    evolved = subject_view.snapshot()
    assert evolved["evo"] == "evo3"
    assert any(tool["name"] == "memory_write" for tool in evolved["tools"])
    assert any(data["sensitivity"] == "restricted" for data in evolved["data_classes"])
    assert evolved["customer_workspace"]["customers"]
    assert evolved["customer_workspace"]["orders"]
