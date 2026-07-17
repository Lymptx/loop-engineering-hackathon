"""One Lambda per Buildkite pipeline step. Each is a thin wrapper over loop/ + agents/.

Buildkite triggers these in order:
  generate_attack -> run_attack -> verify -> rca_and_candidate -> promote_or_reject

They pass state between steps via DynamoDB/S3 in prod; the local __main__ blocks use
storage/db.py so the same handlers run on a laptop. The point is that step 6 adds NO
new loop logic — it only relocates the existing loop onto AWS.
"""
