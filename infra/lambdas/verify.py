"""lambda-verify — call the frozen verifier container, return structured results.

Returns canary_exposed / refund_over_cap / unauthorized_admin — never a bare
pass/fail. Runs the verifier in a container with no shared state in prod.
"""

from __future__ import annotations

# In prod the verifier runs against the sandbox's data store after the interaction.
# Locally, run_attack + verify are fused in orchestrator.run_round; this stub exists
# to keep the 5-step pipeline shape explicit for whoever wires up Buildkite.


def handler(event=None, context=None) -> dict:
    raise NotImplementedError(
        "Step 6: point this at the verifier container's check endpoint. "
        "Laptop mode verifies inside orchestrator.run_round (verifier.check)."
    )


if __name__ == "__main__":
    print("stub — see orchestrator.run_round for the live verification path")
