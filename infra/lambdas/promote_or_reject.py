"""lambda-promote-or-reject — rerun hidden + benign suites against the candidate.

On pass: write the new policy YAML to the file Pomerium watches and push the "live
version" pointer forward. On fail: the Buildkite step goes red and the exact hidden
test that still failed is visible in the log.

Thin wrapper over orchestrator.run_promotion_gate + deploy_policy.
"""

from __future__ import annotations

# See loop/orchestrator.py run_promotion_gate / _promote / deploy_policy for the
# real logic. In prod this runs the suites against a fresh Fargate task running the
# candidate, writes results to DynamoDB, and hot-reloads Pomerium on pass.


def handler(event=None, context=None) -> dict:
    raise NotImplementedError(
        "Step 6: load the Candidate, call orchestrator.run_promotion_gate, and on "
        "pass call orchestrator.deploy_policy + save the promoted DefenderVersion. "
        "Laptop mode does this inside orchestrator.run_round."
    )


if __name__ == "__main__":
    print("stub — see loop/orchestrator.py run_promotion_gate")
