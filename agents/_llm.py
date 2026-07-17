"""Shared helper for the single-shot, forced-JSON agent calls.

Design rule (the biggest mistake to avoid): the loop's state does NOT live inside a
long chat with the model. Each Red/Blue call is ONE completion, given a serialized
slice of our own state, returning structured JSON. That's what makes the loop
debuggable and demoable instead of an opaque conversation.

Note: on Opus 4.8 the `temperature` / `top_p` params are removed (they 400). We get
determinism-ish behaviour via a strict schema + low effort, not a temperature knob.
"""

from __future__ import annotations

import json
import os

import anthropic

_MODEL = os.getenv("AGENT_MODEL", "claude-opus-4-8")


def json_call(
    system: str,
    user: str,
    schema: dict,
    *,
    client: anthropic.Anthropic | None = None,
    max_tokens: int = 2048,
) -> dict:
    """One completion constrained to `schema`, returned as a parsed dict.

    Uses structured outputs (output_config.format) so the response is guaranteed
    to be valid JSON matching the schema — free-text parsing is exactly the thing
    that breaks live on demo day.
    """
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)
