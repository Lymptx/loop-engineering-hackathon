Use the `/live-coevolution-cockpit` skill.

This is a v4 incremental update on top of the existing evolving Customer Ops
subject work. Do not restart the architecture, do not replace the v3 subject
schemas, and do not build a separate business domain.

Goal:

Build a one-click live co-evolution demo where the frontend visibly shows:

- current capability evo stage;
- current defender version;
- current loop phase;
- attacker bundle list growing;
- defender bundle list growing;
- attack attempts streaming in with success/failure;
- blue candidates being generated, rejected, or promoted;
- metrics updating from real verifier and regression results.

The demo must be deterministic and local, but not fake. UI updates must come
from persisted backend events, attack attempts, verifier results, bundle stores,
and promotion decisions.

First inspect the current repository:

1. current v3 subject/evo implementation;
2. persistence/store layer;
3. red/blue loop orchestration;
4. target agent sandbox;
5. verifier/regression suites;
6. existing frontend/dashboard if present;
7. current reset/demo/test commands.

Then implement in runnable milestones:

1. Add persistent loop-event models and storage.
2. Emit events from existing red, blue, verifier, promotion, and evo onboarding
   code paths.
3. Add backend APIs for reset, start, state snapshot, event stream, bundle list,
   generation history, and metrics.
4. Add a cockpit frontend with a Start Demo button and live panels.
5. Wire the Start Demo button to a real deterministic Evo0 -> Evo1 loop.
6. Ensure attacker and defender bundle lists visibly grow during the run.
7. Ensure attack attempts show real success/failure from verifier results.
8. Ensure at least one blue candidate is rejected because benign regression
   fails and a refined candidate is promoted.
9. Preserve one-command full demo and deterministic local tests.

Acceptance criteria:

- A fresh local run can execute one command and open one URL.
- Pressing Start Demo runs the complete deterministic loop.
- The UI shows at least 8 attack attempts.
- At least one attack succeeds against the old defender.
- At least one attack fails after the promoted defender.
- At least one defender candidate is rejected due to benign regression.
- A refined defender is promoted.
- Attack success rate decreases after promotion.
- Benign success rate remains high.
- Attacker bundle list and defender bundle list both grow during the run.
- Generation history shows defender version, attack family, attack success,
  benign success, policy diff summary, and promotion decision.
- Restarting the server does not erase prior demo run history unless reset is
  explicitly invoked.
- No external service is targeted during the demo.

Before declaring completion, run:

- the full test suite;
- the one-command deterministic demo from reset;
- a server restart check proving persisted history reloads.

Return the exact commands, URL, changed files, and a concise explanation of
which visible UI elements are backed by which persisted backend records.
