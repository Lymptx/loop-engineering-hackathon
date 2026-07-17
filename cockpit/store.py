"""JSON-backed, thread-safe persistence for the cockpit.

One file (storage/data/cockpit.json) holds every record type as an append-only list,
each tagged with run_id and a monotonic sequence number. The engine (a background
thread) appends; the API reads. A threading.Lock guards all access.

Persistence rules (skill non-negotiables):
  * Records are immutable once written (bundles upsert by natural key; everything else
    is append-only).
  * A server restart reloads the file, so prior demo history survives.
  * Only an explicit reset() clears the store. It clears cockpit run state; it does NOT
    touch the immutable subject artifacts (capability_versions.json, evo_defenders.json).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path(__file__).parents[1] / "storage" / "data" / "cockpit.json"

_SKELETON = {
    "seq": 0,
    "runs": [],
    "events": [],
    "attack_bundles": [],
    "defender_bundles": [],
    "attempts": [],
    "candidates": [],
    "metrics": [],
    "history": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else _DEFAULT_PATH
        self.lock = threading.Lock()
        self._data = self._load()

    # --- persistence ---
    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return json.loads(json.dumps(_SKELETON))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def reset(self) -> None:
        with self.lock:
            self._data = json.loads(json.dumps(_SKELETON))
            self._save()

    def _next_seq(self) -> int:
        self._data["seq"] += 1
        return self._data["seq"]

    # --- runs ---
    def start_run(self, run_id: str) -> dict:
        with self.lock:
            run = {
                "run_id": run_id,
                "mode": "deterministic_demo",
                "status": "running",
                "started_at": _now(),
                "finished_at": None,
                "current_evo": "evo0",
                "active_defender": None,
                "current_phase": "baseline_evaluation",
            }
            self._data["runs"].append(run)
            self._save()
            return dict(run)

    def update_run(self, run_id: str, **fields) -> None:
        with self.lock:
            for r in self._data["runs"]:
                if r["run_id"] == run_id:
                    r.update(fields)
            self._save()

    def latest_run(self) -> dict | None:
        return self._data["runs"][-1] if self._data["runs"] else None

    # --- events ---
    def add_event(self, run_id: str, type_: str, summary: str, *,
                  evo: str | None = None, defender_version: str | None = None,
                  payload: dict | None = None) -> dict:
        with self.lock:
            seq = self._next_seq()
            evt = {
                "event_id": f"evt-{seq:06d}",
                "run_id": run_id,
                "sequence": seq,
                "timestamp": _now(),
                "type": type_,
                "evo": evo,
                "defender_version": defender_version,
                "summary": summary,
                "payload": payload or {},
            }
            self._data["events"].append(evt)
            self._save()
            return dict(evt)

    def events_since(self, since: int = 0) -> list[dict]:
        with self.lock:
            return [e for e in self._data["events"] if e["sequence"] > since]

    # --- bundles (immutable; upsert by natural key) ---
    def add_attack_bundle(self, entry: dict) -> bool:
        """Upsert by family (immutable). Returns True only when newly added."""
        with self.lock:
            existing = {b["family"] for b in self._data["attack_bundles"]}
            if entry["family"] in existing:
                return False
            self._data["attack_bundles"].append(entry)
            self._save()
            return True

    def add_defender_bundle(self, entry: dict) -> bool:
        with self.lock:
            existing = {b["defender_version"] for b in self._data["defender_bundles"]}
            if entry["defender_version"] in existing:
                return False
            self._data["defender_bundles"].append(entry)
            self._save()
            return True

    def update_attack_bundle_success(self, family: str, defender_version: str,
                                     success: bool) -> None:
        with self.lock:
            for b in self._data["attack_bundles"]:
                if b["family"] == family:
                    tested = set(b.get("tested_defenders", []))
                    tested.add(defender_version)
                    b["tested_defenders"] = sorted(tested)
                    b["latest_success"] = success
            self._save()

    # --- append-only record types ---
    def add_attempt(self, attempt: dict) -> dict:
        with self.lock:
            self._data["attempts"].append(attempt)
            self._save()
            return attempt

    def add_candidate(self, candidate: dict) -> dict:
        with self.lock:
            self._data["candidates"].append(candidate)
            self._save()
            return candidate

    def add_metric(self, metric: dict) -> dict:
        with self.lock:
            self._data["metrics"].append(metric)
            self._save()
            return metric

    def add_history(self, row: dict) -> dict:
        with self.lock:
            self._data["history"].append(row)
            self._save()
            return row

    # --- id helpers ---
    def next_id(self, prefix: str, collection: str) -> str:
        with self.lock:
            n = len(self._data[collection]) + 1
            return f"{prefix}-{n:03d}"

    # --- read snapshots ---
    def attempts(self) -> list[dict]:
        with self.lock:
            return list(self._data["attempts"])

    def snapshot(self) -> dict:
        with self.lock:
            return json.loads(json.dumps(self._data))
