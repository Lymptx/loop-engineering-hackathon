---
name: live-coevolution-cockpit
description: Add a one-click live co-evolution cockpit for Agent Immune CI. Use when building a deterministic frontend demo that streams attacker/defender loop events, growing attacker and defender bundle lists, attack success/failure results, metrics, promotion history, and persistent Evo0->Evo1 security improvement state. Local synthetic sandbox only.
---

# Live Co-Evolution Cockpit

## Goal

Turn the existing v3 evolving Customer Ops subject into a judge-visible demo:

```text
press Start Demo
-> Evo0 baseline appears
-> red attacks stream in
-> old defender fails a new Evo1 path
-> attacker bundle grows
-> blue generates candidates
-> bad candidate is rejected by benign regression
-> refined defender is promoted
-> defender bundle grows
-> metrics improve
```

This skill is incremental. Preserve the existing v3 subject files, target-agent
sandbox, verifier, and promotion semantics. Do not introduce a second business
domain.

## Non-Negotiables

- Drive the UI from persisted backend state and events, not frontend-only fake
  animation.
- Keep the demo deterministic and fully local.
- Keep the frozen verifier and hidden expected outcomes untouched by blue logic.
- Keep old defender versions, attack attempts, bundle entries, reports, and
  promotion decisions immutable.
- Make reset explicit. Server restart must reload prior history.

## Read Before Implementing

Read `references/cockpit-contracts.md` before defining models, APIs, or events.
Read `references/demo-storyboard.md` before wiring the deterministic run.

## Required Visible Panels

Build a cockpit page with:

```text
top status bar:
  current evo stage
  active defender version
  loop phase
  run status

left panel:
  live attack stream
  attack family
  objective
  target path
  defender version tested
  success/failure
  verifier invariant

center panel:
  protected subject trace
  user input / carrier
  tool calls
  Pomerium or policy decision
  verifier observation

right panel:
  attacker bundle list
  defender bundle list

bottom panel:
  generation history and metrics
```

If the repo already has a dashboard, extend it. If not, add the smallest
maintainable frontend that matches the repo stack.

## Backend Work

Add or adapt persistent models equivalent to:

```text
LoopRun
LoopEvent
AttackBundleEntry
DefenderBundleEntry
AttackAttempt
DefenseCandidate
MetricSnapshot
GenerationHistoryRow
```

Emit events from real orchestration points:

```text
demo_reset
demo_started
evo_started
defender_activated
attack_bundle_added
attack_attempt_started
attack_attempt_finished
defender_candidate_generated
defender_candidate_evaluated
defender_rejected
defender_promoted
metric_updated
demo_finished
```

Expose APIs equivalent to:

```text
POST /api/demo/reset
POST /api/demo/start
GET  /api/demo/state
GET  /api/demo/events
GET  /api/demo/attacker-bundles
GET  /api/demo/defender-bundles
GET  /api/demo/generation-history
GET  /api/demo/metrics
```

Use Server-Sent Events, WebSocket, polling, or the repo's existing realtime
pattern. Prefer the simplest reliable option.

## Deterministic Demo Loop

The one-click demo must run a real deterministic sequence:

```text
reset demo state
load Evo0 subject and baseline defender
run Evo0 attacks and benign anchors
onboard Evo1 CRM + outbound email
diff graph and discover confidential-data-to-email path
add/mutate attacker bundle for that path
run attack against old defender and record success
generate over-broad email-deny candidate
reject it because legitimate follow-up email fails
generate refined verified-recipient + same-tenant + redaction candidate
promote refined defender
replay frontier attack and benign anchor
record improved metrics
finish run
```

The UI may pace the run for readability, but pacing must wrap real backend
steps and persisted events.

## Metrics

At minimum, show:

```text
attack_success_rate_by_defender
attack_success_rate_by_family
benign_success_rate
hidden_holdout_attack_success
blocked_attack_count
promoted_defender_count
new_attack_family_count
bundle_size_attacker
bundle_size_defender
```

Compute metrics from stored attempts and regression results, not duplicated
frontend state.

## Generation History

Each row must include:

```text
evo stage
defender version
attack family
frontier attack success
hidden attack success
benign success
policy diff summary
promotion decision
reason
report artifact path if available
```

## One-Command Demo

Preserve or add a command such as:

```text
make demo
```

It should install/verify dependencies as appropriate for the repo, reset or
seed only when explicitly requested by the command, start the backend/frontend,
and print the local URL.

If the repo separates backend and frontend, document and test both:

```text
make test
make demo
```

## Tests

Add tests for:

- event persistence across server restart;
- Start Demo triggers the deterministic loop;
- event stream contains the required event types in order;
- attack attempt rows reflect verifier results;
- over-broad candidate is rejected by benign regression;
- refined defender is promoted;
- bundle lists grow;
- metrics update after promotion;
- reset clears only mutable demo-run state and never deletes immutable version
  artifacts unless the existing repo explicitly treats them as regenerated
  fixtures.

## Completion Report

Return:

- exact commands run;
- local demo URL;
- files changed;
- event model/store added;
- API endpoints added;
- UI panels added;
- which UI panels are backed by which persisted records;
- deterministic vs mocked vs live components;
- test results;
- known limitations.
