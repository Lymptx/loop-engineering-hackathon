# Convenience targets. On Windows without `make`, use the `python main.py ...`
# commands directly (see README).

PYTHON ?= .venv/bin/python
PYTHON_BOOTSTRAP ?= python3.12

.PHONY: install test demo evo cockpit live-demo matrix reset status pomerium-config pomerium-up pomerium-down pomerium-logs pomerium-smoke

$(PYTHON):
	$(PYTHON_BOOTSTRAP) -m venv .venv

install: $(PYTHON)
	$(PYTHON) -m pip install -q -r requirements.txt

# Tests run deterministically and never need ANTHROPIC_API_KEY.
test: install
	DEMO_MODE=deterministic $(PYTHON) -m pytest -q

# The Evo0 golden demo: reproducible, no API key, no external services.
demo: install
	$(PYTHON) main.py demo

# The evolving-subject demo: Evo0 -> Evo1 failure-and-repair, deterministic + local.
evo: install
	$(PYTHON) main.py evo

# One-command live cockpit. Open the printed URL and press Start Demo.
cockpit: install
	$(PYTHON) -m cockpit.server --host 127.0.0.1 --port 8765

live-demo: cockpit

# Regenerate subject/attack_surface_matrix.jsonl from the source files.
matrix: install
	$(PYTHON) -m subject.build_matrix

reset: install
	$(PYTHON) main.py reset

status: install
	$(PYTHON) main.py status

pomerium-config: install
	$(PYTHON) -m pomerium.local_config

pomerium-up: pomerium-config
	docker compose -f pomerium/docker-compose.yaml up --build

pomerium-down:
	docker compose -f pomerium/docker-compose.yaml down

pomerium-logs:
	docker compose -f pomerium/docker-compose.yaml logs -f pomerium

pomerium-smoke:
	@for i in $$(seq 1 60); do \
		curl -fsS http://127.0.0.1:18081/mcp \
			-H 'Content-Type: application/json' \
			--data '{"jsonrpc":"2.0","id":"smoke","method":"tools/call","params":{"name":"lookup_order","arguments":{"order_id":"A1001"}}}' && exit 0; \
		sleep 1; \
	done; \
	echo "Pomerium smoke test failed: is make pomerium-up running?" >&2; \
	exit 1
