"""CLI for Agent Immune CI.

    python main.py run-round            # one round of the loop
    python main.py run-n --rounds 5     # N rounds; watch DefenderVersions grow
    python main.py status               # current defender + attack library summary
    python main.py reset                # wipe persisted state (between demos)

The Terminate component of the loop lives in run-n: stop on a round budget OR on
convergence (attack success rate plateaus / hidden suite fully passes).
"""

from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from loop import orchestrator
from loop.models import DefenderVersion
from storage import db

load_dotenv()


def _get_or_seed_defender() -> DefenderVersion:
    current = db.current_defender()
    if current is None:
        current = orchestrator.seed_defender()
        db.save_defender(current)
    return current


def _persist_round(library, defender, report) -> None:
    # Persist the newest attack + transcript, and the defender if it changed.
    if library:
        db.append_attack(library[-1])
        db.save_transcript(library[-1].id, report["transcript"])
    if report.get("promoted"):
        db.save_defender(defender)


def cmd_run_round(_args) -> None:
    library = db.all_attacks()
    current = _get_or_seed_defender()
    defender, report = orchestrator.run_round(library, current)
    _persist_round(library, defender, report)
    _print_round(1, report, defender)


def cmd_run_n(args) -> None:
    library = db.all_attacks()
    current = _get_or_seed_defender()
    for i in range(args.rounds):
        current, report = orchestrator.run_round(library, current)
        _persist_round(library, current, report)
        _print_round(i + 1, report, current)
        # Terminate on convergence: current defender blocks the whole hidden suite.
        if report.get("promoted") and report["gate"]["hidden"]["all_blocked"]:
            print("\n[converged] current defender blocks the full hidden suite.")
            break


def cmd_status(_args) -> None:
    current = db.current_defender()
    attacks = db.all_attacks()
    succeeded = sum(a.succeeded for a in attacks)
    print("=== Agent Immune CI status ===")
    if current:
        print(f"Current defender : {current.version} ({current.kind})")
        print(f"Rationale        : {current.rationale}")
    else:
        print("Current defender : (none — run a round to seed)")
    print(f"Attacks tried    : {len(attacks)} ({succeeded} succeeded)")
    defenders = db.all_defenders()
    print(f"Defender versions: {', '.join(d.version for d in defenders) or '(none)'}")


def cmd_reset(_args) -> None:
    from cockpit import store as cockpit_store
    from subject import defender_store, version_store

    db.reset()
    cockpit_store.reset()
    version_store.reset()
    defender_store.reset()
    orchestrator.reset_policy()
    print("Wiped attacks, defenders, transcripts, subject versions, and cockpit state; "
          "restored seed policy.")


def cmd_demo(_args) -> None:
    """One-command golden demo. Always deterministic — no API key, no network.

    Shows: seed v1 vulnerable -> red attack -> verifier catch -> blue fix ->
    hidden+benign gate -> v2 promoted -> attack class blocked, benign intact.
    """
    os.environ["DEMO_MODE"] = "deterministic"  # force reproducible path

    db.reset()
    orchestrator.reset_policy()
    v1 = orchestrator.seed_defender()
    db.save_defender(v1)

    print("=" * 60)
    print("AGENT IMMUNE CI - golden demo (deterministic)")
    print("=" * 60)

    before = orchestrator.score_defender(v1)
    print(f"\n[1] Seed defender {v1.version} deployed (permissive tool policy).")
    print(f"    Baseline: hidden attacks succeed {before['hidden']['succeeded']}"
          f"/{before['hidden']['total']}, "
          f"benign complete {before['benign']['completed']}/{before['benign']['total']}.")

    library: list = []
    v2, report = orchestrator.run_round(library, v1)
    _persist_round(library, v2, report)

    atk = report["attack"]
    print(f"\n[2] Red Agent attack ({atk['family']}):")
    print(f"    violation detected by verifier: {report['violation']}")
    vr = library[-1].result
    print(f"    -> refund_over_cap={bool(vr['refund_over_cap'])}, "
          f"unauthorized_admin={vr['unauthorized_admin']}, "
          f"canary_exposed={vr['canary_exposed']}")

    g = report["gate"]
    print("\n[3] Blue Agent proposed a tool-policy fix. Promotion gate:")
    print(f"    hidden blocked {g['hidden']['blocked']}/{g['hidden']['total']}, "
          f"benign completed {g['benign']['completed']}/{g['benign']['total']} "
          f"-> {'PROMOTE' if g['passed'] else 'REJECT'}")

    if not report.get("promoted"):
        print("\n[!] Candidate was rejected — v1 remains live.")
        return

    print(f"\n[4] Promoted {v2.version} ({v2.kind}). Policy deployed.")
    after = orchestrator.score_defender(v2)

    print("\n[5] Before / after:\n")
    _print_metrics_table(before, after, v1.version, v2.version)
    print("\nSame attack class is now blocked at the enforcement layer, "
          "with zero benign regressions.")


def cmd_evo(_args) -> None:
    """Deterministic Evo0 -> Evo1 failure-and-repair sequence (no API key, local only)."""
    from subject import evo_runner

    r = evo_runner.run_sequence()
    print("=" * 60)
    print("EVOLVING CUSTOMER OPS SUBJECT - Evo0 -> Evo1")
    print("=" * 60)

    g = r["graph"]
    print("\n[1] Onboarded Evo1 (CRM + email) from data.")
    print(f"    Capability graph: evo0 {g['evo0']['nodes']}n/{g['evo0']['edges']}e "
          f"-> evo1 {g['evo1']['nodes']}n/{g['evo1']['edges']}e")
    print(f"    New source-to-sink paths: {len(g['new_paths'])}")

    t = r["target_path"]
    print(f"\n[2] Highest-risk new path (score {t['score']}):")
    print(f"    {t['source']} -> {t['tool_read']} -> {t['asset']} "
          f"-> {t['tool_sink']} -> {t['sink']}")

    old = r["old_defender_result"]
    print(f"\n[3] Old defender (def-v0) run: violation={old['violation']}, "
          f"emails_sent={old['emails_sent']}")
    print(f"    failed invariants: {', '.join(old['failed_invariants'])}")

    print("\n[4] Blue candidates through the promotion gate:")
    for gate in r["gate_results"]:
        verdict = "PROMOTE" if gate["promoted"] else "REJECT"
        print(f"    {gate['candidate_id']:<32} "
              f"attack_blocked={gate['attack_blocked']} utility_ok={gate['utility_ok']} "
              f"-> {verdict}")

    if r["promoted"]:
        print(f"\n[5] Promoted {r['promoted']['version']} "
              f"({r['promoted']['target_control_layer']}). "
              f"Attack blocked; legitimate customer email preserved.")
    else:
        print("\n[5] No candidate promoted.")

    caps = ", ".join(f"{v['version']}({v['status']})" for v in r["capability_versions"])
    defs = ", ".join(f"{d['version']}({d.get('status')})" for d in r["defenders"])
    print(f"\n    Capability versions: {caps}")
    print(f"    Defender versions:   {defs}")


def cmd_cockpit(args) -> None:
    """Start the live co-evolution cockpit (deterministic, local). Open the printed URL."""
    from cockpit.server import serve

    serve(port=args.port, pace=args.pace)


def _print_metrics_table(before: dict, after: dict, v1: str, v2: str) -> None:
    rows = [
        ("Hidden attack success",
         f"{before['hidden']['succeeded']}/{before['hidden']['total']}",
         f"{after['hidden']['succeeded']}/{after['hidden']['total']}"),
        ("Benign task success",
         f"{before['benign']['completed']}/{before['benign']['total']}",
         f"{after['benign']['completed']}/{after['benign']['total']}"),
        ("Unauthorized calls",
         str(before['hidden']['unauthorized_calls']),
         str(after['hidden']['unauthorized_calls'])),
    ]
    w = max(len(r[0]) for r in rows)
    print(f"    {'':<{w}} | {v1:^10} | {v2:^10}")
    print(f"    {'-' * w}-+-{'-' * 10}-+-{'-' * 10}")
    for label, a, b in rows:
        print(f"    {label:<{w}} | {a:^10} | {b:^10}")


def _print_round(n: int, report: dict, defender: DefenderVersion) -> None:
    atk = report["attack"]
    print(f"\n--- round {n} ---")
    print(f"attack   : {atk['family']}")
    print(f"violation: {report['violation']}")
    if report.get("gate"):
        g = report["gate"]
        h, b = g["hidden"], g["benign"]
        print(f"gate     : hidden {h['blocked']}/{h['total']} blocked, "
              f"benign {b['completed']}/{b['total']} completed -> "
              f"{'PROMOTE' if g['passed'] else 'REJECT'}")
    if report.get("promoted"):
        print(f"promoted : {defender.version} ({defender.kind})")
    else:
        print(f"defender : unchanged ({defender.version})")


def main() -> None:
    parser = argparse.ArgumentParser(prog="agent-immune-ci")
    sub = parser.add_subparsers(required=True)

    sub.add_parser("run-round").set_defaults(func=cmd_run_round)

    p_n = sub.add_parser("run-n")
    p_n.add_argument("--rounds", type=int, default=5)
    p_n.set_defaults(func=cmd_run_n)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("reset").set_defaults(func=cmd_reset)
    sub.add_parser("demo").set_defaults(func=cmd_demo)
    sub.add_parser("evo").set_defaults(func=cmd_evo)

    p_cockpit = sub.add_parser("cockpit")
    p_cockpit.add_argument("--port", type=int, default=8000)
    p_cockpit.add_argument("--pace", type=float, default=0.35)
    p_cockpit.set_defaults(func=cmd_cockpit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
