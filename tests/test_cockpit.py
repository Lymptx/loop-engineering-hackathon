"""Cockpit: deterministic engine, persistence, event ordering, metrics.

No server/network — tests drive engine.run() against an isolated Store and assert on
the persisted records (the same records the API serves the UI).
"""

import pytest

from cockpit import engine
from cockpit.store import Store

REQUIRED_ORDER = [
    "demo_reset", "demo_started", "evo_started", "defender_activated",
    "attack_bundle_added", "attack_attempt_started", "attack_attempt_finished",
    "metric_updated", "defender_candidate_generated", "defender_candidate_evaluated",
    "defender_rejected", "defender_candidate_generated", "defender_candidate_evaluated",
    "defender_promoted", "demo_finished",
]


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "_ARTIFACTS", tmp_path / "artifacts")
    return Store(tmp_path / "cockpit.json")


def _run(store):
    engine.run(store, pace=0.0)
    return store.snapshot()


def test_start_demo_runs_deterministic_loop(store):
    snap = _run(store)
    assert snap["runs"][-1]["status"] == "finished"
    assert len(snap["attempts"]) >= 8  # acceptance: >= 8 attack attempts


def test_at_least_one_success_old_and_fail_after_promotion(store):
    snap = _run(store)
    exfil = [a for a in snap["attempts"] if a["family"] == "crm_email_exfiltration"]
    old = [a for a in exfil if a["defender_version"] == "def-v1"]
    new = [a for a in exfil if a["defender_version"] == "def-v2"]
    assert any(a["success"] for a in old)          # succeeds vs old defender
    assert all(not a["success"] for a in new)      # blocked after promotion
    assert new  # replayed against the promoted defender


def test_attempts_reflect_verifier_results(store):
    snap = _run(store)
    for a in snap["attempts"]:
        if a["family"] == "crm_email_exfiltration" and a["defender_version"] == "def-v1":
            assert a["success"] is True
            assert a["violated_invariant"] in ("verified_recipient_binding",
                                               "no_restricted_data_egress")


def test_event_stream_has_required_types_in_order(store):
    snap = _run(store)
    types = [e["type"] for e in snap["events"]]
    it = iter(types)
    assert all(t in it for t in REQUIRED_ORDER), types


def test_over_broad_rejected_and_refined_promoted(store):
    snap = _run(store)
    by_id = {c["candidate_id"]: c for c in snap["candidates"]}
    assert by_id["cand-evo1-deny-email"]["status"] == "rejected"
    assert by_id["cand-evo1-refined-email-policy"]["status"] == "promoted"
    # rejected candidate lost utility; promoted one kept it
    assert by_id["cand-evo1-deny-email"]["benign_success"] < 1.0
    assert by_id["cand-evo1-refined-email-policy"]["benign_success"] == 1.0


def test_bundles_grow(store):
    snap = _run(store)
    families = {b["family"] for b in snap["attack_bundles"]}
    assert "crm_email_exfiltration" in families
    assert len(snap["attack_bundles"]) >= 5           # 4 evo0 + 1 evo1
    defs = {b["defender_version"] for b in snap["defender_bundles"]}
    assert defs == {"def-v1", "def-v2"}               # defender bundle grew 1 -> 2


def test_metrics_improve_after_promotion(store):
    snap = _run(store)
    metrics = snap["metrics"]
    assert len(metrics) >= 3
    after_old = metrics[1]["attack_success_rate"]
    after_promo = metrics[-1]["attack_success_rate"]
    assert after_promo < after_old                    # success rate decreases
    assert metrics[-1]["attack_success_rate_by_family"]["crm_email_exfiltration"] == 0.0
    assert metrics[-1]["benign_success_rate"] == 1.0


def test_generation_history_rows(store):
    snap = _run(store)
    decisions = [r["promotion_decision"] for r in snap["history"]]
    assert "rejected" in decisions and "promoted" in decisions
    promoted = next(r for r in snap["history"] if r["promotion_decision"] == "promoted")
    assert promoted["artifact_paths"]  # report artifacts referenced


def test_persistence_across_restart(store):
    _run(store)
    # Simulated restart: a brand-new Store on the same file must reload history.
    reloaded = Store(store.path)
    snap = reloaded.snapshot()
    assert snap["runs"] and snap["events"] and snap["attempts"]


def test_reset_clears_run_state_but_not_version_artifacts(store):
    from subject import version_store
    _run(store)
    assert version_store.all_versions()   # immutable capability artifacts exist
    store.reset()
    snap = store.snapshot()
    assert snap["events"] == [] and snap["attempts"] == [] and snap["runs"] == []
    # capability version artifacts are NOT deleted by a cockpit reset
    assert version_store.all_versions()
