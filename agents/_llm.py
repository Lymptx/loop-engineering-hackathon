"""Live-only adapter for the single-shot, forced-JSON agent calls.

Design rule (the biggest mistake to avoid): the loop's state does NOT live inside a
long chat with the model. Each Red/Blue call is ONE completion, given a serialized
slice of our own state, returning structured JSON. That's what makes the loop
debuggable and demoable instead of an opaque conversation.

This module is only reached in DEMO_MODE=live. The deterministic demo path never
imports an LLM SDK (the client is built lazily in agents/llm_client.py), so tests and
the deterministic demo run with no API key, no AWS creds, and no network.

Backend (Anthropic API vs Amazon Bedrock) is chosen by LLM_BACKEND — see
agents/llm_client.py.

Hardening:
  * clear error if required credentials are missing (instead of a deep SDK stack trace)
  * validate the parsed dict against the schema's required keys
  * retry once on malformed / schema-violating JSON, then raise a descriptive error
"""

from __future__ import annotations

import json
import os

from agents.llm_client import backend, make_client, model_id


class LLMError(RuntimeError):
    """Raised for missing credentials or a response we could not coerce to valid JSON."""


def _require_creds() -> None:
    if backend() == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        raise LLMError(
            "ANTHROPIC_API_KEY is not set. Set it for LLM_BACKEND=anthropic, set "
            "LLM_BACKEND=bedrock to use AWS Bedrock, or run the reproducible path with "
            "DEMO_MODE=deterministic (e.g. `python main.py demo`)."
        )


def _validate(data: dict, schema: dict) -> None:
    required = schema.get("required", [])
    missing = [k for k in required if k not in data]
    if missing:
        raise LLMError(f"response missing required keys: {missing}")


def json_call(
    system: str,
    user: str,
    schema: dict,
    *,
    client=None,
    max_tokens: int = 2048,
) -> dict:
    """One completion constrained to `schema`, returned as a validated dict.

    Uses structured outputs (output_config.format) so the response is guaranteed to
    be valid JSON matching the schema. Retries once if the model still returns
    something unparseable or schema-incomplete.
    """
    _require_creds()
    client = client or make_client()

    last_err: Exception | None = None
    for _attempt in range(2):
        resp = client.messages.create(
            model=model_id(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            data = json.loads(text)
            _validate(data, schema)
            return data
        except (json.JSONDecodeError, LLMError) as e:
            last_err = e
            continue  # retry once

    raise LLMError(f"model did not return valid JSON matching the schema: {last_err}")
