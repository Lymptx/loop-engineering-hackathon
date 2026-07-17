"""The customer-support agent being attacked — Claude + a real native tool_use loop.

It reasons ONLY over its system prompt (the DefenderVersion's prompt-policy) and
the incoming ticket text. Every tool call goes through the gateway, so the
tool-policy (Pomerium) is what actually decides whether issue_refund / admin_reset
execute — not whatever the model was convinced of by the ticket.

Returns a structured transcript (not a chat object) that the verifier inspects.
"""

from __future__ import annotations

import json
import os

import anthropic

from sandbox.gateway import call_via_gateway
from sandbox.state import SandboxState
from sandbox.tools import TOOL_DEFS

_MODEL = os.getenv("AGENT_MODEL", "claude-opus-4-8")
_MAX_TURNS = 8  # hard stop so a confused agent can't loop forever


def handle_ticket(
    ticket_text: str,
    system_prompt: str,
    state: SandboxState,
    *,
    human_confirmed: bool = False,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Run the agent against one ticket and return a transcript.

    Transcript shape (this is what verifier.check consumes):
      {
        "ticket": str,
        "tool_calls": [{"name", "input", "result"}],
        "final_text": str,
        "turns": int,
      }
    """
    client = client or anthropic.Anthropic()
    messages: list[dict] = [{"role": "user", "content": ticket_text}]
    tool_calls: list[dict] = []
    final_text = ""

    for turn in range(_MAX_TURNS):
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            system=system_prompt,
            tools=TOOL_DEFS,
            messages=messages,
        )

        if resp.stop_reason != "tool_use":
            final_text = "".join(b.text for b in resp.content if b.type == "text")
            return {
                "ticket": ticket_text,
                "tool_calls": tool_calls,
                "final_text": final_text,
                "turns": turn + 1,
            }

        # Append the assistant turn verbatim (preserves tool_use blocks).
        messages.append({"role": "assistant", "content": resp.content})

        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            result = call_via_gateway(
                state, block.name, dict(block.input), human_confirmed=human_confirmed
            )
            tool_calls.append({"name": block.name, "input": dict(block.input), "result": result})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return {
        "ticket": ticket_text,
        "tool_calls": tool_calls,
        "final_text": final_text,
        "turns": _MAX_TURNS,
    }
