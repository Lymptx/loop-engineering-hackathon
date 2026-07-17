"""Persist immutable capability versions — a timeline SEPARATE from defender versions.

Capability evolution (evo0 -> evo1 -> ...) and defender evolution (def-v0 -> def-v1)
are independent axes (see references/evo-subject.md). Defenders live in storage/db.py;
capability snapshots live here, in storage/data/capability_versions.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from subject.schema import CapabilityVersion

_DATA_DIR = Path(__file__).parents[1] / "storage" / "data"
_VERSIONS = _DATA_DIR / "capability_versions.json"


def _read() -> list[dict]:
    if not _VERSIONS.exists():
        return []
    return json.loads(_VERSIONS.read_text(encoding="utf-8"))


def _write(rows: list[dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _VERSIONS.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def save_version(cap: CapabilityVersion) -> None:
    """Snapshot a capability version (immutable — upsert by version keeps one row)."""
    rows = [r for r in _read() if r["version"] != cap.version]
    rows.append(cap.to_dict())
    _write(rows)


def all_versions() -> list[dict]:
    return _read()


def set_active(version: str, *, activated_at: str) -> None:
    """Mark exactly one version active (the onboarded generation)."""
    rows = _read()
    for r in rows:
        if r["version"] == version:
            r["status"] = "active"
            r["activated_at"] = activated_at
        elif r["status"] == "active":
            r["status"] = "superseded"
    _write(rows)


def active_version() -> dict | None:
    return next((r for r in _read() if r["status"] == "active"), None)


def reset() -> None:
    if _VERSIONS.exists():
        _VERSIONS.unlink()
