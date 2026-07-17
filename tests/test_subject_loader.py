"""Milestone 2: subject files load through typed schemas and materialize correctly."""

from subject import loader
from subject.schema import (
    BenignWorkflow,
    DefenseOperator,
    Invariant,
    Subject,
    Tool,
)


def test_subject_loads_through_typed_schema():
    s = loader.load_subject()
    assert isinstance(s, Subject)
    assert isinstance(s.tools["email_send"], Tool)
    assert s.tools["email_send"].sink == "external_email_recipient"
    assert all(isinstance(i, Invariant) for i in s.invariants)
    assert all(isinstance(w, BenignWorkflow) for w in s.benign_workflows)
    assert isinstance(s.operators["email_egress_policy"], DefenseOperator)
    assert s.operators["email_egress_policy"].control_layer == "data_flow_egress_policy"


def test_materialize_evo0_is_basic_support():
    s = loader.load_subject()
    evo0 = loader.materialize(s, "evo0")
    assert "email_send" not in evo0.tools
    assert "crm_get_customer" not in evo0.tools
    assert "customer_confidential_profile" not in evo0.data_classes
    assert {"ticket_read", "orders_get", "refund_create"} <= evo0.tools


def test_materialize_evo1_folds_deltas_from_evo0():
    s = loader.load_subject()
    evo1 = loader.materialize(s, "evo1")
    # inherits evo0 tools ...
    assert {"ticket_read", "orders_get", "refund_create"} <= evo1.tools
    # ... and adds evo1 tools + data
    assert {"crm_get_customer", "email_send"} <= evo1.tools
    assert {"customer_confidential_profile", "customer_email"} <= evo1.data_classes
    assert evo1.parent_version == "evo0"


def test_restricted_data_classes_are_evo1():
    s = loader.load_subject()
    assert s.data_classes["customer_confidential_profile"].sensitivity == "restricted"
    assert s.data_classes["internal_support_notes"].sensitivity == "restricted"
