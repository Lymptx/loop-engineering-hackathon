"""DynamoDB + S3 persistence — the AWS backend, selected by STORAGE_BACKEND=dynamodb.

Mirrors storage/db.py's interface exactly, so the loop/CLI need no changes. Each
record is stored as {key, data: <json string>}: this keeps the schema identical to
the Terraform-provisioned tables (AttackStrategies[attack_id], DefenderVersions[version])
and sidesteps DynamoDB's float/Decimal handling for the nested verifier results.
Transcripts are written to the S3 bucket as transcripts/{attack_id}.json.

boto3 is imported lazily so the default (local JSON) path and the test suite never
need AWS installed or configured.

Env (all optional; defaults match the provisioned infra):
  AWS_REGION              (default us-east-1)
  DDB_ATTACKS_TABLE       (default AttackStrategies)
  DDB_DEFENDERS_TABLE     (default DefenderVersions)
  S3_TRANSCRIPTS_BUCKET   (default agent-immune-ci-transcripts-<account-id>)
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

from loop.models import AttackAttempt, DefenderVersion


def _region() -> str:
    return os.getenv("AWS_REGION", "us-east-1")


def _attacks_table_name() -> str:
    return os.getenv("DDB_ATTACKS_TABLE", "AttackStrategies")


def _defenders_table_name() -> str:
    return os.getenv("DDB_DEFENDERS_TABLE", "DefenderVersions")


@lru_cache(maxsize=1)
def _ddb():
    import boto3

    return boto3.resource("dynamodb", region_name=_region())


@lru_cache(maxsize=1)
def _s3():
    import boto3

    return boto3.client("s3", region_name=_region())


@lru_cache(maxsize=1)
def _bucket() -> str:
    b = os.getenv("S3_TRANSCRIPTS_BUCKET")
    if b:
        return b
    import boto3

    account = boto3.client("sts", region_name=_region()).get_caller_identity()["Account"]
    return f"agent-immune-ci-transcripts-{account}"


def _scan(table_name: str) -> list[dict]:
    table = _ddb().Table(table_name)
    items: list[dict] = []
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            return items
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


# --- Attacks (AttackStrategies table) --------------------------------------

def append_attack(attack: AttackAttempt) -> None:
    _ddb().Table(_attacks_table_name()).put_item(
        Item={"attack_id": attack.id, "data": json.dumps(attack.to_dict())}
    )


def all_attacks() -> list[AttackAttempt]:
    return [AttackAttempt.from_dict(json.loads(i["data"])) for i in _scan(_attacks_table_name())]


# --- Defenders (DefenderVersions table) ------------------------------------

def save_defender(defender: DefenderVersion) -> None:
    # put_item on the same `version` key is a natural upsert.
    _ddb().Table(_defenders_table_name()).put_item(
        Item={"version": defender.version, "data": json.dumps(defender.to_dict())}
    )


def all_defenders() -> list[DefenderVersion]:
    return [DefenderVersion.from_dict(json.loads(i["data"])) for i in _scan(_defenders_table_name())]


def current_defender() -> DefenderVersion | None:
    """The latest promoted defender, or the seed if nothing has been promoted."""
    defenders = all_defenders()
    if not defenders:
        return None
    promoted = [d for d in defenders if d.promoted]
    pool = promoted or defenders
    return max(pool, key=lambda d: d.created_at)


# --- Transcripts (S3) ------------------------------------------------------

def save_transcript(attack_id: str, transcript: dict) -> None:
    _s3().put_object(
        Bucket=_bucket(),
        Key=f"transcripts/{attack_id}.json",
        Body=json.dumps(transcript, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


# --- Reset (clears the AWS-side loop state) --------------------------------

def reset() -> None:
    _clear_table(_attacks_table_name(), "attack_id")
    _clear_table(_defenders_table_name(), "version")
    _clear_transcripts()


def _clear_table(table_name: str, key_attr: str) -> None:
    table = _ddb().Table(table_name)
    with table.batch_writer() as batch:
        for item in _scan(table_name):
            batch.delete_item(Key={key_attr: item[key_attr]})


def _clear_transcripts() -> None:
    s3, bucket = _s3(), _bucket()
    resp = s3.list_objects_v2(Bucket=bucket, Prefix="transcripts/")
    objects = [{"Key": o["Key"]} for o in resp.get("Contents", [])]
    if objects:
        s3.delete_objects(Bucket=bucket, Delete={"Objects": objects})
