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
    from loop import orchestrator
    from storage import db

    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(db, "_DATA_DIR", data)
    monkeypatch.setattr(db, "_ATTACKS", data / "attacks.json")
    monkeypatch.setattr(db, "_DEFENDERS", data / "defenders.json")
    monkeypatch.setattr(db, "_TRANSCRIPTS", data / "transcripts")
    monkeypatch.setattr(orchestrator, "_POLICY_PATH", tmp_path / "policy.yaml")
    yield
