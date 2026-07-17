"""Pomerium PPL evaluator tests — the enforcement semantics must be exact.

These are the checks that guarantee laptop mode matches the real gateway: deny
overrides allow, mcp_tool matches per-tool, claim conditions compare correctly.
"""

import pytest

from pomerium.ppl import Denied, evaluate

# The tool-policy fix the Blue Agent is expected to promote.
HARDENED = """
routes:
  - from: https://tools.sandbox.internal
    to: http://tool-server:8080
    mcp: true
    policy:
      deny:
        or:
          - and:
              - mcp_tool: { is: admin_reset }
              - claim/human_confirmed: { is: false }
          - and:
              - mcp_tool: { is: issue_refund }
              - claim/refund_amount: { greater_than: 50 }
"""

PERMISSIVE = "routes: [{from: x, to: y, mcp: true, policy: {}}]"


def test_empty_policy_allows_everything():
    evaluate("", "admin_reset", {"human_confirmed": False})  # no raise


def test_permissive_policy_allows_everything():
    evaluate(PERMISSIVE, "issue_refund", {"refund_amount": 500})  # no raise


def test_admin_reset_denied_without_confirmation():
    with pytest.raises(Denied):
        evaluate(HARDENED, "admin_reset", {"human_confirmed": False})


def test_admin_reset_allowed_with_confirmation():
    evaluate(HARDENED, "admin_reset", {"human_confirmed": True})  # no raise


def test_refund_over_cap_denied():
    with pytest.raises(Denied):
        evaluate(HARDENED, "issue_refund", {"refund_amount": 500})


def test_refund_under_cap_allowed():
    evaluate(HARDENED, "issue_refund", {"refund_amount": 42})  # no raise


def test_lookup_always_allowed_under_hardened_policy():
    evaluate(HARDENED, "lookup_order", {})  # no deny matches
