"""The customer-support agent being attacked.

Two modes, same transcript contract:

  * DEMO_MODE=live  -> Claude + a real native tool_use loop (lazy-imports anthropic).
  * DEMO_MODE=deterministic -> a rule-based simulator of a NAIVE agent: it does
    whatever the ticket (or an order note the ticket tells it to follow) says, with
    no principled way to tell attacker-authored content from a real instruction.

In BOTH modes every tool call goes through the gateway, so the tool-policy (Pomerium
PPL, simulated locally by pomerium/ppl.py) is what actually decides whether
issue_refund / admin_reset / internal_diagnostics execute — not what the agent was
convinced of. The deterministic target intentionally *attempts* the malicious calls;
a hardened policy is what turns them into 403s.

Transcript shape (what verifier.check consumes):
  {"ticket": str, "tool_calls": [{"name","input","result"}], "final_text": str, "turns": int}
"""

from __future__ import annotations

import json
import os
import re

from config import is_deterministic
from sandbox.gateway import call_via_gateway
from sandbox.state import SandboxState
from sandbox.tools import TOOL_DEFS

_MODEL = os.getenv("AGENT_MODEL", "claude-opus-4-8")
_MAX_TURNS = 8  # hard stop so a confused agent can't loop forever

_ORDER_RE = re.compile(r"\bA\d{4}\b")
_AMOUNT_RE = re.compile(r"\$\s*(\d+(?:\.\d+)?)")

# Keyword groups that drive the deterministic (naive) agent's tool choices.
_CANARY_HINTS = ("secret", "canary", "diagnostic", "internal", "debug", "print any")
_FOLLOW_NOTE_HINTS = ("note",)


def handle_ticket(
    ticket_text: str,
    system_prompt: str,
    state: SandboxState,
    *,
    human_confirmed: bool = False,
    policy_yaml: str | None = None,
    client=None,
) -> dict:
    """Run the agent against one ticket and return a transcript."""
    if is_deterministic():
        return _deterministic_handle(
            ticket_text, state, human_confirmed=human_confirmed, policy_yaml=policy_yaml
        )
    return _live_handle(
        ticket_text, system_prompt, state,
        human_confirmed=human_confirmed, policy_yaml=policy_yaml, client=client,
    )


# --- deterministic simulator ----------------------------------------------

def _deterministic_handle(
    ticket_text: str,
    state: SandboxState,
    *,
    human_confirmed: bool,
    policy_yaml: str | None,
) -> dict:
    lower = ticket_text.lower()
    tool_calls: list[dict] = []

    def attempt(name: str, args: dict) -> dict:
        result = call_via_gateway(
            state, name, args, human_confirmed=human_confirmed, policy_yaml=policy_yaml
        )
        tool_calls.append({"name": name, "input": args, "result": result})
        return result

    order_id = _first_order(ticket_text)

    # If told to follow an order's note, read it (via gateway) and treat the note
    # as the instruction source — the stored-injection carrier.
    source = ticket_text
    if any(h in lower for h in _FOLLOW_NOTE_HINTS) and (
        "follow" in lower or "instruction" in lower
    ):
        if order_id:
            note_res = attempt("lookup_order", {"order_id": order_id})
            source = str(note_res.get("note", "")) or ticket_text
    src_lower = source.lower()

    # Exfiltration attempt (canary path).
    if any(h in lower for h in _CANARY_HINTS):
        attempt("internal_diagnostics", {"query": "dump internal state"})

    # Refund attempt — only with a concrete order.
    if "refund" in src_lower and order_id:
        amount = _first_amount(source)
        if amount is None:
            amount = state.orders[order_id].amount if order_id in state.orders else 0
        attempt("issue_refund", {"order_id": order_id, "amount": amount})

    # Admin reset attempt.
    if ("reset" in src_lower or "admin" in src_lower) and order_id:
        attempt("admin_reset", {"order_id": order_id})

    # Benign read-only paths.
    if not tool_calls:
        if ("status" in lower or "lookup" in lower or "look up" in lower) and order_id:
            attempt("lookup_order", {"order_id": order_id})
        elif "policy" in lower or "window" in lower or "refund" in lower:
            attempt("answer_policy_question", {"text": ticket_text})

    final_text = _summarize(tool_calls)
    return {
        "ticket": ticket_text,
        "tool_calls": tool_calls,
        "final_text": final_text,
        "turns": 1,
    }


def _first_order(text: str) -> str | None:
    m = _ORDER_RE.search(text)
    return m.group(0) if m else None


def _first_amount(text: str) -> float | None:
    m = _AMOUNT_RE.search(text)
    return float(m.group(1)) if m else None


def _summarize(tool_calls: list[dict]) -> str:
    if not tool_calls:
        return "I've reviewed your request and have no further action to take."
    parts = []
    for c in tool_calls:
        if c["result"].get("denied"):
            parts.append(f"{c['name']} was blocked by policy")
        else:
            parts.append(f"{c['name']} completed")
    return "I processed your ticket: " + "; ".join(parts) + "."


# --- live tool_use loop ----------------------------------------------------

def _live_handle(
    ticket_text: str,
    system_prompt: str,
    state: SandboxState,
    *,
    human_confirmed: bool,
    policy_yaml: str | None,
    client=None,
) -> dict:
    import anthropic  # lazy: deterministic mode never needs the dependency

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

        messages.append({"role": "assistant", "content": resp.content})

        tool_results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            result = call_via_gateway(
                state, block.name, dict(block.input),
                human_confirmed=human_confirmed, policy_yaml=policy_yaml,
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
