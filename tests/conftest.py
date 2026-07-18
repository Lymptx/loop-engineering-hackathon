"""Test fixtures: force deterministic mode and isolate all on-disk writes.

Setting DEMO_MODE here (at import, before the loop modules run any agent code) means
the whole suite runs with zero Anthropic calls and needs no API key. The autouse
fixture redirects storage + the deployed-policy path to a tmp dir so tests never
touch storage/data/ or pomerium/policy.yaml.
"""

import os

os.environ["DEMO_MODE"] = "deterministic"

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    from cockpit import store as cockpit_store
    from loop import orchestrator
    from storage import db
    from subject import defender_store, version_store

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(db, "_DATA_DIR", data)
    monkeypatch.setattr(db, "_ATTACKS", data / "attacks.json")
    monkeypatch.setattr(db, "_DEFENDERS", data / "defenders.json")
    monkeypatch.setattr(db, "_TRANSCRIPTS", data / "transcripts")
    monkeypatch.setattr(orchestrator, "_POLICY_PATH", tmp_path / "policy.yaml")
    monkeypatch.setattr(
        orchestrator,
        "_POMERIUM_CONFIG_PATH",
        tmp_path / "generated-config.yaml",
    )
    monkeypatch.setattr(version_store, "_DATA_DIR", data)
    monkeypatch.setattr(version_store, "_VERSIONS", data / "capability_versions.json")
    monkeypatch.setattr(defender_store, "_DATA_DIR", data)
    monkeypatch.setattr(defender_store, "_DEFENDERS", data / "evo_defenders.json")
    cockpit_data = data / "cockpit"
    monkeypatch.setattr(cockpit_store, "_DATA_DIR", cockpit_data)
    monkeypatch.setattr(cockpit_store, "_RUNS", cockpit_data / "runs.json")
    monkeypatch.setattr(cockpit_store, "_EVENTS", cockpit_data / "events.json")
    monkeypatch.setattr(cockpit_store, "_ATTACK_BUNDLES", cockpit_data / "attack_bundles.json")
    monkeypatch.setattr(cockpit_store, "_DEFENDER_BUNDLES", cockpit_data / "defender_bundles.json")
    monkeypatch.setattr(cockpit_store, "_ATTEMPTS", cockpit_data / "attack_attempts.json")
    monkeypatch.setattr(cockpit_store, "_CANDIDATES", cockpit_data / "defense_candidates.json")
    monkeypatch.setattr(cockpit_store, "_METRICS", cockpit_data / "metrics.json")
    monkeypatch.setattr(cockpit_store, "_HISTORY", cockpit_data / "generation_history.json")
    monkeypatch.setattr(cockpit_store, "_TRACES", cockpit_data / "traces.json")
    yield
