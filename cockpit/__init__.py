"""Live co-evolution cockpit: a deterministic, local, judge-visible demo.

The UI is driven entirely by persisted backend records (LoopRun, LoopEvent,
AttackAttempt, bundles, metrics, generation history) produced by a real deterministic
Evo0 -> Evo1 loop (cockpit/engine.py reuses the v3 subject + verifier code). Nothing
in the frontend is faked — every panel maps to stored records served by cockpit/server.py.
"""
