# Convenience targets. On Windows without `make`, use the `python main.py ...`
# commands directly (see README).

.PHONY: install test demo evo matrix reset status

install:
	python -m pip install -r requirements.txt

# Tests run deterministically and never need ANTHROPIC_API_KEY.
test:
	DEMO_MODE=deterministic python -m pytest -q

# The Evo0 golden demo: reproducible, no API key, no external services.
demo:
	python main.py demo

# The evolving-subject demo: Evo0 -> Evo1 failure-and-repair, deterministic + local.
evo:
	python main.py evo

# Regenerate subject/attack_surface_matrix.jsonl from the source files.
matrix:
	python -m subject.build_matrix

reset:
	python main.py reset

status:
	python main.py status
