"""Unit proofs for the optional real Pomerium MCP enforcement lane."""

from pathlib import Path

import yaml

from loop import orchestrator
from pomerium.local_config import build_config
from sandbox import gateway
from sandbox.state import SandboxState

POLICY = {
    "routes": [
        {
            "policy": {
                "deny": {
                    "or": [
                        {
                            "and": [
                                {"mcp_tool": {"is": "admin_reset"}},
                                {"claim/human_confirmed": {"is": False}},
                            ]
                        },
                        {"mcp_tool": {"is": "internal_diagnostics"}},
                    ]
                }
            }
        }
    ]
}


def test_local_config_generates_native_mcp_tool_denies():
    config = build_config(POLICY)
    route = config["routes"][0]

    assert route["mcp"] == {"server": {}}
    assert route["policy"]["allow"] == {"and": [{"accept": True}]}
    assert route["policy"]["deny"] == {
        "or": [
            {"mcp_tool": {"is": "admin_reset"}},
            {"mcp_tool": {"is": "internal_diagnostics"}},
        ]
    }


def test_real_gateway_marks_allowed_call_as_pomerium(monkeypatch):
    monkeypatch.setenv("USE_POMERIUM", "1")
    monkeypatch.setattr(gateway, "_ensure_real_gateway_session", lambda _session_id: None)
    monkeypatch.setattr(
        gateway,
        "_post_json",
        lambda *_args, **_kwargs: (
            200,
            {
                "jsonrpc": "2.0",
                "result": {
                    "structuredContent": {
                        "order_id": "A1001",
                        "status": "shipped",
                    }
                },
            },
        ),
    )
    state = SandboxState.fresh()

    result = gateway.call_via_gateway(
        state,
        "lookup_order",
        {"order_id": "A1001"},
        session_id="test-real-allow",
    )

    assert result["enforcement_layer"] == "pomerium"
    assert state.audit_events[-1]["enforcement_layer"] == "pomerium"
    assert state.audit_events[-1]["policy_decision"] == "allow"


def test_real_gateway_marks_http_deny_as_pomerium(monkeypatch):
    monkeypatch.setenv("USE_POMERIUM", "1")
    monkeypatch.setattr(gateway, "_ensure_real_gateway_session", lambda _session_id: None)
    monkeypatch.setattr(gateway, "_post_json", lambda *_args, **_kwargs: (403, "denied"))
    state = SandboxState.fresh()

    result = gateway.call_via_gateway(
        state,
        "internal_diagnostics",
        {},
        session_id="test-real-deny",
    )

    assert result["denied"] is True
    assert result["enforcement_layer"] == "pomerium"
    assert state.audit_events[-1]["enforcement_layer"] == "pomerium"
    assert state.audit_events[-1]["policy_decision"] == "deny"


def test_explicit_candidate_policy_stays_in_simulator(monkeypatch):
    monkeypatch.setenv("USE_POMERIUM", "1")
    monkeypatch.setattr(
        gateway,
        "_call_real_pomerium",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("candidate policy must not reach live Pomerium")
        ),
    )
    state = SandboxState.fresh()

    result = gateway.call_via_gateway(
        state,
        "internal_diagnostics",
        {},
        session_id="candidate",
        policy_yaml=yaml.safe_dump(POLICY),
    )

    assert result["denied"] is True
    assert result["enforcement_layer"] == "ppl_simulator"


def test_deploy_policy_regenerates_isolated_pomerium_config(tmp_path, monkeypatch):
    policy_path = tmp_path / "policy.yaml"
    config_path = tmp_path / "generated-config.yaml"
    monkeypatch.setattr(orchestrator, "_POLICY_PATH", policy_path)
    monkeypatch.setattr(orchestrator, "_POMERIUM_CONFIG_PATH", config_path)

    orchestrator.deploy_policy(yaml.safe_dump(POLICY))

    assert policy_path.exists()
    assert config_path.exists()
    generated = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert generated["routes"][0]["policy"]["deny"]
    assert Path(config_path).parent == tmp_path
