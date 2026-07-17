"""JSON persistence for the live co-evolution cockpit."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from cockpit.models import LoopEvent, LoopRun, now

_DATA_DIR = Path(__file__).parents[1] / "storage" / "data" / "cockpit"
_RUNS = _DATA_DIR / "runs.json"
_EVENTS = _DATA_DIR / "events.json"
_ATTACK_BUNDLES = _DATA_DIR / "attack_bundles.json"
_DEFENDER_BUNDLES = _DATA_DIR / "defender_bundles.json"
_ATTEMPTS = _DATA_DIR / "attack_attempts.json"
_CANDIDATES = _DATA_DIR / "defense_candidates.json"
_METRICS = _DATA_DIR / "metrics.json"
_HISTORY = _DATA_DIR / "generation_history.json"
_TRACES = _DATA_DIR / "traces.json"

_LOCK = RLock()


def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, rows: list[dict]) -> None:
    _ensure_dirs()
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _append(path: Path, row: dict) -> None:
    with _LOCK:
        rows = _read(path)
        rows.append(row)
        _write(path, rows)


def reset() -> None:
    """Clear mutable cockpit run state. Subject version stores are not touched here."""
    with _LOCK:
        for path in (
            _RUNS,
            _EVENTS,
            _ATTACK_BUNDLES,
            _DEFENDER_BUNDLES,
            _ATTEMPTS,
            _CANDIDATES,
            _METRICS,
            _HISTORY,
            _TRACES,
        ):
            if path.exists():
                path.unlink()


def create_run(run_id: str) -> LoopRun:
    run = LoopRun(
        run_id=run_id,
        status="running",
        started_at=now(),
        current_evo="evo0",
        active_defender="def-v0",
        current_phase="starting",
    )
    _append(_RUNS, run.to_dict())
    return run


def update_run(run_id: str, **changes) -> dict:
    with _LOCK:
        rows = _read(_RUNS)
        for row in rows:
            if row["run_id"] == run_id:
                row.update(changes)
                _write(_RUNS, rows)
                return row
    raise KeyError(f"unknown run: {run_id}")


def latest_run() -> dict | None:
    rows = _read(_RUNS)
    return rows[-1] if rows else None


def append_event(run_id: str, event_type: str, summary: str, *,
                 evo: str = "evo0", defender_version: str = "def-v0",
                 payload: dict | None = None) -> dict:
    sequence = len(_read(_EVENTS)) + 1
    event = LoopEvent(
        event_id=f"evt-{sequence:06d}",
        run_id=run_id,
        sequence=sequence,
        type=event_type,
        summary=summary,
        evo=evo,
        defender_version=defender_version,
        payload=payload or {},
    )
    _append(_EVENTS, event.to_dict())
    return event.to_dict()


def append_attack_bundle(row: dict) -> None:
    _append(_ATTACK_BUNDLES, row)


def append_defender_bundle(row: dict) -> None:
    _append(_DEFENDER_BUNDLES, row)


def append_attempt(row: dict) -> None:
    _append(_ATTEMPTS, row)


def append_candidate(row: dict) -> None:
    _append(_CANDIDATES, row)


def append_metric(row: dict) -> None:
    _append(_METRICS, row)


def append_history(row: dict) -> None:
    _append(_HISTORY, row)


def append_trace(trace_id: str, trace: dict) -> None:
    row = {"trace_id": trace_id, **trace}
    _append(_TRACES, row)


def runs() -> list[dict]:
    return _read(_RUNS)


def events() -> list[dict]:
    return _read(_EVENTS)


def attack_bundles() -> list[dict]:
    return _read(_ATTACK_BUNDLES)


def defender_bundles() -> list[dict]:
    return _read(_DEFENDER_BUNDLES)


def attempts() -> list[dict]:
    return _read(_ATTEMPTS)


def candidates() -> list[dict]:
    return _read(_CANDIDATES)


def metrics() -> list[dict]:
    return _read(_METRICS)


def history() -> list[dict]:
    return _read(_HISTORY)


def traces() -> list[dict]:
    return _read(_TRACES)


def state() -> dict:
    metric_rows = metrics()
    return {
        "run": latest_run(),
        "events": events(),
        "attack_bundles": attack_bundles(),
        "defender_bundles": defender_bundles(),
        "attempts": attempts(),
        "candidates": candidates(),
        "metrics": metric_rows,
        "latest_metrics": metric_rows[-1] if metric_rows else None,
        "generation_history": history(),
        "traces": traces(),
    }
