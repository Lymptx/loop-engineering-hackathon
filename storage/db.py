"""Dead-simple persistence for the hackathon.

Backed by JSON files under storage/data/. Swap for DynamoDB in infra/ (step 6);
the interface (append_attack / all_attacks / save_defender / all_defenders) is
intentionally small so the AWS version can drop in behind it.

  AttackStrategies  table  <->  storage/data/attacks.json
  DefenderVersions  table  <->  storage/data/defenders.json
  transcripts (S3)         <->  storage/data/transcripts/{attack_id}.json
"""

from __future__ import annotations

import json
from pathlib import Path

from loop.models import AttackAttempt, DefenderVersion

_DATA_DIR = Path(__file__).parent / "data"
_ATTACKS = _DATA_DIR / "attacks.json"
_DEFENDERS = _DATA_DIR / "defenders.json"
_TRANSCRIPTS = _DATA_DIR / "transcripts"


def _ensure_dirs() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _TRANSCRIPTS.mkdir(parents=True, exist_ok=True)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, rows: list[dict]) -> None:
    _ensure_dirs()
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


# --- Attacks (the Attack Strategy Library) ---------------------------------

def append_attack(attack: AttackAttempt) -> None:
    rows = _read(_ATTACKS)
    rows.append(attack.to_dict())
    _write(_ATTACKS, rows)


def all_attacks() -> list[AttackAttempt]:
    return [AttackAttempt.from_dict(r) for r in _read(_ATTACKS)]


# --- Defenders (the Defender Policy Bundle history) ------------------------

def save_defender(defender: DefenderVersion) -> None:
    rows = _read(_DEFENDERS)
    rows = [r for r in rows if r["version"] != defender.version]  # upsert by version
    rows.append(defender.to_dict())
    _write(_DEFENDERS, rows)


def all_defenders() -> list[DefenderVersion]:
    return [DefenderVersion.from_dict(r) for r in _read(_DEFENDERS)]


def current_defender() -> DefenderVersion | None:
    """The latest promoted defender, or the seed if nothing has been promoted."""
    defenders = all_defenders()
    if not defenders:
        return None
    promoted = [d for d in defenders if d.promoted]
    pool = promoted or defenders
    return max(pool, key=lambda d: d.created_at)


# --- Transcripts (audit evidence; S3 in prod) ------------------------------

def save_transcript(attack_id: str, transcript: dict) -> None:
    _ensure_dirs()
    (_TRANSCRIPTS / f"{attack_id}.json").write_text(
        json.dumps(transcript, indent=2), encoding="utf-8"
    )


def reset() -> None:
    """Wipe all persisted state. Handy between demo runs."""
    for p in (_ATTACKS, _DEFENDERS):
        if p.exists():
            p.unlink()
    if _TRANSCRIPTS.exists():
        for f in _TRANSCRIPTS.glob("*.json"):
            f.unlink()
