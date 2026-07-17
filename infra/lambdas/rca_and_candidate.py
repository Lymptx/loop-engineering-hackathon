"""lambda-rca-and-candidate — Blue Agent (Bedrock). Root-cause + candidate fix.

Takes the failed transcript + verifier output, returns a candidate (prompt diff,
policy diff, or both). Thin wrapper over agents.blue_agent.propose_candidate.
"""

from __future__ import annotations

# See agents/blue_agent.py for the real logic. In prod this reads the failed
# AttackAttempt + verifier result from DynamoDB/S3 and writes the Candidate back.


def handler(event=None, context=None) -> dict:
    raise NotImplementedError(
        "Step 6: load failed attempt + verifier result, call "
        "blue_agent.propose_candidate, persist the Candidate. Laptop mode does "
        "this inside orchestrator.run_round."
    )


if __name__ == "__main__":
    print("stub — see agents/blue_agent.py + orchestrator.run_round")
