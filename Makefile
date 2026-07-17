# Convenience targets. On Windows without `make`, use the `python main.py ...`
# commands directly (see README).

.PHONY: install test demo reset status

install:
	python -m pip install -r requirements.txt

# Tests run deterministically and never need ANTHROPIC_API_KEY.
test:
	DEMO_MODE=deterministic python -m pytest -q

# The golden demo: reproducible, no API key, no external services.
demo:
	python main.py demo

reset:
	python main.py reset

status:
	python main.py status
