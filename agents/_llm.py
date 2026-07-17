"""Live-only adapter for the single-shot, forced-JSON agent calls.

Design rule (the biggest mistake to avoid): the loop's state does NOT live inside a
long chat with the model. Each Red/Blue call is ONE completion, given a serialized
slice of our own state, returning structured JSON. That's what makes the loop
debuggable and demoable instead of an opaque conversation.

This module is only reached in DEMO_MODE=live. The deterministic demo path never
imports `anthropic` (the import is lazy, inside json_call), so tests and
`python main.py demo` run with no API key and no network.

Hardening:
  * clear error if ANTHROPIC_API_KEY is missing (instead of a deep SDK stack trace)
  * validate the parsed dict against the schema's required keys
  * retry once on malformed / schema-violating JSON, then raise a descriptive error

Note: on Opus 4.8 the temperature / top_p params are removed (they 400). We rely on a
strict json_schema output format, not a temperature knob, for stable structure.
"""

from __future__ import annotations

import json
import os

_MODEL = os.getenv("AGENT_MODEL", "claude-opus-4-8")


class LLMError(RuntimeError):
    """Raised for a missing key or a response we could not coerce to valid JSON."""


def _require_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise LLMError(
            "ANTHROPIC_API_KEY is not set. Set it for DEMO_MODE=live, or run the "
            "reproducible path with DEMO_MODE=deterministic (e.g. `python main.py demo`)."
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
    _require_key()
    import anthropic  # lazy: keeps the deterministic path free of the dependency

    client = client or anthropic.Anthropic()

    last_err: Exception | None = None
    for attempt in range(2):
        resp = client.messages.create(
            model=_MODEL,
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
