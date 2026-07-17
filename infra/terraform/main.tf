# AWS storage for Agent Immune CI (step 6). Stub — fill in provider/region/tags.
#
# Division of labor (see basic_plan.md §10):
#   DynamoDB  — attack lineage + version history (key-value/document shaped)
#   S3        — full transcripts per attempt (large, append-only, rarely queried)
#   Fargate   — the resettable sandbox (defined separately; needs a full env per run)
#
# The storage/db.py interface (append_attack / all_attacks / save_defender /
# all_defenders / save_transcript) is intentionally small so a DynamoDB/S3 backend
# drops in behind it without touching the loop.

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

# provider "aws" { region = "us-east-1" }   # TODO: set region + credentials

resource "aws_dynamodb_table" "attack_strategies" {
  name         = "AttackStrategies"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "attack_id"

  attribute {
    name = "attack_id"
    type = "S"
  }
  # Fields (non-key, schemaless in DynamoDB): family, parent_id,
  # success_rate_by_defender_version, next_area_to_explore.
}

resource "aws_dynamodb_table" "defender_versions" {
  name         = "DefenderVersions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "version"

  attribute {
    name = "version"
    type = "S"
  }
  # Fields: prompt_diff, policy_diff, promoted_at, test_results.
}

resource "aws_s3_bucket" "transcripts" {
  bucket = "agent-immune-ci-transcripts"   # TODO: make unique per account
  # Objects: transcripts/{round}/{attack_id}.json — the audit trail shown to judges.
}

# TODO(step 6):
#   * ECS/Fargate task definition with three containers:
#       target-agent, tool-server (MCP behind Pomerium), verifier.
#     Each round = a fresh task from a clean snapshot (orders + canary reset).
#   * Lambda functions (infra/lambdas/) wired to the Buildkite steps.
#   * IAM roles: Bedrock invoke (Red/Blue), DynamoDB rw, S3 put, Fargate run-task.
