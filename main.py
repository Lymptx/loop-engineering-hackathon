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
    db.reset()
    print("Wiped attacks, defenders, and transcripts.")


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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
