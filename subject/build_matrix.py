"""Generate subject/attack_surface_matrix.jsonl from the source files.

The matrix is DERIVED (never hand-maintained): one row per source-to-sink path that
exists at the latest capability generation, ranked by risk. Run:

    python -m subject.build_matrix
"""

from __future__ import annotations

import json
from pathlib import Path

from subject import loader
from subject.capability_graph import build_graph, source_to_sink_paths
from subject.risk_path_ranker import rank

_OUT = Path(__file__).parent / "attack_surface_matrix.jsonl"


def build(subject=None) -> list[dict]:
    subject = subject or loader.load_subject()
    latest = subject.generations[-1].version
    cap = loader.materialize(subject, latest)
    paths = source_to_sink_paths(subject, cap)
    return rank(subject, paths)


def write() -> Path:
    rows = build()
    _OUT.write_text(
        "\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return _OUT


if __name__ == "__main__":
    path = write()
    print(f"wrote {path} ({sum(1 for _ in path.open())} rows)")
