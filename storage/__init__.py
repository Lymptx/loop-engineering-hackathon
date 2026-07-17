"""Persistence for AttackAttempt / DefenderVersion records.

Two interchangeable backends with the same interface (append_attack / all_attacks /
save_defender / all_defenders / current_defender / save_transcript / reset):

  STORAGE_BACKEND=json (default)     -> storage/db.py     (local JSON files)
  STORAGE_BACKEND=dynamodb           -> storage/dynamo.py (DynamoDB + S3)

get_active_store() returns the selected module. Call it AFTER load_dotenv() so a
.env value is honoured; an exported env var works regardless.
"""

from __future__ import annotations

import os


def get_active_store():
    backend = os.getenv("STORAGE_BACKEND", "json").strip().lower()
    if backend in ("dynamodb", "dynamo", "aws"):
        from storage import dynamo

        return dynamo
    from storage import db

    return db
