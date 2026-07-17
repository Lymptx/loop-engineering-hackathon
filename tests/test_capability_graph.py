"""Milestone 3: capability graph, snapshots, diff, ranking, and version store."""

from subject import loader, version_store
from subject.capability_diff import diff
from subject.capability_graph import build_graph, source_to_sink_paths
from subject.risk_path_ranker import rank

TARGET = ("untrusted_customer_ticket", "customer_confidential_profile",
          "external_email_recipient")


def _graphs():
    s = loader.load_subject()
    evo0 = loader.materialize(s, "evo0")
    evo1 = loader.materialize(s, "evo1")
    return s, evo0, evo1, build_graph(s, evo0), build_graph(s, evo1)


def test_evo1_graph_is_bigger_than_evo0():
    _, _, _, g0, g1 = _graphs()
    assert g1.node_count() > g0.node_count()
    assert g1.edge_count() > g0.edge_count()


def test_evo0_has_no_external_egress_path():
    s, evo0, *_ = _graphs()
    assert source_to_sink_paths(s, evo0) == []


def test_evo1_introduces_confidential_to_email_path():
    s, _, evo1, *_ = _graphs()
    paths = source_to_sink_paths(s, evo1)
    keys = {(p["source"], p["asset"], p["sink"]) for p in paths}
    assert TARGET in keys


def test_graph_diff_finds_the_new_path():
    s, evo0, evo1, g0, g1 = _graphs()
    d = diff(s, evo0, evo1, g0, g1)
    assert d["from_version"] == "evo0" and d["to_version"] == "evo1"
    keys = {(p["source"], p["asset"], p["sink"]) for p in d["new_paths"]}
    assert TARGET in keys
    # email_send + crm_get_customer are newly added edges
    assert any("email_send" in e for e in d["added_edges"])


def test_ranker_puts_restricted_egress_on_top():
    s, _, evo1, *_ = _graphs()
    ranked = rank(s, source_to_sink_paths(s, evo1))
    assert ranked[0]["asset_sensitivity"] == "restricted"
    assert ranked[0]["sink"] == "external_email_recipient"


def test_capability_versions_persist_independently():
    version_store.reset()
    s = loader.load_subject()
    version_store.save_version(loader.materialize(s, "evo0", status="active",
                                                  activated_at="t0"))
    version_store.save_version(loader.materialize(s, "evo1"))
    version_store.set_active("evo1", activated_at="t1")

    versions = {v["version"] for v in version_store.all_versions()}
    assert versions == {"evo0", "evo1"}
    assert version_store.active_version()["version"] == "evo1"
