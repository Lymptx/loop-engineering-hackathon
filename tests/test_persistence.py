"""Persistence: records survive a process restart via storage/db.py.

db.all_attacks() / all_defenders() re-read the JSON files on every call, so reading
after a write (with no in-memory cache) is a faithful stand-in for a fresh process.
"""

from loop.models import AttackAttempt, DefenderVersion
from storage import db


def test_attacks_and_defenders_survive_restart():
    db.reset()

    atk = AttackAttempt(family="prompt_injection", payload="p", hypothesis="h",
                        defender_version="v1", result={"violation": True})
    db.append_attack(atk)

    v1 = DefenderVersion(version="v1", system_prompt="s", tool_policy_yaml="policy: {}")
    v2 = DefenderVersion(version="v2", system_prompt="s", tool_policy_yaml="deny: ...",
                        promoted=True, parent_version="v1")
    db.save_defender(v1)
    db.save_defender(v2)

    # Simulated restart: fresh reads from disk, no shared in-memory state.
    attacks = db.all_attacks()
    assert [a.id for a in attacks] == [atk.id]
    assert attacks[0].succeeded is True

    versions = {d.version for d in db.all_defenders()}
    assert versions == {"v1", "v2"}
    assert db.current_defender().version == "v2"  # latest promoted


def test_save_defender_upserts_by_version():
    db.reset()
    db.save_defender(DefenderVersion(version="v1", system_prompt="a", tool_policy_yaml="x"))
    db.save_defender(DefenderVersion(version="v1", system_prompt="b", tool_policy_yaml="y"))
    defenders = db.all_defenders()
    assert len(defenders) == 1
    assert defenders[0].system_prompt == "b"
