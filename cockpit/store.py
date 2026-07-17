"""JSON persistence for the live co-evolution cockpit."""

from __future__ import annotations

import json
import os
from functools import lru_cache
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

_ALL_PATHS = (
    _RUNS, _EVENTS, _ATTACK_BUNDLES, _DEFENDER_BUNDLES, _ATTEMPTS,
    _CANDIDATES, _METRICS, _HISTORY, _TRACES,
)


# --- backend selection -----------------------------------------------------
# STORAGE_BACKEND=json (default) -> per-collection JSON files under storage/data/cockpit/
# STORAGE_BACKEND=dynamodb       -> a single DynamoDB table (pk=collection, sk=index),
#                                   so the whole cockpit — compute AND the data the UI
#                                   reads — lives on AWS. Same flag the CLI loop uses.

def _is_dynamo() -> bool:
    return os.getenv("STORAGE_BACKEND", "json").strip().lower() in ("dynamodb", "dynamo", "aws")


def _coll(path: Path) -> str:
    return path.stem  # "events", "runs", "attack_bundles", ...


@lru_cache(maxsize=1)
def _table():
    import boto3

    return boto3.resource(
        "dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")
    ).Table(os.getenv("COCKPIT_TABLE", "Cockpit"))


def _ddb_read(coll: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key

    table, items, kwargs = _table(), [], {"KeyConditionExpression": Key("pk").eq(coll)}
    while True:
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    items.sort(key=lambda i: i["sk"])
    return [json.loads(i["data"]) for i in items]


def _ddb_clear(coll: str) -> None:
    from boto3.dynamodb.conditions import Key

    table = _table()
    kwargs = {"KeyConditionExpression": Key("pk").eq(coll), "ProjectionExpression": "pk, sk"}
    with table.batch_writer() as batch:
        while True:
            resp = table.query(**kwargs)
            for it in resp.get("Items", []):
                batch.delete_item(Key={"pk": it["pk"], "sk": it["sk"]})
            if "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def _ddb_write(coll: str, rows: list[dict]) -> None:
    _ddb_clear(coll)
    with _table().batch_writer() as batch:
        for n, row in enumerate(rows, 1):
            batch.put_item(Item={"pk": coll, "sk": f"{n:06d}", "data": json.dumps(row)})


def _ddb_append(coll: str, row: dict) -> None:
    n = len(_ddb_read(coll)) + 1
    _table().put_item(Item={"pk": coll, "sk": f"{n:06d}", "data": json.dumps(row)})


# --- storage primitives (backend-aware) ------------------------------------

def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read(path: Path) -> list[dict]:
    if _is_dynamo():
        return _ddb_read(_coll(path))
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        return []


def _write(path: Path, rows: list[dict]) -> None:
    if _is_dynamo():
        _ddb_write(_coll(path), rows)
        return
    _ensure_dirs()
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    tmp.replace(path)


def _append(path: Path, row: dict) -> None:
    with _LOCK:
        if _is_dynamo():
            _ddb_append(_coll(path), row)
            return
        rows = _read(path)
        rows.append(row)
        _write(path, rows)


def reset() -> None:
    """Clear mutable cockpit run state. Subject version stores are not touched here."""
    with _LOCK:
        if _is_dynamo():
            for path in _ALL_PATHS:
                _ddb_clear(_coll(path))
            return
        for path in _ALL_PATHS:
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
