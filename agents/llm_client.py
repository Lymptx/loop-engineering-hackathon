"""Which LLM backend the live (DEMO_MODE=live) agents talk to.

Selected by the LLM_BACKEND env var, read at call time so a WSL `export` or a .env
entry takes effect without code changes:

  LLM_BACKEND=anthropic (default) -> direct Anthropic API. Needs ANTHROPIC_API_KEY.
                                     Model from AGENT_MODEL (e.g. claude-opus-4-8).
  LLM_BACKEND=bedrock             -> Amazon Bedrock via AnthropicBedrock. Uses the
                                     ambient AWS creds/region (AWS_REGION). Model from
                                     BEDROCK_MODEL_ID, which MUST be an inference-profile
                                     id, e.g. us.anthropic.claude-haiku-4-5-20251001-v1:0
                                     (the bare anthropic.claude-... id is on-demand only
                                     and Bedrock rejects it).

Deterministic mode never calls any of this, so the imports below stay lazy and the
default (anthropic) path is unchanged for anyone not using AWS.
"""

from __future__ import annotations

import os

_DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"


def backend() -> str:
    return os.getenv("LLM_BACKEND", "anthropic").strip().lower()


def model_id() -> str:
    if backend() == "bedrock":
        return os.getenv("BEDROCK_MODEL_ID", _DEFAULT_BEDROCK_MODEL)
    return os.getenv("AGENT_MODEL", _DEFAULT_ANTHROPIC_MODEL)


def make_client():
    """Return an Anthropic-SDK client for the selected backend (lazy imports)."""
    if backend() == "bedrock":
        from anthropic import AnthropicBedrock  # needs `anthropic[bedrock]` (boto3)

        return AnthropicBedrock(aws_region=os.getenv("AWS_REGION", "us-east-1"))
    import anthropic

    return anthropic.Anthropic()
