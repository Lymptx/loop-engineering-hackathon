"""lambda-generate-attack — Red Agent (Bedrock). Returns next attack + hypothesis.

Reads the attack library + current defender from storage, calls red_agent, persists
the new (unrun) attack. In prod, swap storage/db for the DynamoDB AttackStrategies
table and use AnthropicBedrockMantle for the model client.
"""

from __future__ import annotations

from agents import red_agent
from loop import orchestrator
from storage import db


def handler(event=None, context=None) -> dict:
    library = db.all_attacks()
    current = db.current_defender() or orchestrator.seed_defender()
    attack = red_agent.generate_next_attack(library, current)
    db.append_attack(attack)
    return {"attack_id": attack.id, "family": attack.family}


if __name__ == "__main__":
    print(handler())
