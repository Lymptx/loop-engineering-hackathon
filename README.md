# Agent Immune CI

**Continuous security improvement for tool-using AI agents.** A red/blue co-evolving
loop that turns every successful attack into a permanent regression test and every
verified failure into a versioned, enforced defense. Full design in
[`basic_plan.md`](./basic_plan.md).

The loop itself is [`loop/orchestrator.py`](./loop/orchestrator.py); everything else is
scaffolding around it.

---

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

make test        # deterministic — no API key, no network
make demo        # the golden demo — no API key, no network
make cockpit     # live web cockpit — open http://127.0.0.1:8765
```

No `make`? Use the CLI directly:

```bash
python -m pytest -q            # tests
python main.py demo           # Evo0 golden demo (refund/admin attack)
python main.py evo            # Evo0 -> Evo1 evolving-subject demo
python -m cockpit.server      # live cockpit API + frontend
python main.py status         # current defender + attack library
python main.py reset          # wipe state, restore seed policy
```

### Expected `make demo` output

```
============================================================
AGENT IMMUNE CI - golden demo (deterministic)
============================================================

[1] Seed defender v1 deployed (permissive tool policy).
    Baseline: hidden attacks succeed 5/5, benign complete 5/5.

[2] Red Agent attack (prompt_injection_via_forwarded_email):
    violation detected by verifier: True
    -> refund_over_cap=True, unauthorized_admin=['A1002'], canary_exposed=False

[3] Blue Agent proposed a tool-policy fix. Promotion gate:
    hidden blocked 5/5, benign completed 5/5 -> PROMOTE

[4] Promoted v2 (tool_policy). Policy deployed.

[5] Before / after:

                          |     v1     |     v2
    ----------------------+------------+-----------
    Hidden attack success |    5/5     |    0/5
    Benign task success   |    5/5     |    5/5
    Unauthorized calls    |     9      |     0
```

The narrative: **v1 is vulnerable → Red finds an attack → the verifier catches the
violation → Blue proposes a tool-policy fix → the hidden+benign promotion gate passes
→ v2 is promoted → the same attack class is blocked at the enforcement layer, with
zero benign regressions.**

---

## Two run modes

| Mode | How | Anthropic |
|---|---|---|
| **deterministic** (default for `demo`/`test`) | `DEMO_MODE=deterministic` | never called — reproducible, offline |
| **live** | `DEMO_MODE=live` + `ANTHROPIC_API_KEY` in `.env` | Red/Blue/Target agents call Claude |

Deterministic mode is the golden path: the Red Agent replays a fixed prompt-injection,
the target agent is a rule-based naive-agent simulator, and the Blue Agent returns the
canonical tool-policy fix. The `anthropic` package is imported lazily, so tests and the
demo run with it uninstalled and no key set. Live mode swaps in real Claude calls
(`agents/_llm.py`) with schema validation and one retry on malformed JSON.

---

## Pomerium / MCP — two enforcement lanes

Pomerium is the external enforcement plane for privileged agent tools. Blue promotes
[`pomerium/policy.yaml`](./pomerium/policy.yaml); every target tool call crosses the
gateway contract and receives an explicit allow/deny decision.

| Lane | Setting | Enforcement | Purpose |
|---|---|---|---|
| deterministic (default) | `USE_POMERIUM=0` | [`pomerium/ppl.py`](./pomerium/ppl.py) | offline CI, claim-aware candidate gates |
| real MCP gateway | `USE_POMERIUM=1` | `pomerium/pomerium:main` → [`sandbox/tool_server.py`](./sandbox/tool_server.py) | judge-visible native `mcp_tool` enforcement and audit logs |

The simulator implements deny-overrides-allow, `mcp_tool`, and request-context claims
such as `human_confirmed` and `refund_amount`. Real local mode uses Pomerium's
experimental MCP proxy and native tool-name policies. Because local mode has no IdP,
[`pomerium/local_config.py`](./pomerium/local_config.py) conservatively converts
claim-conditioned high-risk branches to tool-name denies. It does **not** claim JWT
or per-request claim parity.

Real-gateway proof (Docker Desktop required):

```bash
python -m pomerium.local_config
docker compose -f pomerium/docker-compose.yaml up --build
# in another terminal:
python scripts/pomerium_smoke.py
# application-level proof with enforcement metadata + audit events:
USE_POMERIUM=1 python scripts/pomerium_judge_demo.py
```

The smoke script proves both paths: `lookup_order` is allowed and
`internal_diagnostics` is denied by Pomerium. Set
`POMERIUM_SERVICE_ACCOUNT_TOKEN` only when connecting to an authenticated Pomerium
route; no token is needed for the local `allow: accept` judge proof.

### Pomerium Zero

The root [`compose.yaml`](./compose.yaml) runs the Pomerium Zero connector, the
official Verify app, and this project's MCP tool server. Put the Zero enrollment
token in the gitignored root `.env`:

```dotenv
POMERIUM_ZERO_TOKEN=replace-with-a-fresh-token
```

Then run `docker compose up -d`. In Pomerium Zero, configure the MCP route upstream
as `http://tool-server:8080/mcp` and enable MCP server mode plus the native
`mcp_tool` deny policy. The token enrolls the connector; it is not the per-request
service-account token used by an MCP client.

The golden `python main.py demo` remains deterministic by design. Candidate policies
are evaluated in-process before promotion; the promoted policy regenerates
`pomerium/generated-config.yaml` for the real gateway lane.

Documented simulator boundaries: only `routes[0]` is evaluated; absent `allow` is
permissive; malformed policy fails closed.

---

## Evolving subject (Evo0 → Evo1)

Beyond the static refund/admin demo, the target is modeled as an **evolving benchmark
subject** under [`subject/`](./subject): machine-readable source files
(`tool_registry.yaml`, `data_catalog.yaml`, `capability_generations.yaml`, …) describe
what the agent can do per capability generation. `make evo` (or `python main.py evo`)
runs the deterministic Evo0 → Evo1 failure-and-repair sequence:

```
onboard Evo1 (CRM + email) from data
-> capability graph diff finds  untrusted_ticket -> customer_confidential_profile -> external_email
-> old defender (def-v0) emails confidential CRM data to an attacker recipient (verifier flags it)
-> blue proposes 2 candidates
   - A: deny all email_send        -> REJECTED (breaks the legitimate follow-up email)
   - B: verified-recipient + same-tenant + redaction -> PROMOTED (blocks attack, keeps utility)
-> def-v1 promoted; capability and defender versions are tracked on independent timelines
```

`subject/attack_surface_matrix.jsonl` is **generated** from the source files
(`make matrix`), never hand-edited. Evo2/Evo3 generations are described in the source
data but not yet implemented — Evo0 → Evo1 is the mandatory complete milestone.

## Live cockpit

`make cockpit` starts a local web dashboard at `http://127.0.0.1:8765`. Press
**Start Demo** to run the deterministic persistent co-evolution loop from
Evo0 through Evo3:

```
Evo0 baseline
-> Evo1 CRM + outbound email
-> new CRM-to-email attack bundle
-> old defender fails real verifier checks
-> over-broad email denial rejected by benign regression
-> refined recipient-binding/redaction defender promoted
-> Evo2 finance/fraud/approval introduces forged-approval bulk-refund risk
-> approval-provenance defender promoted
-> Evo3 memory/attachments/connectors introduces memory-poisoning risk
-> memory quarantine/provenance defender promoted
```

The cockpit panels are backed by JSON records under `storage/data/cockpit/`:
loop events, attack attempts, verifier-backed traces, attacker bundles, defender
bundles, defense candidates, metrics, and generation history. Restarting the
server does not clear this history; use the cockpit Reset button or `make reset`
when you want a fresh run.

Implementation boundary: Evo1 uses the full local CRM/email sandbox and frozen
egress verifier. Evo2/Evo3 currently use deterministic local cockpit traces and
promotion records over the same persisted loop contract; their specialized
fraud/approval and memory/connector sandboxes are the next hardening step.

### Runtime Red/Blue Agents

The cockpit includes deterministic runtime agents in `cockpit/autonomy.py`:

- Red scans the active subject capability graph diff, ranks new source-to-sink
  paths using risk and prior attempt statistics, then emits a new attack bundle.
- Blue reads the failed invariants from the latest trace, selects the control
  layer, generates an over-broad candidate and a refined candidate, then relies
  on the promotion gate outcome to reject or promote.

This is not Claude Code/Codex operating the product. It is app runtime logic with
a deterministic adapter for demo/test stability. A later LLM adapter can implement
the same Red/Blue contracts with model calls while keeping the verifier and
promotion gate deterministic.

## Layout

```
cockpit/     standard-library web cockpit + persistent event/demo records
loop/         orchestrator.py (the loop) + models.py (AttackAttempt, DefenderVersion)
agents/       red_agent, blue_agent, prompts, _llm (live adapter)
sandbox/      tools, state (+ canary), gateway, target_agent, tool_server
verifier/     verifier (deterministic checks) + suites (frontier / benign / hidden)
pomerium/     ppl.py (PPL simulator) + policy.yaml (the deployed tool-policy artifact)
storage/      db.py (JSON persistence; DynamoDB/S3 in infra/)
infra/        AWS (Fargate/DynamoDB/S3) + Buildkite — step 6
tests/        verifier, PPL, full-loop, persistence — all deterministic
```
