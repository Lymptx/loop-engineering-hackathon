"""Cockpit backend on the Python stdlib (no web-framework dependency).

Serves the single-page frontend and the JSON APIs. Start Demo runs the deterministic
engine in a background thread so the UI can poll events while the loop progresses.
Polling (GET /api/demo/events?since=N) is the realtime transport — the simplest
reliable option for a local demo.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cockpit import engine
from cockpit.store import Store

_STATIC = Path(__file__).parent / "static" / "index.html"


def _default_state(store: Store) -> dict:
    run = store.latest_run()
    if run:
        return run
    return {"run_id": None, "status": "idle", "current_evo": "evo0",
            "active_defender": None, "current_phase": "idle"}


class Cockpit:
    """Holds the shared store + run lock; builds a request handler bound to them."""

    def __init__(self, store: Store | None = None, pace: float = 0.35):
        self.store = store or Store()
        self.pace = pace
        self._run_lock = threading.Lock()
        self._running = False

    def start_run(self) -> dict:
        with self._run_lock:
            if self._running:
                return {"error": "a run is already in progress"}
            self._running = True

        def _worker():
            try:
                engine.run(self.store, pace=self.pace)
            finally:
                self._running = False

        threading.Thread(target=_worker, daemon=True).start()
        return {"ok": True}

    def handler(self):
        cockpit = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # quiet
                pass

            def _send_json(self, obj, code=200):
                body = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                snap = cockpit.store.snapshot()
                if path in ("/", "/index.html"):
                    body = _STATIC.read_text(encoding="utf-8").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif path == "/api/demo/state":
                    self._send_json(_default_state(cockpit.store))
                elif path == "/api/demo/events":
                    since = int(parse_qs(parsed.query).get("since", ["0"])[0])
                    self._send_json(cockpit.store.events_since(since))
                elif path == "/api/demo/attempts":
                    self._send_json(snap["attempts"])
                elif path == "/api/demo/attacker-bundles":
                    self._send_json(snap["attack_bundles"])
                elif path == "/api/demo/defender-bundles":
                    self._send_json(snap["defender_bundles"])
                elif path == "/api/demo/generation-history":
                    self._send_json(snap["history"])
                elif path == "/api/demo/metrics":
                    self._send_json(snap["metrics"])
                else:
                    self._send_json({"error": "not found"}, 404)

            def do_POST(self):
                path = urlparse(self.path).path
                if path == "/api/demo/reset":
                    cockpit.store.reset()
                    self._send_json({"ok": True})
                elif path == "/api/demo/start":
                    self._send_json(cockpit.start_run())
                else:
                    self._send_json({"error": "not found"}, 404)

        return Handler


def serve(port: int = 8000, pace: float = 0.35) -> None:
    cockpit = Cockpit(pace=pace)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), cockpit.handler())
    url = f"http://127.0.0.1:{port}/"
    print(f"Cockpit running at {url}")
    print("Open the URL and press Start Demo. Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping cockpit")
        httpd.shutdown()
