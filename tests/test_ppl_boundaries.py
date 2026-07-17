"""PPL evaluator boundary behaviour — the documented MVP edges must be exact."""

import pytest

from pomerium.ppl import Denied, evaluate

# Three deny branches (admin without confirmation, over-cap refund, diagnostics).
HARDENED = """
routes:
  - from: x
    to: y
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
          - mcp_tool: { is: internal_diagnostics }
"""


@pytest.mark.parametrize("tool,claims", [
    ("admin_reset", {"human_confirmed": False}),
    ("issue_refund", {"refund_amount": 500}),
    ("internal_diagnostics", {}),
])
def test_each_deny_branch_blocks(tool, claims):
    with pytest.raises(Denied):
        evaluate(HARDENED, tool, claims)


@pytest.mark.parametrize("tool,claims", [
    ("admin_reset", {"human_confirmed": True}),
    ("issue_refund", {"refund_amount": 42}),
    ("lookup_order", {}),
])
def test_non_matching_calls_pass(tool, claims):
    evaluate(HARDENED, tool, claims)  # no raise


def test_deny_overrides_allow():
    policy = """
    routes:
      - from: x
        to: y
        policy:
          allow:
            and:
              - mcp_tool: { is: issue_refund }
          deny:
            and:
              - mcp_tool: { is: issue_refund }
    """
    with pytest.raises(Denied):
        evaluate(policy, "issue_refund", {})


def test_present_allow_requires_a_match():
    policy = """
    routes:
      - from: x
        to: y
        policy:
          allow:
            and:
              - mcp_tool: { is: lookup_order }
    """
    evaluate(policy, "lookup_order", {})          # allowed
    with pytest.raises(Denied):
        evaluate(policy, "issue_refund", {"refund_amount": 1})  # no allow match


def test_missing_allow_is_permissive():
    evaluate("routes: [{from: x, to: y, policy: {}}]", "issue_refund", {"refund_amount": 999})


def test_empty_policy_is_permissive():
    evaluate("", "admin_reset", {"human_confirmed": False})


def test_malformed_policy_fails_closed():
    with pytest.raises(Denied):
        evaluate("routes: [ this is : : not valid", "lookup_order", {})
