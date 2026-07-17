"""Global runtime configuration.

The one knob that matters for the demo: DEMO_MODE.

  DEMO_MODE=deterministic  -> no Anthropic calls at all. Red/Blue/Target agents use
                              fixed, rule-based behaviour. This is the golden demo
                              path: fully reproducible, needs no API key, no network.
  DEMO_MODE=live (default) -> Red/Blue/Target call Claude via agents/_llm.py.

`python main.py demo` and the test suite force deterministic mode, so neither ever
requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import os

DETERMINISTIC = "deterministic"
LIVE = "live"


def demo_mode() -> str:
    return os.getenv("DEMO_MODE", LIVE).strip().lower()


def is_deterministic() -> bool:
    return demo_mode() == DETERMINISTIC
