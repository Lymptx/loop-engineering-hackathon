"""lambda-run-attack — send the latest attack payload to the running target agent.

In prod this posts to the target-agent Fargate task; locally it calls handle_ticket
directly. Captures the transcript to S3 (storage.save_transcript locally).
"""

from __future__ import annotations

from sandbox.state import SandboxState
from sandbox.target_agent import handle_ticket
from storage import db


def handler(event=None, context=None) -> dict:
    attacks = db.all_attacks()
    if not attacks:
        return {"error": "no attack to run"}
    attack = attacks[-1]
    current = db.current_defender()
    state = SandboxState.fresh()
    transcript = handle_ticket(
        attack.payload, current.system_prompt, state,
        human_confirmed=False, policy_yaml=current.tool_policy_yaml,
    )
    db.save_transcript(attack.id, transcript)
    return {"attack_id": attack.id, "tool_calls": len(transcript["tool_calls"])}


if __name__ == "__main__":
    print(handler())
