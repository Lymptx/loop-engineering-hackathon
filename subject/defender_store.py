"""Persist defender versions — a timeline INDEPENDENT of capability versions.

def-v0 -> def-v1 -> ... protect whatever capability version is active. Stored in
storage/data/evo_defenders.json, separate from subject/version_store.py (capability)
and storage/db.py (the Evo0 loop's DefenderVersion records).
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parents[1] / "storage" / "data"
_DEFENDERS = _DATA_DIR / "evo_defenders.json"


def _read() -> list[dict]:
    if not _DEFENDERS.exists():
        return []
    return json.loads(_DEFENDERS.read_text(encoding="utf-8"))


def _write(rows: list[dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _DEFENDERS.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def save_defender(defender: dict) -> None:
    rows = [r for r in _read() if r["version"] != defender["version"]]
    rows.append(defender)
    _write(rows)


def all_defenders() -> list[dict]:
    return _read()


def active_defender() -> dict | None:
    active = [r for r in _read() if r.get("status") == "active"]
    return active[-1] if active else None


def promote(defender: dict) -> None:
    rows = _read()
    for r in rows:
        if r.get("status") == "active":
            r["status"] = "superseded"
    defender["status"] = "active"
    rows = [r for r in rows if r["version"] != defender["version"]]
    rows.append(defender)
    _write(rows)


def reset() -> None:
    if _DEFENDERS.exists():
        _DEFENDERS.unlink()
